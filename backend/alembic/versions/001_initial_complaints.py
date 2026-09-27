"""Create initial complaints table with constraints and indexes

Revision ID: 001_initial_complaints
Revises: 
Create Date: 2026-09-27 15:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_complaints"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "complaints",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("reporter_contact", sa.String(length=255), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "water",
                "electricity",
                "sanitation",
                "roads",
                "streetlights",
                "other",
                name="complaint_category",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "high",
                "normal",
                "low",
                name="complaint_priority",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "in_progress",
                "resolved",
                "rejected",
                name="complaint_status",
                native_enum=False,
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column("ai_summary", sa.String(length=140), nullable=True),
        sa.Column("triaged_by", sa.String(length=50), nullable=True),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(text) >= 10 AND length(text) <= 2000",
            name="ck_complaints_text_length",
        ),
        sa.CheckConstraint(
            "length(location) >= 3 AND length(location) <= 200",
            name="ck_complaints_location_length",
        ),
    )

    # Required composite index for status/priority queries
    op.create_index(
        "ix_complaints_status_priority",
        "complaints",
        ["status", "priority"],
        unique=False,
    )

    # Required index for timestamp ordering and pagination queries
    op.create_index(
        "ix_complaints_created_at",
        "complaints",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
