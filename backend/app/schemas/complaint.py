"""
Pydantic schemas for Complaint request validation and response serialization.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.complaint import CategoryEnum, PriorityEnum, StatusEnum


class ComplaintCreate(BaseModel):
    """Schema for submitting a new complaint."""

    text: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed description of the issue (10–2000 characters).",
        examples=["Water pipeline broke near Street 12, clean water flooding the street since morning."],
    )
    location: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Location of the issue (3–200 characters).",
        examples=["Sector F-7/2, Street 12, Islamabad"],
    )
    reporter_contact: str | None = Field(
        default=None,
        max_length=255,
        description="Optional contact information of the reporter.",
        examples=["+923001234567"],
    )
    category: CategoryEnum | None = Field(
        default=None,
        description="Optional pre-assigned category; auto-triaged if omitted.",
    )
    priority: PriorityEnum | None = Field(
        default=None,
        description="Optional pre-assigned priority; auto-triaged if omitted.",
    )


class ComplaintStatusUpdate(BaseModel):
    """Schema for updating complaint status according to the state machine."""

    status: StatusEnum = Field(
        ...,
        description="Target status to transition the complaint into.",
        examples=[StatusEnum.IN_PROGRESS],
    )


class ComplaintResponse(BaseModel):
    """Schema representing a single serialized complaint."""

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None = None
    category: CategoryEnum
    priority: PriorityEnum
    status: StatusEnum
    ai_summary: str | None = None
    triaged_by: str | None = None
    triage_latency_ms: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplaintListResponse(BaseModel):
    """Paginated list of complaints."""

    items: list[ComplaintResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ComplaintStatsResponse(BaseModel):
    """Aggregated complaint statistics."""

    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
