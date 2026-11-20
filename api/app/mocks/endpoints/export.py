from app.api.v1.endpoints import export as real
from app.api.v1.endpoints.export import BBoxQuery, SchemaQuery
from app.mocks.endpoints import mirrors
from app.mocks.services import export as service
from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{table}.geojson")
@mirrors(real.export_geojson)
def export_geojson(table: str, bbox: BBoxQuery = None, schema: SchemaQuery = "public"):
    filename, body = service.export_geojson(table, schema, bbox)
    return Response(
        content=body,
        media_type="application/geo+json",
        headers=real.attachment(filename),
    )


@router.get("/{table}.csv")
@mirrors(real.export_csv)
def export_csv(table: str, bbox: BBoxQuery = None, schema: SchemaQuery = "public"):
    filename, chunks = service.export_csv(table, schema, bbox)
    return StreamingResponse(
        chunks, media_type="text/csv; charset=utf-8", headers=real.attachment(filename)
    )
