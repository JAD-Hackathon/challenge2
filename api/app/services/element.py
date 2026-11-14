import uuid
from collections.abc import Sequence

from app.core.exceptions import NotFoundError
from app.models.element import Element, ElementCategory
from app.repositories import element as element_repo
from sqlalchemy.orm import Session


def list_elements(db: Session, category: ElementCategory | None = None) -> Sequence[Element]:
    return element_repo.list_elements(db, category)


def get_element(db: Session, element_id: uuid.UUID) -> Element:
    element = element_repo.get_element(db, element_id)
    if element is None:
        raise NotFoundError("Element not found")
    return element
