"""
Ollama triage provider for fully offline local containerized inference.

Implements Assignment Section 2.5 requirements:
- Fully offline zero-dependency path (runs in Docker Compose).
- Zero external API keys, zero external network calls, zero PII transmission.
- Same TriageProvider interface.
- 10-second timeout and structured JSON output validation.
"""

import asyncio
import logging
import random

import httpx

from app.core.config import get_settings
from app.providers.triage.base import (
    TriageError,
    TriageRateLimitError,
    TriageResult,
    TriageServerError,
    TriageTimeoutError,
)
from app.providers.triage.guardrails import (
    SYSTEM_PROMPT,
    build_triage_user_prompt,
    extract_and_validate_triage_json,
)

logger = logging.getLogger(__name__)


class OllamaTriage:
    """Offline local containerized triage provider using Ollama REST API."""

    def __init__(
        self,
        name: str = "ollama",
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        settings = get_settings()
        self.name = name
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        # Enforce hard cap of 10.0s requirement
        self.timeout_seconds = min(float(timeout_seconds or settings.OLLAMA_TIMEOUT_SECONDS), 10.0)

    async def triage(self, text: str, location: str) -> TriageResult:
        """
        Classify complaint using local Ollama model with timeout and structured JSON format.

        Raises:
            TriageTimeoutError: On 10s timeout after retry.
            TriageServerError: If Ollama container returns 5xx.
            TriageValidationError: On malformed JSON output.
        """
        user_content = build_triage_user_prompt(text=text, location=location)

        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "options": {
                "temperature": 0.1,
            },
        }

        endpoint = f"{self.base_url}/api/chat"
        timeout = httpx.Timeout(self.timeout_seconds, connect=4.0)

        # Attempt 1, followed by at most 1 jittered retry strictly on timeout, 429, or 5xx
        max_attempts = 2
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(
                        "Ollama triage call to %s (model: %s, attempt: %d)",
                        endpoint,
                        self.model,
                        attempt,
                    )
                    response = await client.post(endpoint, json=payload)

                    # HTTP 429 Rate Limit (RETRYABLE)
                    if response.status_code == 429:
                        raise TriageRateLimitError(
                            f"Ollama rate limit exceeded (HTTP 429): {response.text[:100]}",
                            provider=self.name,
                        )

                    # HTTP 5xx Server Error (RETRYABLE)
                    if response.status_code >= 500:
                        raise TriageServerError(
                            f"Ollama server error (HTTP {response.status_code})",
                            provider=self.name,
                        )

                    # Any other error code >= 400: NEVER RETRY
                    if response.status_code >= 400:
                        raise TriageError(
                            f"Ollama returned non-retryable HTTP {response.status_code}",
                            provider=self.name,
                        )

                    data = response.json()
                    raw_content = data.get("message", {}).get("content", "")

                    return extract_and_validate_triage_json(raw_content, provider_name=self.name)

                except (TimeoutError, httpx.TimeoutException) as exc:
                    # Timeout (RETRYABLE)
                    last_error = TriageTimeoutError(
                        f"Ollama request timed out after {self.timeout_seconds:.1f}s: {exc}",
                        provider=self.name,
                    )
                except (TriageRateLimitError, TriageServerError) as exc:
                    # HTTP 429 or 5xx (RETRYABLE)
                    last_error = exc
                except Exception as exc:
                    # Everything else (e.g. connection errors, client 4xx, validation error): NO RETRY
                    raise exc

                if attempt < max_attempts:
                    jitter = random.uniform(0.1, 0.3)
                    sleep_time = 0.4 + jitter
                    logger.warning(
                        "Ollama call failed on attempt 1 (%s). Retrying in %.2fs...",
                        last_error,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)

        if last_error:
            raise last_error
        raise TriageError("Ollama triage failed with unknown state", provider=self.name)


# Alias for backward compatibility
OllamaTriageProvider = OllamaTriage
