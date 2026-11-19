from typing import NamedTuple

from geoalchemy2 import WKTElement
from sqlalchemy import Engine, text

from app.database.base import Base

# Coordinate order: our code always names lat and lon, so they can't be swapped by position.
# The lon-first formats (WKT, GeoJSON, ST_MakeEnvelope, the export `bbox`) are only ever
# built in one place each: point() below, repositories/spatial.py and repositories/element.py.


class LatLon(NamedTuple):
    """A WGS84 position. Build it with keywords: LatLon(lat=40.64, lon=-8.65)."""

    lat: float
    lon: float


def point(*, lat: float, lon: float) -> WKTElement:
    """Value for a POINT(4326) column. Keyword-only because WKT order is lon, lat."""
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
