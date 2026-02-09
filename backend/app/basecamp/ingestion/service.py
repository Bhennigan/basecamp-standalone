"""Ingestion service for Base Camp OS."""

from __future__ import annotations

import json as json_lib
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
from app.db.models import DataRecord, DataSource, ExtractedEntity, IngestionJob
from app.exceptions import TracecatNotFoundError, TracecatValidationError
from app.service import BaseWorkspaceService

# Service imports for pipeline integrations
from app.enrichment.service import EnrichmentService
from app.enrichment.entities import Entity
from app.storage.minio_client import get_minio_client
from app.vectors.qdrant_client import VectorClient
from app.vectors.embeddings import EmbeddingGenerator
from app.graph.neo4j_client import Neo4jClient, get_neo4j_client
from app.graph.exporter import GraphExporter
from app.events.publisher import EventPublisher, get_event_publisher
from app.review.service import ReviewService


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
        """List all data sources for the workspace.

        Args:
            source_type: Optional filter by source type.
            is_active: Optional filter by active status.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of data source summaries.
        """
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
        """Get a data source by ID.

        Args:
            source_id: The data source ID.

        Returns:
            The data source details.

        Raises:
            TracecatNotFoundError: If source not found.
        """
        source = await self._get_source_model(source_id)
        return self._source_to_read(source)

    async def create_source(self, params: DataSourceCreate) -> DataSourceRead:
        """Create a new data source.

        Args:
            params: The source creation parameters.

        Returns:
            The created data source.
        """
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
        """Update a data source.

        Args:
            source_id: The data source ID.
            params: The update parameters.

        Returns:
            The updated data source.

        Raises:
            TracecatNotFoundError: If source not found.
        """
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
        """Delete a data source.

        Args:
            source_id: The data source ID.

        Raises:
            TracecatNotFoundError: If source not found.
        """
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
        """List ingestion jobs for the workspace.

        Args:
            source_id: Optional filter by source.
            state: Optional filter by state.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of job summaries.
        """
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
                created_at=j.created_at,
            )
            for j in jobs
        ]

    async def get_job(self, job_id: uuid.UUID) -> IngestionJobRead:
        """Get an ingestion job by ID.

        Args:
            job_id: The job ID.

        Returns:
            The job details.

        Raises:
            TracecatNotFoundError: If job not found.
        """
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
        """Upload a file for ingestion.

        Args:
            content: The file content.
            filename: The filename.
            source_id: Optional associated data source.
            schema_id: Optional schema to use.

        Returns:
            The upload response with job ID.
        """
        # Detect file format
        file_format = self._detect_format(filename)

        # Create ingestion job
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

        # Process the file
        await self._process_file(job, content)

        return IngestionUploadResponse(
            job_id=job.id,
            message=f"File '{filename}' uploaded and processing started",
        )

    async def _process_file(self, job: IngestionJob, content: bytes) -> None:
        """Process an uploaded file through the full pipeline.

        Pipeline stages:
        1. Parse file content
        2. Store raw file in MinIO
        3. Infer/validate schema
        4. Store DataRecords in PostgreSQL
        5. Extract & enrich entities
        6. Index vectors in Qdrant
        7. Export entities to Neo4j graph
        8. Publish events via NATS
        9. Queue low-confidence items for review

        Each integration is wrapped in try/except so a single service failure
        does not break the pipeline.
        """
        all_entities: list[Entity] = []

        try:
            # Update state to analyzing
            job.state = IngestionState.ANALYZING
            job.started_at = datetime.utcnow()
            await self.session.flush()

            # Parse the file
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
                # Publish failure event
                await self._publish_event_safe(
                    "failed", job=job, error_message=job.error_message
                )
                return

            job.total_records = parse_result.total_rows

            # ── Step 2: Store raw file in MinIO ──────────────────────────
            await self._store_raw_file(job, content)

            # Update state to validating
            job.state = IngestionState.VALIDATING
            await self.session.flush()

            # If no schema specified, try to infer or create one
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

            # Update state to transforming
            job.state = IngestionState.TRANSFORMING
            await self.session.flush()

            # Update state to loading
            job.state = IngestionState.LOADING
            await self.session.flush()

            # Create data records
            processed = 0
            failed = 0
            created_records: list[DataRecord] = []

            for parsed_record in parse_result.records:
                try:
                    record = DataRecord(
                        workspace_id=self.workspace_id,
                        schema_id=schema_id,
                        job_id=job.id,
                        data=parsed_record.data,
                    )
                    self.session.add(record)
                    created_records.append(record)
                    processed += 1
                except Exception as e:
                    self.logger.warning(
                        "Failed to create record",
                        row=parsed_record.row_number,
                        error=str(e),
                    )
                    failed += 1

            await self.session.flush()

            # ── Step 5: Entity extraction & enrichment ───────────────────
            all_entities = await self._extract_and_store_entities(
                created_records, job
            )

            # ── Step 6: Vector indexing in Qdrant ────────────────────────
            await self._index_vectors(all_entities)

            # ── Step 7: Export to Neo4j graph ────────────────────────────
            await self._export_to_graph(all_entities)

            # ── Step 9: Queue low-confidence entities for review ─────────
            await self._queue_for_review(all_entities, job)

            # Update job status
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
                entities_extracted=len(all_entities),
            )

            # ── Step 8: Publish success event via NATS ───────────────────
            await self._publish_event_safe("complete", job=job, record_count=processed)

        except Exception as e:
            self.logger.error("Ingestion failed", job_id=str(job.id), error=str(e))
            job.state = IngestionState.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await self.session.flush()
            await self._publish_event_safe(
                "failed", job=job, error_message=str(e)
            )

    # ── Pipeline integration helpers ─────────────────────────────────────

    async def _store_raw_file(self, job: IngestionJob, content: bytes) -> None:
        """Upload the original file to MinIO raw bucket."""
        try:
            minio = get_minio_client()
            object_name = f"{self.workspace_id}/{job.id}/{job.file_name}"
            content_type = "application/octet-stream"
            if job.file_name:
                if job.file_name.endswith(".csv"):
                    content_type = "text/csv"
                elif job.file_name.endswith(".json") or job.file_name.endswith(".jsonl"):
                    content_type = "application/json"
                elif job.file_name.endswith(".xlsx"):
                    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            minio.upload_bytes("raw", object_name, content, content_type=content_type)
            self.logger.info(
                "Stored raw file in MinIO",
                bucket="raw",
                object_name=object_name,
            )
        except Exception as e:
            self.logger.warning("MinIO upload failed — continuing without raw storage", error=str(e))

    async def _extract_and_store_entities(
        self, records: list[DataRecord], job: IngestionJob
    ) -> list[Entity]:
        """Extract entities from records, enrich, deduplicate, and store."""
        all_entities: list[Entity] = []
        try:
            raw_entities: list[Entity] = []
            source_label = f"ingestion:{job.file_name}"

            for record in records:
                try:
                    extracted = EnrichmentService.extract_entities(
                        record.data, source_label
                    )
                    for entity in extracted:
                        entity.source_record_id = record.id
                    raw_entities.extend(extracted)
                except Exception as e:
                    self.logger.warning(
                        "Entity extraction failed for record",
                        record_id=str(record.id),
                        error=str(e),
                    )

            # Deduplicate
            deduplicated = EnrichmentService.deduplicate_entities(raw_entities)

            # Enrich each entity
            for entity in deduplicated:
                entity = EnrichmentService.enrich_entity(entity)

            # Load existing entities for this workspace to handle upserts
            existing_stmt = select(ExtractedEntity).where(
                ExtractedEntity.workspace_id == self.workspace_id
            )
            existing_result = await self.session.execute(existing_stmt)
            existing_map: dict[str, ExtractedEntity] = {
                f"{e.entity_type}:{e.normalized_value}": e
                for e in existing_result.scalars().all()
            }

            # Store in PostgreSQL (upsert: update existing, insert new)
            for entity in deduplicated:
                try:
                    key = f"{entity.type}:{entity.normalized_value}"
                    existing = existing_map.get(key)
                    if existing:
                        # Update existing entity
                        existing.last_seen = entity.last_seen
                        existing.confidence = max(existing.confidence, entity.confidence)
                        if entity.threat_level:
                            existing.threat_level = entity.threat_level
                        existing.tags = list(set((existing.tags or []) + entity.tags))
                        existing.entity_metadata = {**(existing.entity_metadata or {}), **entity.metadata}
                        entity.id = existing.id
                    else:
                        db_entity = ExtractedEntity(
                            id=entity.id,
                            workspace_id=self.workspace_id,
                            entity_type=entity.type,
                            value=entity.value,
                            normalized_value=entity.normalized_value,
                            confidence=entity.confidence,
                            threat_level=entity.threat_level,
                            source=entity.source,
                            source_record_id=entity.source_record_id,
                            tags=entity.tags,
                            entity_metadata=entity.metadata,
                            first_seen=entity.first_seen,
                            last_seen=entity.last_seen,
                        )
                        self.session.add(db_entity)
                    all_entities.append(entity)
                except Exception as e:
                    self.logger.warning(
                        "Failed to store entity",
                        entity_value=entity.value,
                        error=str(e),
                    )

            await self.session.flush()
            self.logger.info(
                "Entities extracted and stored",
                raw_count=len(raw_entities),
                deduplicated_count=len(deduplicated),
                stored_count=len(all_entities),
            )
        except Exception as e:
            self.logger.warning("Entity enrichment pipeline failed", error=str(e))

        return all_entities

    async def _index_vectors(self, entities: list[Entity]) -> None:
        """Generate embeddings and upsert to Qdrant."""
        if not entities:
            return
        try:
            qdrant = VectorClient()
            embedder = EmbeddingGenerator()

            for entity in entities:
                try:
                    text = embedder.entity_to_text({
                        "type": entity.type,
                        "value": entity.value,
                        "tags": entity.tags,
                        "metadata": entity.metadata,
                    })
                    vector = embedder.generate(text)
                    payload = {
                        "entity_type": entity.type,
                        "value": entity.value,
                        "normalized_value": entity.normalized_value,
                        "threat_level": entity.threat_level,
                        "confidence": entity.confidence,
                        "workspace_id": self.workspace_id,
                        "tags": entity.tags,
                    }
                    await qdrant.upsert_entity(entity.id, vector, payload)
                except Exception as e:
                    self.logger.warning(
                        "Vector indexing failed for entity",
                        entity_id=entity.id,
                        error=str(e),
                    )

            self.logger.info("Vector indexing complete", count=len(entities))
        except Exception as e:
            self.logger.warning("Qdrant vector indexing failed", error=str(e))

    async def _export_to_graph(self, entities: list[Entity]) -> None:
        """Push entities and relationships to Neo4j."""
        if not entities:
            return
        try:
            neo4j = await get_neo4j_client()
            exporter = GraphExporter(neo4j)

            for entity in entities:
                try:
                    node_data = {
                        "id": str(entity.id),
                        "entity_type": entity.type,
                        "value": entity.value,
                        "normalized_value": entity.normalized_value,
                        "confidence": entity.confidence,
                        "threat_level": entity.threat_level,
                        "source": entity.source,
                        "workspace_id": str(self.workspace_id),
                        "tags": entity.tags,
                        "metadata": entity.metadata,
                    }
                    await neo4j.create_entity_node(node_data)
                except Exception as e:
                    self.logger.warning(
                        "Graph export failed for entity",
                        entity_id=entity.id,
                        error=str(e),
                    )

            # Build relationships between entities from the same source record
            record_groups: dict[str, list[Entity]] = {}
            for entity in entities:
                if entity.source_record_id:
                    record_groups.setdefault(entity.source_record_id, []).append(entity)
            for record_id, group in record_groups.items():
                if len(group) > 1:
                    for i, a in enumerate(group[:-1]):
                        for b in group[i + 1:]:
                            try:
                                await neo4j.create_relationship(
                                    source_id=str(a.id),
                                    target_id=str(b.id),
                                    relationship_type="ASSOCIATED_WITH",
                                    properties={"reason": "same_source_record", "source_record_id": str(record_id)},
                                )
                            except Exception:
                                pass

            self.logger.info("Graph export complete", count=len(entities))
        except Exception as e:
            self.logger.warning("Neo4j graph export failed", error=str(e))

    async def _queue_for_review(
        self, entities: list[Entity], job: IngestionJob
    ) -> None:
        """Queue low-confidence entities for human review."""
        if not entities:
            return
        try:
            review_count = 0
            for entity in entities:
                if entity.confidence < 0.7:
                    await ReviewService.queue_for_review(
                        db=self.session,
                        workspace_id=self.workspace_id,
                        entity_id=entity.id,
                        item_type=entity.type,
                        confidence_score=entity.confidence,
                        data={
                            "value": entity.value,
                            "threat_level": entity.threat_level,
                            "source": entity.source,
                            "tags": entity.tags,
                        },
                        reason=f"Low confidence ({entity.confidence:.2f}) during ingestion of {job.file_name}",
                    )
                    review_count += 1
            if review_count:
                await self.session.flush()
                self.logger.info("Queued entities for review", count=review_count)
        except Exception as e:
            self.logger.warning("Review queue submission failed", error=str(e))

    async def _publish_event_safe(self, event_type: str, **kwargs) -> None:
        """Publish an ingestion event via NATS (best-effort)."""
        try:
            publisher = await get_event_publisher()
            job: IngestionJob = kwargs.get("job")
            if event_type == "complete":
                await publisher.ingestion_complete(
                    file_id=str(job.id),
                    file_name=job.file_name or "",
                    record_count=kwargs.get("record_count", 0),
                    schema_id=str(job.schema_id) if job.schema_id else None,
                    correlation_id=str(job.id),
                )
            elif event_type == "failed":
                await publisher.ingestion_failed(
                    file_name=job.file_name or "",
                    error_message=kwargs.get("error_message", "Unknown error"),
                    error_type="ingestion_error",
                    correlation_id=str(job.id),
                )
        except Exception as e:
            self.logger.warning("NATS event publishing failed", error=str(e))

    def _detect_format(self, filename: str) -> FileFormat:
        """Detect file format from filename.

        Args:
            filename: The filename.

        Returns:
            The detected file format.

        Raises:
            TracecatValidationError: If format not supported.
        """
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
        """Parse file content using appropriate parser.

        Args:
            content: The file content.
            file_format: The file format.
            filename: The filename.

        Returns:
            The parse result.
        """
        if file_format == FileFormat.JSON:
            parser = JSONParser()
        elif file_format == FileFormat.CSV:
            parser = CSVParser()
        elif file_format == FileFormat.EXCEL:
            parser = ExcelParser()
        else:
            # Try to detect from content
            parser = JSONParser()

        return parser.parse(content, filename=filename)

    async def _get_source_model(self, source_id: uuid.UUID) -> DataSource:
        """Get the raw source model.

        Args:
            source_id: The source ID.

        Returns:
            The source model.

        Raises:
            TracecatNotFoundError: If not found.
        """
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
        """Get the raw job model.

        Args:
            job_id: The job ID.

        Returns:
            The job model.

        Raises:
            TracecatNotFoundError: If not found.
        """
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
        """Convert source model to read schema.

        Args:
            source: The source model.

        Returns:
            The read schema.
        """
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
        """Convert job model to read schema.

        Args:
            job: The job model.

        Returns:
            The read schema.
        """
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
