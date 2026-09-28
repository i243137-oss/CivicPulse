"""
Readiness probe endpoint.

Checks dependency reachability (PostgreSQL database).
Returns HTTP 200 only when required dependencies are reachable,
or HTTP 503 naming the failing dependency.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db

router = APIRouter(tags=["readiness"])


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
)
async def get_readiness(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ReadinessResponse:
    """
    Readiness probe verifying both database and Redis connectivity.
    Unlike /health (which has zero dependencies), /ready verifies all
    required runtime dependencies.
    """
    db_ok = False
    redis_ok = False
    errors: list[str] = []

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as err:
        errors.append(f"Database dependency unreachable: {err}")

    try:
        pong = await redis.ping()
        redis_ok = bool(pong)
    except Exception as err:
        errors.append(f"Redis dependency unreachable: {err}")

    if not db_ok or not redis_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="; ".join(errors),
        )

    return ReadinessResponse(
        status="ready",
        database="connected",
        redis="connected",
    )
