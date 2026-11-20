"""Mirror of the ML service contract (ml/docs/data_contract.md). Keep in sync with ml/src/service/schemas.py.

IDs: image_id is chosen by the API (ML only uses it as a file name). observation_id and
element_id are created by ML. observation_id is any string, stored as it is (ML sends
"<image_id>:<hex>"). element_id is any string too (ML sends "el_<hex>" for new elements), but
the catalogue keys elements by UUID: see ElementId.
"""

import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field

Source = Literal["mapillary", "kartaview", "video"]


def _element_uuid(value: Any) -> Any:
    """A UUID stays as it is (elements the API sent come back with its own ids). Any other
    string is mapped to a fixed UUID, so the same ML id always means the same element."""
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_URL, f"ml-element:{value}")
    return value


ElementId = Annotated[uuid.UUID, BeforeValidator(_element_uuid)]


class CameraMeta(BaseModel):
    image_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")  # ML uses it as a file name
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    heading: float = Field(ge=0, lt=360)
    fov: float | None = Field(None, gt=0, lt=180)
    camera_height_m: float | None = None  # never available from Mapillary/KartaView
    source: Source | None = None
    sequence_id: str | None = None
    frame_index: int | None = Field(None, ge=0)


class Observation(BaseModel):
    observation_id: str
    type: str  # e.g. "sign.stop"
    score: float = Field(ge=0, le=1)
    bbox_xyxy: list[int] = Field(min_length=4, max_length=4)
    bearing_deg: float | None = None
    est_lat: float | None = None
    est_lon: float | None = None
    uncertainty_m: float | None = None
    # Optional extra in the contract, e.g. {"limit": 50} for sign.speed_limit (phase 2)
    attributes: dict[str, Any] | None = None


class InferResponse(BaseModel):
    image_id: str
    blurred_image_path: str  # relative to SHARED_DIR
    observations: list[Observation]


class MLElement(BaseModel):
    element_id: ElementId
    type: str
    lat: float
    lon: float
    confidence: float = Field(ge=0, le=1)
    observation_ids: list[str]
    best_observation_id: str
    status: Literal["auto", "verified", "corrected", "rejected"] = "auto"
    attributes: dict[str, Any] | None = (
        None  # optional extra, see Observation.attributes
    )


class DedupRequest(BaseModel):
    observations: list[Observation]
    images: list[CameraMeta]
    existing_elements: list[MLElement] = []


class DedupResponse(BaseModel):
    elements: list[MLElement]
    unassigned_observation_ids: list[str] = []
    removed_element_ids: list[ElementId] = []

