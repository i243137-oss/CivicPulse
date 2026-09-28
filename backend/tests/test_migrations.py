"""
Tests for Alembic database migrations.

Verifies:
- Migrations apply cleanly to an empty database (upgrade head)
- Required table, columns, and indexes are created
- Migrations reverse cleanly (downgrade -1 / base)
"""

import os
import tempfile

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_and_downgrade() -> None:
    # Create a temporary SQLite database file for testing migration upgrade/downgrade
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    sync_engine = None
    try:
        sync_url = f"sqlite:///{tmp_db_path}"
        async_url = f"sqlite+aiosqlite:///{tmp_db_path}"

        alembic_ini_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        )
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", async_url)

        # 1. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        # 2. Inspect created schema
        sync_engine = create_engine(sync_url)
        inspector = inspect(sync_engine)
        tables = inspector.get_table_names()
        assert "complaints" in tables

        # Verify columns
        columns = {col["name"] for col in inspector.get_columns("complaints")}
        required_columns = {
            "id",
            "text",
            "location",
            "reporter_contact",
            "category",
            "priority",
            "status",
            "ai_summary",
            "triaged_by",
            "triage_latency_ms",
            "created_at",
            "updated_at",
        }
        assert required_columns.issubset(columns)

        # Verify required indexes
        indexes = {idx["name"] for idx in inspector.get_indexes("complaints")}
        assert "ix_complaints_status_priority" in indexes
        assert "ix_complaints_created_at" in indexes

        # 3. Downgrade to base
        command.downgrade(alembic_cfg, "base")

        # Verify table dropped
        inspector_after = inspect(sync_engine)
        assert "complaints" not in inspector_after.get_table_names()

    finally:
        if sync_engine is not None:
            sync_engine.dispose()
        try:
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)
        except OSError:
            pass
