"""
Triage provider interface and implementations.

Defines the TriageResult schema and TriageProvider Protocol, adhering to the
clean architecture rule: outbound integrations sit behind interfaces in providers/.
"""

import time
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.models.complaint import CategoryEnum, PriorityEnum


class TriageResult(BaseModel):
    """Structured output expected from any triage provider."""

    category: CategoryEnum = Field(
        ...,
        description="Assigned municipal complaint category.",
    )
    priority: PriorityEnum = Field(
        ...,
        description="Assigned urgency/priority level.",
    )
    ai_summary: str = Field(
        ...,
        max_length=140,
        description="Concise one-line summary (up to 140 characters).",
    )
    triaged_by: str = Field(
        ...,
        description="Identifier of the provider or fallback engine (e.g. 'rules', 'llm:simulated').",
    )
    triage_latency_ms: int = Field(
        ...,
        ge=0,
        description="Latency of the triage inference in milliseconds.",
    )


@runtime_checkable
class TriageProvider(Protocol):
    """Protocol that all AI / rule triage providers must implement."""

    async def triage(self, text: str, location: str) -> TriageResult:
        """Classify and summarize an incoming complaint."""
        ...


class RuleBasedTriageProvider:
    """
    Deterministic rule-based triage provider.
    Used for local testing, fallback, and environments without active LLM credentials.
    """

    def __init__(self, provider_id: str = "rules") -> None:
        self.provider_id = provider_id

    async def triage(self, text: str, location: str) -> TriageResult:
        start_time = time.perf_counter()
        lower_text = text.lower()

        # Keyword mapping for municipal domains
        if any(w in lower_text for w in ["water", "pani", "pipe", "leak", "tanker", "fajr", "flooding", "sewer", "gutter", "drain"]):
            if any(w in lower_text for w in ["sewer", "gutter", "drain", "kachra", "garbage", "trash", "sanitation"]):
                category = CategoryEnum.SANITATION
            else:
                category = CategoryEnum.WATER
        elif any(w in lower_text for w in ["bijli", "electricity", "transformer", "spark", "current", "wire", "voltage", "power", "load shedding"]):
            category = CategoryEnum.ELECTRICITY
        elif any(w in lower_text for w in ["kachra", "garbage", "waste", "trash", "sanitation", "filth", "dump"]):
            category = CategoryEnum.SANITATION
        elif any(w in lower_text for w in ["road", "pothole", "gaddha", "asphalt", "traffic", "crater", "tyre", "accident"]):
            category = CategoryEnum.ROADS
        elif any(w in lower_text for w in ["streetlight", "light", "lamp", "andhera", "dark", "pole"]):
            category = CategoryEnum.STREETLIGHTS
        else:
            category = CategoryEnum.OTHER

        # Priority heuristics
        if any(w in lower_text for w in ["urgent", "danger", "burst", "spark", "sparking", "hazard", "khata", "emergency", "severe", "life"]):
            priority = PriorityEnum.HIGH
        elif any(w in lower_text for w in ["low", "minor", "delay", "cosmetic"]):
            priority = PriorityEnum.LOW
        else:
            priority = PriorityEnum.NORMAL

        # Create concise summary under 140 characters
        summary = f"{category.value.capitalize()} issue reported at {location}: {text[:80].strip()}"
        if len(summary) > 137:
            summary = summary[:137] + "..."

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return TriageResult(
            category=category,
            priority=priority,
            ai_summary=summary,
            triaged_by=self.provider_id,
            triage_latency_ms=latency_ms,
        )


class SimulatedTriageProvider(RuleBasedTriageProvider):
    """Simulated provider that behaves deterministically for test suites."""

    def __init__(self) -> None:
        super().__init__(provider_id="llm:simulated")
