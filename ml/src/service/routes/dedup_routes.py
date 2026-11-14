from fastapi import APIRouter, status
from src.service.mock import mock_dedup
from src.service.schemas import DedupRequest, DedupResponse
from src.service.exceptions import APIError
from src.config import get_settings

router = APIRouter()


@router.post("/dedup", response_model=DedupResponse)
def dedup(request: DedupRequest):
    if get_settings().service.mock:
        return mock_dedup(request)

    raise APIError(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        code="not_implemented",
        message="real pipeline is not implemented yet (set mock: true)",
    )
