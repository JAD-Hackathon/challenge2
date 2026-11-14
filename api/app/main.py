from contextlib import asynccontextmanager

from app.api.deps import SessionDep
from app.api.router import register_routers
from app.core.exceptions import register_exception_handlers
from app.database import engine
from app.database.postgis import create_tables, enable_postgis
from fastapi import FastAPI
from sqlalchemy import text


@asynccontextmanager
async def lifespan(app: FastAPI):
    enable_postgis(engine)  # must run before create_tables so Geometry columns work
    create_tables(engine)
    yield


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)
register_routers(app)


@app.get("/health/db")
def health_db(db: SessionDep):
    postgis = db.execute(text("SELECT postgis_lib_version()")).scalar_one()
    return {"database": "ok", "postgis": postgis}
