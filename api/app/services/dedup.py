"""Detections of a batch -> ML /dedup -> elements in the catalogue (used by services/ingest.py).

Observation ids are the ones ML returns, and so are element ids (ML's non-UUID ids are mapped to
a fixed UUID, see schemas/ml.py): the API never makes its own, so they match ML's logs.

ML rebuilds 'auto' elements from the observations it is sent, and reports every existing 'auto'
element it didn't rebuild as removed. So, next to the new detections, the API sends the
observations (and cameras) of the 'auto' elements nearby: ML can then merge old and new views,
and an element is only removed when its views were all given to other elements.
Elements a human checked (verified / corrected / rejected) are sent without their observations:
ML never moves them, it only links new views to verified / corrected ones.
"""

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core import taxonomy
from app.database.postgis import LatLon, point
from app.models.element import LOCKED_STATUSES, Element, ElementStatus
from app.models.observation import Observation
from app.repositories import element as element_repo
from app.schemas import ml
from app.services import ml_client

log = logging.getLogger(__name__)

SEARCH_MARGIN_M = 50  # existing elements this close to new detections are sent to ML


@dataclass
class PendingObservations:
    """Observations added to the session that still have to go through /dedup."""

    rows: dict[str, Observation] = field(default_factory=dict)
    detections: list[ml.Observation] = field(default_factory=list)
    cameras: dict[str, ml.CameraMeta] = field(default_factory=dict)

    def add(
        self, db: Session, detection: ml.Observation, camera: ml.CameraMeta
    ) -> Observation:
        has_position = detection.est_lat is not None and detection.est_lon is not None
        row = Observation(
            id=detection.observation_id,
            image_id=camera.image_id,
            type=detection.type,
            score=detection.score,
            bbox_xyxy=detection.bbox_xyxy,
            attributes=detection.attributes or {},
            bearing_deg=detection.bearing_deg,
            geom=(
                point(lat=detection.est_lat, lon=detection.est_lon)
                if has_position
                else None
            ),
            uncertainty_m=detection.uncertainty_m,
        )
        db.add(row)
        self.rows[row.id] = row
        self.detections.append(detection)
        self.cameras[camera.image_id] = camera
        return row

    def points(self) -> list[LatLon]:
        """Cameras + estimated object positions, to find existing elements nearby."""
        points = [LatLon(lat=c.lat, lon=c.lon) for c in self.cameras.values()]
        points += [
            LatLon(lat=o.est_lat, lon=o.est_lon)
            for o in self.detections
            if o.est_lat is not None and o.est_lon is not None
        ]
        return points


@dataclass
class DedupResult:
    elements: list[
        Element
    ]  # created, updated, or (if human-checked) just given new views
    removed_ids: list[uuid.UUID]


def run_dedup(db: Session, pending: PendingObservations) -> DedupResult:
    if not pending.rows:
        return DedupResult([], [])
    existing = [
        e
        for e in element_repo.list_near(db, pending.points(), SEARCH_MARGIN_M)
        if e.observations
    ]
    earlier = [
        o for e in existing if e.status is ElementStatus.AUTO for o in e.observations
    ]
    response = ml_client.dedup(
        ml.DedupRequest(
            observations=pending.detections + [_observation_to_ml(o) for o in earlier],
            images=list(pending.cameras.values()) + _cameras(earlier, pending.cameras),
            existing_elements=[_to_ml(e) for e in existing],
        )
    )
    sent = pending.rows | {o.id: o for o in earlier}
    views_before = {e.id: {o.id for o in e.observations} for e in existing}
    return _apply(db, response, sent, views_before)


def _to_ml(element: Element) -> ml.MLElement:
    """Rejected elements are sent too, so ML knows that spot is a false positive."""
    return ml.MLElement(
        element_id=element.id,
        type=taxonomy.class_name(element.category, element.type),
        lat=element.latitude,
        lon=element.longitude,
        confidence=element.confidence,
        observation_ids=[o.id for o in element.observations],
        best_observation_id=element.best_observation_id or element.observations[0].id,
        status=element.status.value,
        attributes=element.attributes or None,
    )


def _observation_to_ml(row: Observation) -> ml.Observation:
    """A stored observation, as /infer returned it."""
    return ml.Observation(
        observation_id=row.id,
        type=row.type,
        score=row.score,
        bbox_xyxy=row.bbox_xyxy,
        bearing_deg=row.bearing_deg,
        est_lat=row.latitude,
        est_lon=row.longitude,
        uncertainty_m=row.uncertainty_m,
        attributes=row.attributes or None,
    )


