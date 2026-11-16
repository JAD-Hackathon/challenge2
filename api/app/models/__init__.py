# Import every model here so Base.metadata knows about it and create_all() creates its table.
from app.models.element import Element, ElementCategory, ElementStatus
from app.models.image import Image
from app.models.observation import Observation

__all__ = ["Element", "ElementCategory", "ElementStatus", "Image", "Observation"]
