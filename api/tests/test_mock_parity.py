"""The mock routes must expose exactly what the real ones do, or the web tests the wrong thing."""

from app.api.v1.router import router as real_v1
from app.mocks.router import router as mock_v1
from fastapi import APIRouter, FastAPI


def _openapi(router: APIRouter) -> dict:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app.openapi()


def test_mock_openapi_matches_real():
    real, mock = _openapi(real_v1), _openapi(mock_v1)
    assert mock["paths"].keys() == real["paths"].keys()
    for path in real["paths"]:
        assert mock["paths"][path] == real["paths"][path], path
    assert mock["components"] == real["components"]
