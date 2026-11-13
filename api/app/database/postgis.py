from sqlalchemy import Engine, text


def enable_postgis(engine: Engine) -> None:
    """Make sure the PostGIS extension exists in the target database (idempotent)."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
