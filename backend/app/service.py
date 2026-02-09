"""Base service classes."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.types import Role


class _KwargsLogger:
    """Thin wrapper that turns keyword args into structured log `extra` fields
    so that the stdlib logger + JSON formatter emit them correctly."""

    def __init__(self, logger: logging.Logger):
        self._log = logger

    def _fmt(self, msg: str, kwargs: dict) -> str:
        if kwargs:
            parts = " ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{msg} | {parts}"
        return msg

    def info(self, msg: str, **kw):
        self._log.info(self._fmt(msg, kw))

    def warning(self, msg: str, **kw):
        self._log.warning(self._fmt(msg, kw))

    def error(self, msg: str, **kw):
        self._log.error(self._fmt(msg, kw))

    def debug(self, msg: str, **kw):
        self._log.debug(self._fmt(msg, kw))


class BaseWorkspaceService:
    """Base service for workspace-scoped operations."""

    service_name: str = "base"

    def __init__(self, session: AsyncSession, role: Role | None = None):
        self.session = session
        self.role = role
        self.workspace_id = role.workspace_id if role else None
        self.logger = _KwargsLogger(logging.getLogger(f"app.{self.service_name}"))

