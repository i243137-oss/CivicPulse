"""
Base schemas, protocols, and exceptions for CivicPulse AI triage providers.

Follows Assignment Section 2.5:
- TriageResult schema exactly matching required fields: category, priority, summary, confidence.
- TriageProvider Protocol defining the pluggable interface.
- Standard exception hierarchy for timeouts, rate limits, server errors, and validation errors.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from app.models.complaint import CategoryEnum, PriorityEnum


class TriageError(Exception):
    """Base class for all triage provider failures."""

    def __init__(self, message: str, provider: str | None = None):
        super().__init__(message)
        self.provider = provider


class TriageTimeoutError(TriageError):
    """Raised when an AI provider call exceeds the 10-second hard cap timeout."""


class TriageRateLimitError(TriageError):
    """Raised when an AI provider returns HTTP 429 Too Many Requests."""


class TriageServerError(TriageError):
    """Raised when an AI provider returns HTTP 5xx Server Error."""


class TriageValidationError(TriageError):
    """Raised when AI provider output is malformed, invalid JSON, or fails schema validation."""


class TriageResult(BaseModel):
    """
    Structured output schema for municipal complaint triage.

    Exactly implements Assignment Section 2.5:
    - category: CategoryEnum (water, electricity, sanitation, roads, streetlights, other)
    - priority: PriorityEnum (low, medium, high, critical)
    - summary: str (concise one-line summary, max 140 chars)
    - confidence: float (0.0 to 1.0)
    """

    category: CategoryEnum = Field(
        ...,
        description="Classified municipal category.",
    )
    priority: PriorityEnum = Field(
        ...,
        description="Assigned urgency level.",
    )
    summary: str = Field(
        ...,
        max_length=140,
        description="Concise one-line summary (maximum 140 characters).",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_data(cls, data: dict) -> dict:
        """Normalize summary alias, priority mappings, and category casing."""
        if isinstance(data, dict):
            if "summary" not in data and "ai_summary" in data:
                data["summary"] = data["ai_summary"]
            # Map 'critical' urgency to PriorityEnum.HIGH, 'medium' to PriorityEnum.NORMAL
            if "priority" in data and isinstance(data["priority"], str):
                p = data["priority"].lower().strip()
                if p == "critical":
                    data["priority"] = PriorityEnum.HIGH
                elif p == "medium":
                    data["priority"] = PriorityEnum.NORMAL
                else:
                    data["priority"] = p
            if "category" in data and isinstance(data["category"], str):
                data["category"] = data["category"].lower().strip()
            # Enforce max 140 characters if model exceeds limit slightly
            if "summary" in data and isinstance(data["summary"], str) and len(data["summary"]) > 140:
                data["summary"] = data["summary"][:137] + "..."
        return data

    @property
    def ai_summary(self) -> str:
        """Compatibility accessor matching the complaint table column name."""
        return self.summary


@runtime_checkable
class TriageProvider(Protocol):
    """Protocol defining the interface for all CivicPulse triage providers."""

    name: str

    async def triage(self, text: str, location: str) -> TriageResult:
        """
        Classify and summarize an incoming municipal complaint.

        Args:
            text: Complaint description text submitted by the citizen.
            location: Municipal location string (street/sector/city).

        Returns:
            TriageResult: Validated structured triage result.

        Raises:
            TriageTimeoutError: When provider call exceeds timeout.
            TriageRateLimitError: When provider returns HTTP 429.
            TriageServerError: When provider returns HTTP 5xx.
            TriageValidationError: When provider output fails schema validation.
            TriageError: For other unrecoverable provider failures.
        """
        ...
