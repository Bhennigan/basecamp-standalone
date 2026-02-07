"""Database dependencies for FastAPI."""

from typing import Annotated, AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db


# Type alias for dependency injection
AsyncDBSession = Annotated[AsyncSession, Depends(get_db)]

