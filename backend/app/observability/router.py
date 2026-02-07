"""Prometheus metrics endpoint router for Base Camp OS."""

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
    REGISTRY,
)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/metrics/health")
async def metrics_health() -> dict:
    """Health check for the metrics endpoint.
    
    Returns:
        dict: Health status of the metrics system
    """
    return {
        "status": "healthy",
        "metrics_enabled": True,
        "endpoint": "/metrics"
    }
