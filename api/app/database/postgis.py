from app.database.base import Base
from geoalchemy2 import WKTElement
from sqlalchemy import Engine, text


def point(lat: float, lon: float) -> WKTElement:
    """Value for a POINT(4326) column. WKT order is lon, lat."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def enable_postgis(engine: Engine) -> None:
    """Make sure the PostGIS extension exists in the target database (idempotent)."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


def create_tables(engine: Engine) -> None:
    """Create any missing tables for the models in app/models.

    Only creates tables that don't exist yet — it never alters existing ones.
    After changing a model, drop the table (or `docker compose down -v`) and restart.
    """
    import app.models  # noqa: F401  — registers every model on Base.metadata

    Base.metadata.create_all(engine)
