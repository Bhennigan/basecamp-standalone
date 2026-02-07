"""Ingestion router for Base Camp OS."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from app.auth.credentials import WorkspaceUserDep

from app.basecamp.enums import DataSourceType, IngestionState
from app.basecamp.ingestion.service import IngestionService
from app.basecamp.schemas import (
    DataSourceCreate,
    DataSourceRead,
    DataSourceReadMinimal,
    DataSourceUpdate,
    IngestionJobRead,
    IngestionJobReadMinimal,
    IngestionUploadResponse,
)
from app.db.dependencies import AsyncDBSession
from app.exceptions import TracecatNotFoundError

router = APIRouter(prefix="", tags=["basecamp"])

# Removed - using WorkspaceUserDep from credentials
# WorkspaceUser = Annotated[
# Role,
# RoleACL(
#     allow_user=True,
#     allow_service=True,
#     require_workspace="yes",
# ),
# ]


# --- File Upload ---


@router.post("/upload", status_code=HTTP_201_CREATED)
async def upload_file(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    file: UploadFile = File(...),
    source_id: uuid.UUID | None = Query(default=None),
    schema_id: uuid.UUID | None = Query(default=None),
) -> IngestionUploadResponse:
    """Upload a file for ingestion.

    Supported formats: JSON, CSV, Excel (.xlsx, .xls)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    service = IngestionService(session, role)
    return await service.upload_file(
        content=content,
        filename=file.filename,
        source_id=source_id,
        schema_id=schema_id,
    )


# --- Data Sources ---


@router.get("/sources")
async def list_sources(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    source_type: DataSourceType | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[DataSourceReadMinimal]:
    """List all data sources for the workspace."""
    service = IngestionService(session, role)
    return await service.list_sources(
        source_type=source_type,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.get("/sources/{source_id}")
async def get_source(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    source_id: uuid.UUID,
) -> DataSourceRead:
    """Get a data source by ID."""
    service = IngestionService(session, role)
    try:
        return await service.get_source(source_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Source not found"
        ) from None


@router.post("/sources", status_code=HTTP_201_CREATED)
async def create_source(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    params: DataSourceCreate,
) -> DataSourceRead:
    """Create a new data source."""
    service = IngestionService(session, role)
    return await service.create_source(params)


@router.patch("/sources/{source_id}")
async def update_source(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    source_id: uuid.UUID,
    params: DataSourceUpdate,
) -> DataSourceRead:
    """Update a data source."""
    service = IngestionService(session, role)
    try:
        return await service.update_source(source_id, params)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Source not found"
        ) from None


@router.delete("/sources/{source_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_source(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    source_id: uuid.UUID,
) -> None:
    """Delete a data source."""
    service = IngestionService(session, role)
    try:
        await service.delete_source(source_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Source not found"
        ) from None


# --- Ingestion Jobs ---


@router.get("/jobs")
async def list_jobs(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    source_id: uuid.UUID | None = Query(default=None),
    state: IngestionState | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[IngestionJobReadMinimal]:
    """List ingestion jobs for the workspace."""
    service = IngestionService(session, role)
    return await service.list_jobs(
        source_id=source_id,
        state=state,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}")
async def get_job(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    job_id: uuid.UUID,
) -> IngestionJobRead:
    """Get an ingestion job by ID."""
    service = IngestionService(session, role)
    try:
        return await service.get_job(job_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Job not found"
        ) from None
