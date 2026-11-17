"""Tests run in mock mode with a throwaway shared folder: no database or ML service needed.

Settings are read when app modules are imported, so the environment is set before any import.
"""

import io
import os
import random
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["API_MOCK"] = "true"
os.environ["SHARED_DIR"] = tempfile.mkdtemp(prefix="api-tests-shared-")
os.environ["MEDIA_URL"] = "/media"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, UnidentifiedImageError  # noqa: E402

from app.main import app  # noqa: E402
from app.mocks.store import store  # noqa: E402
from app.schemas import ml  # noqa: E402
from app.schemas.video import UploadedVideo  # noqa: E402
from app.services import media, ml_client  # noqa: E402
from app.services.ml_client import MLInputError, MLServiceError  # noqa: E402

T0 = datetime(2025, 6, 12, 10, 15, tzinfo=UTC)  # when the test videos were "recorded"


@pytest.fixture
def shared_dir() -> Path:
    return Path(os.environ["SHARED_DIR"])


@pytest.fixture
def client():
    with TestClient(app) as c:  # runs the lifespan: seeds the mock store
        yield c
    store.reset()


# --- ML service ---


class MLStub:
    """Behaves like the ML service in mock mode (ml/src/service/mock.py), without HTTP:
    ids derived from image_id / first observation, blurred copy written to the shared folder.
    Every image gets a speed_limit sign ({"limit": 50}) and a street lamp.

    infer_video stands for the proposed /infer-video: 3 frames, 5 m apart, going north."""

    def __init__(self) -> None:
        self.inferred: list[ml.CameraMeta] = []
        self.dedups: list[ml.DedupRequest] = []
        self.videos: list[
            tuple[bytes, bytes, ml.VideoInferMeta]
        ] = []  # video, track, meta

    def infer(self, image: bytes, meta: ml.CameraMeta, content_type="image/jpeg"):
        if image == b"ML down":
            raise MLServiceError("ML service unreachable")
        try:
            picture = Image.open(io.BytesIO(image)).convert("RGB")
        except (UnidentifiedImageError, OSError):
            raise MLInputError(
                "ML unsupported_image: could not read the image"
            ) from None
        self.inferred.append(meta)
        media.images_dir().mkdir(parents=True, exist_ok=True)
        picture.save(media.images_dir() / f"{meta.image_id}.jpg")
        return self._detections(meta)

    def infer_video(
        self, video: UploadedVideo, sequence_id: str
    ) -> ml.InferVideoResponse:
        content = video.file.read()  # what would be streamed to ML
        if content == b"not a video":
            raise MLInputError("ML unsupported_video: could not read the video")
        self.videos.append((content, video.track, video.meta.for_ml(sequence_id)))
        frames = []
        for i in range(3):
            camera = ml.CameraMeta(
                image_id=f"{sequence_id}_{i:04d}", lat=40.64 + i * 5 / 111_195, lon=-8.65,
                heading=0, fov=video.meta.fov, source="video", sequence_id=sequence_id,
                frame_index=i,
            )  # fmt: skip
            media.images_dir().mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (320, 240), "grey").save(
                media.images_dir() / f"{camera.image_id}.jpg"
            )
            inferred = self._detections(camera)
            frames.append(
                ml.InferredFrame(
                    camera=camera,
                    captured_at=T0 + timedelta(seconds=i),
                    blurred_image_path=inferred.blurred_image_path,
                    observations=inferred.observations,
                )
            )
        return ml.InferVideoResponse(sequence_id=sequence_id, frames=frames)

    def _detections(self, meta: ml.CameraMeta) -> ml.InferResponse:
        rng = random.Random(meta.image_id)

        def detection(type_: str, attributes=None) -> ml.Observation:
            return ml.Observation(
                observation_id=uuid.UUID(int=rng.getrandbits(128)),
                type=type_, score=0.9, bbox_xyxy=[10, 10, 50, 50], bearing_deg=meta.heading,
                est_lat=meta.lat + 0.0001, est_lon=meta.lon, uncertainty_m=2.0,
                attributes=attributes,
            )  # fmt: skip

        return ml.InferResponse(
            image_id=meta.image_id,
            blurred_image_path=f"images/{meta.image_id}.jpg",
            observations=[
                detection("sign.speed_limit", {"limit": 50}),
                detection("light.street_lamp"),
            ],
        )

    def dedup(self, request: ml.DedupRequest) -> ml.DedupResponse:
        """One element per class, like ML's mock (which ignores existing_elements)."""
        self.dedups.append(request)
        groups: dict[str, list[ml.Observation]] = {}
        for o in request.observations:
            groups.setdefault(o.type, []).append(o)
        return ml.DedupResponse(
            elements=[
                ml.MLElement(
                    element_id=uuid.uuid5(
                        uuid.NAMESPACE_URL, str(group[0].observation_id)
                    ),
                    type=type_,
                    lat=sum(o.est_lat for o in group) / len(group),
                    lon=sum(o.est_lon for o in group) / len(group),
                    confidence=max(o.score for o in group),
                    observation_ids=[o.observation_id for o in group],
                    best_observation_id=group[0].observation_id,
                )
                for type_, group in groups.items()
            ]
        )


@pytest.fixture
def ml_stub(monkeypatch) -> MLStub:
    stub = MLStub()
    monkeypatch.setattr(ml_client, "infer", stub.infer)
    monkeypatch.setattr(ml_client, "dedup", stub.dedup)
    monkeypatch.setattr(ml_client, "infer_video", stub.infer_video)
    return stub


# --- files ---


def _jpeg(size: tuple[int, int] = (640, 480), colour: str = "steelblue") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def make_jpeg():
    return _jpeg


def _gpx(seconds: int = 6, speed_mps: float = 5.0, start: datetime = T0) -> bytes:
    """Going north at speed_mps from (40.64, -8.65), one point per second (GPX 1.1)."""
    points = "".join(
        f'<trkpt lat="{40.64 + speed_mps * s / 111_195:.8f}" lon="-8.65">'
        f"<time>{(start + timedelta(seconds=s)).isoformat().replace('+00:00', 'Z')}</time></trkpt>"
        for s in range(seconds + 1)
    )
    return (
        '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{points}</trkseg></trk></gpx>"
    ).encode()


@pytest.fixture
def make_gpx():
    return _gpx
