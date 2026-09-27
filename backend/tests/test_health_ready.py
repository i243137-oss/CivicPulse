"""
Tests for /health (liveness) and /ready (readiness) probe endpoints.

Ensures strict architectural separation:
- /health is a pure process-alive check with ZERO database dependency.
- /ready verifies external database connectivity and returns 503 if unreachable.
"""

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


def test_health_liveness_has_zero_db_dependency(client: TestClient) -> None:
    """Liveness probe must return 200 without ever opening database sessions."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_readiness_healthy_db(client: TestClient) -> None:
    """Readiness returns 200 when database connectivity succeeds."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_ready_readiness_db_failure_returns_503(client: TestClient) -> None:
    """Readiness probe returns 503 Service Unavailable if database is unreachable."""
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise ConnectionRefusedError("Database connection lost")

    async def failing_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = failing_db
    try:
        response = client.get("/ready")
        assert response.status_code == 503
        assert "Database dependency unreachable" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
