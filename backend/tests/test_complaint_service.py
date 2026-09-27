"""
Unit tests for ComplaintService business logic.

Validates:
- Automated triage inference when fields omitted
- Manual triage preservation when explicit category/priority supplied
- NotFound error raising
- State machine validation within service layer
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import (
    CategoryEnum,
    PriorityEnum,
    StatusEnum,
)
from app.providers.triage import RuleBasedTriageProvider
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import (
    ComplaintNotFoundError,
    ComplaintService,
)
from app.services.state_machine import InvalidStateTransitionError


@pytest.mark.asyncio
async def test_service_create_triggers_triage(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    provider = RuleBasedTriageProvider()
    service = ComplaintService(repository=repo, triage_provider=provider)

    payload = ComplaintCreate(
        text="Huge electric spark in transformer causing outage on our road.",
        location="Sector I-8/4, Islamabad",
        reporter_contact="+923009988776",
        # category and priority omitted to trigger triage
    )

    complaint = await service.create_complaint(payload)
    assert complaint.id is not None
    assert complaint.category == CategoryEnum.ELECTRICITY
    assert complaint.priority == PriorityEnum.HIGH
    assert complaint.status == StatusEnum.OPEN
    assert complaint.triaged_by == "rules"
    assert complaint.ai_summary is not None


@pytest.mark.asyncio
async def test_service_create_respects_manual_category(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    provider = RuleBasedTriageProvider()
    service = ComplaintService(repository=repo, triage_provider=provider)

    payload = ComplaintCreate(
        text="General administrative issue with street numbering signboards.",
        location="Sector F-8/2, Islamabad",
        category=CategoryEnum.OTHER,
        priority=PriorityEnum.LOW,
    )

    complaint = await service.create_complaint(payload)
    assert complaint.category == CategoryEnum.OTHER
    assert complaint.priority == PriorityEnum.LOW
    assert complaint.triaged_by == "user:manual"


@pytest.mark.asyncio
async def test_service_get_not_found(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    service = ComplaintService(repository=repo, triage_provider=RuleBasedTriageProvider())

    with pytest.raises(ComplaintNotFoundError):
        await service.get_complaint(uuid.uuid4())


@pytest.mark.asyncio
async def test_service_update_status_transitions(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    service = ComplaintService(repository=repo, triage_provider=RuleBasedTriageProvider())

    payload = ComplaintCreate(
        text="Blocked sewer pipe flooding back alleyway behind homes.",
        location="Street 20, Sector G-8/1",
        category=CategoryEnum.SANITATION,
        priority=PriorityEnum.NORMAL,
    )
    complaint = await service.create_complaint(payload)
    cid = complaint.id

    # Valid: open -> in_progress
    updated = await service.update_status(cid, StatusEnum.IN_PROGRESS)
    assert updated.status == StatusEnum.IN_PROGRESS

    # Valid: in_progress -> resolved
    updated2 = await service.update_status(cid, StatusEnum.RESOLVED)
    assert updated2.status == StatusEnum.RESOLVED

    # Invalid: resolved is terminal; transition to open must raise error
    with pytest.raises(InvalidStateTransitionError):
        await service.update_status(cid, StatusEnum.OPEN)
