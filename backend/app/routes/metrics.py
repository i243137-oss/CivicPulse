"""
Prometheus metrics scrape endpoint.

Exposes standard Prometheus text metrics format for cluster scrapers (e.g., Prometheus Operator).
"""

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Scrape Prometheus metrics",
    include_in_schema=True,
)
def get_metrics() -> Response:
    """
    Expose Prometheus text-formatted metrics.
    Includes HTTP traffic rates/latencies, AI triage durations, fallbacks, and cache performance.
    """
    metrics_data = generate_latest(REGISTRY)
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST,
    )
