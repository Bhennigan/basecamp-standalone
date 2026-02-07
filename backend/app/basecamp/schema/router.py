"""Schema router for Base Camp OS."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from app.auth.credentials import WorkspaceUserDep
from app.basecamp.enums import SchemaStatus
from app.basecamp.schema.service import SchemaService
from app.basecamp.schemas import (
    BaseCampSchemaCreate,
    BaseCampSchemaRead,
    BaseCampSchemaReadMinimal,
    BaseCampSchemaUpdate,
    SchemaInferRequest,
    SchemaInferResponse,
)
from app.db.dependencies import AsyncDBSession
from app.exceptions import TracecatNotFoundError

router = APIRouter(prefix="", tags=["basecamp"])


@router.get("")
async def list_schemas(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    status: SchemaStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[BaseCampSchemaReadMinimal]:
    """List all schemas for the workspace."""
    service = SchemaService(session, role)
    return await service.list_schemas(
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{schema_id}")
async def get_schema(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    schema_id: uuid.UUID,
) -> BaseCampSchemaRead:
    """Get a specific schema by ID."""
    service = SchemaService(session, role)
    try:
        return await service.get_schema(schema_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Schema {schema_id} not found",
        )


@router.post("", status_code=HTTP_201_CREATED)
async def create_schema(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    data: BaseCampSchemaCreate,
) -> BaseCampSchemaRead:
    """Create a new schema."""
    service = SchemaService(session, role)
    return await service.create_schema(data)


@router.patch("/{schema_id}")
async def update_schema(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    schema_id: uuid.UUID,
    data: BaseCampSchemaUpdate,
) -> BaseCampSchemaRead:
    """Update an existing schema."""
    service = SchemaService(session, role)
    try:
        return await service.update_schema(schema_id, data)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Schema {schema_id} not found",
        )


@router.delete("/{schema_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_schema(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    schema_id: uuid.UUID,
) -> None:
    """Delete a schema."""
    service = SchemaService(session, role)
    try:
        await service.delete_schema(schema_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Schema {schema_id} not found",
        )


@router.post("/infer")
async def infer_schema(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    data: SchemaInferRequest,
) -> SchemaInferResponse:
    """Infer a schema from sample data."""
    service = SchemaService(session, role)
    return await service.infer_schema(data)
