import uuid

from app.core.exceptions import NotFoundError
from app.database.postgis import point
from app.models.element import Element, ElementCategory, ElementStatus, status_after_verify
from app.repositories import element as element_repo
from app.schemas.element import ElementRead, ElementUpdate
from app.schemas.image import attribution
from app.services import media
from sqlalchemy.orm import Session


def to_element_read(element: Element) -> ElementRead:
    best = element.best_observation
    image = best.image if best else None
    return ElementRead(
        id=element.id,
        name=element.name,
        category=element.category,
        type=element.type,
        attributes=element.attributes or {},
        status=element.status,
        confidence=element.confidence,
        latitude=element.latitude,
        longitude=element.longitude,
        image_id=image.id if image else None,
        image_url=media.media_url(image.blurred_image_path) if image else None,
        bbox_xyxy=best.bbox_xyxy if best else None,
        attribution=attribution(image.author, image.license, image.source) if image else None,
        observation_count=len(element.observations),
        created_at=element.created_at,
        updated_at=element.updated_at,
    )


def list_elements(
    db: Session, category: ElementCategory | None = None, status: ElementStatus | None = None
) -> list[ElementRead]:
    return [to_element_read(e) for e in element_repo.list_elements(db, category, status)]


def get_element(db: Session, element_id: uuid.UUID) -> ElementRead:
    return to_element_read(_get(db, element_id))


def _get(db: Session, element_id: uuid.UUID) -> Element:
    element = element_repo.get_element(db, element_id)
    if element is None:
        raise NotFoundError("Element not found")
    return element


def flag_false_positive(db: Session, element_id: uuid.UUID) -> ElementRead:
    """A technician saw the element isn't really there: mark it 'rejected'. Flagging twice is fine.

    Rejected elements are kept (hidden from the default list) and sent to ML /dedup with their
    status, so new images of the same spot don't create them again.
    """
    element = _get(db, element_id)
    if element.status is not ElementStatus.REJECTED:
        element.status = ElementStatus.REJECTED
        db.commit()
    return to_element_read(element)


def update_element(db: Session, element_id: uuid.UUID, changes: ElementUpdate) -> ElementRead:
    """A technician fixes the type, attributes (e.g. the speed limit) or position."""
    element = _get(db, element_id)
    element.category, element.type, element.name, element.attributes = changes.classify(
        element.category, element.type, element.attributes or {}
    )
    if changes.latitude is not None and changes.longitude is not None:
        element.geom = point(changes.latitude, changes.longitude)
    element.status = ElementStatus.CORRECTED
    db.commit()
    return to_element_read(element)


def verify_element(db: Session, element_id: uuid.UUID) -> ElementRead:
    """A technician confirms the element is right (also undoes a false-positive flag)."""
    element = _get(db, element_id)
    status = status_after_verify(element.status)
    if element.status is not status:
        element.status = status
        db.commit()
    return to_element_read(element)
