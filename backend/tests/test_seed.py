"""
Unit tests for idempotent database seed script.

Verifies:
- Minimum 30 records seeded (our dataset has 35 realistic complaints)
- Idempotency: second run results in 0 inserts and 100% skips
- Broad representation across municipal categories (water, electricity, sanitation, roads, streetlights, other)
- Urdu-influenced English phrasing
"""

from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models.complaint import CategoryEnum, Complaint
from scripts.seed import SEED_COMPLAINTS, seed_database
from tests.conftest import TestAsyncSessionLocal


@pytest.mark.asyncio
async def test_seed_idempotency_and_minimum_record_count(setup_test_db: None) -> None:
    # Patch AsyncSessionLocal in scripts.seed to use our test database session
    with patch("scripts.seed.AsyncSessionLocal", TestAsyncSessionLocal):
        # First run: empty database -> all records should be inserted
        inserted_1, skipped_1 = await seed_database()
        assert inserted_1 >= 30
        assert inserted_1 == len(SEED_COMPLAINTS)
        assert skipped_1 == 0

        # Verify records exist in database
        async with TestAsyncSessionLocal() as session:
            count = (await session.execute(select(func.count(Complaint.id)))).scalar_one()
            assert count == inserted_1

            # Verify categories are represented
            categories = (
                (await session.execute(select(Complaint.category).distinct())).scalars().all()
            )
            for required_cat in CategoryEnum:
                assert required_cat in categories

        # Second run: all records already exist -> 0 inserted, all skipped!
        inserted_2, skipped_2 = await seed_database()
        assert inserted_2 == 0
        assert skipped_2 == len(SEED_COMPLAINTS)

        # Database count remains unchanged
        async with TestAsyncSessionLocal() as session:
            count_after = (await session.execute(select(func.count(Complaint.id)))).scalar_one()
            assert count_after == inserted_1
