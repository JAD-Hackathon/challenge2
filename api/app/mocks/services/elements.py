"""Mock of app/services/element.py."""

import uuid

from app.mocks.store import now, store
from app.models.element import ElementCategory, ElementStatus, status_after_verify
from app.schemas.element import ElementRead, ElementUpdate


def list_elements(
    category: ElementCategory | None = None, status: ElementStatus | None = None
) -> list[ElementRead]:
    return store.list_elements(category, status)


def get_element(element_id: uuid.UUID) -> ElementRead:
    return store.get_element(element_id)


def flag_false_positive(element_id: uuid.UUID) -> ElementRead:
    with store.lock:
        element = store.get_element(element_id)
        if element.status is not ElementStatus.REJECTED:
            element = element.model_copy(
                update={"status": ElementStatus.REJECTED, "updated_at": now()}
            )
            store.save_element(element)
        return element


def update_element(element_id: uuid.UUID, changes: ElementUpdate) -> ElementRead:
    with store.lock:
        element = store.get_element(element_id)
        category, type_, name, attributes = changes.classify(
            element.category, element.type, element.attributes
        )
        update = {
            "category": category,
            "type": type_,
            "name": name,
            "attributes": attributes,
            "status": ElementStatus.CORRECTED,
            "updated_at": now(),
        }
        if changes.latitude is not None and changes.longitude is not None:
            update |= {"latitude": changes.latitude, "longitude": changes.longitude}
        element = element.model_copy(update=update)
        store.save_element(element)
        return element


def verify_element(element_id: uuid.UUID) -> ElementRead:
    with store.lock:
        element = store.get_element(element_id)
        status = status_after_verify(element.status)
        if element.status is not status:
            element = element.model_copy(update={"status": status, "updated_at": now()})
            store.save_element(element)
        return element
