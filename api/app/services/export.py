"""GeoJSON / CSV export of any spatial table (queries live in repositories/spatial.py)."""

import csv
import io
from collections.abc import Iterator, Sequence
from datetime import date

from app.core.exceptions import InvalidInputError, NotFoundError
from app.repositories import spatial as spatial_repo
from app.repositories.spatial import BBox, SpatialTable
from sqlalchemy import RowMapping
from sqlalchemy.orm import Session


def parse_bbox(bbox: str | None) -> BBox | None:
    if bbox is None:
        return None
    try:
        parts = tuple(float(v) for v in bbox.split(","))
    except ValueError:
        parts = ()
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise InvalidInputError("bbox must be 'min_lon,min_lat,max_lon,max_lat'")
    return parts  # type: ignore[return-value]


def list_layers(db: Session) -> list[SpatialTable]:
    return spatial_repo.list_spatial_tables(db)


def _resolve(db: Session, table: str, schema: str) -> SpatialTable:
    t = spatial_repo.get_spatial_table(db, table, schema)
    if t is None:
        raise NotFoundError(f"No spatial table '{schema}.{table}'")
    return t


def _filename(table: str, ext: str) -> str:
    return f"{table}_{date.today().isoformat()}.{ext}"


def export_geojson(
    db: Session, table: str, schema: str = "public", bbox: str | None = None
) -> tuple[str, str]:
    """Returns (filename, geojson body)."""
    box = parse_bbox(bbox)
    t = _resolve(db, table, schema)
    return _filename(table, "geojson"), spatial_repo.fetch_geojson(db, t, box)


def export_csv(
    db: Session, table: str, schema: str = "public", bbox: str | None = None
) -> tuple[str, Iterator[str]]:
    """Returns (filename, CSV chunks). Rows are fetched before streaming starts."""
    box = parse_bbox(bbox)
    t = _resolve(db, table, schema)
    columns, rows = spatial_repo.fetch_rows(db, t, box)
    return _filename(table, "csv"), _write_csv(columns, rows)


def _write_csv(columns: list[str], rows: Sequence[RowMapping]) -> Iterator[str]:
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
