"""GeoJSON / CSV export of any spatial table (queries live in repositories/spatial.py)."""

import csv
import io
import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidInputError, NotFoundError
from app.repositories import spatial as spatial_repo
from app.repositories.spatial import BBox, SpatialTable


def parse_bbox(bbox: str | None) -> BBox | None:
    """'min_lon,min_lat,max_lon,max_lat', longitude first: the GeoJSON order, and what
    Leaflet's map.getBounds().toBBoxString() returns. 422 if it isn't a valid WGS84 box."""
    if bbox is None:
        return None
    try:
        box: BBox | None = BBox(*(float(v) for v in bbox.split(",")))
    except (TypeError, ValueError):  # not 4 values / not numbers
        box = None
    if (
        box is None
        or not -180 <= box.min_lon < box.max_lon <= 180
        or not -90 <= box.min_lat < box.max_lat <= 90
    ):
        raise InvalidInputError(
            "bbox must be 'min_lon,min_lat,max_lon,max_lat' (longitude first), "
            "e.g. -8.66,40.62,-8.63,40.65 for central Aveiro"
        )
    return box


def _resolve(db: Session, table: str, schema: str) -> SpatialTable:
    t = spatial_repo.get_spatial_table(db, table, schema)
    if t is None:
        raise NotFoundError(f"No spatial table '{schema}.{table}'")
    return t


def export_filename(table: str, ext: str) -> str:
    return f"{table}_{date.today().isoformat()}.{ext}"


def export_geojson(
    db: Session, table: str, schema: str = "public", bbox: str | None = None
) -> tuple[str, str]:
    """Returns (filename, geojson body)."""
    box = parse_bbox(bbox)
    t = _resolve(db, table, schema)
    return export_filename(table, "geojson"), spatial_repo.fetch_geojson(db, t, box)


def export_csv(
    db: Session, table: str, schema: str = "public", bbox: str | None = None
) -> tuple[str, Iterator[str]]:
    """Returns (filename, CSV chunks). Rows are fetched before streaming starts."""
    box = parse_bbox(bbox)
    t = _resolve(db, table, schema)
    columns, rows = spatial_repo.fetch_rows(db, t, box)
    return export_filename(table, "csv"), write_csv(columns, rows)


def _cell(value: object) -> object:
    # JSON columns (e.g. attributes) and arrays (bbox_xyxy) as JSON, not Python repr
    return (
        json.dumps(value, ensure_ascii=False)
        if isinstance(value, dict | list)
        else value
    )


def write_csv(
    columns: list[str], rows: Sequence[Mapping[str, object]]
) -> Iterator[str]:
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
        writer.writerow([_cell(row[c]) for c in columns])
        yield flush()
