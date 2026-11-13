from app.api.endpoints import export
from fastapi import FastAPI

ROUTERS = [export.router]


def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)
