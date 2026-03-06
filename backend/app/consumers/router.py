"""Consumer API endpoints -- downstream engines use these to pull normalized data."""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_, func
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND

from app.auth.credentials import WorkspaceUserDep
from app.db.dependencies import AsyncDBSession
from app.db.models import Consumer as ConsumerModel, DataRecord, BaseCampSchema
from app.consumers.models import (
    ConsumerCreate,
    ConsumerRead,
    ConsumerUpdate,
    ChangeFeedResponse,
    SchemaRegistryEntry,
)

router = APIRouter(prefix="", tags=["consumers"])


def _model_to_read(c: ConsumerModel) -> ConsumerRead:
    return ConsumerRead(
        id=c.id,
        workspace_id=c.workspace_id,
        name=c.name,
        description=c.description,
        callback_url=c.callback_url,
        schema_ids=c.schema_ids or [],
        mapping_profile_id=c.mapping_profile_id,
        active=c.active,
        api_key=c.api_key,
        last_poll=c.last_poll.isoformat() if c.last_poll else None,
        created_at=c.created_at.isoformat() if c.created_at else "",
        updated_at=c.updated_at.isoformat() if c.updated_at else "",
    )


@router.get("/")
async def list_consumers(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
) -> list[ConsumerRead]:
    """List all registered consumers."""
    stmt = (
        select(ConsumerModel)
        .where(ConsumerModel.workspace_id == str(role.workspace_id))
        .order_by(ConsumerModel.created_at.desc())
    )
    result = await session.execute(stmt)
    return [_model_to_read(c) for c in result.scalars().all()]


@router.post("/", status_code=HTTP_201_CREATED)
async def create_consumer(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    data: ConsumerCreate,
) -> ConsumerRead:
    """Register a new consumer. Returns an API key for the change feed."""
    consumer = ConsumerModel(
        workspace_id=str(role.workspace_id),
        name=data.name,
        description=data.description,
        callback_url=data.callback_url,
        schema_ids=data.schema_ids,
        mapping_profile_id=data.mapping_profile_id,
        active=data.active,
        api_key=f"bc_{secrets.token_urlsafe(32)}",
    )
    session.add(consumer)
    await session.flush()
    await session.refresh(consumer)
    return _model_to_read(consumer)


@router.get("/{consumer_id}")
async def get_consumer(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    consumer_id: str,
) -> ConsumerRead:
    """Get consumer details."""
    stmt = select(ConsumerModel).where(
        and_(
            ConsumerModel.workspace_id == str(role.workspace_id),
            ConsumerModel.id == consumer_id,
        )
    )
    result = await session.execute(stmt)
    consumer = result.scalar_one_or_none()
    if not consumer:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Consumer not found")
    return _model_to_read(consumer)


@router.patch("/{consumer_id}")
async def update_consumer(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    consumer_id: str,
    data: ConsumerUpdate,
) -> ConsumerRead:
    """Update consumer settings."""
    stmt = select(ConsumerModel).where(
        and_(
            ConsumerModel.workspace_id == str(role.workspace_id),
            ConsumerModel.id == consumer_id,
        )
    )
    result = await session.execute(stmt)
    consumer = result.scalar_one_or_none()
    if not consumer:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Consumer not found")

    if data.name is not None:
        consumer.name = data.name
    if data.description is not None:
        consumer.description = data.description
    if data.callback_url is not None:
        consumer.callback_url = data.callback_url
    if data.schema_ids is not None:
        consumer.schema_ids = data.schema_ids
    if data.mapping_profile_id is not None:
        consumer.mapping_profile_id = data.mapping_profile_id
    if data.active is not None:
        consumer.active = data.active

    await session.flush()
    await session.refresh(consumer)
    return _model_to_read(consumer)


@router.delete("/{consumer_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_consumer(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    consumer_id: str,
) -> None:
    """Unregister a consumer."""
    stmt = select(ConsumerModel).where(
        and_(
            ConsumerModel.workspace_id == str(role.workspace_id),
            ConsumerModel.id == consumer_id,
        )
    )
    result = await session.execute(stmt)
    consumer = result.scalar_one_or_none()
    if not consumer:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Consumer not found")
    await session.delete(consumer)
    await session.flush()


@router.get("/{consumer_id}/feed")
async def change_feed(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    consumer_id: str,
    cursor: str | None = Query(default=None, description="ISO timestamp cursor from previous poll"),
    limit: int = Query(default=100, ge=1, le=1000),
    schema_id: str | None = Query(default=None),
) -> ChangeFeedResponse:
    """Pull new records since last cursor (change feed pattern).

    Downstream engines poll this endpoint to get new normalized data.
    First call: omit cursor to get latest records.
    Subsequent calls: pass the cursor from the previous response.
    """
    stmt_consumer = select(ConsumerModel).where(
        and_(
            ConsumerModel.workspace_id == str(role.workspace_id),
            ConsumerModel.id == consumer_id,
        )
    )
    result = await session.execute(stmt_consumer)
    consumer = result.scalar_one_or_none()
    if not consumer:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Consumer not found")

    conditions = [DataRecord.workspace_id == str(role.workspace_id)]

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            conditions.append(DataRecord.created_at > cursor_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor format (expected ISO timestamp)")

    if schema_id:
        conditions.append(DataRecord.schema_id == schema_id)
    elif consumer.schema_ids:
        conditions.append(DataRecord.schema_id.in_(consumer.schema_ids))

    stmt = (
        select(DataRecord)
        .where(and_(*conditions))
        .order_by(DataRecord.created_at.asc())
        .limit(limit + 1)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    has_more = len(records) > limit
    records = records[:limit]

    consumer.last_poll = datetime.utcnow()
    await session.flush()

    new_cursor = records[-1].created_at.isoformat() if records else (cursor or "")

    return ChangeFeedResponse(
        records=[
            {
                "id": r.id,
                "schema_id": r.schema_id,
                "data": r.data,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
        cursor=new_cursor,
        has_more=has_more,
        count=len(records),
    )


@router.get("/registry/schemas")
async def schema_registry(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
) -> list[SchemaRegistryEntry]:
    """List all schemas available for consumption with record counts.

    Downstream engines use this to discover what data is available.
    """
    stmt = (
        select(
            BaseCampSchema,
            func.count(DataRecord.id).label("record_count"),
        )
        .outerjoin(DataRecord, DataRecord.schema_id == BaseCampSchema.id)
        .where(BaseCampSchema.workspace_id == str(role.workspace_id))
        .group_by(BaseCampSchema.id)
        .order_by(BaseCampSchema.name)
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        SchemaRegistryEntry(
            id=schema.id,
            name=schema.name,
            description=schema.description,
            version=schema.version,
            fields=schema.fields if isinstance(schema.fields, list) else [],
            record_count=count,
        )
        for schema, count in rows
    ]
