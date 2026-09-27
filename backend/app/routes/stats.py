"""
Statistics HTTP routes.

Returns aggregated counts across categories, priorities, and statuses.
"""

from fastapi import APIRouter, Depends, status

from app.dependencies import get_complaint_service
from app.schemas.complaint import ComplaintStatsResponse
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/api/stats", tags=["statistics"])


@router.get(
    "",
    response_model=ComplaintStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated complaint statistics",
)
async def get_stats(
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintStatsResponse:
    """Return aggregated count totals across complaints."""
    data = await service.get_stats()
    return ComplaintStatsResponse(
        total=data["total"],
        by_status=data["by_status"],
        by_category=data["by_category"],
        by_priority=data["by_priority"],
    )
