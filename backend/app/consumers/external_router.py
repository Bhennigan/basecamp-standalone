"""External API endpoints for downstream platforms.

Authenticate with: Authorization: Bearer <api_key>
No workspace headers required — the API key maps to a consumer and workspace.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_, func

from app.consumers.auth import ConsumerAuthDep
from app.db.dependencies import AsyncDBSession
from app.db.models import DataRecord, BaseCampSchema, MappingProfile
from app.consumers.models import ChangeFeedResponse, SchemaRegistryEntry
from app.transform.engine import transform_record
from app.transform.models import FieldMapping

router = APIRouter(prefix="", tags=["External API"])


@router.get("/feed")
async def external_feed(
    *,
    consumer: ConsumerAuthDep,
    session: AsyncDBSession,
    cursor: str | None = Query(default=None, description="ISO timestamp from previous response"),
    limit: int = Query(default=100, ge=1, le=1000),
    schema_id: str | None = Query(default=None, description="Filter to specific schema"),
) -> ChangeFeedResponse:
    """Pull normalized data since last cursor.

    First call: omit cursor to get latest records.
    Subsequent calls: pass cursor from previous response.
    """
    conditions = [DataRecord.workspace_id == consumer.workspace_id]

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            conditions.append(DataRecord.created_at > cursor_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor (expected ISO timestamp)")

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
    records = list(result.scalars().all())

    has_more = len(records) > limit
    records = records[:limit]

    # Update last_poll
    consumer.last_poll = datetime.utcnow()
    await session.flush()

    # Load egress mapping if consumer has one
    mapping_rules = None
    drop_unmapped = False
    if consumer.mapping_profile_id:
        stmt_mp = select(MappingProfile).where(MappingProfile.id == consumer.mapping_profile_id)
        mp_result = await session.execute(stmt_mp)
        profile = mp_result.scalar_one_or_none()
        if profile and profile.mappings:
            mapping_rules = [FieldMapping(**m) for m in profile.mappings]
            drop_unmapped = profile.drop_unmapped

    output_records = []
    for r in records:
        data = r.data
        if mapping_rules:
            data, _ = transform_record(data, mapping_rules, drop_unmapped)
        output_records.append({
            "id": r.id,
            "schema_id": r.schema_id,
            "data": data,
            "created_at": r.created_at.isoformat(),
        })

    new_cursor = records[-1].created_at.isoformat() if records else (cursor or "")

    return ChangeFeedResponse(
        records=output_records,
        cursor=new_cursor,
        has_more=has_more,
        count=len(output_records),
    )


@router.get("/schemas")
async def external_schema_registry(
    *,
    consumer: ConsumerAuthDep,
    session: AsyncDBSession,
) -> list[SchemaRegistryEntry]:
    """Discover available schemas and record counts."""
    stmt = (
        select(
            BaseCampSchema,
            func.count(DataRecord.id).label("record_count"),
        )
        .outerjoin(DataRecord, DataRecord.schema_id == BaseCampSchema.id)
        .where(BaseCampSchema.workspace_id == consumer.workspace_id)
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
