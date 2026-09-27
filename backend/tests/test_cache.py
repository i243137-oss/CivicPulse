"""
Tests for read-through statistics caching, TTL expiration, and write-time invalidation.

Verifies:
- Cache MISS on initial request returning X-Cache: MISS
- Cache HIT on subsequent request returning X-Cache: HIT
- Cache expiration after TTL expires
- Cache invalidation on new complaint submission (POST /api/complaints)
- Cache invalidation on complaint status transition (PATCH /api/complaints/{id}/status)
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_stats_cache_miss_then_hit(client: TestClient) -> None:
    """First request is a MISS; immediate subsequent request is a HIT."""
    # 1. Initial request: MISS
    res1 = client.get("/api/stats")
    assert res1.status_code == 200
    assert res1.headers.get("X-Cache") == "MISS"
    data1 = res1.json()

    # 2. Immediate second request: HIT
    res2 = client.get("/api/stats")
    assert res2.status_code == 200
    assert res2.headers.get("X-Cache") == "HIT"
    data2 = res2.json()

    # The payload must be identical
    assert data1 == data2


def test_stats_cache_invalidation_on_complaint_create(client: TestClient) -> None:
    """Submitting a new complaint invalidates the stats cache."""
    # 1. Warm the cache
    res_warm1 = client.get("/api/stats")
    assert res_warm1.headers.get("X-Cache") == "MISS"

    res_warm2 = client.get("/api/stats")
    assert res_warm2.headers.get("X-Cache") == "HIT"
    initial_total = res_warm2.json()["total"]

    # 2. Create a new complaint (write operation)
    res_create = client.post(
        "/api/complaints",
        json={
            "text": "Streetlight on Main Boulevard pole 14 has been broken for three nights.",
            "location": "Main Boulevard, Block B, Lahore",
            "category": "streetlights",
        },
    )
    assert res_create.status_code == 201

    # 3. Next stats request must be a MISS because cache was invalidated on write
    res_after_write = client.get("/api/stats")
    assert res_after_write.status_code == 200
    assert res_after_write.headers.get("X-Cache") == "MISS"
    assert res_after_write.json()["total"] == initial_total + 1

    # 4. Subsequent request is a HIT with the new count
    res_next_hit = client.get("/api/stats")
    assert res_next_hit.status_code == 200
    assert res_next_hit.headers.get("X-Cache") == "HIT"
    assert res_next_hit.json()["total"] == initial_total + 1


def test_stats_cache_invalidation_on_status_update(client: TestClient) -> None:
    """Updating a complaint's status invalidates the stats cache."""
    # 1. Create a complaint
    res_create = client.post(
        "/api/complaints",
        json={
            "text": "Water leakage in sector F-7/1 pipeline flooding the road since morning.",
            "location": "Sector F-7/1, Street 4, Islamabad",
            "category": "water",
        },
    )
    assert res_create.status_code == 201
    complaint_id = res_create.json()["id"]

    # 2. Warm the stats cache
    client.get("/api/stats")  # MISS
    res_cached = client.get("/api/stats")  # HIT
    assert res_cached.headers.get("X-Cache") == "HIT"
    assert res_cached.json()["by_status"].get("open", 0) >= 1
    in_progress_before = res_cached.json()["by_status"].get("in_progress", 0)

    # 3. Update status (open -> in_progress)
    res_patch = client.patch(
        f"/api/complaints/{complaint_id}/status",
        json={"status": "in_progress"},
    )
    assert res_patch.status_code == 200

    # 4. Next stats request must be a MISS due to write invalidation
    res_after_patch = client.get("/api/stats")
    assert res_after_patch.status_code == 200
    assert res_after_patch.headers.get("X-Cache") == "MISS"
    assert res_after_patch.json()["by_status"]["in_progress"] == in_progress_before + 1

    # 5. Subsequent request is a HIT
    res_next_hit = client.get("/api/stats")
    assert res_next_hit.status_code == 200
    assert res_next_hit.headers.get("X-Cache") == "HIT"


@pytest.mark.asyncio
async def test_cache_service_ttl_expiration(fake_redis) -> None:
    """Verify that cached stats expire after the configured TTL."""
    from app.schemas.complaint import ComplaintStatsResponse
    from app.services.cache_service import CacheService

    cache = CacheService(key_prefix="test:expire:")
    stats = ComplaintStatsResponse(
        total=5,
        by_status={"open": 5},
        by_category={"water": 5},
        by_priority={"high": 5},
    )

    # Store with a short 1-second TTL
    await cache.set_cached_stats(fake_redis, stats, ttl=1)

    # Verify immediate retrieval is a HIT
    cached = await cache.get_cached_stats(fake_redis)
    assert cached is not None
    assert cached.total == 5

    # Check remaining TTL
    ttl = await fake_redis.ttl(cache.stats_key)
    assert 0 < ttl <= 1

    # Wait for TTL to elapse
    time.sleep(1.1)

    # After expiration, it must return None (MISS)
    expired = await cache.get_cached_stats(fake_redis)
    assert expired is None


def test_config_stats_cache_ttl_setting() -> None:
    """Confirm Settings enforces 30-second TTL as required by specification."""
    settings = get_settings()
    assert settings.REDIS_STATS_CACHE_TTL == 30
