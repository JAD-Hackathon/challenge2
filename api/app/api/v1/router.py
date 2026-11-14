from app.api.v1.endpoints import elements, export
from fastapi import APIRouter

router = APIRouter(prefix="/v1")
router.include_router(elements.router)
router.include_router(export.router)
