"""
Rule-based triage provider.

Implements Assignment Section 2.5:
- Deterministic keyword fallback.
- Always available, 0 network dependencies, never fails.
"""

from app.models.complaint import CategoryEnum, PriorityEnum
from app.providers.triage.base import TriageResult


class RuleBasedTriage:
    """
    Deterministic rule-based triage provider using municipal keyword heuristics.
    Serves as the zero-failure baseline and primary fallback provider.
    """

    def __init__(self, name: str = "rules") -> None:
        self.name = name

    async def triage(self, text: str, location: str) -> TriageResult:
        """Deterministically classify complaints based on domain vocabulary."""
        lower = text.lower()

        # Category heuristics
        if any(w in lower for w in ["water", "pani", "pipe", "burst main", "leak", "tanker", "flooding", "water supply"]):
            category = CategoryEnum.WATER
        elif any(w in lower for w in ["bijli", "electricity", "transformer", "spark", "current", "wire", "voltage", "power outage", "short circuit"]):
            category = CategoryEnum.ELECTRICITY
        elif any(w in lower for w in ["kachra", "garbage", "waste", "trash", "sanitation", "filth", "dump", "sewer", "gutter", "drain"]):
            category = CategoryEnum.SANITATION
        elif any(w in lower for w in ["road", "pothole", "gaddha", "asphalt", "crater", "broken road", "manhole cover"]):
            category = CategoryEnum.ROADS
        elif any(w in lower for w in ["streetlight", "street light", "light", "lamp", "andhera", "dark street", "pole light"]):
            category = CategoryEnum.STREETLIGHTS
        else:
            category = CategoryEnum.OTHER

        # Priority heuristics
        if any(w in lower for w in [
            "electrocution", "fire hazard", "gas leak", "life threatening", "severe injury",
            "urgent", "danger", "burst", "hazard", "spark", "sparking", "surge", "emergency", "flooding", "outage"
        ]):
            priority = PriorityEnum.HIGH
        elif any(w in lower for w in ["minor", "cosmetic", "suggestion", "delay"]):
            priority = PriorityEnum.LOW
        else:
            priority = PriorityEnum.NORMAL

        # Construct concise summary under 140 characters
        clean_text = " ".join(text.split())
        summary = f"{category.value.capitalize()} issue at {location}: {clean_text}"
        if len(summary) > 140:
            summary = summary[:137] + "..."

        return TriageResult(
            category=category,
            priority=priority,
            summary=summary,
            confidence=0.90,
        )


# Alias for backward compatibility
RuleBasedTriageProvider = RuleBasedTriage
