from fastapi import APIRouter, FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import settings

# Add new versions here (e.g. v2_router); older ones keep working side by side
VERSIONED_ROUTERS: list[APIRouter] = [v1_router]


def register_routers(app: FastAPI) -> None:
    for router in VERSIONED_ROUTERS:
        app.include_router(router, prefix=settings.API_PREFIX)
