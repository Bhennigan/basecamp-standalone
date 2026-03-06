"""Ingestion service for Base Camp OS."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select

from app.basecamp.enums import DataSourceType, FileFormat, IngestionState
from app.basecamp.ingestion.parsers.csv_parser import CSVParser
from app.basecamp.ingestion.parsers.excel_parser import ExcelParser
from app.basecamp.ingestion.parsers.json_parser import JSONParser
from app.basecamp.schemas import (
    DataSourceCreate,
    DataSourceRead,
    DataSourceReadMinimal,
    DataSourceUpdate,
    IngestionJobRead,
    IngestionJobReadMinimal,
    IngestionUploadResponse,
)
from app.basecamp.types import ParseResult
from app.db.models import DataRecord, DataSource, IngestionJob
from app.exceptions import TracecatNotFoundError, TracecatValidationError
from app.service import BaseWorkspaceService


class IngestionService(BaseWorkspaceService):
    """Service for data ingestion and source management."""

    service_name = "basecamp_ingestion"

    # --- Data Source Management ---

    async def list_sources(
        self,
        *,
        source_type: DataSourceType | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DataSourceReadMinimal]:
        """List all data sources for the workspace."""
        conditions = [DataSource.workspace_id == self.workspace_id]

        if source_type:
            conditions.append(DataSource.source_type == source_type)
        if is_active is not None:
            conditions.append(DataSource.is_active == is_active)

        stmt = (
            select(DataSource)
            .where(and_(*conditions))
            .order_by(DataSource.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        sources = result.scalars().all()

        return [
            DataSourceReadMinimal(
                id=s.id,
                name=s.name,
                source_type=s.source_type,
                is_active=s.is_active,
            )
            for s in sources
        ]

    async def get_source(self, source_id: uuid.UUID) -> DataSourceRead:
        """Get a data source by ID."""
        source = await self._get_source_model(source_id)
        return self._source_to_read(source)

    async def create_source(self, params: DataSourceCreate) -> DataSourceRead:
        """Create a new data source."""
        source = DataSource(
            workspace_id=self.workspace_id,
            name=params.name,
            source_type=params.source_type,
            description=params.description,
            config=params.config,
            schema_id=params.schema_id,
            is_active=True,
        )

        self.session.add(source)
        await self.session.flush()
        await self.session.refresh(source)

        self.logger.info(
            "Created data source",
            source_id=str(source.id),
            name=source.name,
            source_type=source.source_type,
        )

        return self._source_to_read(source)

    async def update_source(
        self,
        source_id: uuid.UUID,
        params: DataSourceUpdate,
    ) -> DataSourceRead:
        """Update a data source."""
        source = await self._get_source_model(source_id)

        if params.name is not None:
            source.name = params.name
        if params.description is not None:
            source.description = params.description
        if params.config is not None:
            source.config = params.config
        if params.schema_id is not None:
            source.schema_id = params.schema_id
        if params.is_active is not None:
            source.is_active = params.is_active

        await self.session.flush()
        await self.session.refresh(source)

        self.logger.info("Updated data source", source_id=str(source_id))

        return self._source_to_read(source)

    async def delete_source(self, source_id: uuid.UUID) -> None:
        """Delete a data source."""
        source = await self._get_source_model(source_id)
        await self.session.delete(source)
        await self.session.flush()
        self.logger.info("Deleted data source", source_id=str(source_id))

    # --- Ingestion Jobs ---

    async def list_jobs(
        self,
        *,
        source_id: uuid.UUID | None = None,
        state: IngestionState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IngestionJobReadMinimal]:
        """List ingestion jobs for the workspace."""
        conditions = [IngestionJob.workspace_id == self.workspace_id]

        if source_id:
            conditions.append(IngestionJob.source_id == source_id)
        if state:
            conditions.append(IngestionJob.state == state)

        stmt = (
            select(IngestionJob)
            .where(and_(*conditions))
            .order_by(IngestionJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        return [
            IngestionJobReadMinimal(
                id=j.id,
                state=j.state,
                file_name=j.file_name,
                processed_records=j.processed_records,
                failed_records=j.failed_records,
                created_at=j.created_at,
                updated_at=j.updated_at,
            )
            for j in jobs
        ]

    async def get_job(self, job_id: uuid.UUID) -> IngestionJobRead:
        """Get an ingestion job by ID."""
        job = await self._get_job_model(job_id)
        return self._job_to_read(job)

    async def upload_file(
        self,
        content: bytes,
        filename: str,
        *,
        source_id: uuid.UUID | None = None,
        schema_id: uuid.UUID | None = None,
    ) -> IngestionUploadResponse:
        """Upload a file for ingestion."""
        file_format = self._detect_format(filename)

        job = IngestionJob(
            workspace_id=self.workspace_id,
            source_id=source_id,
            schema_id=schema_id,
            state=IngestionState.RECEIVED,
            file_name=filename,
            file_format=file_format,
            processed_records=0,
            failed_records=0,
        )

        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)

        self.logger.info(
            "Created ingestion job",
            job_id=str(job.id),
            filename=filename,
            format=file_format,
        )

        await self._process_file(job, content)

        return IngestionUploadResponse(
            job_id=job.id,
            message=f"File '{filename}' uploaded and processing started",
        )

    async def _process_file(self, job: IngestionJob, content: bytes) -> None:
        """Process an uploaded file through the ingestion pipeline."""
        try:
            job.state = IngestionState.ANALYZING
            job.started_at = datetime.utcnow()
            await self.session.flush()

            parse_result = self._parse_content(content, job.file_format, job.file_name)

            if parse_result.errors and all(
                e.severity == "error" for e in parse_result.errors
            ):
                job.state = IngestionState.FAILED
                job.error_message = "; ".join(
                    e.message for e in parse_result.errors[:5]
                )
                job.completed_at = datetime.utcnow()
                await self.session.flush()
                return

            job.total_records = parse_result.total_rows

            job.state = IngestionState.VALIDATING
            await self.session.flush()

            # Auto-create schema if needed
            schema_id = job.schema_id
            if not schema_id and parse_result.inferred_schema:
                from app.basecamp.schema.service import SchemaService

                schema_service = SchemaService(self.session, self.role)
                schema_name = f"auto_{job.file_name}_{str(job.id)[:8]}"
                schema = await schema_service.create_schema_from_inferred(
                    name=schema_name,
                    inferred_schema=parse_result.inferred_schema,
                    description=f"Auto-generated from {job.file_name}",
                )
                schema_id = schema.id
                job.schema_id = schema_id

            job.state = IngestionState.TRANSFORMING
            await self.session.flush()

            # Apply mapping profile if one exists for this target schema
            mappings = await self._get_mapping_for_schema(schema_id) if schema_id else None

            job.state = IngestionState.LOADING
            await self.session.flush()

            processed = 0
            failed = 0

            for parsed_record in parse_result.records:
                try:
                    record_data = parsed_record.data

                    if mappings:
                        from app.transform.engine import transform_record
                        record_data, _errors = transform_record(
                            record_data, mappings, drop_unmapped=False
                        )

                    record = DataRecord(
                        workspace_id=self.workspace_id,
                        schema_id=schema_id,
                        ingestion_job_id=job.id,
                        job_id=job.id,
                        data=record_data,
                    )
                    self.session.add(record)
                    processed += 1
                except Exception as e:
                    self.logger.warning(
                        "Failed to create record",
                        row=parsed_record.row_number,
                        error=str(e),
                    )
                    failed += 1

            await self.session.flush()

            job.state = IngestionState.COMPLETE
            job.processed_records = processed
            job.failed_records = failed
            job.completed_at = datetime.utcnow()
            await self.session.flush()

            self.logger.info(
                "Ingestion completed",
                job_id=str(job.id),
                processed=processed,
                failed=failed,
            )

            # Dispatch webhooks to consumers with callback URLs
            if processed > 0 and schema_id:
                try:
                    from app.consumers.webhooks import dispatch_webhooks

                    # Build lightweight record summaries for webhook payload
                    webhook_records = []
                    stmt = (
                        select(DataRecord)
                        .where(DataRecord.ingestion_job_id == job.id)
                        .limit(1000)
                    )
                    result = await self.session.execute(stmt)
                    for r in result.scalars().all():
                        webhook_records.append({
                            "id": r.id,
                            "schema_id": r.schema_id,
                            "data": r.data,
                            "created_at": r.created_at.isoformat(),
                        })

                    await dispatch_webhooks(
                        session=self.session,
                        workspace_id=str(self.workspace_id),
                        schema_id=str(schema_id),
                        records=webhook_records,
                    )
                except Exception as e:
                    self.logger.warning(
                        "Webhook dispatch failed (ingestion unaffected)",
                        error=str(e),
                    )

        except Exception as e:
            self.logger.error("Ingestion failed", job_id=str(job.id), error=str(e))
            job.state = IngestionState.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await self.session.flush()

    async def _get_mapping_for_schema(self, schema_id: str) -> list | None:
        """Find a mapping profile that targets this schema."""
        from app.db.models import MappingProfile as MappingProfileModel
        from app.transform.models import FieldMapping

        stmt = select(MappingProfileModel).where(
            and_(
                MappingProfileModel.workspace_id == self.workspace_id,
                MappingProfileModel.target_schema_id == schema_id,
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile and profile.mappings:
            return [FieldMapping(**m) for m in profile.mappings]
        return None

    # --- Helpers ---

    def _detect_format(self, filename: str) -> FileFormat:
        """Detect file format from filename."""
        lower_name = filename.lower()

        if lower_name.endswith(".json") or lower_name.endswith(".jsonl"):
            return FileFormat.JSON
        elif lower_name.endswith(".csv"):
            return FileFormat.CSV
        elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
            return FileFormat.EXCEL

        raise TracecatValidationError(
            f"Unsupported file format: {filename}. Supported: .json, .jsonl, .csv, .xlsx, .xls"
        )

    def _parse_content(
        self,
        content: bytes,
        file_format: FileFormat | None,
        filename: str | None,
    ) -> ParseResult:
        """Parse file content using appropriate parser."""
        if file_format == FileFormat.JSON:
            parser = JSONParser()
        elif file_format == FileFormat.CSV:
            parser = CSVParser()
        elif file_format == FileFormat.EXCEL:
            parser = ExcelParser()
        else:
            parser = JSONParser()

        return parser.parse(content, filename=filename)

    async def _get_source_model(self, source_id: uuid.UUID) -> DataSource:
        stmt = select(DataSource).where(
            and_(
                DataSource.workspace_id == self.workspace_id,
                DataSource.id == source_id,
            )
        )
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        if not source:
            raise TracecatNotFoundError(f"Data source {source_id} not found")
        return source

    async def _get_job_model(self, job_id: uuid.UUID) -> IngestionJob:
        stmt = select(IngestionJob).where(
            and_(
                IngestionJob.workspace_id == self.workspace_id,
                IngestionJob.id == job_id,
            )
        )
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            raise TracecatNotFoundError(f"Ingestion job {job_id} not found")
        return job

    def _source_to_read(self, source: DataSource) -> DataSourceRead:
        return DataSourceRead(
            id=source.id,
            name=source.name,
            source_type=source.source_type,
            description=source.description,
            config=source.config,
            schema_id=source.schema_id,
            is_active=source.is_active,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    def _job_to_read(self, job: IngestionJob) -> IngestionJobRead:
        return IngestionJobRead(
            id=job.id,
            source_id=job.source_id,
            schema_id=job.schema_id,
            state=job.state,
            file_name=job.file_name,
            file_format=job.file_format,
            total_records=job.total_records,
            processed_records=job.processed_records,
            failed_records=job.failed_records,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
