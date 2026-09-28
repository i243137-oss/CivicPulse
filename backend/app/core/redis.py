"""
Redis connection management, connection pooling, and health probing.

Provides an asynchronous Redis client interface backed by connection pooling.
Used for distributed rate limiting and read-through statistics caching.
"""

import logging
from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool and client references
_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


def get_redis_pool() -> ConnectionPool:
    """Retrieve or initialize the global Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = ConnectionPool.from_url(
            settings.REDIS_CONNECTION_URL,
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
            retry_on_timeout=True,
        )
    return _redis_pool


def get_redis_client() -> Redis:
    """Retrieve or initialize the global async Redis client."""
    global _redis_client
    if _redis_client is None:
        pool = get_redis_pool()
        _redis_client = Redis(connection_pool=pool)
    return _redis_client


def set_redis_client(client: Redis | None) -> None:
    """Explicitly override global Redis client (primarily for testing with FakeRedis)."""
    global _redis_client
    _redis_client = client


async def close_redis_client() -> None:
    """Close the global Redis client and pool during application shutdown."""
    global _redis_client, _redis_pool
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as exc:
            logger.warning(f"Error closing Redis client: {exc}")
        finally:
            _redis_client = None

    if _redis_pool is not None:
        try:
            await _redis_pool.disconnect()
        except Exception as exc:
            logger.warning(f"Error disconnecting Redis pool: {exc}")
        finally:
            _redis_pool = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency for accessing the async Redis client."""
    client = get_redis_client()
    try:
        yield client
    finally:
        pass


async def check_redis_health() -> bool:
    """
    Ping Redis to verify server connectivity for readiness probes.

    Returns True if Redis responds to PING within timeout, False otherwise.
    """
    try:
        client = get_redis_client()
        pong = await client.ping()
        return bool(pong)
    except Exception as exc:
        logger.warning(f"Redis readiness probe check failed: {exc}")
        return False
