"""
Prometheus telemetry metrics for CivicPulse.

Implements Assignment Phase 8 requirements:
- HTTP request counters and latency histograms.
- AI triage request counters and inference latency histograms.
- Fallback invocation counters.
- Redis cache hit/miss request counters.
"""

from typing import Any

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Histogram


def _get_or_create_counter(
    name: str,
    documentation: str,
    labelnames: list[str],
    registry: CollectorRegistry = REGISTRY,
) -> Counter:
    """Safe getter or creator for Prometheus Counter."""
    names_to_collectors: dict[str, Any] = getattr(registry, "_names_to_collectors", {})
    if name in names_to_collectors:
        collector = names_to_collectors[name]
        if isinstance(collector, Counter):
            return collector
    return Counter(name, documentation, labelnames=labelnames, registry=registry)


def _get_or_create_histogram(
    name: str,
    documentation: str,
    labelnames: list[str],
    buckets: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry: CollectorRegistry = REGISTRY,
) -> Histogram:
    """Safe getter or creator for Prometheus Histogram."""
    names_to_collectors: dict[str, Any] = getattr(registry, "_names_to_collectors", {})
    if name in names_to_collectors:
        collector = names_to_collectors[name]
        if isinstance(collector, Histogram):
            return collector
    return Histogram(
        name,
        documentation,
        labelnames=labelnames,
        buckets=buckets,
        registry=registry,
    )


# 1. HTTP Traffic Metrics
HTTP_REQUESTS_TOTAL = _get_or_create_counter(
    name="civicpulse_http_requests_total",
    documentation="Total count of completed HTTP requests.",
    labelnames=["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = _get_or_create_histogram(
    name="civicpulse_http_request_duration_seconds",
    documentation="HTTP request latency in seconds.",
    labelnames=["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 2. AI Triage & Fallback Metrics
AI_TRIAGE_REQUESTS_TOTAL = _get_or_create_counter(
    name="civicpulse_ai_triage_requests_total",
    documentation="Total number of AI triage classification attempts.",
    labelnames=["provider", "status"],
)

AI_TRIAGE_DURATION_SECONDS = _get_or_create_histogram(
    name="civicpulse_ai_triage_duration_seconds",
    documentation="Latency of AI triage provider inference in seconds.",
    labelnames=["provider"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

AI_FALLBACK_TOTAL = _get_or_create_counter(
    name="civicpulse_ai_fallback_total",
    documentation="Count of times the triage service fell back to heuristic rules upon AI failure.",
    labelnames=["from_provider", "to_provider"],
)

# 3. Cache Performance Metrics
CACHE_REQUESTS_TOTAL = _get_or_create_counter(
    name="civicpulse_cache_requests_total",
    documentation="Total count of cache lookups categorized by hit or miss.",
    labelnames=["cache_type", "result"],
)
