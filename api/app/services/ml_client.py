"""HTTP client for the ML service (POST /infer, POST /dedup, POST /infer-video)."""

import json
from pathlib import Path

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.ml import (
    CameraMeta,
    DedupRequest,
    DedupResponse,
    InferResponse,
    InferVideoResponse,
)
from app.schemas.video import UploadedVideo
from app.services import media


class MLServiceError(AppError):
    """ML is down or broken (unreachable, 5xx): the whole operation fails."""

    status_code = 502


class MLInputError(MLServiceError):
    """ML refused this input (4xx: invalid_meta, unsupported_image): only this item fails."""

    status_code = 422


class MLNotImplementedError(MLServiceError):
    """ML doesn't do this yet (404 = no such endpoint, 501 = not_implemented)."""

    status_code = 501


def _client(timeout: float) -> httpx.Client:
    return httpx.Client(base_url=settings.ML_SERVICE_URL, timeout=timeout)


def _raise_for_error(response: httpx.Response, path: str = "") -> None:
    if response.is_success:
        return
    if response.status_code == 404:
        raise MLNotImplementedError(f"ML service has no {path} endpoint yet")
    try:  # ML errors look like {"error": {"code": ..., "message": ...}}
        error = response.json()["error"]
        detail = f"ML {error['code']}: {error['message']}"
    except (ValueError, KeyError, TypeError):
        detail = f"ML service returned HTTP {response.status_code}"
    if response.status_code == 501:
        raise MLNotImplementedError(detail)
    raise (MLInputError if response.is_client_error else MLServiceError)(detail)


def _print_response(path: str, response: httpx.Response) -> None:
    """DEBUG: show exactly what ML returned (status + body, pretty-printed if JSON)."""
    print(f"\n[ML] POST {path} -> HTTP {response.status_code}", flush=True)
    try:
        body = json.dumps(response.json(), indent=2, ensure_ascii=False)
    except ValueError:
        body = response.text
    print(f"[ML] response body:\n{body}", flush=True)


def _post(path: str, timeout: float | None = None, **kwargs) -> httpx.Response:
    try:
        with _client(timeout or settings.ML_TIMEOUT_S) as client:
            response = client.post(path, **kwargs)
    except httpx.HTTPError as e:
        print(f"\n[ML] POST {path} -> unreachable: {e!r}", flush=True)
        raise MLServiceError(f"ML service unreachable: {e}") from e
    _print_response(path, response)
    _raise_for_error(response, path)
    return response


def _parse[M: BaseModel](model: type[M], response: httpx.Response) -> M:
    try:
        return model.model_validate_json(response.content)
    except ValidationError as e:  # e.g. an id that isn't a UUID
        print(f"[ML] response does not match {model.__name__}:\n{e}", flush=True)
        raise MLServiceError(
            f"ML response breaks the contract: {e.errors()[0]['msg']}"
        ) from e


def infer(
    image: bytes, meta: CameraMeta, content_type: str = "image/jpeg"
) -> InferResponse:
    print(
        f"\n[ML] /infer request: image_id={meta.image_id} lat={meta.lat} lon={meta.lon} "
        f"heading={meta.heading} ({len(image)} bytes, {content_type})",
        flush=True,
    )
    response = _post(
        "/infer",
        files={"image": (f"{meta.image_id}.jpg", image, content_type)},
        data={"meta": meta.model_dump_json()},
    )
    return _parse(InferResponse, response)


def dedup(request: DedupRequest) -> DedupResponse:
    print(
        f"\n[ML] /dedup request: {len(request.observations)} observations, "
        f"{len(request.images)} images, {len(request.existing_elements)} existing elements",
        flush=True,
    )
    response = _post("/dedup", json=request.model_dump(mode="json"))
    return _parse(DedupResponse, response)


def infer_video(video: UploadedVideo, sequence_id: str) -> InferVideoResponse:
    """ML picks the frames and places them (GPX track > GPS in the video > meta.route), then
    blurs + detects each one.

    Proposed endpoint, see "Video" in api/README.md. The video is streamed, not loaded in memory.
    """
    files = {
        "video": (
            video.filename or "video.mp4",
            video.file,
            video.content_type or "application/octet-stream",
        )
    }
    if video.track is not None:
        files["track"] = ("track.gpx", video.track, "application/gpx+xml")
    print(
        f"\n[ML] /infer-video request: sequence_id={sequence_id} file={video.filename!r} "
        f"track={'yes' if video.track is not None else 'no'}",
        flush=True,
    )
    response = _post(
        "/infer-video",
        timeout=settings.ML_VIDEO_TIMEOUT_S,
        files=files,
        data={"meta": video.meta.for_ml(sequence_id).model_dump_json()},
    )
    return _parse(InferVideoResponse, response)


def blurred_image_file(result: InferResponse) -> Path:
    """Absolute path of the blurred image ML wrote to the shared folder."""
    return media.shared_path(result.blurred_image_path)
