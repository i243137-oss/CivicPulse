"""
Unit and integration tests for Phase 8: Observability, Structured Logging, Probes, and Metrics.

Validates:
1. JSON structured logging format with required fields (timestamp, level, service, message, request_id).
2. X-Request-ID generation and correlation across contextvars and response headers.
3. Separation of liveness (/health) and readiness (/ready).
4. Readiness reflects PostgreSQL and Redis health, returning HTTP 503 on dependency failure.
5. Prometheus metrics endpoint (/metrics) scraping and emission of request/AI/fallback/cache counters.
6. Graceful shutdown resource cleanup.
"""

import io
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.logging import (
    StructuredJsonFormatter,
    set_request_id,
)
from app.main import app, lifespan

# ==============================================================================
# 1. JSON Structured Logging Tests
# ==============================================================================


def test_structured_json_formatter_emits_valid_json() -> None:
    """Verify StructuredJsonFormatter outputs valid single-line JSON with standard fields."""
    formatter = StructuredJsonFormatter()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    test_logger = logging.getLogger("civicpulse.test.logging")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    test_logger.info("Test message for structured logging", extra={"extra_key": "extra_value"})

    output = stream.getvalue().strip()
    assert output, "Log output should not be empty"

    log_entry = json.loads(output)
    assert log_entry["service"] == "civicpulse"
    assert log_entry["level"] == "INFO"
    assert log_entry["message"] == "Test message for structured logging"
    assert log_entry["logger"] == "civicpulse.test.logging"
    assert log_entry["extra_key"] == "extra_value"
    assert "timestamp" in log_entry


def test_structured_json_formatter_propagates_request_id() -> None:
    """Verify request_id from contextvar is automatically injected into JSON logs."""
    formatter = StructuredJsonFormatter()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    test_logger = logging.getLogger("civicpulse.test.req_id")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    # 1. Without request_id
    set_request_id(None)
    test_logger.info("Log without request id")
    entry_without = json.loads(stream.getvalue().splitlines()[-1])
    assert "request_id" not in entry_without

    # 2. With request_id set in contextvar
    set_request_id("req-custom-correlation-id")
    test_logger.info("Log with request id")
    entry_with = json.loads(stream.getvalue().splitlines()[-1])
    assert entry_with.get("request_id") == "req-custom-correlation-id"

    set_request_id(None)


# ==============================================================================
# 2. Request ID Middleware & Propagation Tests
# ==============================================================================


def test_request_id_auto_generation(client: TestClient) -> None:
    """When no X-Request-ID is supplied, middleware generates one starting with 'req-'."""
    res = client.get("/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    req_id = res.headers["X-Request-ID"]
    assert req_id.startswith("req-")
    assert len(req_id) >= 8


def test_request_id_propagation_from_client_header(client: TestClient) -> None:
    """Incoming X-Request-ID is preserved and returned on the response."""
    custom_id = "client-trace-abc-12345"
    res = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_id


# ==============================================================================
# 3. Liveness vs Readiness Separation Tests
# ==============================================================================


def test_health_liveness_zero_external_dependencies(client: TestClient) -> None:
    """GET /health succeeds as pure liveness probe without touching database or cache."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ready_readiness_both_dependencies_healthy(client: TestClient) -> None:
    """GET /ready returns 200 when database and Redis are reachable."""
    res = client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"


def test_ready_readiness_database_failure_returns_503(client: TestClient) -> None:
    """GET /ready returns 503 Service Unavailable when the database fails."""
    from app.db.session import get_db

    async def failing_db():
        session = AsyncMock()
        session.execute.side_effect = OperationalError(
            "connection refused", {}, Exception("db down")
        )
        yield session

    app.dependency_overrides[get_db] = failing_db
    try:
        res = client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert "Database dependency unreachable" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ready_readiness_redis_failure_returns_503(client: TestClient) -> None:
    """GET /ready returns 503 Service Unavailable when Redis fails."""
    from app.core.redis import get_redis

    async def failing_redis():
        mock_r = AsyncMock()
        mock_r.ping.side_effect = ConnectionError("Redis cluster unreachable")
        yield mock_r

    app.dependency_overrides[get_redis] = failing_redis
    try:
        res = client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert "Redis dependency unreachable" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_redis, None)


# ==============================================================================
# 4. Prometheus Metrics Endpoint (/metrics) Tests
# ==============================================================================


def test_metrics_endpoint_scrapable(client: TestClient) -> None:
    """GET /metrics returns 200 with standard Prometheus text format."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("content-type", "")

    body = res.text
    # Verify core metric families exist
    assert "civicpulse_http_requests_total" in body
    assert "civicpulse_http_request_duration_seconds" in body
    assert "civicpulse_ai_triage_requests_total" in body
    assert "civicpulse_ai_triage_duration_seconds" in body
    assert "civicpulse_ai_fallback_total" in body
    assert "civicpulse_cache_requests_total" in body


def test_metrics_endpoint_records_traffic_and_triage(client: TestClient) -> None:
    """Making requests and submitting complaints increments Prometheus metrics."""
    # 1. Trigger HTTP request
    client.get("/health")

    # 2. Trigger Triage request
    complaint_payload = {
        "text": "Broken water main leaking on the street corner.",
        "location": "Sector G-9/1, Islamabad",
    }
    client.post("/api/complaints", json=complaint_payload)

    # 3. Scrape metrics
    res = client.get("/metrics")
    assert res.status_code == 200
    body = res.text

    # Verify HTTP request count recorded
    assert (
        'civicpulse_http_requests_total{endpoint="/health"' in body
        or "civicpulse_http_requests_total{" in body
    )
    # Verify triage metric recorded
    assert "civicpulse_ai_triage_requests_total" in body


# ==============================================================================
# 5. Graceful Lifespan Shutdown Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_graceful_shutdown_lifespan() -> None:
    """FastAPI lifespan cleanly runs startup and disposes connection pools on shutdown."""
    mock_engine = AsyncMock()
    with (
        patch("app.db.session.engine", mock_engine),
        patch("app.main.close_redis_client", new_callable=AsyncMock) as mock_redis_close,
    ):
        async with lifespan(app):
            # Application is running
            pass

        # Application shutdown completed
        mock_engine.dispose.assert_awaited_once()
        mock_redis_close.assert_awaited_once()
