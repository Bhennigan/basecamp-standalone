"""Tracecat integration router for Base Camp OS."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter
from starlette.status import HTTP_201_CREATED

from app.auth.credentials import WorkspaceUserDep
from app.basecamp.enums import IngestionState
from app.basecamp.schemas import (
    DataQueryRequest,
    TracecatIngestRequest,
    TracecatIngestResponse,
    TracecatQueryRequest,
    TracecatQueryResponse,
)
from app.basecamp.storage.service import DataRecordService
from app.db.dependencies import AsyncDBSession
from app.db.models import DataRecord, DataSource, IngestionJob
from app.service import BaseWorkspaceService

router = APIRouter(prefix="", tags=["basecamp"])


class TracecatIntegrationService(BaseWorkspaceService):
    """Service for Tracecat workflow integration."""

    service_name = "basecamp_integration"

    async def ingest_from_workflow(
        self,
        request: TracecatIngestRequest,
    ) -> TracecatIngestResponse:
        """Ingest data from a Tracecat workflow."""
        data_list = request.data if isinstance(request.data, list) else [request.data]

        job = IngestionJob(
            workspace_id=str(self.workspace_id),
            data_source_id=str(request.source_id) if request.source_id else None,
            schema_id=str(request.schema_id) if request.schema_id else None,
            state=IngestionState.RECEIVED,
            file_name="tracecat_workflow",
            file_format=None,
            record_count=len(data_list),
        )

        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)

        schema_id = request.schema_id
        if not schema_id and request.source_id:
            from sqlalchemy import select
            stmt = select(DataSource).where(DataSource.id == str(request.source_id))
            result = await self.session.execute(stmt)
            source = result.scalar_one_or_none()
            if source and source.schema_id:
                schema_id = source.schema_id

        job.state = IngestionState.COMPLETE
        await self.session.flush()

        return TracecatIngestResponse(
            job_id=job.id,
            records_received=len(data_list),
        )

    async def query_from_workflow(
        self,
        request: TracecatQueryRequest,
    ) -> TracecatQueryResponse:
        """Query data from a Tracecat workflow."""
        service = DataRecordService(self.session, self.role)

        query_request = DataQueryRequest(
            schema_id=request.schema_id,
            filters=request.filters,
            limit=request.limit,
            offset=0,
        )

        response = await service.query(query_request)

        return TracecatQueryResponse(
            records=[r.data for r in response.records],
            total_count=response.total_count,
        )


@router.post("/ingest", status_code=HTTP_201_CREATED)
async def ingest_from_workflow(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    request: TracecatIngestRequest,
) -> TracecatIngestResponse:
    """Webhook for ingesting data from Tracecat workflows."""
    service = TracecatIntegrationService(session, role)
    return await service.ingest_from_workflow(request)


@router.post("/query")
async def query_from_workflow(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    request: TracecatQueryRequest,
) -> TracecatQueryResponse:
    """Query endpoint for Tracecat workflows."""
    service = TracecatIntegrationService(session, role)
    return await service.query_from_workflow(request)
