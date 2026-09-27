"""
Unit tests for ComplaintRepository.

Validates:
- CRUD persistence
- Filtering by category, priority, status
- Pagination calculations
- Aggregated statistics calculations
- Exists checks
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import (
    CategoryEnum,
    Complaint,
    PriorityEnum,
    StatusEnum,
)
from app.repositories.complaint_repository import ComplaintRepository


@pytest.mark.asyncio
async def test_repository_create_and_get_by_id(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    complaint_id = uuid.uuid4()

    complaint = Complaint(
        id=complaint_id,
        text="Water pipeline leaking heavily on main boulevard road.",
        location="Blue Area, Sector F-6, Islamabad",
        reporter_contact="+923001112233",
        category=CategoryEnum.WATER,
        priority=PriorityEnum.HIGH,
        status=StatusEnum.OPEN,
        ai_summary="Water pipeline leak in Blue Area.",
        triaged_by="rules",
        triage_latency_ms=10,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    created = await repo.create(complaint)
    assert created.id == complaint_id

    fetched = await repo.get_by_id(complaint_id)
    assert fetched is not None
    assert fetched.text == complaint.text
    assert fetched.category == CategoryEnum.WATER
    assert fetched.priority == PriorityEnum.HIGH


@pytest.mark.asyncio
async def test_repository_list_and_filters(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)

    c1 = Complaint(
        text="Electricity wire sparking dangerously near house.",
        location="Sector G-7/2, Street 10",
        category=CategoryEnum.ELECTRICITY,
        priority=PriorityEnum.HIGH,
        status=StatusEnum.OPEN,
    )
    c2 = Complaint(
        text="Garbage heap lying on empty plot for several days.",
        location="Sector I-8/1, Street 25",
        category=CategoryEnum.SANITATION,
        priority=PriorityEnum.NORMAL,
        status=StatusEnum.IN_PROGRESS,
    )
    c3 = Complaint(
        text="Streetlight broken outside street 14 mosque.",
        location="Sector F-10/2, Street 14",
        category=CategoryEnum.STREETLIGHTS,
        priority=PriorityEnum.LOW,
        status=StatusEnum.RESOLVED,
    )

    await repo.create(c1)
    await repo.create(c2)
    await repo.create(c3)

    # Test unfiltered list
    all_complaints, total = await repo.list_complaints(skip=0, limit=10)
    assert total == 3
    assert len(all_complaints) == 3

    # Test category filter
    elec_list, total_elec = await repo.list_complaints(category=CategoryEnum.ELECTRICITY)
    assert total_elec == 1
    assert elec_list[0].category == CategoryEnum.ELECTRICITY

    # Test status filter
    in_prog_list, total_prog = await repo.list_complaints(status=StatusEnum.IN_PROGRESS)
    assert total_prog == 1
    assert in_prog_list[0].status == StatusEnum.IN_PROGRESS

    # Test priority filter
    high_list, total_high = await repo.list_complaints(priority=PriorityEnum.HIGH)
    assert total_high == 1
    assert high_list[0].priority == PriorityEnum.HIGH


@pytest.mark.asyncio
async def test_repository_get_stats(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)

    c1 = Complaint(
        text="Water leakage outside corner shop.",
        location="Sector G-9/1",
        category=CategoryEnum.WATER,
        priority=PriorityEnum.HIGH,
        status=StatusEnum.OPEN,
    )
    c2 = Complaint(
        text="Sanitation problem with dirty gutter overflow.",
        location="Sector G-9/2",
        category=CategoryEnum.SANITATION,
        priority=PriorityEnum.NORMAL,
        status=StatusEnum.OPEN,
    )

    await repo.create(c1)
    await repo.create(c2)

    stats = await repo.get_stats()
    assert stats["total"] == 2
    assert stats["by_status"].get("open") == 2
    assert stats["by_category"].get("water") == 1
    assert stats["by_category"].get("sanitation") == 1
    assert stats["by_priority"].get("high") == 1
    assert stats["by_priority"].get("normal") == 1


@pytest.mark.asyncio
async def test_repository_exists_methods(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    cid = uuid.uuid4()
    unique_text = "Unique description for testing exists query."

    c = Complaint(
        id=cid,
        text=unique_text,
        location="Sector E-7",
        category=CategoryEnum.OTHER,
        priority=PriorityEnum.LOW,
        status=StatusEnum.OPEN,
    )
    await repo.create(c)

    assert await repo.exists_by_id(cid) is True
    assert await repo.exists_by_id(uuid.uuid4()) is False
    assert await repo.exists_by_text(unique_text) is True
    assert await repo.exists_by_text("Non-existent text here") is False
