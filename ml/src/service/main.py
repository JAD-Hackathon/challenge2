from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.config import get_settings
from src.service.exceptions import APIError
from src.service.routes import routers


app = FastAPI(title="Ctrl+F Aveiro ML service")
for router in routers:
    app.include_router(router)


@app.exception_handler(APIError)
async def error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
def health():
    return {"status": "ok", "mock": get_settings().service.mock}
