import uuid

from app.api.v1.endpoints import elements as real
from app.api.v1.endpoints.elements import StatusQuery
from app.mocks.endpoints import mirrors
from app.mocks.services import elements as service
from app.models.element import ElementCategory
from app.schemas.element import ElementRead, ElementUpdate
from fastapi import APIRouter

router = APIRouter(prefix="/elements", tags=["elements"])


@router.get("", response_model=list[ElementRead])
@mirrors(real.list_elements)
def list_elements(category: ElementCategory | None = None, status: StatusQuery = None):
    return service.list_elements(category, status)


@router.get("/{element_id}", response_model=ElementRead)
@mirrors(real.get_element)
def get_element(element_id: uuid.UUID):
    return service.get_element(element_id)


@router.patch("/{element_id}", response_model=ElementRead)
@mirrors(real.update_element)
def update_element(element_id: uuid.UUID, changes: ElementUpdate):
    return service.update_element(element_id, changes)


@router.post("/{element_id}/verify", response_model=ElementRead)
@mirrors(real.verify_element)
def verify_element(element_id: uuid.UUID):
    return service.verify_element(element_id)


@router.post("/{element_id}/false-positive", response_model=ElementRead)
@mirrors(real.flag_false_positive)
def flag_false_positive(element_id: uuid.UUID):
    return service.flag_false_positive(element_id)
