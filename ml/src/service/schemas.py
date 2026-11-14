from typing import Literal
from pydantic import BaseModel, Field


class CameraMeta(BaseModel):
    image_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")  # used as a file name
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    heading: float = Field(ge=0, lt=360)
    fov: float | None = None
    camera_height_m: float | None = None
    source: Literal["mapillary", "kartaview", "video"] | None = None
    sequence_id: str | None = None
    frame_index: int | None = None


class Observation(BaseModel):
    observation_id: str
    type: str  # e.g. "sign.stop"
    score: float = Field(ge=0, le=1)
    bbox_xyxy: list[int] = Field(min_length=4, max_length=4)
    bearing_deg: float | None = None
    est_lat: float | None = None
    est_lon: float | None = None
    uncertainty_m: float | None = None


class InferResponse(BaseModel):
    image_id: str
    blurred_image_path: str
    observations: list[Observation]


class Element(BaseModel):
    element_id: str
    type: str
    lat: float
    lon: float
    confidence: float = Field(ge=0, le=1)
    observation_ids: list[str]
    best_observation_id: str
    status: Literal["auto", "verified", "corrected", "rejected"] = "auto"


class DedupRequest(BaseModel):
    observations: list[Observation]
    images: list[CameraMeta]  # only image_id, lat, lon, heading are used
    existing_elements: list[Element] = []


class DedupResponse(BaseModel):
    elements: list[Element]
    unassigned_observation_ids: list[str] = []
    removed_element_ids: list[str] = []
