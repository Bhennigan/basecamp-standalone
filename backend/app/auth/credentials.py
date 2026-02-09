"""Authentication credentials and access control."""

from typing import Optional, Annotated
from fastapi import Depends, Header, HTTPException
import uuid

from app.auth.types import Role


def get_workspace_role(
    x_workspace_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
    x_service_id: str = Header(default=None),
) -> Role:
    """Extract role from request headers.
    
    For standalone mode, we use a default workspace if not specified.
    """
    # In standalone mode, use default values if not provided
    workspace_id = uuid.UUID(x_workspace_id) if x_workspace_id != "default" else uuid.UUID("00000000-0000-0000-0000-000000000000")
    
    user_id = None
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            user_id = None
    
    is_service = x_service_id is not None
    
    return Role(
        user_id=user_id,
        workspace_id=workspace_id,
        service_id=x_service_id,
        is_service=is_service,
    )


class RoleACL:
    """Role-based access control dependency factory."""
    
    def __init__(
        self,
        allow_user: bool = True,
        allow_service: bool = True,
        allow_executor: bool = False,
        require_workspace: str = "yes",
    ):
        self.allow_user = allow_user
        self.allow_service = allow_service
        self.allow_executor = allow_executor
        self.require_workspace = require_workspace


# Create a dependency for workspace-scoped role
WorkspaceUserDep = Annotated[Role, Depends(get_workspace_role)]
