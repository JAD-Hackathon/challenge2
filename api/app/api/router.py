from fastapi import FastAPI

ROUTERS = []

def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)