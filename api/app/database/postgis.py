from app.database.base import Base
from sqlalchemy import Engine, text


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
