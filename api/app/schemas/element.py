import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.core import taxonomy
from app.core.exceptions import InvalidInputError
from app.models.element import ElementCategory, ElementStatus

# Key/value facts about an element, e.g. {"limit": 30} for a speed_limit sign
Attributes = dict[str, Any]


class ElementRead(BaseModel):
    id: uuid.UUID
    name: str = Field(examples=["Limite de velocidade"])
    category: ElementCategory
    type: str | None = Field(examples=["speed_limit"])
    attributes: Attributes = Field(
        default_factory=dict,
        description="Extra facts by type, e.g. {'limit': 30} for sign/speed_limit. "
        "A key can be missing while ML can't read it yet (speed limit value: phase 2).",
        examples=[{"limit": 30}],
    )
    status: ElementStatus
    confidence: float
    latitude: float
    longitude: float
    image_id: str | None = Field(
        None, description="Image with the best view of the element"
    )
    image_url: str | None = Field(
        None, description="Blurred image (faces and plates hidden)"
    )
    bbox_xyxy: list[int] | None = Field(
        None,
        description="[x1, y1, x2, y2] px of the element in image_url: crop it to show it",
    )
    attribution: str | None = Field(None, examples=["© jsmith, CC BY-SA 4.0"])
    observation_count: int = Field(
        0, description="Detections (views) merged into this element"
    )
    created_at: datetime
    updated_at: datetime


class ElementUpdate(BaseModel):
    """A technician's correction. Only the fields sent change; the element becomes 'corrected'."""

    category: ElementCategory | None = None
    type: str | None = Field(None, examples=["speed_limit"])
    attributes: Attributes | None = Field(
        None,
        description="Replaces all attributes. Left out: kept, or cleared if the type changes",
        examples=[{"limit": 50}],
    )
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be sent together")
        if all(getattr(self, f) is None for f in type(self).model_fields):
            raise ValueError("nothing to change")
        return self

    def classify(
        self, category: ElementCategory, type_: str | None, attributes: Attributes
    ) -> tuple[ElementCategory, str, str, Attributes]:
        """(category, type, name, attributes) after the change. 422 if the class doesn't exist."""
        new_category, new_type = self.category or category, self.type or type_
        name = taxonomy.class_name(new_category, new_type)
        if name not in taxonomy.LABELS:
            raise InvalidInputError(
                f"Unknown type '{name}'. Use one of: {', '.join(taxonomy.CLASS_NAMES)}"
            )
        if self.attributes is not None:
            attributes = self.attributes
        elif (new_category, new_type) != (category, type_):
            attributes = {}  # they described the old type
        return new_category, new_type, taxonomy.label(name), attributes
