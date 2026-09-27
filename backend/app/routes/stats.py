"""
Statistics HTTP routes.

Returns aggregated counts across categories, priorities, and statuses.
"""

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.dependencies import get_complaint_service
from app.schemas.complaint import ComplaintStatsResponse
from app.services.cache_service import cache_service
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/api/stats", tags=["statistics"])


@router.get(
    "",
    response_model=ComplaintStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated complaint statistics",
)
async def get_stats(
    response: Response,
    service: ComplaintService = Depends(get_complaint_service),
    redis: Redis = Depends(get_redis),
) -> ComplaintStatsResponse:
    """
    Return aggregated count totals across complaints.

    Implements read-through caching in Redis with a 30-second TTL.
    Exposes X-Cache: HIT or X-Cache: MISS header on the HTTP response.
    """
    cached = await cache_service.get_cached_stats(redis)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    # Cache MISS: calculate fresh statistics from repository
    response.headers["X-Cache"] = "MISS"
    data = await service.get_stats()
    stats = ComplaintStatsResponse(
        total=data["total"],
        by_status=data["by_status"],
        by_category=data["by_category"],
        by_priority=data["by_priority"],
    )
    await cache_service.set_cached_stats(redis, stats)
    return stats
