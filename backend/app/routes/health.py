"""
Liveness endpoint.

Phase 1 scope only: a process-alive check with no external dependencies.
This must never be extended to touch Postgres or Redis — that is precisely
the distinction the assignment draws between /health (liveness) and /ready
(readiness). Readiness is added in Phase 8 once the database and cache
layers exist.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
)
def get_health() -> HealthResponse:
    """Return 200 if the process is alive. Deliberately has no dependencies."""
    return HealthResponse(status="ok")
