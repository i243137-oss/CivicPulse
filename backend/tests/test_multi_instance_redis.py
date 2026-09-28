"""
Multi-Instance Verification Tests for Phase 3 Exit Gate.

Demonstrates that under multiple independent backend instances sharing the same Redis cluster:
1. Cache read-through is shared across instances (Instance A warm -> Instance B HIT).
2. Cache invalidation on write propagates across instances (Instance A write -> Instance B MISS).
3. Rate limiting quota is shared and enforced atomically across instances (requests across A & B share limit).
"""

from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.redis import get_redis, set_redis_client
from app.db.session import get_db
from app.main import app
from tests.conftest import TestAsyncSessionLocal


@pytest.fixture(scope="function")
def shared_redis_server() -> fakeredis.FakeServer:
    """A single shared in-memory Redis server backing multiple client instances."""
    return fakeredis.FakeServer()


def create_backend_instance(
    shared_server: fakeredis.FakeServer,
) -> TestClient:
    """Factory creating an independent backend TestClient attached to the shared Redis server."""
    instance_redis = fakeredis.aioredis.FakeRedis(server=shared_server, decode_responses=True)

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestAsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
        yield instance_redis

    # Wire overrides for this instance
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    set_redis_client(instance_redis)

    return TestClient(app)


def test_multi_instance_cache_sharing_and_invalidation(
    setup_test_db: None,
    shared_redis_server: fakeredis.FakeServer,
) -> None:
    """
    Exit Gate Verification 1: Cache behavior across multiple backend instances.
    - Instance 1 receives first request: MISS (warms cache in shared Redis).
    - Instance 2 receives subsequent request: HIT (reads cache written by Instance 1).
    - Instance 1 performs write: invalidates shared Redis key.
    - Instance 2 receives request: MISS (detects invalidation performed by Instance 1).
    """
    instance_1 = create_backend_instance(shared_redis_server)
    instance_2 = create_backend_instance(shared_redis_server)

    try:
        # Step 1: Instance 1 fetches stats -> MISS
        res1 = instance_1.get("/api/stats")
        assert res1.status_code == 200
        assert res1.headers.get("X-Cache") == "MISS"
        initial_total = res1.json()["total"]

        # Step 2: Instance 2 fetches stats -> HIT (shared Redis)
        res2 = instance_2.get("/api/stats")
        assert res2.status_code == 200
        assert res2.headers.get("X-Cache") == "HIT"
        assert res2.json()["total"] == initial_total

        # Step 3: Instance 1 creates a new complaint -> invalidates stats in shared Redis
        res_create = instance_1.post(
            "/api/complaints",
            json={
                "text": "Frequent voltage fluctuation causing transformer sparks on Street 7.",
                "location": "Sector G-11/3, Street 7, Islamabad",
                "category": "electricity",
            },
        )
        assert res_create.status_code == 201

        # Step 4: Instance 2 fetches stats -> MISS (because Instance 1 invalidated cache!)
        res3 = instance_2.get("/api/stats")
        assert res3.status_code == 200
        assert res3.headers.get("X-Cache") == "MISS"
        assert res3.json()["total"] == initial_total + 1

        # Step 5: Instance 1 fetches stats -> HIT (cache was re-warmed by Instance 2)
        res4 = instance_1.get("/api/stats")
        assert res4.status_code == 200
        assert res4.headers.get("X-Cache") == "HIT"
        assert res4.json()["total"] == initial_total + 1
    finally:
        app.dependency_overrides.clear()
        set_redis_client(None)


def test_multi_instance_distributed_rate_limiting(
    setup_test_db: None,
    shared_redis_server: fakeredis.FakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exit Gate Verification 2: Distributed rate limiting across multiple backend instances.
    - Rate limit: 4 requests per minute.
    - Client distributes 4 requests across Instance 1 and Instance 2.
    - 5th request to Instance 1 is blocked with HTTP 429.
    - 6th request to Instance 2 is blocked with HTTP 429.
    - Demonstrates that quota is enforced atomically across backend replicas.
    """
    settings = config.get_settings()
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 4)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

    instance_1 = create_backend_instance(shared_redis_server)
    instance_2 = create_backend_instance(shared_redis_server)

    client_headers = {"X-Forwarded-For": "203.0.113.42"}

    try:
        # Request 1 -> Instance 1 (allowed, 3 remaining)
        r1 = instance_1.get("/api/meta/providers", headers=client_headers)
        assert r1.status_code == 200
        assert r1.headers["X-RateLimit-Remaining"] == "3"

        # Request 2 -> Instance 2 (allowed, 2 remaining)
        r2 = instance_2.get("/api/meta/providers", headers=client_headers)
        assert r2.status_code == 200
        assert r2.headers["X-RateLimit-Remaining"] == "2"

        # Request 3 -> Instance 1 (allowed, 1 remaining)
        r3 = instance_1.get("/api/meta/providers", headers=client_headers)
        assert r3.status_code == 200
        assert r3.headers["X-RateLimit-Remaining"] == "1"

        # Request 4 -> Instance 2 (allowed, 0 remaining)
        r4 = instance_2.get("/api/meta/providers", headers=client_headers)
        assert r4.status_code == 200
        assert r4.headers["X-RateLimit-Remaining"] == "0"

        # Request 5 -> Instance 1 (BLOCKED across instances)
        r5 = instance_1.get("/api/meta/providers", headers=client_headers)
        assert r5.status_code == 429
        assert "Retry-After" in r5.headers
        assert r5.headers["X-RateLimit-Remaining"] == "0"

        # Request 6 -> Instance 2 (ALSO BLOCKED across instances)
        r6 = instance_2.get("/api/meta/providers", headers=client_headers)
        assert r6.status_code == 429
        assert "Retry-After" in r6.headers
        assert r6.headers["X-RateLimit-Remaining"] == "0"
    finally:
        app.dependency_overrides.clear()
        set_redis_client(None)
