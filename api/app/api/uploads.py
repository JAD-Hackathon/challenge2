"""Multipart upload forms, shared by the real and mock endpoints.

POST /images  images: file (repeat once per image)
              metas:  JSON array, one per file, each either
                        {"lat": 40.64, "lon": -8.65, "heading": 90, ...}   ImageMeta
                        {"mapillary": {<Mapillary API v4 image record>}}
                        {"kartaview": {<KartaView API v2 photo record>}}
POST /videos  video:  file (streamed to ML, never read into memory)
              track:  GPX file recorded during the video (passed to ML as is)
              meta:   '{"spacing_m": 5, ...}' (optional)
"""

from typing import Annotated, Any

from app.core.config import settings
from app.core.exceptions import InvalidInputError, TooLargeError
from app.schemas.image import ImageMeta, UploadedImage
from app.schemas.video import UploadedVideo, VideoMeta
from app.services import street_view
from fastapi import File, Form, UploadFile
from pydantic import TypeAdapter, ValidationError

ImagesForm = Annotated[
    list[UploadFile],
    File(description="Image files (JPEG/PNG). Repeat the `images` field for each file."),
]
MetasForm = Annotated[
    str,
    Form(
        description="JSON array, one item per file in the same order. Each item is an "
        "ImageMeta (lat, lon, heading required) or a source record: "
        '{"mapillary": {...}} / {"kartaview": {...}} (other keys override the record).',
        examples=[
            '[{"lat": 40.6412, "lon": -8.6538, "heading": 92.5}, '
            '{"mapillary": {"id": "123", "computed_geometry": {"type": "Point", '
            '"coordinates": [-8.6538, 40.6412]}, "computed_compass_angle": 92.5}}]'
        ],
    ),
]

VideoForm = Annotated[
    UploadFile,
    File(description="Video (mp4, mov, ...), up to MAX_VIDEO_MB. Passed to ML, never saved."),
]
TrackForm = Annotated[
    UploadFile,
    File(description="GPS track recorded during the video: GPX with a <time> on each point"),
]
VideoMetaForm = Annotated[
    str,
    Form(
        description="Optional JSON VideoMeta (spacing_m, start_time, time_offset_s, "
        "heading_offset_deg, fov, camera_height_m, author, license)",
        examples=['{"spacing_m": 5, "time_offset_s": 0}'],
    ),
]

_metas = TypeAdapter(list[dict[str, Any]])
SOURCE_RECORDS = {"mapillary": street_view.from_mapillary, "kartaview": street_view.from_kartaview}


def read_batch(images: list[UploadFile], metas: str) -> list[UploadedImage]:
    if len(images) > settings.MAX_BATCH_SIZE:
        raise InvalidInputError(f"At most {settings.MAX_BATCH_SIZE} images per request")
    try:
        items = _metas.validate_json(metas)
    except ValidationError as e:
        raise InvalidInputError(f"metas{_error_text(e)}") from None
    if len(items) != len(images):
        raise InvalidInputError(f"Got {len(images)} images but {len(items)} metas")

    parsed = [_image_meta(i, item) for i, item in enumerate(items)]
    usable = [m for m in parsed if isinstance(m, ImageMeta)]
    street_view.assign_frame_indexes(usable)
    ids = [m.image_id for m in usable if m.image_id]
    if len(ids) != len(set(ids)):
        raise InvalidInputError("metas: the same image_id is used twice")

    return [
        UploadedImage(
            index=i,
            filename=file.filename,
            content_type=file.content_type,
            content=file.file.read(),
            meta=meta if isinstance(meta, ImageMeta) else None,
            error=meta if isinstance(meta, str) else None,
        )
        for i, (file, meta) in enumerate(zip(images, parsed, strict=True))
    ]


def _image_meta(index: int, item: dict[str, Any]) -> ImageMeta | str:
    """ImageMeta, or why a Mapillary/KartaView record can't be used (only that file fails).

    A plain ImageMeta that doesn't validate is a client bug: the whole request gets a 422.
    """
    for source, convert in SOURCE_RECORDS.items():
        if source not in item:
            continue
        try:
            meta = convert(item[source])
            if meta is None:
                return f"{source} image without position / heading, or a 360° panorama"
            overrides = {k: v for k, v in item.items() if k != source}  # e.g. author
            return ImageMeta.model_validate({**meta.model_dump(), **overrides})
        except ValidationError as e:
            return f"{source} record{_error_text(e)}"
        except KeyError as e:
            return f"{source} record: missing {e}"
        except (AttributeError, TypeError, ValueError) as e:
            return f"{source} record: {e}"
    try:
        return ImageMeta.model_validate(item)
    except ValidationError as e:
        raise InvalidInputError(f"metas[{index}]{_error_text(e)}") from None


def read_video(video: UploadFile, track: UploadFile, meta: str) -> UploadedVideo:
    if (video.size or 0) > settings.MAX_VIDEO_MB * 1024 * 1024:
        raise TooLargeError(f"The video is bigger than {settings.MAX_VIDEO_MB} MB")
    try:
        video_meta = VideoMeta.model_validate_json(meta)
    except ValidationError as e:
        raise InvalidInputError(f"meta{_error_text(e)}") from None
    return UploadedVideo(
        file=video.file,
        filename=video.filename,
        content_type=video.content_type,
        track=track.file.read(),
        meta=video_meta,
    )


def _error_text(e: ValidationError) -> str:
    """First error as '[0].heading: Input should be less than 360'."""
    error = e.errors()[0]
    path = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error["loc"])
    return f"{path}: {error['msg']}"
