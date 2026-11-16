import uuid
from typing import Annotated

from app.api.deps import SessionDep
from app.models.element import ElementCategory, ElementStatus
from app.schemas.element import ElementRead, ElementUpdate
from app.services import element as element_service
from fastapi import APIRouter, Query

router = APIRouter(prefix="/elements", tags=["elements"])

# Shared with app/mocks/endpoints/elements.py so both expose the same parameter
StatusQuery = Annotated[
    ElementStatus | None,
    Query(description="Only elements with this status. Default: all except 'rejected'"),
]


@router.get("", response_model=list[ElementRead])
def list_elements(
    db: SessionDep, category: ElementCategory | None = None, status: StatusQuery = None
):
    return element_service.list_elements(db, category, status)


@router.get("/{element_id}", response_model=ElementRead)
def get_element(db: SessionDep, element_id: uuid.UUID):
    return element_service.get_element(db, element_id)


@router.patch("/{element_id}", response_model=ElementRead)
def update_element(db: SessionDep, element_id: uuid.UUID, changes: ElementUpdate):
    """Correct an element: its type (`category` + `type`), `attributes` (e.g. the speed limit)
    and/or position (`latitude` + `longitude`). Only the fields sent change.

    It becomes `corrected`, which ML never changes. If the type changes and `attributes` isn't
    sent, the old attributes are cleared (they described the old type).
    """
    return element_service.update_element(db, element_id, changes)


@router.post("/{element_id}/verify", response_model=ElementRead)
def verify_element(db: SessionDep, element_id: uuid.UUID):
    """Confirm an element is right: it becomes `verified`, which ML never changes.

    Also undoes a false-positive flag. A `corrected` element stays `corrected` (already checked).
    """
    return element_service.verify_element(db, element_id)


@router.post("/{element_id}/false-positive", response_model=ElementRead)
def flag_false_positive(db: SessionDep, element_id: uuid.UUID):
    """Flag an element as a false positive (a technician checked its image: it isn't there).

    It becomes `rejected`: hidden from the default list (see them with `?status=rejected`) and
    never created again from new images. Flagging an already rejected element changes nothing;
    `verify` undoes it.
    """
    return element_service.flag_false_positive(db, element_id)
