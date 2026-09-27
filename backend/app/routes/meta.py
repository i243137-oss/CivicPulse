"""
Metadata and observability routes.

Surfaces active triage provider, telemetry, and latency metrics.
"""

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.dependencies import get_triage_service
from app.services.triage_service import TriageService

router = APIRouter(prefix="/api/meta", tags=["metadata"])


class ProviderInfoResponse(BaseModel):
    active_provider: str
    recent_outcomes: list[dict[str, Any]] = []


@router.get(
    "/providers",
    response_model=ProviderInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Active triage provider and recent outcomes",
)
def get_providers_meta(
    triage_service: TriageService = Depends(get_triage_service),
) -> ProviderInfoResponse:
    """Return active provider configuration, recent outcomes, and triage telemetry."""
    provider = triage_service.primary_provider
    provider_name = getattr(provider, "name", getattr(provider, "provider_id", provider.__class__.__name__))
    recent = triage_service.get_recent_outcomes()

    return ProviderInfoResponse(
        active_provider=provider_name,
        recent_outcomes=recent,
    )
