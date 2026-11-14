import uuid
from collections.abc import Sequence

from app.models.element import Element, ElementCategory
from sqlalchemy import select
from sqlalchemy.orm import Session


def list_elements(db: Session, category: ElementCategory | None = None) -> Sequence[Element]:
    stmt = select(Element).order_by(Element.created_at)
    if category:
        stmt = stmt.where(Element.category == category)
    return db.scalars(stmt).all()


def get_element(db: Session, element_id: uuid.UUID) -> Element | None:
    return db.get(Element, element_id)
