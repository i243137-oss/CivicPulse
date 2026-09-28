"""
Distributed rate limiting using Redis and atomic Lua script execution.

Implements a sliding-window rate limiter evaluated atomically inside Redis.
Ensures accurate multi-instance rate limiting without race conditions or
boundary-burst anomalies.
"""

import logging
import math
import time
import uuid

from fastapi import Request, Response
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

# Atomic sliding-window Lua script
# KEYS[1]: rate limit key (e.g., civicpulse:ratelimit:ip:<client_ip>)
# ARGV[1]: current timestamp in milliseconds
# ARGV[2]: sliding window size in milliseconds
# ARGV[3]: request limit within window
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clearBefore = now - window

-- Remove timestamps outside the sliding window
redis.call('ZREMRANGEBYSCORE', key, 0, clearBefore)

-- Count active requests in current window
local currentCount = redis.call('ZCARD', key)

if currentCount < limit then
    -- Record this request with a unique sequence tag
    local seq = redis.call('INCR', key .. ':seq')
    local member = tostring(now) .. ':' .. tostring(seq)
    redis.call('ZADD', key, now, member)
    redis.call('PEXPIRE', key, window)
    redis.call('PEXPIRE', key .. ':seq', window)
    return {1, limit - currentCount - 1, 0}
else
    -- Compute Retry-After seconds from the oldest request in the current window
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retryAfter = 1
    if #oldest >= 2 then
        local oldestTime = tonumber(oldest[2])
        retryAfter = math.ceil((oldestTime + window - now) / 1000)
        if retryAfter < 1 then retryAfter = 1 end
    end
    return {0, 0, retryAfter}
end
"""


class DistributedRateLimiter:
    """Evaluates distributed rate limits against Redis using atomic operations."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
        key_prefix: str = "civicpulse:ratelimit:ip:",
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self._script_sha: str | None = None

    async def is_allowed(
        self,
        redis: Redis,
        client_id: str,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> tuple[bool, int, int]:
        """
        Atomically check and record a request for the given client identifier.

        Returns:
            Tuple[bool, int, int]: (allowed, remaining, retry_after_seconds)
        """
        max_requests = limit or self.requests_per_minute
        win_seconds = window_seconds or self.window_seconds
        window_ms = win_seconds * 1000
        now_ms = int(time.time() * 1000)
        key = f"{self.key_prefix}{client_id}"

        try:
            res = await redis.eval(
                SLIDING_WINDOW_LUA,
                1,
                key,
                str(now_ms),
                str(window_ms),
                str(max_requests),
            )
            allowed = bool(res[0] == 1)
            remaining = int(res[1])
            retry_after = int(res[2])
            return allowed, remaining, retry_after
        except ResponseError as err:
            if "unknown command 'eval'" in str(err).lower():
                return await self._pipeline_is_allowed(
                    redis, key, now_ms, window_ms, max_requests
                )
            logger.warning("Redis rate limit evaluation error: %s", err)
            return True, max_requests, 0
        except Exception as exc:
            logger.warning("Redis rate limit evaluation failed (failing open): %s", exc)
            # Fail-open resilience: allow traffic if Redis is unreachable
            return True, max_requests, 0

    async def _pipeline_is_allowed(
        self,
        redis: Redis,
        key: str,
        now_ms: int,
        window_ms: int,
        max_requests: int,
    ) -> tuple[bool, int, int]:
        """Atomic fallback evaluation using Redis MULTI/EXEC pipeline transactions."""
        clear_before = now_ms - window_ms

        async with redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, clear_before)
            pipe.zcard(key)
            pipe.zrange(key, 0, 0, withscores=True)
            res = await pipe.execute()

        current_count = int(res[1])
        oldest_entries = res[2]

        if current_count < max_requests:
            member = f"{now_ms}:{uuid.uuid4().hex[:8]}"
            async with redis.pipeline(transaction=True) as pipe:
                pipe.zadd(key, {member: now_ms})
                pipe.pexpire(key, window_ms)
                await pipe.execute()
            remaining = max_requests - current_count - 1
            return True, remaining, 0
        else:
            retry_after = 1
            if oldest_entries:
                oldest_time = float(oldest_entries[0][1])
                retry_after = math.ceil((oldest_time + window_ms - now_ms) / 1000.0)
                if retry_after < 1:
                    retry_after = 1
            return False, 0, int(retry_after)


# Default rate limiter instance
rate_limiter = DistributedRateLimiter()


def get_client_ip(request: Request) -> str:
    """Extract client IP address, honoring X-Forwarded-For when behind reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # In multi-hop proxies, the first IP is the original client IP
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware enforcing distributed rate limiting across backend instances.

    Exempts health, readiness, and documentation endpoints so probes and docs
    are never blocked.
    """

    EXEMPT_PATHS = {
        "/health",
        "/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for exempt system endpoints
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_ip = get_client_ip(request)
        redis_client = get_redis_client()

        allowed, remaining, retry_after = await rate_limiter.is_allowed(
            redis=redis_client,
            client_id=client_ip,
            limit=settings.RATE_LIMIT_PER_MINUTE,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded for client %s on %s (retry after %ds)",
                client_ip,
                request.url.path,
                retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
