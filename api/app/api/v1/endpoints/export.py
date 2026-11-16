from typing import Annotated

from app.api.deps import SessionDep
from app.services import export as export_service
from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/export", tags=["export"])

BBoxQuery = Annotated[
    str | None,
    Query(
        description="Filter by WGS84 bounding box: min_lon,min_lat,max_lon,max_lat",
        examples=["-8.66,40.62,-8.63,40.65"],
    ),
]
SchemaQuery = Annotated[str, Query()]


def attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


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
        for t in export_service.list_layers(db)
    ]


@router.get("/{table}.geojson")
def export_geojson(
    db: SessionDep, table: str, bbox: BBoxQuery = None, schema: SchemaQuery = "public"
):
    filename, body = export_service.export_geojson(db, table, schema, bbox)
    return Response(content=body, media_type="application/geo+json", headers=attachment(filename))


@router.get("/{table}.csv")
def export_csv(db: SessionDep, table: str, bbox: BBoxQuery = None, schema: SchemaQuery = "public"):
    filename, chunks = export_service.export_csv(db, table, schema, bbox)
    return StreamingResponse(
        chunks, media_type="text/csv; charset=utf-8", headers=attachment(filename)
    )
