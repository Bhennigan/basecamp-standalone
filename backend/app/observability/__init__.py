"""Observability module for Base Camp OS.

Provides metrics, logging, and middleware for monitoring the application.
"""

from app.observability.metrics import (
    request_count,
    request_latency,
    active_connections,
    entities_processed,
    ingestion_jobs,
    enrichment_operations,
)
from app.observability.middleware import MetricsMiddleware, LoggingMiddleware
from app.observability.router import router as metrics_router
from app.observability.logging import setup_logging, get_logger

__all__ = [
    "request_count",
    "request_latency",
    "active_connections",
    "entities_processed",
    "ingestion_jobs",
    "enrichment_operations",
    "MetricsMiddleware",
    "LoggingMiddleware",
    "metrics_router",
    "setup_logging",
    "get_logger",
]
