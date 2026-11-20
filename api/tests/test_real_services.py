"""Real-mode services (batch ingest, dedup, false-positive flag) with ML and PostGIS stubbed.

What PostGIS computes on a real round trip (latitude/longitude, timestamps) is filled in by the
stubs, so these check the services' logic, not the SQL.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from app.core import taxonomy
from app.database.postgis import LatLon, point
from app.models.element import Element, ElementCategory, ElementStatus
from app.models.image import Image
from app.models.observation import Observation
from app.repositories import element as element_repo
from app.repositories import image as image_repo
from app.schemas import ml
from app.schemas.image import ImageMeta, ImageStatus, UploadedImage
from app.schemas.video import UploadedVideo, VideoMeta
from app.services import dedup, ingest, ml_client
from app.services import element as element_service
from app.services.ml_client import MLInputError, MLNotImplementedError, MLServiceError

NOW = datetime(2026, 11, 16, tzinfo=UTC)
SIGN = ElementCategory.TRAFFIC_SIGN


class FakeSession:
    """Just enough of a Session for the services: remembers what was added and deleted."""

    def __init__(self, *elements: Element):
        self.elements = {e.id: e for e in elements}
        self.added: list = []
        self.deleted: list = []
        self.commits = 0
        self.rolled_back = False

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Element):
            self.elements[obj.id] = obj

    def get(self, model, key, **_):
        return self.elements.get(key) if model is Element else None

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rolled_back = True

    def of(self, cls):
        return [o for o in self.added if isinstance(o, cls)]


def element(status=ElementStatus.AUTO, type_="stop") -> Element:
    e = Element(
        id=uuid.uuid4(), name=taxonomy.label(f"sign.{type_}"), category=SIGN, type=type_,
        status=status, confidence=0.8, attributes={},
    )  # fmt: skip
    # computed by PostGIS / server defaults for real
    e.latitude, e.longitude, e.created_at, e.updated_at = 40.64, -8.65, NOW, NOW
    e.observations = [Observation(id=str(uuid.uuid4()), type=f"sign.{type_}", score=0.8)]
    return e


@pytest.fixture
def stub_queries(monkeypatch):
    def get_elements(db, ids):
        found = [db.elements[i] for i in ids if i in db.elements]
        for e in found:  # what a real round trip fills in
            e.latitude, e.longitude = e.latitude or 40.64, e.longitude or -8.65
            e.created_at, e.updated_at = e.created_at or NOW, NOW
            e.status = e.status or ElementStatus.AUTO
        return found

    monkeypatch.setattr(
        image_repo, "image_exists", lambda db, image_id: image_id == "seen"
    )
    monkeypatch.setattr(element_repo, "list_near", lambda db, points, margin_m: [])
    monkeypatch.setattr(element_repo, "get_elements", get_elements)


def upload(index: int, content: bytes, **meta) -> UploadedImage:
    return UploadedImage(
        index=index, filename=f"{index}.jpg", content_type="image/jpeg", content=content,
        meta=ImageMeta(lat=40.64, lon=-8.65, heading=90, **meta),
    )  # fmt: skip


# --- batch upload ---


def test_ingest_batch(stub_queries, ml_stub, make_jpeg):
    db = FakeSession()
    jpeg = make_jpeg()

    result = ingest.ingest_batch(
        db,
        [
            upload(0, jpeg),
            upload(1, b"bad"),
            upload(2, jpeg, image_id="seen"),
            upload(3, jpeg),
        ],
    )

    assert [r.status for r in result.images] == [
        ImageStatus.PROCESSED, ImageStatus.FAILED, ImageStatus.DUPLICATE, ImageStatus.PROCESSED,
    ]  # fmt: skip
    assert result.images[1].error == "ML unsupported_image: could not read the image"
    assert "seen" not in [
        m.image_id for m in ml_stub.inferred
    ]  # duplicates never reach ML
    assert db.commits == 1
    assert len(db.of(Image)) == 2

    # ids are ML's, not the API's
    observations = db.of(Observation)
    sent = ml_stub.dedups[0].observations
    assert [o.id for o in observations] == [o.observation_id for o in sent]
    assert len(ml_stub.dedups) == 1  # one dedup for the whole batch

    sign = next(e for e in db.of(Element) if e.type == "speed_limit")
    assert sign.id == uuid.uuid5(uuid.NAMESPACE_URL, str(sent[0].observation_id))
    assert (sign.category, sign.name, sign.attributes) == (
        SIGN,
        "Limite de velocidade",
        {"limit": 50},
    )
    assert sign.best_observation_id == sent[0].observation_id
    assert {o.element_id for o in observations if o.type == "sign.speed_limit"} == {
        sign.id
    }
    assert {e.id for e in result.elements} == {e.id for e in db.of(Element)}


def test_ingest_batch_ml_down_saves_nothing(
    stub_queries, ml_stub, make_jpeg, shared_dir
):
    db = FakeSession()
    with pytest.raises(MLServiceError):
        ingest.ingest_batch(
            db, [upload(0, make_jpeg(), image_id="first"), upload(1, b"ML down")]
        )
    assert db.rolled_back and db.commits == 0
    assert not (shared_dir / "images" / "first.jpg").exists()  # blurred copy cleaned up


def test_ingest_video(stub_queries, ml_stub, shared_dir, make_video, make_gpx):
    import io

    db = FakeSession()
    video = UploadedVideo(
        file=io.BytesIO(make_video()), filename="ride.mp4", content_type="video/mp4",
        track=make_gpx(), meta=VideoMeta(spacing_m=10, author="team"),
    )  # fmt: skip
    result = ingest.ingest_video(db, video)

    images = db.of(Image)
    assert [i.id for i in images] == [f"{result.sequence_id}_{n:04d}" for n in range(4)]
    assert {(i.source, i.sequence_id, i.author) for i in images} == {
        ("video", result.sequence_id, "team")
    }
    assert [i.frame_index for i in images] == [0, 1, 2, 3]
    assert [c.image_id for c in ml_stub.inferred] == [i.id for i in images]  # via /infer
    assert len(ml_stub.dedups) == 1 and db.commits == 1
    assert {e.type for e in result.elements} == {"speed_limit", "street_lamp"}


def test_ingest_video_ml_down_saves_nothing(
    stub_queries, ml_stub, monkeypatch, shared_dir, make_video, make_gpx
):
    import io

    def dedup_down(request):
        raise MLServiceError("ML service unreachable")

    monkeypatch.setattr(ml_client, "dedup", dedup_down)
    db = FakeSession()
    video = UploadedVideo(
        io.BytesIO(make_video()), "v.mp4", "video/mp4", make_gpx(), VideoMeta()
    )
    with pytest.raises(MLServiceError):
        ingest.ingest_video(db, video)
    assert db.rolled_back and db.commits == 0
    sequence_id = ml_stub.inferred[-1].sequence_id
    assert not list(
        (shared_dir / "images").glob(f"{sequence_id}_*")
    )  # ML's blurred frames cleaned up


# --- dedup ---


def test_dedup_never_changes_human_decisions(monkeypatch):
    verified, merged_away, rejected = (
        element(ElementStatus.VERIFIED),
        element(),
        element(ElementStatus.REJECTED),
    )
    db = FakeSession(verified, merged_away, rejected)
    monkeypatch.setattr(
        element_repo, "list_near", lambda *a: [verified, merged_away, rejected]
    )

    pending = dedup.PendingObservations()
    camera = ml.CameraMeta(image_id="img", lat=40.64, lon=-8.65, heading=0)
    new_view = pending.add(
        db, ml.Observation(observation_id=str(uuid.uuid4()), type="sign.yield", score=0.9,
                           bbox_xyxy=[1, 1, 5, 5]), camera,
    )  # fmt: skip
    sent = []

    def fake_dedup(request):
        sent.append(request)
        return ml.DedupResponse(
            elements=[
                ml.MLElement(
                    element_id=verified.id,
                    type="sign.yield",
                    lat=1,
                    lon=1,
                    confidence=0.1,
                    observation_ids=[new_view.id],
                    best_observation_id=new_view.id,
                )  # fmt: skip
            ],
            removed_element_ids=[merged_away.id, rejected.id],
        )

    monkeypatch.setattr(ml_client, "dedup", fake_dedup)
    result = dedup.run_dedup(db, pending)

    statuses = {e.element_id: e.status for e in sent[0].existing_elements}
    assert statuses[rejected.id] == "rejected"  # ML is told about false positives
    assert (verified.type, verified.confidence) == ("stop", 0.8)  # untouched...
    assert new_view.element_id == verified.id  # ...but the new view is linked to it
    assert db.deleted == [merged_away]  # rejected elements are never deleted
    assert result.removed_ids == [merged_away.id]


def test_dedup_skips_unknown_classes(monkeypatch, ml_stub):
    db = FakeSession()
    monkeypatch.setattr(element_repo, "list_near", lambda *a: [])
    pending = dedup.PendingObservations()
    row = pending.add(
        db,
        ml.Observation(observation_id=str(uuid.uuid4()), type="bench.wooden", score=0.9,
                       bbox_xyxy=[1, 1, 5, 5], est_lat=40.64, est_lon=-8.65),
        ml.CameraMeta(image_id="i", lat=40.64, lon=-8.65, heading=0),
    )  # fmt: skip
    assert dedup.run_dedup(db, pending).elements == []
    assert row.element_id is None and db.of(Element) == []


# --- false positive ---


def test_flag_false_positive(monkeypatch):
    target = element()
    monkeypatch.setattr(element_repo, "get_element", lambda db, element_id: target)
    monkeypatch.setattr(ml_client, "infer", lambda *a, **k: pytest.fail("ML called"))
    db = FakeSession(target)

    flagged = element_service.flag_false_positive(db, target.id)
    assert flagged.status is ElementStatus.REJECTED and db.commits == 1

    element_service.flag_false_positive(
        db, target.id
    )  # already rejected: nothing to save
    assert db.commits == 1


def test_update_element(monkeypatch):
    from app.schemas.element import ElementUpdate

    target = element(type_="speed_limit")
    target.attributes = {"limit": 50}
    monkeypatch.setattr(element_repo, "get_element", lambda db, element_id: target)
    db = FakeSession(target)

    element_service.update_element(
        db,
        target.id,
        ElementUpdate(attributes={"limit": 30}, latitude=40.7, longitude=-8.6),
    )
    assert (target.type, target.attributes, target.status) == (
        "speed_limit", {"limit": 30}, ElementStatus.CORRECTED,
    )  # fmt: skip
    assert target.geom.data == "POINT(-8.6 40.7)" and db.commits == 1

    element_service.update_element(db, target.id, ElementUpdate(type="stop"))
    assert (target.name, target.attributes) == ("Stop", {})


def test_verify_element(monkeypatch):
    target = element(ElementStatus.REJECTED)
    monkeypatch.setattr(element_repo, "get_element", lambda db, element_id: target)
    db = FakeSession(target)

    assert (
        element_service.verify_element(db, target.id).status is ElementStatus.VERIFIED
    )
    element_service.verify_element(db, target.id)  # already verified: nothing to save
    assert db.commits == 1

    target.status = ElementStatus.CORRECTED
    assert (
        element_service.verify_element(db, target.id).status is ElementStatus.CORRECTED
    )


# --- ML client ---


def test_ml_errors_are_split_by_status():
    with pytest.raises(MLInputError, match="invalid_meta: heading"):
        ml_client._raise_for_error(
            httpx.Response(
                400, json={"error": {"code": "invalid_meta", "message": "heading"}}
            )
        )
    with pytest.raises(MLServiceError) as error:
        ml_client._raise_for_error(httpx.Response(500, text="boom"))
    assert not isinstance(error.value, MLInputError)
    with pytest.raises(MLNotImplementedError, match="has no /infer-video endpoint"):
        ml_client._raise_for_error(
            httpx.Response(404, json={"detail": "Not Found"}), "/infer-video"
        )
    with pytest.raises(MLNotImplementedError, match="not_implemented"):
        ml_client._raise_for_error(
            httpx.Response(
                501, json={"error": {"code": "not_implemented", "message": "x"}}
            )
        )


def test_ml_ids():
    """Observation ids are any string (ML sends short hex ids); element ids must be UUIDs (502)."""
    body = {"image_id": "x", "blurred_image_path": "images/x.jpg", "observations": [
        {"observation_id": "a1b2c3d4e5f6", "type": "sign.stop", "score": 0.9, "bbox_xyxy": [1, 1, 2, 2]}
    ]}  # fmt: skip
    parsed = ml_client._parse(ml.InferResponse, httpx.Response(200, json=body))
    assert parsed.observations[0].observation_id == "a1b2c3d4e5f6"

    body = {"elements": [
        {"element_id": "a1b2", "type": "sign.stop", "lat": 1, "lon": 1, "confidence": 0.9,
         "observation_ids": ["a1b2c3d4e5f6"], "best_observation_id": "a1b2c3d4e5f6"}
    ]}  # fmt: skip
    with pytest.raises(MLServiceError, match="breaks the contract"):
        ml_client._parse(ml.DedupResponse, httpx.Response(200, json=body))


def test_taxonomy():
    assert taxonomy.split_class("sign.speed_limit") == (SIGN, "speed_limit")
    with pytest.raises(ValueError):
        taxonomy.split_class("bench.wooden")
    assert taxonomy.label("waste.new_kind") == "New kind"


# --- coordinates ---


def test_point_takes_named_coordinates():
    assert point(lat=40.64, lon=-8.65).data == "POINT(-8.65 40.64)"  # WKT is lon, lat
    with pytest.raises(TypeError):
        point(40.64, -8.65)  # type: ignore[misc]  # positional: could be swapped


def test_dedup_search_points():
    """Cameras + positioned detections, as named LatLon (no lat/lon guessing)."""
    camera = ml.CameraMeta(image_id="cam", lat=40.64, lon=-8.65, heading=0)
    pending = dedup.PendingObservations()
    for est_lat, est_lon in [(40.6401, -8.6501), (None, None)]:
        detection = ml.Observation(
            observation_id=str(uuid.uuid4()),
            type="sign.stop",
            score=0.9,
            bbox_xyxy=[1, 1, 2, 2],
            est_lat=est_lat,
            est_lon=est_lon,
        )
        pending.add(FakeSession(), detection, camera)
    assert pending.points() == [
        LatLon(lat=40.64, lon=-8.65),
        LatLon(lat=40.6401, lon=-8.6501),
    ]
