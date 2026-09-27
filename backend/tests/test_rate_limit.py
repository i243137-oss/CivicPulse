"""
Tests for distributed rate limiting with Redis atomic Lua script execution.

Verifies:
- Standard requests return X-RateLimit-Limit and X-RateLimit-Remaining headers
- Request quota exhaustion returns HTTP 429 Too Many Requests with Retry-After header
- Exempt endpoints (/health and /ready) are never blocked by rate limiting
- Client IP resolution from X-Forwarded-For proxy headers
- Atomic sliding window behavior inside Redis
"""

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import DistributedRateLimiter


@pytest.mark.asyncio
async def test_atomic_rate_limiter_sliding_window(fake_redis) -> None:
    """Verify that atomic Lua script correctly tracks requests and blocks when limit is exceeded."""
    limiter = DistributedRateLimiter(requests_per_minute=3, window_seconds=60)
    client_id = "test-client-1"

    # Request 1: allowed, 2 remaining
    allowed1, rem1, retry1 = await limiter.is_allowed(fake_redis, client_id, limit=3, window_seconds=60)
    assert allowed1 is True
    assert rem1 == 2
    assert retry1 == 0

    # Request 2: allowed, 1 remaining
    allowed2, rem2, retry2 = await limiter.is_allowed(fake_redis, client_id, limit=3, window_seconds=60)
    assert allowed2 is True
    assert rem2 == 1
    assert retry2 == 0

    # Request 3: allowed, 0 remaining
    allowed3, rem3, retry3 = await limiter.is_allowed(fake_redis, client_id, limit=3, window_seconds=60)
    assert allowed3 is True
    assert rem3 == 0
    assert retry3 == 0

    # Request 4: BLOCKED (exceeds limit 3)
    allowed4, rem4, retry4 = await limiter.is_allowed(fake_redis, client_id, limit=3, window_seconds=60)
    assert allowed4 is False
    assert rem4 == 0
    assert retry4 > 0  # Retry-After must be calculated in seconds


def test_rate_limit_headers_on_successful_request(client: TestClient) -> None:
    """Successful API requests must include X-RateLimit-Limit and X-RateLimit-Remaining."""
    response = client.get("/api/meta/providers")
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert int(response.headers["X-RateLimit-Remaining"]) >= 0


def test_rate_limit_exceeded_returns_429(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the request limit is reached, middleware returns HTTP 429 with Retry-After."""
    from app.core import config

    # Temporarily set limit to 2 requests per minute for fast deterministic testing
    settings = config.get_settings()
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

    test_ip = "192.168.1.100"
    headers = {"X-Forwarded-For": test_ip}

    # Request 1: allowed
    res1 = client.get("/api/meta/providers", headers=headers)
    assert res1.status_code == 200
    assert res1.headers["X-RateLimit-Remaining"] == "1"

    # Request 2: allowed
    res2 = client.get("/api/meta/providers", headers=headers)
    assert res2.status_code == 200
    assert res2.headers["X-RateLimit-Remaining"] == "0"

    # Request 3: BLOCKED with HTTP 429
    res3 = client.get("/api/meta/providers", headers=headers)
    assert res3.status_code == 429
    assert res3.json() == {"detail": "Too many requests. Please try again later."}
    assert "Retry-After" in res3.headers
    assert int(res3.headers["Retry-After"]) >= 1
    assert res3.headers["X-RateLimit-Remaining"] == "0"


def test_health_and_ready_probes_are_exempt_from_rate_limiting(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Liveness (/health) and readiness (/ready) probes must never be blocked by rate limiting."""
    from app.core import config

    # Set rate limit to 1 request per minute
    settings = config.get_settings()
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)

    test_ip = "10.0.0.99"
    headers = {"X-Forwarded-For": test_ip}

    # Consume API quota
    res1 = client.get("/api/meta/providers", headers=headers)
    assert res1.status_code == 200

    # API is now blocked
    res2 = client.get("/api/meta/providers", headers=headers)
    assert res2.status_code == 429

    # /health probe must STILL succeed with 200 OK
    res_health = client.get("/health", headers=headers)
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # /ready probe must STILL succeed with 200 OK
    res_ready = client.get("/ready", headers=headers)
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


def test_rate_limiting_isolated_by_client_ip(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exhausting quota for one client IP does not affect other client IPs."""
    from app.core import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)

    ip_a = {"X-Forwarded-For": "10.1.1.1"}
    ip_b = {"X-Forwarded-For": "10.1.1.2"}

    # IP A uses its quota
    assert client.get("/api/meta/providers", headers=ip_a).status_code == 200
    assert client.get("/api/meta/providers", headers=ip_a).status_code == 429

    # IP B is unaffected and succeeds
    assert client.get("/api/meta/providers", headers=ip_b).status_code == 200
