"""
Metadata and observability routes.

Surfaces active triage provider and telemetry.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.dependencies import get_triage_provider
from app.providers.triage import TriageProvider

router = APIRouter(prefix="/api/meta", tags=["metadata"])


class ProviderInfoResponse(BaseModel):
    active_provider: str
    recent_outcomes: list[dict] = []


@router.get(
    "/providers",
    response_model=ProviderInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Active triage provider and recent outcomes",
)
def get_providers_meta(
    provider: TriageProvider = Depends(get_triage_provider),
) -> ProviderInfoResponse:
    """Return active provider configuration and triage telemetry."""
    provider_name = getattr(provider, "provider_id", provider.__class__.__name__)
    return ProviderInfoResponse(
        active_provider=provider_name,
        recent_outcomes=[],
    )
