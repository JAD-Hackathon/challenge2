import enum
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.element import Attributes, ElementRead
from app.schemas.ml import CameraMeta, Source

IMAGE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"  # ML uses it as a file name


def new_image_id() -> str:
    return f"up_{uuid.uuid4().hex}"


PLATFORMS = {"mapillary": "Mapillary", "kartaview": "KartaView"}


def attribution(
    author: str | None, license: str | None, source: str | None = None
) -> str | None:
    """Credit line, e.g. '© jsmith (Mapillary), CC BY-SA 4.0' (required by CC BY-SA)."""
    platform = PLATFORMS.get(source or "")
    credit = f"© {author}" if author else None
    if platform:
        credit = f"{credit} ({platform})" if credit else platform
    return ", ".join(p for p in (credit, license) if p) or None


class ImageMeta(BaseModel):
    """Metadata for one uploaded image (one per file, same order as the files)."""

    image_id: str | None = Field(
        None,
        pattern=IMAGE_ID_PATTERN,
        description="Optional stable id (e.g. 'mly_123'). Generated when missing. "
        "An id that was already processed is skipped as 'duplicate'.",
    )
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    heading: float = Field(
        ge=0, lt=360, description="Camera direction, ° clockwise from north"
    )
    fov: float | None = Field(
        None, gt=0, lt=180, description="Horizontal field of view, °"
    )
    camera_height_m: float | None = Field(None, gt=0)
    source: Source | None = None
    sequence_id: str | None = None
    frame_index: int | None = Field(None, ge=0)
    author: str | None = Field(None, max_length=256)
    license: str | None = Field(None, max_length=64, examples=["CC BY-SA 4.0"])
    captured_at: datetime | None = None

    def camera(self, image_id: str) -> CameraMeta:
        return CameraMeta(
            image_id=image_id,
            **self.model_dump(include=set(CameraMeta.model_fields) - {"image_id"}),
        )


@dataclass(frozen=True)
class UploadedImage:
    """One file of a batch, already read and paired with its metadata."""

    index: int
    filename: str | None
    content_type: str | None
    content: bytes
    meta: (
        ImageMeta | None
    )  # None: its Mapillary/KartaView record can't be used, see error
    error: str | None = None


class ImageStatus(enum.StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"  # image_id already processed: skipped
    FAILED = "failed"  # ML refused it, or its Mapillary/KartaView record isn't usable (error)


class ImageResult(BaseModel):
    index: int = Field(description="Position of the file in the request")
    filename: str | None
    image_id: str | None
    status: ImageStatus
    image_url: str | None = Field(None, description="Blurred image")
    observation_count: int = Field(0, description="Detections found in the image")
    error: str | None = None


class BatchResponse(BaseModel):
    images: list[ImageResult]
    elements: list[ElementRead] = Field(
        description="Elements created or updated by the batch"
    )
    removed_element_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Elements merged into others: remove them from the map",
    )


class ObservationRead(BaseModel):
    id: str
    element_id: uuid.UUID | None
    type: str = Field(examples=["sign.speed_limit"])
    score: float
    bbox_xyxy: list[int]
    attributes: Attributes = Field(default_factory=dict)
    latitude: float | None
    longitude: float | None
    uncertainty_m: float | None


class ImageRead(BaseModel):
    id: str
    source: str | None
    latitude: float
    longitude: float
    heading: float
    fov: float | None
    image_url: str = Field(description="Blurred image")
    filename: str | None
    attribution: str | None
    captured_at: datetime | None
    created_at: datetime
    observations: list[ObservationRead] = Field(
        description="Detections, draw bbox_xyxy on image"
    )
