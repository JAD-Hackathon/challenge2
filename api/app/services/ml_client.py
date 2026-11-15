"""HTTP client for the ML service (POST /infer, POST /dedup)."""

from pathlib import Path

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.ml import CameraMeta, DedupRequest, DedupResponse, InferResponse


class MLServiceError(AppError):
    status_code = 502


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.ML_SERVICE_URL, timeout=settings.ML_TIMEOUT_S)


def _raise_for_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:  # ML errors look like {"error": {"code": ..., "message": ...}}
        error = response.json()["error"]
        detail = f"ML {error['code']}: {error['message']}"
    except (ValueError, KeyError, TypeError):
        detail = f"ML service returned HTTP {response.status_code}"
    raise MLServiceError(detail)


def _post(path: str, **kwargs) -> httpx.Response:
    try:
        with _client() as client:
            response = client.post(path, **kwargs)
    except httpx.HTTPError as e:
        raise MLServiceError(f"ML service unreachable: {e}") from e
    _raise_for_error(response)
    return response


def infer(image: bytes, meta: CameraMeta, content_type: str = "image/jpeg") -> InferResponse:
    response = _post(
        "/infer",
        files={"image": (f"{meta.image_id}.jpg", image, content_type)},
        data={"meta": meta.model_dump_json()},
    )
    return InferResponse.model_validate_json(response.content)


def dedup(request: DedupRequest) -> DedupResponse:
    response = _post("/dedup", json=request.model_dump(mode="json"))
    return DedupResponse.model_validate_json(response.content)


def blurred_image_file(result: InferResponse) -> Path:
    """Absolute path of the blurred image ML wrote to the shared folder."""
    return Path(settings.SHARED_DIR).resolve() / result.blurred_image_path
