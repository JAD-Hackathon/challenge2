"""Mock of app/services/export.py: only the 'elements' layer, built from the store."""

import json
from collections.abc import Iterator
from typing import Any

from app.core.exceptions import NotFoundError
from app.mocks.store import store
from app.schemas.element import ElementRead
from app.services.export import export_filename, parse_bbox, write_csv

LAYER = {
    "schema": "public",
    "table": "elements",
    "geometry_column": "geom",
    "geometry_type": "POINT",
    "srid": 4326,
}
# Same columns as the real elements table (geometry left out, like the real export)
COLUMNS = [
    "id", "name", "category", "type", "attributes", "status", "confidence",
    "best_observation_id", "created_at", "updated_at",
]  # fmt: skip


def export_geojson(
    table: str, schema: str = "public", bbox: str | None = None
) -> tuple[str, str]:
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(e.longitude, 7), round(e.latitude, 7)],
            },
            "properties": _properties(e),
        }
        for e in _elements(table, schema, bbox)
    ]
    body = json.dumps(
        {"type": "FeatureCollection", "features": features}, ensure_ascii=False
    )
    return export_filename(table, "geojson"), body


def export_csv(
    table: str, schema: str = "public", bbox: str | None = None
) -> tuple[str, Iterator[str]]:
    rows = [
        {**_properties(e), "latitude": e.latitude, "longitude": e.longitude}
        for e in _elements(table, schema, bbox)
    ]
    return export_filename(table, "csv"), write_csv(
        [*COLUMNS, "latitude", "longitude"], rows
    )


def _elements(table: str, schema: str, bbox: str | None) -> list[ElementRead]:
    box = parse_bbox(bbox)
    if (schema, table) != (LAYER["schema"], LAYER["table"]):
        raise NotFoundError(f"No spatial table '{schema}.{table}'")
    return [
        e
        for e in store.all_elements()  # the real export includes every status too
        if box is None
        or (
            box.min_lon <= e.longitude <= box.max_lon
            and box.min_lat <= e.latitude <= box.max_lat
        )
    ]


def _properties(e: ElementRead) -> dict[str, Any]:
    values = e.model_dump(mode="json")
    best = store.best_observation_id(e.id)
    values["best_observation_id"] = str(best) if best else None
    return {c: values[c] for c in COLUMNS}
