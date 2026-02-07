"""Observability middleware for Base Camp OS."""

import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.metrics import (
    request_count,
    request_latency,
    active_connections,
)
from app.observability.logging import (
    get_logger,
    set_correlation_id,
    get_correlation_id,
)

logger = get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics for HTTP requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Track active connections
        active_connections.inc()
        
        # Get endpoint path (normalize to avoid high cardinality)
        path = request.url.path
        method = request.method
        
        # Normalize paths with IDs to reduce metric cardinality
        normalized_path = self._normalize_path(path)
        
        # Record request timing
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            # Calculate duration
            duration = time.perf_counter() - start_time
            
            # Record metrics
            request_count.labels(
                method=method,
                endpoint=normalized_path,
                status_code=str(status_code)
            ).inc()
            
            request_latency.labels(
                method=method,
                endpoint=normalized_path
            ).observe(duration)
            
            # Decrease active connections
            active_connections.dec()
        
        return response
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality by replacing IDs with placeholders."""
        parts = path.split("/")
        normalized_parts = []
        
        for part in parts:
            # Replace UUIDs with placeholder
            if self._is_uuid(part):
                normalized_parts.append("{id}")
            # Replace numeric IDs with placeholder
            elif part.isdigit():
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)
        
        return "/".join(normalized_parts)
    
    def _is_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request logging with correlation IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Set correlation ID in context
        set_correlation_id(correlation_id)
        
        # Extract request info
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Log request start
        logger.info(
            "Request started",
            extra={
                "http_method": method,
                "http_path": path,
                "http_query": query,
                "client_ip": client_host,
                "user_agent": user_agent,
                "correlation_id": correlation_id,
            }
        )
        
        # Process request
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request completion
            logger.info(
                "Request completed",
                extra={
                    "http_method": method,
                    "http_path": path,
                    "http_status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                }
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "http_method": method,
                    "http_path": path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                },
                exc_info=True
            )
            raise
