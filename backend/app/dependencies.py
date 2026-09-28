"""
Dependency injection wiring.

Injects repositories and providers into services, ensuring routes receive
fully constructed services without touching sessions or SQL directly.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.providers.triage.base import TriageProvider
from app.providers.triage.factory import create_triage_provider
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.triage_service import TriageService

# Active triage provider and service singletons
_default_triage_provider: TriageProvider | None = None
_default_triage_service: TriageService | None = None


def get_triage_provider() -> TriageProvider:
    """Return the active triage provider instance, initialized from config."""
    global _default_triage_provider
    if _default_triage_provider is None:
        _default_triage_provider = create_triage_provider()
    return _default_triage_provider


def set_triage_provider(provider: TriageProvider | None) -> None:
    """Explicitly override the active triage provider (primarily for tests)."""
    global _default_triage_provider, _default_triage_service
    _default_triage_provider = provider
    _default_triage_service = None


def get_triage_service(
    provider: TriageProvider = Depends(get_triage_provider),
) -> TriageService:
    """Dependency injecting TriageService orchestrator."""
    global _default_triage_service
    if _default_triage_service is None or _default_triage_service.primary_provider != provider:
        _default_triage_service = TriageService(primary_provider=provider)
    return _default_triage_service


def get_complaint_repository(
    db: AsyncSession = Depends(get_db),
) -> ComplaintRepository:
    """Dependency injecting ComplaintRepository with an active DB session."""
    return ComplaintRepository(session=db)


def get_complaint_service(
    repository: ComplaintRepository = Depends(get_complaint_repository),
    triage_service: TriageService = Depends(get_triage_service),
) -> ComplaintService:
    """Dependency injecting ComplaintService wired with repository and triage orchestrator."""
    return ComplaintService(
        repository=repository,
        triage_service=triage_service,
    )