def _cameras(
    rows: Iterable[Observation], known: dict[str, ml.CameraMeta]
) -> list[ml.CameraMeta]:
    """Cameras of the images these observations come from (ML uses them for ray checks)."""
    images = {o.image.id: o.image for o in rows if o.image_id not in known}
    return [
        ml.CameraMeta(image_id=i.id, lat=i.latitude, lon=i.longitude, heading=i.heading)
        for i in images.values()
    ]


def _link(rows: Iterable[Observation], element: Element) -> None:
    for row in rows:
        # Through the relationship, so the element the view leaves drops it from its list too:
        # the removal check in _apply reads that list, and deleting an element unlinks every
        # view still in it.
        row.element = element
        row.element_id = element.id  # the relationship only sets it at flush


def _apply(
    db: Session,
    response: ml.DedupResponse,
    sent: dict[str, Observation],
    views_before: dict[uuid.UUID, set[str]],
) -> DedupResult:
    """sent: every observation in the request (new and earlier ones), by id.
    views_before: observation ids of each existing element sent, before this dedup."""
    touched: dict[uuid.UUID, Element] = {}
    print(
        f"\n[DEDUP] ML returned {len(response.elements)} elements, "
        f"{len(response.unassigned_observation_ids)} unassigned observations, "
        f"{len(response.removed_element_ids)} removed elements",
        flush=True,
    )
    if response.unassigned_observation_ids:
        print(
            f"[DEDUP] unassigned observations: {response.unassigned_observation_ids}",
            flush=True,
        )

    for found in response.elements:
        rows = [sent[i] for i in found.observation_ids if i in sent]
        if not rows:
            print(
                f"[DEDUP] element {found.element_id} ({found.type}): "
                "none of the observations sent, skipped",
                flush=True,
            )
            continue

        element = db.get(Element, found.element_id)
        if element is not None and element.status in LOCKED_STATUSES:
            # New view of something a human already decided on: link it, change nothing else
            moved = [r for r in rows if r.element_id != element.id]
            print(
                f"[DEDUP] element {found.element_id} is {element.status.value} (locked): "
                f"linked {len(moved)} observations, nothing else changed",
                flush=True,
            )
            if moved:
                _link(moved, element)
                touched[element.id] = element
            continue

        if element is not None and views_before.get(element.id) == {r.id for r in rows}:
            print(
                f"[DEDUP] element {found.element_id} ({found.type}): same views, unchanged",
                flush=True,
            )
            continue

        try:
            category, type_ = taxonomy.split_class(found.type)
        except ValueError:
            print(
                f"[DEDUP] element {found.element_id}: unknown class {found.type!r}, skipped",
                flush=True,
            )
            log.warning(
                "ML returned unknown class %r, observations left unassigned", found.type
            )
            continue

        print(
            f"[DEDUP] element {found.element_id}: "
            f"{'CREATE' if element is None else 'UPDATE'} {found.type} "
            f"at ({found.lat}, {found.lon}) conf={found.confidence} "
            f"obs={len(rows)}/{len(found.observation_ids)} "
            f"attributes={found.attributes}",
            flush=True,
        )
        if element is None:
            element = Element(id=found.element_id)
            db.add(element)
        best = sent.get(found.best_observation_id)
        element.name = taxonomy.label(found.type)
        element.category = category
        element.type = type_
        element.confidence = found.confidence
        element.geom = point(lat=found.lat, lon=found.lon)
        element.best_observation_id = found.best_observation_id
        if found.attributes is not None:
            element.attributes = found.attributes
        elif best is not None:
            element.attributes = best.attributes
        else:
            element.attributes = element.attributes or {}
        _link(rows, element)
        touched[element.id] = element

    removed: list[uuid.UUID] = []
    for element_id in response.removed_element_ids:
        element = db.get(Element, element_id)
        if (
            element is None
            or element.status in LOCKED_STATUSES
            or element_id in touched
        ):
            print(
                f"[DEDUP] remove {element_id}: ignored (missing, locked or just updated)",
                flush=True,
            )
            continue
        if element.observations:  # ML didn't give these views to another element
            print(
                f"[DEDUP] remove {element_id}: kept, {len(element.observations)} "
                "observations were not placed elsewhere",
                flush=True,
            )
            continue
        print(f"[DEDUP] remove {element_id}: deleted", flush=True)
        db.delete(element)
        removed.append(element_id)

    db.flush()
    return DedupResult(list(touched.values()), removed)
