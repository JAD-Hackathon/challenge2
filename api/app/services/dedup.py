"""Detections of a batch -> ML /dedup -> elements in the catalogue (used by services/ingest.py).

Observation and element ids are the ones ML returns: the API never makes its own, so they match
ML's logs. ML's mock derives observation ids from the image_id, which is fine because an
image_id is only sent to ML once (ingest skips ids that were already processed).
"""

import logging
import uuid
from dataclasses import dataclass, field

from app.core import taxonomy
from app.database.postgis import LatLon, point
from app.models.element import LOCKED_STATUSES, Element
from app.models.observation import Observation
from app.repositories import element as element_repo
from app.schemas import ml
from app.services import ml_client
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

SEARCH_MARGIN_M = 50  # existing elements this close to new detections are sent to ML


@dataclass
class PendingObservations:
    """Observations added to the session that still have to go through /dedup."""

    rows: dict[uuid.UUID, Observation] = field(default_factory=dict)
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
    existing = element_repo.list_near(db, pending.points(), SEARCH_MARGIN_M)
    response = ml_client.dedup(
        ml.DedupRequest(
            observations=pending.detections,
            images=list(pending.cameras.values()),
            existing_elements=[_to_ml(e) for e in existing if e.observations],
        )
    )
    return _apply(db, response, pending)


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


def _apply(
    db: Session, response: ml.DedupResponse, pending: PendingObservations
) -> DedupResult:
    touched: dict[uuid.UUID, Element] = {}

    for found in response.elements:
        new_rows = [pending.rows[i] for i in found.observation_ids if i in pending.rows]
        if not new_rows:
            continue  # nothing new for this element

        element = db.get(Element, found.element_id)
        if element is not None and element.status in LOCKED_STATUSES:
            # New view of something a human already decided on: link it, change nothing else
            for row in new_rows:
                row.element_id = element.id
            touched[element.id] = element
            continue

        try:
            category, type_ = taxonomy.split_class(found.type)
        except ValueError:
            log.warning(
                "ML returned unknown class %r, observations left unassigned", found.type
            )
            continue

        if element is None:
            element = Element(id=found.element_id)
            db.add(element)
        best = pending.rows.get(found.best_observation_id)
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
        for row in new_rows:
            row.element_id = element.id
        touched[element.id] = element

    removed: list[uuid.UUID] = []
    for element_id in response.removed_element_ids:
        element = db.get(Element, element_id)
        if (
            element is None
            or element.status in LOCKED_STATUSES
            or element_id in touched
        ):
            continue
        db.delete(element)  # its observations are kept, unassigned
        removed.append(element_id)

    db.flush()
    return DedupResult(list(touched.values()), removed)
