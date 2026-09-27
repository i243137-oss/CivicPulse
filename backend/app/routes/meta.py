"""
Metadata and observability routes.

Surfaces active triage provider, telemetry, latency metrics, and cache hit rate.
"""

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.dependencies import get_triage_service
from app.services.triage_service import TriageService

router = APIRouter(prefix="/api/meta", tags=["metadata"])


class CacheMetrics(BaseModel):
    hits: int = 0
    misses: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0


class ProviderInfoResponse(BaseModel):
    active_provider: str
    cache_metrics: CacheMetrics = CacheMetrics()
    recent_outcomes: list[dict[str, Any]] = []


@router.get(
    "/providers",
    response_model=ProviderInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Active triage provider, cache metrics, and recent outcomes",
)
async def get_providers_meta(
    triage_service: TriageService = Depends(get_triage_service),
    redis: Redis = Depends(get_redis),
) -> ProviderInfoResponse:
    """Return active provider configuration, measured cache hit rate, and triage telemetry."""
    provider = triage_service.primary_provider
    provider_name = getattr(provider, "name", getattr(provider, "provider_id", provider.__class__.__name__))
    recent = triage_service.get_recent_outcomes()
    cache_data = await triage_service.get_cache_metrics(redis)

    return ProviderInfoResponse(
        active_provider=provider_name,
        cache_metrics=CacheMetrics(**cache_data),
        recent_outcomes=recent,
    )
