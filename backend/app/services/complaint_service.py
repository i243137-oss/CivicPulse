"""
Complaint service.

Implements all core business rules:
- Triage orchestration, caching, and metadata assignment
- State machine transition validation
- Complaint creation and retrieval workflow
- Aggregate statistics calculation
"""

import uuid
from typing import Any

from redis.asyncio import Redis

from app.models.complaint import (
    CategoryEnum,
    Complaint,
    PriorityEnum,
    StatusEnum,
)
from app.providers.triage.base import TriageProvider
from app.providers.triage.rules import RuleBasedTriage
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import ComplaintCreate
from app.services.state_machine import validate_transition
from app.services.triage_service import TriageService


class ComplaintNotFoundError(Exception):
    """Raised when a requested complaint is not found in persistence."""

    def __init__(self, complaint_id: uuid.UUID):
        self.complaint_id = complaint_id
        super().__init__(f"Complaint with ID '{complaint_id}' was not found.")


class ComplaintService:
    """Business service coordinating repositories, state machines, and triage providers."""

    def __init__(
        self,
        repository: ComplaintRepository,
        triage_provider: TriageProvider | None = None,
        triage_service: TriageService | None = None,
    ) -> None:
        self.repository = repository
        if triage_service is not None:
            self.triage_service = triage_service
            self.triage_provider = triage_service.primary_provider
        elif triage_provider is not None:
            self.triage_provider = triage_provider
            self.triage_service = TriageService(primary_provider=triage_provider)
        else:
            default_provider = RuleBasedTriage()
            self.triage_provider = default_provider
            self.triage_service = TriageService(primary_provider=default_provider)

    async def create_complaint(
        self,
        data: ComplaintCreate,
        redis: Redis | None = None,
    ) -> Complaint:
        """
        Create and persist a new complaint.
        Runs triage orchestration if category or priority are not explicitly supplied.
        Enforces strict PII exclusion: reporter_contact is NEVER sent to AI providers.
        """
        category = data.category
        priority = data.priority
        ai_summary: str | None = None
        triaged_by: str | None = None
        triage_latency_ms: int | None = None

        # Execute triage orchestration (handles content-hash cache, primary provider, fallback)
        outcome = await self.triage_service.execute_triage(
            text=data.text,
            location=data.location,
            redis=redis,
        )

        if category is None:
            category = outcome.result.category
        if priority is None:
            priority = outcome.result.priority

        ai_summary = outcome.result.summary
        triage_latency_ms = outcome.triage_latency_ms

        if data.category is not None and data.priority is not None:
            # Caller supplied explicit values; mark as manual user classification
            triaged_by = "user:manual"
        else:
            triaged_by = outcome.triaged_by

        complaint = Complaint(
            text=data.text,
            location=data.location,
            reporter_contact=data.reporter_contact,
            category=category,
            priority=priority,
            status=StatusEnum.OPEN,
            ai_summary=ai_summary,
            triaged_by=triaged_by,
            triage_latency_ms=triage_latency_ms,
        )

        return await self.repository.create(complaint)

    async def get_complaint(self, complaint_id: uuid.UUID) -> Complaint:
        """Retrieve a complaint by ID, raising ComplaintNotFoundError if absent."""
        complaint = await self.repository.get_by_id(complaint_id)
        if not complaint:
            raise ComplaintNotFoundError(complaint_id)
        return complaint

    async def list_complaints(
        self,
        category: CategoryEnum | None = None,
        priority: PriorityEnum | None = None,
        status: StatusEnum | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Complaint], int]:
        """List complaints with pagination and filters."""
        # Enforce page_size bounds (page_size <= 100 per spec)
        page_size = max(1, min(page_size, 100))
        page = max(1, page)
        skip = (page - 1) * page_size

        return await self.repository.list_complaints(
            category=category,
            priority=priority,
            status=status,
            skip=skip,
            limit=page_size,
        )

    async def update_status(
        self,
        complaint_id: uuid.UUID,
        target_status: StatusEnum,
    ) -> Complaint:
        """
        Transition the status of an existing complaint.
        Validates the transition against the formal state machine.
        Raises InvalidStateTransitionError if the transition is prohibited.
        """
        complaint = await self.get_complaint(complaint_id)

        # Validate state machine transition
        validate_transition(current=complaint.status, target=target_status)

        complaint.status = target_status
        return await self.repository.update(complaint)

    async def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics across complaints."""
        return await self.repository.get_stats()
