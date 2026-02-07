"""Storage router for Base Camp OS."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from app.auth.credentials import WorkspaceUserDep
from app.basecamp.enums import FileFormat
from app.basecamp.schemas import (
    DataExportRequest,
    DataQueryRequest,
    DataQueryResponse,
    DataRecordCreate,
    DataRecordRead,
    DataRecordUpdate,
)
from app.basecamp.storage.service import DataRecordService
from app.db.dependencies import AsyncDBSession
from app.exceptions import TracecatNotFoundError

router = APIRouter(prefix="", tags=["basecamp"])


@router.get("/records")
async def list_records(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    schema_id: uuid.UUID | None = Query(default=None),
    job_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[DataRecordRead]:
    """List data records."""
    service = DataRecordService(session, role)
    return await service.list_records(
        schema_id=schema_id,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )


@router.get("/records/{record_id}")
async def get_record(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    record_id: uuid.UUID,
) -> DataRecordRead:
    """Get a data record by ID."""
    service = DataRecordService(session, role)
    try:
        return await service.get_record(record_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Record not found"
        ) from None


@router.post("/records", status_code=HTTP_201_CREATED)
async def create_record(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    params: DataRecordCreate,
) -> DataRecordRead:
    """Create a new data record."""
    service = DataRecordService(session, role)
    return await service.create_record(params)


@router.patch("/records/{record_id}")
async def update_record(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    record_id: uuid.UUID,
    params: DataRecordUpdate,
) -> DataRecordRead:
    """Update a data record."""
    service = DataRecordService(session, role)
    try:
        return await service.update_record(record_id, params)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Record not found"
        ) from None


@router.delete("/records/{record_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_record(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    record_id: uuid.UUID,
) -> None:
    """Delete a data record."""
    service = DataRecordService(session, role)
    try:
        await service.delete_record(record_id)
    except TracecatNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Record not found"
        ) from None


@router.post("/query")
async def query_records(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    request: DataQueryRequest,
) -> DataQueryResponse:
    """Query data records with filtering."""
    service = DataRecordService(session, role)
    return await service.query(request)


@router.post("/export")
async def export_records(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    request: DataExportRequest,
) -> Response:
    """Export data records to a file format."""
    service = DataRecordService(session, role)
    content = await service.export(request)

    if request.format == FileFormat.JSON:
        media_type = "application/json"
        filename = "export.json"
    elif request.format == FileFormat.CSV:
        media_type = "text/csv"
        filename = "export.csv"
    elif request.format == FileFormat.EXCEL:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "export.xlsx"
    else:
        media_type = "application/json"
        filename = "export.json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
