"""Authentication types."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class Role:
    """User role with workspace context."""
    user_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    service_id: str | None = None
    is_service: bool = False
    
    @property
    def type(self) -> str:
        return "service" if self.is_service else "user"

