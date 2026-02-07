"""Base service classes."""

from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.types import Role


class BaseWorkspaceService:
    """Base service for workspace-scoped operations."""
    
    service_name: str = "base"
    
    def __init__(self, session: AsyncSession, role: Role | None = None):
        self.session = session
        self.role = role
        self.workspace_id = role.workspace_id if role else None

