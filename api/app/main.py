from contextlib import asynccontextmanager

from app.api.deps import SessionDep
from app.api.router import register_routers
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.database import engine
from app.database.postgis import create_tables, enable_postgis
from app.services import media
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.API_MOCK:
        from app.mocks import setup_mock_data

        setup_mock_data()  # in-memory catalogue + seed images in SHARED_DIR/images
    else:
        enable_postgis(engine)  # must run before create_tables so Geometry columns work
        create_tables(engine)
    yield


def mount_media(app: FastAPI) -> None:
    """Serve the blurred images in the shared folder: GET /media/images/<image_id>.jpg"""
    images_dir = media.images_dir()
    images_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        f"{media.MEDIA_MOUNT}/{media.IMAGES_SUBDIR}",
        StaticFiles(directory=images_dir),
        name="images",
    )


app = FastAPI(title="Ctrl+F Aveiro API", lifespan=lifespan)
register_exception_handlers(app)
register_routers(app)
mount_media(app)


@app.get("/health")
def health():
    return {"status": "ok", "mock": settings.API_MOCK}


@app.get("/health/db")
def health_db(db: SessionDep):
    if settings.API_MOCK:
        return {"database": "mock", "postgis": None}
    postgis = db.execute(text("SELECT postgis_lib_version()")).scalar_one()
    return {"database": "ok", "postgis": postgis}
