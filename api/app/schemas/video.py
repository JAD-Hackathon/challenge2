import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO

from pydantic import BaseModel, Field

from app.schemas.image import BatchResponse
from app.schemas.ml import LocationSource, RoutePoint, VideoInferMeta


def new_sequence_id() -> str:
    return f"vid_{uuid.uuid4().hex}"


class VideoMeta(BaseModel):
    """Optional settings for a video upload. Everything has a default."""

    spacing_m: float = Field(
        5.0, ge=1, le=100, description="Keep one frame every N metres"
    )
    start_time: datetime | None = Field(
        None,
        description="UTC time of the first frame, if the video's own clock is wrong",
    )
    time_offset_s: float = Field(
        0,
        description="Seconds added to every frame time, to line the video up with the GPS",
    )
    heading_offset_deg: float = Field(
        0,
        ge=-180,
        le=180,
        description="Camera vs direction of travel: 0 front, 90 right",
    )
    fov: float | None = Field(
        None, gt=0, lt=180, description="Horizontal field of view, °"
    )
    camera_height_m: float | None = Field(None, gt=0)
    route: list[RoutePoint] | None = Field(
        None,
        min_length=2,
        max_length=5000,
        description="Only for a video without GPS (no track file, no GPS stored in the video): "
        "the path the camera followed, start to end, e.g. drawn on a map. ML spreads the frames "
        "along it at constant speed, so positions are approximate",
    )
    author: str | None = Field(None, max_length=256)
    license: str | None = Field(None, max_length=64)

    def for_ml(self, sequence_id: str) -> VideoInferMeta:
        """Everything but the attribution, which the API keeps for itself."""
        return VideoInferMeta(
            sequence_id=sequence_id, **self.model_dump(exclude={"author", "license"})
        )


@dataclass(frozen=True)
class UploadedVideo:
    file: BinaryIO  # streamed to ML: never read into memory, never saved
    filename: str | None
    content_type: str | None
    track: bytes | None  # GPX, passed to ML as is; None: GPS in the video or meta.route
    meta: VideoMeta

    def frame_filename(self, frame_index: int | None) -> str:
        return f"{self.filename or 'video'}#{frame_index}"


class VideoResponse(BatchResponse):
    """images = one result per frame ML kept (image_id = <sequence_id>_<frame_index>)."""

    sequence_id: str
    location_source: LocationSource | None = Field(
        None,
        description="Where the frame positions come from: 'track' (the GPX), 'embedded' "
        "(GPS stored in the video), 'route' (meta.route: approximate positions)",
    )
