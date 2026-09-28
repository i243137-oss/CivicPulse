"""
Triage provider factory.

Instantiates the active TriageProvider implementation based on runtime configuration.
Supports LLMTriage, OllamaTriage, RuleBasedTriage, and SimulatedTriage.
"""

import logging

from app.core.config import get_settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage

logger = logging.getLogger(__name__)


def create_triage_provider(provider_name: str | None = None) -> TriageProvider:
    """
    Factory creating a TriageProvider instance based on TRIAGE_PROVIDER environment setting.

    Options:
    - 'llm': Hosted LLM via OpenAI-compatible endpoint.
    - 'ollama': Offline local containerized model.
    - 'rules': Zero-dependency deterministic keyword rules.
    - 'simulated': Deterministic test fake with failure injection for CI.
    """
    settings = get_settings()
    selected = (provider_name or settings.TRIAGE_PROVIDER).lower().strip()

    if selected == "llm":
        logger.info("Initializing LLMTriage provider (model: %s)", settings.LLM_MODEL)
        return LLMTriage()
    elif selected == "ollama":
        logger.info("Initializing OllamaTriage provider (base_url: %s)", settings.OLLAMA_BASE_URL)
        return OllamaTriage()
    elif selected == "rules":
        logger.info("Initializing RuleBasedTriage provider")
        return RuleBasedTriage()
    elif selected == "simulated":
        logger.info("Initializing SimulatedTriage provider")
        return SimulatedTriage()
    else:
        logger.warning(
            "Unknown TRIAGE_PROVIDER '%s'. Defaulting to SimulatedTriage.",
            selected,
        )
        return SimulatedTriage()
