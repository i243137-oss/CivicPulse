from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_require_database() -> None:
    """
    Liveness must never depend on Postgres/Redis. There is no DB/cache wiring
    in the app at all yet (Phase 1), so this test simply pins the contract:
    /health responds without any dependency setup.
    """
    response = client.get("/health")
    assert response.status_code == 200


def test_root_returns_service_metadata() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "service" in body
    assert "environment" in body
