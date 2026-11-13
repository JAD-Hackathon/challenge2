"""Generic GeoJSON / CSV export of any spatial table registered in PostGIS.

Tables are discovered through PostGIS's `geometry_columns` view, so any model with a
geometry column becomes exportable without touching this module. Output coordinates
are always WGS84 (EPSG:4326).
"""

import csv
import io
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


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
    for t in list_spatial_tables(db):
        if t.table == table and t.schema == schema:
            return t
    return None


def _q(db: Session, ident: str) -> str:
    return db.get_bind().dialect.identifier_preparer.quote(ident)


def _from_where(
    db: Session, t: SpatialTable, bbox: BBox | None
) -> tuple[str, dict[str, Any]]:
    # Identifiers come from geometry_columns (validated), and are quoted anyway
    sql = f"FROM {_q(db, t.schema)}.{_q(db, t.table)} AS t"
    params: dict[str, Any] = {}
    if bbox:
        sql += (
            f" WHERE ST_Intersects(t.{_q(db, t.geom_column)},"
            f" ST_Transform(ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326),"
            f" ST_SRID(t.{_q(db, t.geom_column)})))"
        )
        params = dict(zip(("minx", "miny", "maxx", "maxy"), bbox, strict=True))
    return sql, params


def export_geojson(db: Session, t: SpatialTable, bbox: BBox | None = None) -> str:
    """FeatureCollection built entirely by PostGIS; non-geometry columns become properties."""
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


def iter_csv(db: Session, t: SpatialTable, bbox: BBox | None = None) -> Iterator[str]:
    """CSV with every non-geometry column plus latitude/longitude (and WKT for non-points)."""
    geom = _q(db, t.geom_column)
    from_where, params = _from_where(db, t, bbox)
    is_point = t.geometry_type.upper() == "POINT"
    if is_point:
        extra = f"ST_Y(ST_Transform(t.{geom}, 4326)) AS latitude, ST_X(ST_Transform(t.{geom}, 4326)) AS longitude"
    else:
        extra = (
            f"ST_Y(ST_Transform(ST_PointOnSurface(t.{geom}), 4326)) AS latitude, "
            f"ST_X(ST_Transform(ST_PointOnSurface(t.{geom}), 4326)) AS longitude, "
            f"ST_AsText(ST_Transform(t.{geom}, 4326)) AS wkt"
        )
    result = db.execute(text(f"SELECT t.*, {extra} {from_where}"), params)
    columns = [c for c in result.keys() if c != t.geom_column]
    rows = (
        result.mappings().all()
    )  # fetch now so the DB session can close before streaming
    return _write_csv(columns, rows)


def _write_csv(columns: list[str], rows) -> Iterator[str]:
    buf = io.StringIO()
    writer = csv.writer(buf)

    def flush() -> str:
        out = buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        return out

    buf.write("﻿")  # BOM so Excel reads accents correctly
    writer.writerow(columns)
    yield flush()
    for row in rows:
        writer.writerow([row[c] for c in columns])
        yield flush()
