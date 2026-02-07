"""Audit middleware for automatic request logging"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .models import AuditAction
from .service import AuditService


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all API requests for audit purposes"""
    
    # Paths to exclude from audit logging
    EXCLUDED_PATHS = {
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/compliance/audit",
        "/api/compliance/integrity/verify",
        "/api/compliance/report"
    }
    
    # Map HTTP methods to audit actions
    METHOD_ACTION_MAP = {
        "GET": AuditAction.READ,
        "POST": AuditAction.CREATE,
        "PUT": AuditAction.UPDATE,
        "PATCH": AuditAction.UPDATE,
        "DELETE": AuditAction.DELETE
    }
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    def _should_log(self, path: str) -> bool:
        """Check if the request should be logged"""
        # Exclude static paths
        if path in self.EXCLUDED_PATHS:
            return False
        
        # Exclude paths that start with excluded prefixes
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False
        
        return True
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request, handling proxies"""
        # Check for forwarded headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _extract_resource_info(self, path: str) -> tuple[str, str]:
        """Extract resource type and ID from path"""
        parts = path.strip("/").split("/")
        
        # Skip api prefix
        if parts and parts[0] == "api":
            parts = parts[1:]
        
        resource_type = parts[0] if parts else "unknown"
        
        # Try to find resource ID (usually after resource type)
        resource_id = None
        if len(parts) >= 2:
            # Check if second part looks like an ID
            potential_id = parts[1]
            if potential_id and not potential_id.startswith("_"):
                resource_id = potential_id
        
        return resource_type, resource_id
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log audit entry"""
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Check if we should log this request
        if not self._should_log(request.url.path):
            return response
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Get audit action
        action = self.METHOD_ACTION_MAP.get(request.method, AuditAction.READ)
        
        # Extract resource info
        resource_type, resource_id = self._extract_resource_info(request.url.path)
        
        # Get user info from request state if available
        user_id = getattr(request.state, "user_id", None)
        user_email = getattr(request.state, "user_email", None)
        workspace_id = getattr(request.state, "workspace_id", "default-workspace")
        
        # Prepare audit details
        details = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user_agent": request.headers.get("User-Agent", "unknown")
        }
        
        # Log the audit entry asynchronously
        # Note: In production, this would use a background task or queue
        try:
            from app.db.database import async_session
            async with async_session() as db:
                service = AuditService(db)
                await service.log_action(
                    workspace_id=workspace_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=self._get_client_ip(request),
                    details=details
                )
        except Exception:
            # Audit logging failure should not break the request
            # In production, this would be logged to a fallback system
            pass
        
        return response
