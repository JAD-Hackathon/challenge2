"""Mock of app/services/ingest.py and app/services/image.py.

Uploads go to the real ML service (run it with ML_MOCK=true, its default): /infer for each
image or /infer-video for a video, then one /dedup, exactly like real mode. Only the database is
replaced, by the in-memory store. ML writes the blurred images to the shared folder, so
SHARED_DIR must be the same folder ML uses (both in Docker, or both run locally).
"""

import uuid
from datetime import datetime

from app.mocks.store import new_element, now, store
from app.schemas import ml
from app.schemas.element import ElementRead
from app.schemas.image import (
    BatchResponse,
    ImageRead,
    ImageResult,
    ImageStatus,
    ObservationRead,
    UploadedImage,
    attribution,
    new_image_id,
)
from app.schemas.video import UploadedVideo, VideoResponse, new_sequence_id
from app.services import media, ml_client
from app.services.ml_client import MLInputError


def ingest_batch(uploads: list[UploadedImage]) -> BatchResponse:
    collected = _Collected()
    results: list[ImageResult] = []
    for upload in uploads:
        meta = upload.meta
        if meta is None:  # unusable Mapillary / KartaView record
            results.append(
                ImageResult(
                    index=upload.index,
                    filename=upload.filename,
                    image_id=None,
                    status=ImageStatus.FAILED,
                    error=upload.error,
                )  # fmt: skip
            )
            continue
        image_id = meta.image_id or new_image_id()
        base = {
            "index": upload.index,
            "filename": upload.filename,
            "image_id": image_id,
        }
        if store.has_image(image_id):
            results.append(
                ImageResult(
                    **base,
                    status=ImageStatus.DUPLICATE,
                    error="image_id already processed",
                )
            )
            continue

        camera = meta.camera(image_id)
        try:
            inferred = ml_client.infer(
                upload.content, camera, upload.content_type or "image/jpeg"
            )
        except MLInputError as e:
            results.append(
                ImageResult(**base, status=ImageStatus.FAILED, error=e.detail)
            )
            continue

        image = collected.add(
            camera, inferred.blurred_image_path, inferred.observations,
            filename=upload.filename, author=meta.author, license=meta.license,
            captured_at=meta.captured_at,
        )  # fmt: skip
        results.append(_processed(base, image, inferred.observations))
    return BatchResponse(images=results, elements=collected.save())


def ingest_video(video: UploadedVideo) -> VideoResponse:
    result = ml_client.infer_video(video, new_sequence_id())
    collected = _Collected()
    results: list[ImageResult] = []
    for index, frame in enumerate(result.frames):
        filename = video.frame_filename(frame.camera.frame_index)
        image = collected.add(
            frame.camera, frame.blurred_image_path, frame.observations,
            filename=filename, author=video.meta.author, license=video.meta.license,
            captured_at=frame.captured_at,
        )  # fmt: skip
        base = {"index": index, "filename": filename, "image_id": image.id}
        results.append(_processed(base, image, frame.observations))
    return VideoResponse(
        images=results, elements=collected.save(), sequence_id=result.sequence_id
    )


def get_image(image_id: str) -> ImageRead:
    return store.get_image(image_id)


class _Collected:
    """Images and detections of one upload, saved to the store together after ML /dedup."""

    def __init__(self) -> None:
        self.images: list[ImageRead] = []
        self.detections: dict[uuid.UUID, tuple[ml.Observation, ImageRead]] = {}
        self.cameras: list[ml.CameraMeta] = []

    def add(
        self,
        camera: ml.CameraMeta,
        blurred_image_path: str,
        observations: list[ml.Observation],
        *,
        filename: str | None,
        author: str | None,
        license: str | None,
        captured_at: datetime | None,
    ) -> ImageRead:
        image = ImageRead(
            id=camera.image_id,
            source=camera.source,
            latitude=camera.lat,
            longitude=camera.lon,
            heading=camera.heading,
            fov=camera.fov,
            image_url=media.media_url(blurred_image_path),
            filename=filename,
            attribution=attribution(author, license, camera.source),
            captured_at=captured_at,
            created_at=now(),
            observations=[],
        )
        self.images.append(image)
        self.detections |= {d.observation_id: (d, image) for d in observations}
        self.cameras.append(camera)
        return image

    def save(self) -> list[ElementRead]:
        """One ML /dedup for everything collected, then store it all. Returns the new elements."""
        found = []
        if self.detections:
            request = ml.DedupRequest(
                observations=[d for d, _ in self.detections.values()],
                images=self.cameras,
            )
            found = ml_client.dedup(request).elements
        pairs = [(f, _element(f, self.detections)) for f in found]
        element_of = {
            o: e.id for f, e in pairs if e is not None for o in f.observation_ids
        }

        with store.lock:
            for image in self.images:
                store.save_image(image)
            for detection, image in self.detections.values():
                store.add_observation(
                    image.id,
                    _observation(detection, element_of.get(detection.observation_id)),
                )
            for f, element in pairs:
                if element is not None:
                    store.save_element(
                        element, best_observation_id=f.best_observation_id
                    )
        return [e for _, e in pairs if e is not None]


def _processed(
    base: dict, image: ImageRead, observations: list[ml.Observation]
) -> ImageResult:
    return ImageResult(
        **base,
        status=ImageStatus.PROCESSED,
        image_url=image.image_url,
        observation_count=len(observations),
    )


def _element(
    found: ml.MLElement, detections: dict[uuid.UUID, tuple[ml.Observation, ImageRead]]
) -> ElementRead | None:
    """ML /dedup element -> catalogue element (None for classes the API doesn't know)."""
    best, image = detections[found.best_observation_id]
    try:
        return new_element(
            element_id=found.element_id,
            class_name=found.type,
            attributes=found.attributes
            if found.attributes is not None
            else best.attributes or {},
            confidence=found.confidence,
            lat=found.lat,
            lon=found.lon,
            image=image,
            bbox_xyxy=best.bbox_xyxy,
            observation_count=len(found.observation_ids),
            created_at=now(),
        )
    except ValueError:
        return None


def _observation(
    detection: ml.Observation, element_id: uuid.UUID | None
) -> ObservationRead:
    return ObservationRead(
        id=detection.observation_id,
        element_id=element_id,
        type=detection.type,
        score=detection.score,
        bbox_xyxy=detection.bbox_xyxy,
        attributes=detection.attributes or {},
        latitude=detection.est_lat,
        longitude=detection.est_lon,
        uncertainty_m=detection.uncertainty_m,
    )
