"""
Hosted LLM triage provider with structured output, timeout, and jittered retry.

Implements Assignment Section 2.5 requirements:
- Calls an OpenAI-compatible hosted LLM API (Groq, Gemini, etc.).
- Enforces strict 10-second request timeout.
- Performs one jittered retry on timeout, HTTP 429, or HTTP 5xx only.
- Never retries HTTP 400.
- Requests structured JSON output and validates against TriageResult schema.
- Treats user text as untrusted input with prompt-injection guardrails.
- Never logs API keys.
"""

import asyncio
import logging
import random
import time

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


class LLMTriage:
    """Production AI triage provider calling an OpenAI-compatible endpoint."""

    def __init__(
        self,
        name: str = "llm",
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        settings = get_settings()
        self.name = name
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout_seconds = min(float(timeout_seconds or settings.LLM_TIMEOUT_SECONDS), 10.0)

    async def triage(self, text: str, location: str) -> TriageResult:
        """
        Classify complaint using hosted LLM with timeout, single retry, and validation.

        Raises:
            TriageTimeoutError: On 10s timeout after retry.
            TriageRateLimitError: On HTTP 429 after retry.
            TriageServerError: On HTTP 5xx after retry.
            TriageValidationError: On malformed or non-conforming model output (not retried).
            TriageError: If missing API key or client error (HTTP 400, not retried).
        """
        if not self.api_key:
            raise TriageError("Missing LLM_API_KEY for hosted provider", provider=self.name)

        user_content = build_triage_user_prompt(text=text, location=location)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/chat/completions"
        timeout = httpx.Timeout(self.timeout_seconds, connect=5.0)

        # Attempt 1, followed by at most 1 jittered retry strictly on timeout, 429, or 5xx
        max_attempts = 2
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(
                        "LLM triage call to %s (model: %s, attempt: %d)",
                        self.base_url,
                        self.model,
                        attempt,
                    )
                    start_time = time.perf_counter()
                    response = await client.post(endpoint, json=payload, headers=headers)
                    elapsed = time.perf_counter() - start_time

                    # HTTP 429 Rate Limit (RETRYABLE)
                    if response.status_code == 429:
                        raise TriageRateLimitError(
                            f"LLM provider rate limit exceeded (HTTP 429): {response.text[:100]}",
                            provider=self.name,
                        )

                    # HTTP 5xx Server Error (RETRYABLE)
                    if response.status_code >= 500:
                        raise TriageServerError(
                            f"LLM provider server error (HTTP {response.status_code})",
                            provider=self.name,
                        )

                    # Any other error code >= 400 (e.g. 400, 401, 403, 404): NEVER RETRY
                    if response.status_code >= 400:
                        raise TriageError(
                            f"LLM provider returned non-retryable HTTP {response.status_code}: {response.text[:200]}",
                            provider=self.name,
                        )

                    data = response.json()
                    raw_content = data["choices"][0]["message"]["content"]
                    logger.debug("LLM raw response (%.2fs): %.100s", elapsed, raw_content)

                    # Validate structured output
                    return extract_and_validate_triage_json(raw_content, provider_name=self.name)

                except (TimeoutError, httpx.TimeoutException) as exc:
                    # Timeout (RETRYABLE)
                    last_error = TriageTimeoutError(
                        f"LLM request timed out after {self.timeout_seconds:.1f}s: {exc}",
                        provider=self.name,
                    )
                except (TriageRateLimitError, TriageServerError) as exc:
                    # HTTP 429 or 5xx (RETRYABLE)
                    last_error = exc
                except Exception as exc:
                    # Everything else (e.g. connection errors, 400, validation error): NO RETRY
                    raise exc

                # If this was attempt 1 and error is retryable, perform jittered sleep
                if attempt < max_attempts:
                    jitter = random.uniform(0.1, 0.4)
                    sleep_time = 0.5 + jitter
                    logger.warning(
                        "LLM triage call failed on attempt 1 (%s). Retrying in %.2fs with jitter...",
                        last_error,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)

        # Exhausted retry attempts
        if last_error:
            raise last_error
        raise TriageError("LLM triage failed with unknown state", provider=self.name)


# Alias for backward compatibility
LLMTriageProvider = LLMTriage
