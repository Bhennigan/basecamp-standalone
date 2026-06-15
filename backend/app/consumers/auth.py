"""API key authentication for external consumers."""
from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app.db.dependencies import AsyncDBSession
from app.db.models import Consumer


def sha256hex(raw: str) -> str:
    """Hash a raw API key for storage/lookup. Never store the raw key."""
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_consumer_from_api_key(
    session: AsyncDBSession,
    authorization: str = Header(..., description="Bearer bc_xxx API key"),
) -> Consumer:
    """Authenticate an external consumer via API key.

    Usage: Authorization: Bearer bc_xxxxxxx
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header. Expected: Bearer <api_key>",
        )

    api_key = authorization[7:]  # Strip "Bearer "

    if not api_key.startswith("bc_"):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    stmt = select(Consumer).where(Consumer.api_key_hash == sha256hex(api_key))
    result = await session.execute(stmt)
    consumer = result.scalar_one_or_none()

    if not consumer:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not consumer.active:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Consumer is inactive",
        )

    return consumer


ConsumerAuthDep = Annotated[Consumer, Depends(get_consumer_from_api_key)]
