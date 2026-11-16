"""Mock of app/api/v1/router.py (and app/api/router.py's VERSIONED_ROUTERS)."""

from app.mocks.endpoints import elements, export, images, videos
from fastapi import APIRouter

router = APIRouter(prefix="/v1")
router.include_router(elements.router)
router.include_router(images.router)
router.include_router(videos.router)
router.include_router(export.router)

VERSIONED_ROUTERS: list[APIRouter] = [router]
