"""Uploads -> ML -> one ML /dedup for the whole upload -> catalogue.

POST /images: ML /infer for each image. A file ML refuses only fails that item.
POST /videos: the API picks one frame every spacing_m metres and places it with the GPS track,
              see video_frames.py. Then each frame is an image like any other: ML /infer,
              stored, one /dedup for the whole video.
Either way, if ML is down the whole upload fails and nothing is saved.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.database.postgis import point
from app.models.image import Image
from app.repositories import element as element_repo
from app.repositories import image as image_repo
from app.schemas import ml
from app.schemas.image import (
    BatchResponse,
    ImageResult,
    ImageStatus,
    UploadedImage,
    new_image_id,
)
from app.schemas.video import UploadedVideo, VideoResponse, new_sequence_id
from app.services import media, ml_client, video_frames
from app.services.dedup import DedupResult, PendingObservations, run_dedup
from app.services.element import to_element_read
from app.services.ml_client import MLInputError


def ingest_batch(db: Session, uploads: Iterable[UploadedImage]) -> BatchResponse:
    with _all_or_nothing(db) as work:
        results = [_infer_one(db, work, upload) for upload in uploads]
        dedup = run_dedup(db, work.pending)
    return BatchResponse(images=results, **_changes(db, dedup))


def ingest_video(db: Session, video: UploadedVideo) -> VideoResponse:
    """The frames, placed along the GPS track, go through ingest_batch like images."""
    sequence_id = new_sequence_id()
    with video_frames.open_video(video, sequence_id) as frames:
        batch = ingest_batch(db, frames)
    return VideoResponse(**dict(batch), sequence_id=sequence_id)


# --- steps ---


@dataclass
class _Work:
    pending: PendingObservations = field(default_factory=PendingObservations)
    written: list[Path] = field(
        default_factory=list
    )  # blurred images ML wrote for this upload


@contextmanager
def _all_or_nothing(db: Session) -> Iterator[_Work]:
    work = _Work()
    try:
        yield work
        db.commit()
    except Exception:
        db.rollback()
        for (
            path
        ) in work.written:  # don't leave blurred images of an upload that wasn't saved
            path.unlink(missing_ok=True)
        raise


def _infer_one(db: Session, work: _Work, upload: UploadedImage) -> ImageResult:
    meta = upload.meta
    if meta is None:  # unusable Mapillary / KartaView record
        return ImageResult(
            index=upload.index, filename=upload.filename, image_id=None,
            status=ImageStatus.FAILED, error=upload.error,
        )  # fmt: skip
    image_id = meta.image_id or new_image_id()
    base = {"index": upload.index, "filename": upload.filename, "image_id": image_id}

    if image_repo.image_exists(db, image_id):
        return ImageResult(
            **base, status=ImageStatus.DUPLICATE, error="image_id already processed"
        )

    camera = meta.camera(image_id)
    try:
        inferred = ml_client.infer(
            upload.content, camera, upload.content_type or "image/jpeg"
        )
    except MLInputError as e:
        print(f"[INGEST] image {image_id}: ML refused it: {e.detail}", flush=True)
        return ImageResult(**base, status=ImageStatus.FAILED, error=e.detail)

    print(
        f"[INGEST] image {image_id}: {len(inferred.observations)} observations "
        f"{[(o.type, round(o.score, 2)) for o in inferred.observations]}, "
        f"blurred -> {inferred.blurred_image_path}",
        flush=True,
    )
    _save_image(
        db, work, camera, inferred.blurred_image_path, inferred.observations,
        filename=upload.filename, author=meta.author, license=meta.license,
        captured_at=meta.captured_at,
    )  # fmt: skip
    return _processed(base, inferred.blurred_image_path, inferred.observations)


def _save_image(
    db: Session,
    work: _Work,
    camera: ml.CameraMeta,
    blurred_image_path: str,
    observations: list[ml.Observation],
    *,
    filename: str | None,
    author: str | None,
    license: str | None,
    captured_at: datetime | None,
) -> None:
    work.written.append(media.shared_path(blurred_image_path))
    db.add(
        Image(
            id=camera.image_id,
            source=camera.source,
            geom=point(lat=camera.lat, lon=camera.lon),
            heading=camera.heading,
            fov=camera.fov,
            camera_height_m=camera.camera_height_m,
            sequence_id=camera.sequence_id,
            frame_index=camera.frame_index,
            blurred_image_path=blurred_image_path,
            filename=filename,
            author=author,
            license=license,
            captured_at=captured_at,
        )
    )
    for detection in observations:
        work.pending.add(db, detection, camera)


def _processed(
    base: dict[str, Any], blurred_image_path: str, observations: list[ml.Observation]
) -> ImageResult:
    return ImageResult(
        **base,
        status=ImageStatus.PROCESSED,
        image_url=media.media_url(blurred_image_path),
        observation_count=len(observations),
    )


def _changes(db: Session, dedup: DedupResult) -> dict[str, Any]:
    """elements / removed_element_ids of the response, read back fresh after the commit."""
    elements = element_repo.get_elements(db, [e.id for e in dedup.elements])
    return {
        "elements": [to_element_read(e) for e in elements],
        "removed_element_ids": dedup.removed_ids,
    }
