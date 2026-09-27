"""
Complaint HTTP routes.

Responsible solely for HTTP concerns: parsing parameters, invoking service methods,
and formatting responses and HTTP status codes. Contains no direct SQL or business rules.
"""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.dependencies import get_complaint_service
from app.models.complaint import CategoryEnum, PriorityEnum, StatusEnum
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintStatusUpdate,
)
from app.services.cache_service import cache_service
from app.services.complaint_service import (
    ComplaintNotFoundError,
    ComplaintService,
)
from app.services.state_machine import InvalidStateTransitionError

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new complaint",
)
async def create_complaint(
    payload: ComplaintCreate,
    service: ComplaintService = Depends(get_complaint_service),
    redis: Redis = Depends(get_redis),
) -> ComplaintResponse:
    """
    Submit a citizen complaint.
    Validates input, triggers triage orchestration, and persists the record.
    Invalidates statistics cache so subsequent stats requests fetch fresh data.
    """
    complaint = await service.create_complaint(payload, redis=redis)
    await cache_service.invalidate_stats_cache(redis)
    return ComplaintResponse.model_validate(complaint)


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
    summary="Get complaint by ID",
)
async def get_complaint(
    complaint_id: uuid.UUID,
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintResponse:
    """Retrieve details of a single complaint by UUID."""
    try:
        complaint = await service.get_complaint(complaint_id)
        return ComplaintResponse.model_validate(complaint)
    except ComplaintNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.get(
    "",
    response_model=ComplaintListResponse,
    status_code=status.HTTP_200_OK,
    summary="List complaints with filters and pagination",
)
async def list_complaints(
    category: CategoryEnum | None = Query(None, description="Filter by category"),
    priority: PriorityEnum | None = Query(None, description="Filter by priority"),
    complaint_status: StatusEnum | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintListResponse:
    """
    List complaints filtered by category, priority, and/or status with pagination.
    Returns matching complaints along with total item count and page calculations.
    """
    complaints, total = await service.list_complaints(
        category=category,
        priority=priority,
        status=complaint_status,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(c) for c in complaints],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
    summary="Update complaint status",
)
async def update_complaint_status(
    complaint_id: uuid.UUID,
    payload: ComplaintStatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
    redis: Redis = Depends(get_redis),
) -> ComplaintResponse:
    """
    Transition a complaint's status according to the finite state machine.
    Rejects invalid state transitions with HTTP 409 Conflict naming the transition.
    Invalidates statistics cache so subsequent stats requests fetch fresh data.
    """
    try:
        updated = await service.update_status(
            complaint_id=complaint_id,
            target_status=payload.status,
        )
        await cache_service.invalidate_stats_cache(redis)
        return ComplaintResponse.model_validate(updated)
    except ComplaintNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(err),
                "current_status": err.current_status.value,
                "target_status": err.target_status.value,
            },
        ) from err
