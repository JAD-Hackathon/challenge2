# Import every model here so Base.metadata knows about it and create_all() creates its table.
from app.models.element import Element, ElementCategory

__all__ = ["Element", "ElementCategory"]
