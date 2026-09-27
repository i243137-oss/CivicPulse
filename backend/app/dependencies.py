"""
Dependency injection wiring.

Injects repositories and providers into services, ensuring routes receive
fully constructed services without touching sessions or SQL directly.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.providers.triage import RuleBasedTriageProvider, TriageProvider
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService

# Singleton triage provider instance (can be swapped or overridden)
_default_triage_provider = RuleBasedTriageProvider()


def get_triage_provider() -> TriageProvider:
    """Return the active triage provider instance."""
    return _default_triage_provider


def get_complaint_repository(
    db: AsyncSession = Depends(get_db),
) -> ComplaintRepository:
    """Dependency injecting ComplaintRepository with an active DB session."""
    return ComplaintRepository(session=db)


def get_complaint_service(
    repository: ComplaintRepository = Depends(get_complaint_repository),
    triage_provider: TriageProvider = Depends(get_triage_provider),
) -> ComplaintService:
    """Dependency injecting ComplaintService wired with repository and triage provider."""
    return ComplaintService(
        repository=repository,
        triage_provider=triage_provider,
    )
