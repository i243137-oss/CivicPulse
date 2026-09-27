"""
Triage orchestration service with content-hash caching, fallback chain, and telemetry.

Implements Assignment Section 2.5 requirements:
- Content-hash caching in Redis with 24-hour TTL.
- Eliminates redundant inference for duplicate complaints.
- Deterministic fallback chain: falls back to RuleBasedTriage on any primary AI failure.
- Records triaged_by = 'rules:fallback' upon fallback.
- Records triage_latency_ms and maintains telemetry metrics.
- Enforces strict PII exclusion (only text and location are passed for classification).
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings
from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.rules import RuleBasedTriage

logger = logging.getLogger(__name__)


@dataclass
class TriageExecutionOutcome:
    """Metadata describing a completed triage execution."""
    result: TriageResult
    triaged_by: str
    triage_latency_ms: int
    cached: bool
    fallback_used: bool


class TriageService:
    """
    Coordinates complaint classification across caching, primary AI provider,
    and deterministic fallback.
    """

    CACHE_KEY_PREFIX = "civicpulse:triage:cache:"
    METRIC_HITS_KEY = "civicpulse:triage:metrics:hits"
    METRIC_MISSES_KEY = "civicpulse:triage:metrics:misses"

    def __init__(
        self,
        primary_provider: TriageProvider,
        fallback_provider: TriageProvider | None = None,
    ) -> None:
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider or RuleBasedTriage(name="rules")
        self._recent_outcomes: list[dict[str, Any]] = []

    def compute_content_hash(self, text: str, location: str) -> str:
        """Generate deterministic SHA-256 hash of normalized text and location."""
        normalized = f"{text.strip().lower()}|{location.strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def get_cached_result(self, redis: Redis | None, content_hash: str) -> TriageResult | None:
        """Lookup previously classified triage result from Redis cache."""
        if redis is None:
            return None

        key = f"{self.CACHE_KEY_PREFIX}{content_hash}"
        try:
            raw = await redis.get(key)
            if raw:
                data = json.loads(raw)
                await redis.incr(self.METRIC_HITS_KEY)
                logger.info("Triage cache HIT for content hash %s", content_hash[:12])
                return TriageResult.model_validate(data)
            await redis.incr(self.METRIC_MISSES_KEY)
        except Exception as exc:
            logger.warning("Redis triage cache read error (failing open): %s", exc)

        return None

    async def set_cached_result(
        self,
        redis: Redis | None,
        content_hash: str,
        result: TriageResult,
        ttl_seconds: int = 86400,
    ) -> None:
        """Cache triage result in Redis with 24-hour TTL."""
        if redis is None:
            return

        key = f"{self.CACHE_KEY_PREFIX}{content_hash}"
        try:
            payload = result.model_dump_json()
            await redis.set(key, payload, ex=ttl_seconds)
            logger.debug("Stored triage result in cache for hash %s (TTL: %ds)", content_hash[:12], ttl_seconds)
        except Exception as exc:
            logger.warning("Redis triage cache write error: %s", exc)

    async def execute_triage(
        self,
        text: str,
        location: str,
        redis: Redis | None = None,
    ) -> TriageExecutionOutcome:
        """
        Execute triage with caching, provider inference, and fallback.

        1. Check content-hash cache (24h TTL).
        2. On cache miss, execute primary AI provider.
        3. On failure/timeout, trigger fallback to RuleBasedTriage (triaged_by = 'rules:fallback').
        4. Cache successful result and record telemetry.
        """
        settings = get_settings()
        content_hash = self.compute_content_hash(text=text, location=location)

        # 1. Content-hash cache lookup
        if settings.TRIAGE_CACHE_ENABLED and redis is not None:
            cached_result = await self.get_cached_result(redis, content_hash)
            if cached_result is not None:
                outcome = TriageExecutionOutcome(
                    result=cached_result,
                    triaged_by=f"cache:{self.primary_provider.name}",
                    triage_latency_ms=1,
                    cached=True,
                    fallback_used=False,
                )
                self._record_telemetry(outcome, location)
                return outcome

        # 2. Primary provider execution
        start_time = time.perf_counter()
        fallback_used = False
        triaged_by = self.primary_provider.name
        result: TriageResult

        try:
            logger.info("Executing triage with primary provider: %s", self.primary_provider.name)
            result = await self.primary_provider.triage(text=text, location=location)
            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))

            # Cache successful primary inference
            if settings.TRIAGE_CACHE_ENABLED and redis is not None:
                await self.set_cached_result(
                    redis=redis,
                    content_hash=content_hash,
                    result=result,
                    ttl_seconds=settings.TRIAGE_CACHE_TTL,
                )

        except Exception as exc:
            # 3. Fallback chain: Primary AI provider failed
            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            fallback_used = True
            triaged_by = "rules:fallback"
            logger.warning(
                "Primary triage provider '%s' failed (%s) after %dms. Falling back to %s.",
                self.primary_provider.name,
                exc,
                latency_ms,
                self.fallback_provider.name,
            )

            # RuleBasedTriage is guaranteed never to raise
            result = await self.fallback_provider.triage(text=text, location=location)

        outcome = TriageExecutionOutcome(
            result=result,
            triaged_by=triaged_by,
            triage_latency_ms=latency_ms,
            cached=False,
            fallback_used=fallback_used,
        )
        self._record_telemetry(outcome, location)
        return outcome

    def _record_telemetry(self, outcome: TriageExecutionOutcome, location: str) -> None:
        """Record in-memory telemetry for recent triage executions."""
        entry = {
            "timestamp": time.time(),
            "triaged_by": outcome.triaged_by,
            "category": outcome.result.category.value,
            "priority": outcome.result.priority.value,
            "latency_ms": outcome.triage_latency_ms,
            "cached": outcome.cached,
            "fallback_used": outcome.fallback_used,
            "confidence": outcome.result.confidence,
        }
        self._recent_outcomes.append(entry)
        # Keep last 50 outcomes in memory
        if len(self._recent_outcomes) > 50:
            self._recent_outcomes = self._recent_outcomes[-50:]

    def get_recent_outcomes(self) -> list[dict[str, Any]]:
        """Return list of recent triage execution outcomes."""
        return list(self._recent_outcomes)

    async def get_cache_metrics(self, redis: Redis | None = None) -> dict[str, Any]:
        """Retrieve measured content-hash cache metrics (hits, misses, hit rate)."""
        hits = 0
        misses = 0

        if redis is not None:
            try:
                raw_hits = await redis.get(self.METRIC_HITS_KEY)
                raw_misses = await redis.get(self.METRIC_MISSES_KEY)
                hits = int(raw_hits) if raw_hits else 0
                misses = int(raw_misses) if raw_misses else 0
            except Exception as exc:
                logger.warning("Error fetching cache metrics from Redis: %s", exc)
        else:
            hits = sum(1 for o in self._recent_outcomes if o.get("cached"))
            misses = sum(1 for o in self._recent_outcomes if not o.get("cached"))

        total = hits + misses
        hit_rate = round(hits / total, 4) if total > 0 else 0.0

        return {
            "hits": hits,
            "misses": misses,
            "total_requests": total,
            "hit_rate": hit_rate,
        }

