from datetime import date
from typing import Annotated

from app.api.deps import SessionDep
from app.services import export as export_service
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/export", tags=["export"])


def _parse_bbox(bbox: str | None) -> export_service.BBox | None:
    if bbox is None:
        return None
    try:
        parts = tuple(float(v) for v in bbox.split(","))
    except ValueError:
        parts = ()
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise HTTPException(422, "bbox must be 'min_lon,min_lat,max_lon,max_lat'")
    return parts  # type: ignore[return-value]


def _resolve(db: SessionDep, table: str, schema: str) -> export_service.SpatialTable:
    t = export_service.get_spatial_table(db, table, schema)
    if t is None:
        raise HTTPException(404, f"No spatial table '{schema}.{table}'")
    return t


BBoxQuery = Annotated[
    str | None,
    Query(
        description="Filter by WGS84 bounding box: min_lon,min_lat,max_lon,max_lat",
        examples=["-8.66,40.62,-8.63,40.65"],
    ),
]
SchemaQuery = Annotated[str, Query()]


@router.get("/layers")
def list_layers(db: SessionDep):
    """Tables that can be exported (every table with a PostGIS geometry column)."""
    return [
        {
            "schema": t.schema,
            "table": t.table,
            "geometry_column": t.geom_column,
            "geometry_type": t.geometry_type,
            "srid": t.srid,
        }
        for t in export_service.list_spatial_tables(db)
    ]


@router.get("/{table}.geojson")
def export_geojson(
    db: SessionDep, table: str, bbox: BBoxQuery = None, schema: SchemaQuery = "public"
):
    t = _resolve(db, table, schema)
    body = export_service.export_geojson(db, t, _parse_bbox(bbox))
    filename = f"{table}_{date.today().isoformat()}.geojson"
    return Response(
        content=body,
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{table}.csv")
def export_csv(
    db: SessionDep, table: str, bbox: BBoxQuery = None, schema: SchemaQuery = "public"
):
    t = _resolve(db, table, schema)
    filename = f"{table}_{date.today().isoformat()}.csv"
    return StreamingResponse(
        export_service.iter_csv(db, t, _parse_bbox(bbox)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
