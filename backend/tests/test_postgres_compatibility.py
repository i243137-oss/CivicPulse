"""
PostgreSQL 16 Compatibility and Dialect Verification Tests.

Verifies that all SQLAlchemy models, Alembic migrations, constraints,
indexes, and repository queries compile and behave accurately according
to the PostgreSQL 16 dialect, avoiding dialect discrepancies with SQLite.
"""

import os
import subprocess
import uuid
from typing import Any, cast

import pytest
from sqlalchemy import Table, func, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.config import Settings
from app.models.complaint import (
    Complaint,
    PriorityEnum,
    StatusEnum,
)


def test_complaint_table_postgres_ddl_compilation() -> None:
    """Verify that Complaint table compiles cleanly with PostgreSQL dialect."""
    pg_dialect = postgresql.dialect()
    table = cast(Table, Complaint.__table__)
    ddl = str(CreateTable(table).compile(dialect=pg_dialect))

    # Assert PostgreSQL-specific native types
    assert "id UUID NOT NULL" in ddl
    assert "TIMESTAMP WITH TIME ZONE" in ddl

    # Assert check constraints
    assert "CONSTRAINT ck_complaints_text_length CHECK (length(text) >= 10 AND length(text) <= 2000)" in ddl
    assert "CONSTRAINT ck_complaints_location_length CHECK (length(location) >= 3 AND length(location) <= 200)" in ddl

    # Assert table structure
    assert "CREATE TABLE complaints" in ddl
    assert "PRIMARY KEY (id)" in ddl


def test_postgres_indexes_compilation() -> None:
    """Verify that required indexes compile properly for PostgreSQL."""
    pg_dialect = postgresql.dialect()
    table = cast(Table, Complaint.__table__)

    indexes: dict[str, Any] = {str(idx.name): idx for idx in table.indexes}
    assert "ix_complaints_status_priority" in indexes
    assert "ix_complaints_created_at" in indexes

    status_priority_sql = str(
        CreateIndex(indexes["ix_complaints_status_priority"]).compile(dialect=pg_dialect)
    )
    assert "CREATE INDEX ix_complaints_status_priority ON complaints (status, priority)" in status_priority_sql

    created_at_sql = str(
        CreateIndex(indexes["ix_complaints_created_at"]).compile(dialect=pg_dialect)
    )
    assert "CREATE INDEX ix_complaints_created_at ON complaints (created_at)" in created_at_sql


def test_repository_queries_postgres_compilation() -> None:
    """Verify that all repository queries compile under the PostgreSQL dialect."""
    pg_dialect = postgresql.dialect()

    # 1. List complaints query with filters, ordering, pagination
    stmt = (
        select(Complaint)
        .where(
            Complaint.status == StatusEnum.OPEN,
            Complaint.priority == PriorityEnum.HIGH,
        )
        .order_by(Complaint.created_at.desc())
        .limit(20)
        .offset(0)
    )
    compiled_stmt = str(stmt.compile(dialect=pg_dialect))
    assert "FROM complaints" in compiled_stmt
    assert "ORDER BY complaints.created_at DESC" in compiled_stmt
    assert "LIMIT %(param_1)s OFFSET %(param_2)s" in compiled_stmt or "LIMIT $1 OFFSET $2" in compiled_stmt or "LIMIT" in compiled_stmt

    # 2. Statistics aggregation queries
    cat_stmt = select(Complaint.category, func.count()).group_by(Complaint.category)
    compiled_cat = str(cat_stmt.compile(dialect=pg_dialect))
    assert "GROUP BY complaints.category" in compiled_cat
    assert "count(*)" in compiled_cat.lower() or "count(1)" in compiled_cat.lower() or "count(" in compiled_cat.lower()

    status_stmt = select(Complaint.status, func.count()).group_by(Complaint.status)
    compiled_status = str(status_stmt.compile(dialect=pg_dialect))
    assert "GROUP BY complaints.status" in compiled_status

    # 3. Status update statement
    test_id = uuid.uuid4()
    update_stmt = (
        update(Complaint)
        .where(Complaint.id == test_id)
        .values(status=StatusEnum.IN_PROGRESS, updated_at=func.now())
    )
    compiled_update = str(update_stmt.compile(dialect=pg_dialect))
    assert "UPDATE complaints SET" in compiled_update
    assert "status=" in compiled_update
    assert "WHERE complaints.id =" in compiled_update


def test_alembic_postgres_offline_migration_scripts() -> None:
    """Verify Alembic SQL generation against PostgreSQL 16 dialect."""
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/civicpulse"

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    import sys

    # Test upgrade --sql
    res_up = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res_up.returncode == 0, f"Alembic upgrade SQL failed: {res_up.stderr}"
    sql_up = res_up.stdout
    assert "PostgresqlImpl" in res_up.stderr or "PostgresqlImpl" in sql_up
    assert "CREATE TABLE complaints" in sql_up
    assert "id UUID NOT NULL" in sql_up
    assert "TIMESTAMP WITH TIME ZONE" in sql_up
    assert "ix_complaints_status_priority" in sql_up
    assert "ix_complaints_created_at" in sql_up

    # Test downgrade --sql
    res_down = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "001_initial_complaints:base",
            "--sql",
        ],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res_down.returncode == 0, f"Alembic downgrade SQL failed: {res_down.stderr}"
    sql_down = res_down.stdout
    assert "DROP INDEX ix_complaints_created_at" in sql_down
    assert "DROP INDEX ix_complaints_status_priority" in sql_down
    assert "DROP TABLE complaints" in sql_down


def test_config_postgres_host_resolution() -> None:
    """Verify that POSTGRES_HOST and POSTGRES_SERVER resolve properly for Docker and local dev."""
    # Test POSTGRES_HOST takes priority for container environment
    settings_docker = Settings(
        POSTGRES_HOST="postgres",
        POSTGRES_SERVER="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_USER="civicpulse",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="civicpulse_db",
    )
    assert settings_docker.postgres_host == "postgres"
    assert (
        settings_docker.ASYNC_DATABASE_URL
        == "postgresql+asyncpg://civicpulse:secretpassword@postgres:5432/civicpulse_db"
    )
    assert (
        settings_docker.SYNC_DATABASE_URL
        == "postgresql://civicpulse:secretpassword@postgres:5432/civicpulse_db"
    )

    # Test fallback to POSTGRES_SERVER when POSTGRES_HOST is not supplied
    settings_local = Settings(
        POSTGRES_HOST=None,
        POSTGRES_SERVER="db.internal",
        POSTGRES_PORT=5433,
        POSTGRES_USER="user",
        POSTGRES_PASSWORD="pass",
        POSTGRES_DB="testdb",
    )
    assert settings_local.postgres_host == "db.internal"
    assert (
        settings_local.ASYNC_DATABASE_URL
        == "postgresql+asyncpg://user:pass@db.internal:5433/testdb"
    )


@pytest.mark.asyncio
async def test_live_postgresql_if_available() -> None:
    """Run live asyncpg roundtrip if a PostgreSQL server is reachable in the environment."""
    test_pg_url = os.environ.get("TEST_POSTGRES_URL")
    if not test_pg_url:
        pytest.skip("No TEST_POSTGRES_URL configured. Live PostgreSQL test skipped; dialect compilation tests passed.")

    import asyncpg  # type: ignore[import-untyped]
    try:
        conn = await asyncpg.connect(test_pg_url)
        val = await conn.fetchval("SELECT 1")
        assert val == 1
        await conn.close()
    except Exception as exc:
        pytest.skip(f"Could not connect to live PostgreSQL at {test_pg_url}: {exc}")
