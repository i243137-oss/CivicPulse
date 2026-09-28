"""
Complaint repository.

All SQL and persistence operations for complaints live strictly within this repository.
No SQL or direct database queries exist outside repositories.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import (
    CategoryEnum,
    Complaint,
    PriorityEnum,
    StatusEnum,
)


class ComplaintRepository:
    """Repository handling all database interactions for Complaint entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, complaint: Complaint) -> Complaint:
        """Persist a new complaint to the database."""
        self.session.add(complaint)
        await self.session.flush()
        await self.session.refresh(complaint)
        return complaint

    async def get_by_id(self, complaint_id: uuid.UUID) -> Complaint | None:
        """Retrieve a complaint by its unique UUID."""
        statement = select(Complaint).where(Complaint.id == complaint_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_complaints(
        self,
        category: CategoryEnum | None = None,
        priority: PriorityEnum | None = None,
        status: StatusEnum | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Complaint], int]:
        """
        List complaints with optional filtering and pagination.
        Ordered by created_at DESC (servicing query via ix_complaints_created_at).
        Filter by status and priority (servicing query via ix_complaints_status_priority).
        """
        # Base filter conditions
        conditions = []
        if category is not None:
            conditions.append(Complaint.category == category)
        if priority is not None:
            conditions.append(Complaint.priority == priority)
        if status is not None:
            conditions.append(Complaint.status == status)

        # Count total matching rows
        count_stmt = select(func.count(Complaint.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Query paginated rows
        query_stmt = select(Complaint)
        if conditions:
            query_stmt = query_stmt.where(*conditions)
        query_stmt = query_stmt.order_by(Complaint.created_at.desc()).offset(skip).limit(limit)

        rows_result = await self.session.execute(query_stmt)
        complaints = list(rows_result.scalars().all())

        return complaints, total

    async def update(self, complaint: Complaint) -> Complaint:
        """Update an existing complaint."""
        await self.session.flush()
        await self.session.refresh(complaint)
        return complaint

    async def get_stats(self) -> dict[str, Any]:
        """
        Calculate aggregated statistics:
        - Total count
        - Breakdown by status
        - Breakdown by category
        - Breakdown by priority
        """
        # Total count
        total_stmt = select(func.count(Complaint.id))
        total = (await self.session.execute(total_stmt)).scalar_one()

        # Group by status
        status_stmt = select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)
        status_rows = (await self.session.execute(status_stmt)).all()
        by_status = {
            s.value if isinstance(s, StatusEnum) else str(s): count for s, count in status_rows
        }

        # Group by category
        cat_stmt = select(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category)
        cat_rows = (await self.session.execute(cat_stmt)).all()
        by_category = {
            c.value if isinstance(c, CategoryEnum) else str(c): count for c, count in cat_rows
        }

        # Group by priority
        prio_stmt = select(Complaint.priority, func.count(Complaint.id)).group_by(
            Complaint.priority
        )
        prio_rows = (await self.session.execute(prio_stmt)).all()
        by_priority = {
            p.value if isinstance(p, PriorityEnum) else str(p): count for p, count in prio_rows
        }

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "by_priority": by_priority,
        }

    async def exists_by_text(self, text: str) -> bool:
        """Check if a complaint with the exact text exists (used for idempotent seeding)."""
        stmt = select(func.count(Complaint.id)).where(Complaint.text == text)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def exists_by_id(self, complaint_id: uuid.UUID) -> bool:
        """Check if a complaint with the given UUID exists."""
        stmt = select(func.count(Complaint.id)).where(Complaint.id == complaint_id)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0
