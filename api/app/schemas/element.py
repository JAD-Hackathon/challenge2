import uuid
from datetime import datetime

from app.models.element import ElementCategory
from pydantic import BaseModel, ConfigDict


class ElementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: ElementCategory
    type: str | None
    confidence: float
    latitude: float
    longitude: float
    image_url: str | None
    attribution: str | None
    created_at: datetime
