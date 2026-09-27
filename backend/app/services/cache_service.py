"""
Cache service for managing Redis-backed read-through caching and invalidation.

Implements read-through statistics caching with a 30-second TTL and
immediate cache invalidation following complaint creation or status updates.
"""

import logging

from redis.asyncio import Redis

from app.core.config import get_settings
from app.schemas.complaint import ComplaintStatsResponse

logger = logging.getLogger(__name__)

STATS_CACHE_KEY = "civicpulse:stats:summary"


class CacheService:
    """Service handling read-through caching and cache key invalidation."""

    def __init__(self, key_prefix: str = "civicpulse:") -> None:
        self.key_prefix = key_prefix
        self.stats_key = f"{key_prefix}stats:summary"

    async def get_cached_stats(self, redis: Redis) -> ComplaintStatsResponse | None:
        """
        Retrieve cached complaint statistics from Redis if available.

        Returns ComplaintStatsResponse on cache HIT, None on cache MISS or error.
        """
        try:
            raw_data = await redis.get(self.stats_key)
            if raw_data:
                logger.debug("Stats cache HIT for key %s", self.stats_key)
                return ComplaintStatsResponse.model_validate_json(raw_data)
            logger.debug("Stats cache MISS for key %s", self.stats_key)
            return None
        except Exception as exc:
            logger.warning("Failed to retrieve stats from Redis cache: %s", exc)
            return None

    async def set_cached_stats(
        self,
        redis: Redis,
        stats: ComplaintStatsResponse,
        ttl: int | None = None,
    ) -> None:
        """
        Store computed complaint statistics into Redis with explicit TTL.

        Defaults to 30-second TTL as required by the specification.
        """
        settings = get_settings()
        cache_ttl = ttl if ttl is not None else settings.REDIS_STATS_CACHE_TTL
        try:
            serialized = stats.model_dump_json()
            await redis.set(self.stats_key, serialized, ex=cache_ttl)
            logger.debug("Stored stats cache in key %s (TTL: %ds)", self.stats_key, cache_ttl)
        except Exception as exc:
            logger.warning("Failed to store stats into Redis cache: %s", exc)

    async def invalidate_stats_cache(self, redis: Redis) -> None:
        """
        Invalidate cached statistics immediately after any state-changing write.

        Called on complaint creation and complaint status transitions.
        """
        try:
            deleted = await redis.delete(self.stats_key)
            logger.debug("Invalidated stats cache key %s (deleted=%s)", self.stats_key, deleted)
        except Exception as exc:
            logger.warning("Failed to invalidate stats cache in Redis: %s", exc)


# Default singleton instance
cache_service = CacheService()
