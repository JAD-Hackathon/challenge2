import uuid

from app.api.deps import SessionDep
from app.models.element import ElementCategory
from app.schemas.element import ElementRead
from app.services import element as element_service
from fastapi import APIRouter

router = APIRouter(prefix="/elements", tags=["elements"])


@router.get("", response_model=list[ElementRead])
def list_elements(db: SessionDep, category: ElementCategory | None = None):
    return element_service.list_elements(db, category)


@router.get("/{element_id}", response_model=ElementRead)
def get_element(db: SessionDep, element_id: uuid.UUID):
    return element_service.get_element(db, element_id)
