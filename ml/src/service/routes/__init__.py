from fastapi import APIRouter
from .infer_routes import router as infer_router
from .dedup_routes import router as dedup_router

routers: list[APIRouter] = [infer_router, dedup_router]
