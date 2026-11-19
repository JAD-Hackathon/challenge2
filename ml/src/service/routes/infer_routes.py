from __future__ import annotations

import io
import logging
from functools import lru_cache

from fastapi import APIRouter, File, Form, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from src.config import get_settings
from src.pipeline import InferencePipeline
from src.service.exceptions import APIError
from src.service.mock import mock_infer
from src.service.schemas import CameraMeta, InferResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def _get_pipeline() -> InferencePipeline:
    """Lazily instantiate and warm up the singleton InferencePipeline."""
    pipeline = InferencePipeline(settings=get_settings())
    pipeline.warmup()
    return pipeline


def _decode_image(image_bytes: bytes) -> Image.Image:
    """Decode raw uploaded bytes into a PIL Image or raise 415 unsupported_image."""
    if not image_bytes:
        raise APIError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="unsupported_image",
            message="uploaded image file is empty",
        )
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        return img
    except (UnidentifiedImageError, OSError) as e:
        raise APIError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="unsupported_image",
            message="cannot decode image file (expected valid JPEG/PNG/WebP)",
        ) from e


@router.post("/infer", response_model=InferResponse)
async def infer(
    image: UploadFile = File(..., description="JPEG/PNG image file"),
    meta: str = Form(..., description="JSON string matching CameraMeta schema"),
):
    """Run privacy redaction, 2-stage detection, and 3D localization on one image."""
    try:
        meta = CameraMeta.model_validate_json(meta)
    except ValidationError as e:
        error = e.errors()[0]
        field = ".".join(str(part) for part in error["loc"])
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_meta",
            message=f"{field}: {error['msg']}",
        ) from e

    image_bytes = await image.read()

    if get_settings().service.mock:
        return mock_infer(image_bytes, meta)

    pil_image = _decode_image(image_bytes)

    try:
        pipeline = _get_pipeline()
        return await run_in_threadpool(pipeline.run, pil_image, meta)
    except APIError:
        raise
    except Exception as e:
        logger.exception("Inference failed for image_id=%s", meta.image_id)
        raise APIError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal",
            message=f"inference pipeline failed: {e}",
        ) from e
