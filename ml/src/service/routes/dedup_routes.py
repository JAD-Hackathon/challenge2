from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, status

from src.service.mock import mock_dedup
from src.service.schemas import DedupRequest, DedupResponse
from src.service.exceptions import APIError
from src.dedup.deduplicator import AssetDeduplicator
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def _get_deduplicator() -> AssetDeduplicator:
    """Lazily instantiate the singleton AssetDeduplicator."""
    deduplicator = AssetDeduplicator(get_settings().dedup)
    return deduplicator


@router.post("/dedup", response_model=DedupResponse)
def dedup(request: DedupRequest):
    """Cluster multi-view street observations into deduplicated physical Elements."""
    if get_settings().service.mock:
        return mock_dedup(request)

    try:
        deduplicator = _get_deduplicator()
        return deduplicator.deduplicate(request)
    except APIError:
        raise
    except Exception as e:
        logger.exception("Deduplication failed")
        raise APIError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal",
            message=f"Deduplication failed: {e}",
        ) from e
