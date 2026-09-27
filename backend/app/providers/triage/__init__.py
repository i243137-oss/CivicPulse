"""
CivicPulse AI triage provider package.

Follows Assignment Section 5.7:
- app/providers/triage/{base,llm,ollama,rules,simulated,factory}.py
"""

from app.providers.triage.base import (
    TriageError,
    TriageProvider,
    TriageRateLimitError,
    TriageResult,
    TriageServerError,
    TriageTimeoutError,
    TriageValidationError,
)
from app.providers.triage.factory import create_triage_provider
from app.providers.triage.guardrails import (
    SYSTEM_PROMPT,
    build_triage_user_prompt,
    extract_and_validate_triage_json,
)
from app.providers.triage.llm import LLMTriage, LLMTriageProvider
from app.providers.triage.ollama import OllamaTriage, OllamaTriageProvider
from app.providers.triage.rules import RuleBasedTriage, RuleBasedTriageProvider
from app.providers.triage.simulated import SimulatedTriage, SimulatedTriageProvider

__all__ = [
    "TriageResult",
    "TriageProvider",
    "TriageError",
    "TriageTimeoutError",
    "TriageRateLimitError",
    "TriageServerError",
    "TriageValidationError",
    "LLMTriage",
    "LLMTriageProvider",
    "OllamaTriage",
    "OllamaTriageProvider",
    "RuleBasedTriage",
    "RuleBasedTriageProvider",
    "SimulatedTriage",
    "SimulatedTriageProvider",
    "create_triage_provider",
    "SYSTEM_PROMPT",
    "build_triage_user_prompt",
    "extract_and_validate_triage_json",
]
