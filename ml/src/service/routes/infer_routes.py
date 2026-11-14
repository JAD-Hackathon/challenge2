from fastapi import APIRouter, UploadFile, File, Form, status
from pydantic import ValidationError
from src.service.mock import mock_infer
from src.service.schemas import CameraMeta, InferResponse
from src.service.exceptions import APIError
from src.config import get_settings

router = APIRouter()


@router.post("/infer", response_model=InferResponse)
async def infer(
    image: UploadFile = File(..., description="JPEG/PNG image file"),
    meta: str = Form(..., description="JSON string matching CameraMeta schema"),
):
    try:
        camera = CameraMeta.model_validate_json(meta)
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
        return mock_infer(image_bytes, camera)

    raise APIError(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        code="not_implemented",
        message="real pipeline is not implemented yet (set mock: true)",
    )
