"""
Simulated triage provider for deterministic CI/CD and testing.

Implements Assignment Section 2.5:
- Deterministic fake for CI: seeded, 0 network dependency.
- Configurable failure injection to verify timeout, rate limit, malformed JSON, and fallback behavior.
"""

from typing import Literal

from app.providers.triage.base import (
    TriageError,
    TriageRateLimitError,
    TriageResult,
    TriageServerError,
    TriageTimeoutError,
    TriageValidationError,
)
from app.providers.triage.rules import RuleBasedTriage

FailureMode = Literal[
    "timeout",
    "rate_limit",
    "server_error",
    "malformed_json",
    "always_raise",
]


class SimulatedTriage:
    """
    Deterministic simulated provider for local testing and CI pipeline verification.
    Supports failure injection to test resilience patterns and fallback chains.
    """

    def __init__(
        self,
        name: str = "llm:simulated",
        fail_mode: FailureMode | None = None,
    ) -> None:
        self.name = name
        self.fail_mode = fail_mode
        self._rules = RuleBasedTriage(name=name)

    def set_failure_mode(self, fail_mode: FailureMode | None) -> None:
        """Dynamically configure failure injection mode for testing."""
        self.fail_mode = fail_mode

    async def triage(self, text: str, location: str) -> TriageResult:
        """Execute simulated triage or raise configured failure."""
        if self.fail_mode == "timeout":
            raise TriageTimeoutError(
                f"Simulated AI call exceeded 10.0s timeout cap ({self.name})",
                provider=self.name,
            )
        elif self.fail_mode == "rate_limit":
            raise TriageRateLimitError(
                f"Simulated provider rate limit exceeded (HTTP 429) ({self.name})",
                provider=self.name,
            )
        elif self.fail_mode == "server_error":
            raise TriageServerError(
                f"Simulated provider upstream failure (HTTP 503) ({self.name})",
                provider=self.name,
            )
        elif self.fail_mode == "malformed_json":
            raise TriageValidationError(
                f"Simulated provider returned malformed JSON ({self.name})",
                provider=self.name,
            )
        elif self.fail_mode == "always_raise":
            raise TriageError(
                f"Simulated provider unhandled crash ({self.name})",
                provider=self.name,
            )

        # Base case: deterministic classification matching rules
        result = await self._rules.triage(text, location)
        return TriageResult(
            category=result.category,
            priority=result.priority,
            summary=result.summary,
            confidence=0.95,
        )


# Alias for backward compatibility
SimulatedTriageProvider = SimulatedTriage
