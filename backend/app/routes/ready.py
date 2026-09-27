"""
Readiness probe endpoint.

Checks dependency reachability (PostgreSQL database).
Returns HTTP 200 only when required dependencies are reachable,
or HTTP 503 naming the failing dependency.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["readiness"])


class ReadinessResponse(BaseModel):
    status: str
    database: str


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
)
async def get_readiness(
    db: AsyncSession = Depends(get_db),
) -> ReadinessResponse:
    """
    Readiness probe verifying database connectivity.
    Unlike /health, this verifies external dependencies.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database dependency unreachable: {err}",
        ) from err

    return ReadinessResponse(
        status="ready",
        database="connected",
    )
