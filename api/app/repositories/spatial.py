"""Generic PostGIS queries over any table that has a geometry column.

Tables are discovered through PostGIS's `geometry_columns` view, so new models with a
geometry column work here without changes. Coordinates are always returned in WGS84.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session


class BBox(NamedTuple):
    """WGS84 box. Field order = the `bbox` query parameter (lon first, like GeoJSON)."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@dataclass(frozen=True)
class SpatialTable:
    schema: str
    table: str
    geom_column: str
    srid: int
    geometry_type: str


def list_spatial_tables(db: Session) -> list[SpatialTable]:
    rows = db.execute(
        text(
            """
            SELECT f_table_schema, f_table_name, f_geometry_column, srid, type
            FROM geometry_columns
            WHERE f_table_schema NOT IN ('topology', 'tiger')
            ORDER BY f_table_schema, f_table_name
            """
        )
    ).all()
    return [SpatialTable(*r) for r in rows]


def get_spatial_table(
    db: Session, table: str, schema: str = "public"
) -> SpatialTable | None:
    row = db.execute(
        text(
            """
            SELECT f_table_schema, f_table_name, f_geometry_column, srid, type
            FROM geometry_columns
            WHERE f_table_schema = :schema AND f_table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).first()
    return SpatialTable(*row) if row else None


def _q(db: Session, ident: str) -> str:
    return db.get_bind().dialect.identifier_preparer.quote(ident)


def _from_where(
    db: Session, t: SpatialTable, bbox: BBox | None
) -> tuple[str, dict[str, Any]]:
    # Identifiers come from geometry_columns (validated), and are quoted anyway
    geom = _q(db, t.geom_column)
    sql = f"FROM {_q(db, t.schema)}.{_q(db, t.table)} AS t"
    params: dict[str, Any] = {}
    if bbox:
        sql += (
            f" WHERE ST_Intersects(t.{geom},"
            f" ST_Transform(ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326), ST_SRID(t.{geom})))"
        )
        params = {
            "minx": bbox.min_lon,
            "miny": bbox.min_lat,
            "maxx": bbox.max_lon,
            "maxy": bbox.max_lat,
        }
    return sql, params


def fetch_geojson(db: Session, t: SpatialTable, bbox: BBox | None = None) -> str:
    """FeatureCollection built by PostGIS; non-geometry columns become properties."""
    geom = _q(db, t.geom_column)
    from_where, params = _from_where(db, t, bbox)
    sql = f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(json_agg(json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(t.{geom}, 4326), 7)::json,
                'properties', to_jsonb(t) - :geom_col
            )), '[]'::json)
        )::text
        {from_where}
    """
    return db.execute(text(sql), {**params, "geom_col": t.geom_column}).scalar_one()


def fetch_rows(
    db: Session, t: SpatialTable, bbox: BBox | None = None
) -> tuple[list[str], Sequence[RowMapping]]:
    """Every non-geometry column plus latitude/longitude (and WKT for non-point geometries)."""
    geom = _q(db, t.geom_column)
    from_where, params = _from_where(db, t, bbox)
    if t.geometry_type.upper() == "POINT":
        extra = (
            f"ST_Y(ST_Transform(t.{geom}, 4326)) AS latitude, "
            f"ST_X(ST_Transform(t.{geom}, 4326)) AS longitude"
        )
    else:
        extra = (
            f"ST_Y(ST_Transform(ST_PointOnSurface(t.{geom}), 4326)) AS latitude, "
            f"ST_X(ST_Transform(ST_PointOnSurface(t.{geom}), 4326)) AS longitude, "
            f"ST_AsText(ST_Transform(t.{geom}, 4326)) AS wkt"
        )
    result = db.execute(text(f"SELECT t.*, {extra} {from_where}"), params)
    columns = [c for c in result.keys() if c != t.geom_column]  # noqa: SIM118
    return columns, result.mappings().all()
