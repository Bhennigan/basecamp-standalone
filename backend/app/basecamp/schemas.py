"""API schemas for Base Camp OS module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.basecamp.enums import (
    DataSourceType,
    FileFormat,
    IngestionState,
    SchemaStatus,
)
from app.core.schemas import Schema

# --- Data Source Schemas ---


class DataSourceCreate(Schema):
    """Request schema for creating a data source."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: DataSourceType
    description: str | None = Field(default=None, max_length=1000)
    config: dict[str, Any] = Field(default_factory=dict)
    schema_id: uuid.UUID | None = Field(default=None)


class DataSourceUpdate(Schema):
    """Request schema for updating a data source."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    config: dict[str, Any] | None = None
    schema_id: uuid.UUID | None = None
    is_active: bool | None = None


class DataSourceRead(Schema):
    """Response schema for a data source."""

    id: uuid.UUID
    name: str
    source_type: DataSourceType
    description: str | None
    config: dict[str, Any]
    schema_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DataSourceReadMinimal(Schema):
    """Minimal response schema for a data source."""

    id: uuid.UUID
    name: str
    source_type: DataSourceType
    is_active: bool


# --- Schema Schemas ---


class SchemaFieldCreate(Schema):
    """Schema for defining a field in a schema."""

    name: str = Field(..., min_length=1, max_length=255)
    field_type: str = Field(
        ..., description="Data type: str, int, float, bool, datetime, json"
    )
    nullable: bool = Field(default=True)
    default: Any = Field(default=None)
    description: str | None = Field(default=None, max_length=500)


class SchemaFieldRead(Schema):
    """Response schema for a schema field."""

    name: str
    field_type: str
    nullable: bool
    default: Any
    description: str | None


class BaseCampSchemaCreate(Schema):
    """Request schema for creating a schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    fields: list[SchemaFieldCreate] = Field(default_factory=list)


class BaseCampSchemaUpdate(Schema):
    """Request schema for updating a schema."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    fields: list[SchemaFieldCreate] | None = None
    status: SchemaStatus | None = None


class BaseCampSchemaRead(Schema):
    """Response schema for a schema."""

    id: uuid.UUID
    name: str
    description: str | None
    version: int
    status: SchemaStatus
    fields: list[SchemaFieldRead]
    created_at: datetime
    updated_at: datetime


class BaseCampSchemaReadMinimal(Schema):
    """Minimal response schema for a schema."""

    id: uuid.UUID
    name: str
    version: int
    status: SchemaStatus


class SchemaInferRequest(Schema):
    """Request schema for schema inference preview."""

    sample_data: list[dict[str, Any]] = Field(
        ..., min_length=1, description="Sample records to infer schema from"
    )
    source_format: FileFormat | None = Field(default=None)


class SchemaInferResponse(Schema):
    """Response schema for schema inference preview."""

    inferred_fields: list[SchemaFieldRead]
    record_count: int
    confidence: float


# --- Ingestion Job Schemas ---


class IngestionJobRead(Schema):
    """Response schema for an ingestion job."""

    id: uuid.UUID
    source_id: uuid.UUID | None
    schema_id: uuid.UUID | None
    state: IngestionState
    file_name: str | None
    file_format: FileFormat | None
    total_records: int | None
    processed_records: int
    failed_records: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IngestionJobReadMinimal(Schema):
    """Minimal response schema for an ingestion job."""

    id: uuid.UUID
    state: IngestionState
    file_name: str | None
    processed_records: int
    created_at: datetime


class IngestionUploadResponse(Schema):
    """Response schema for file upload."""

    job_id: uuid.UUID
    message: str


# --- Data Record Schemas ---


class DataRecordRead(Schema):
    """Response schema for a data record."""

    id: uuid.UUID
    schema_id: uuid.UUID
    job_id: uuid.UUID | None
    data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DataRecordCreate(Schema):
    """Request schema for creating a data record."""

    schema_id: uuid.UUID
    data: dict[str, Any]


class DataRecordUpdate(Schema):
    """Request schema for updating a data record."""

    data: dict[str, Any]


class DataQueryRequest(Schema):
    """Request schema for querying data records."""

    schema_id: uuid.UUID
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_direction: str = Field(default="desc", pattern="^(asc|desc)$")


class DataQueryResponse(Schema):
    """Response schema for data queries."""

    records: list[DataRecordRead]
    total_count: int
    limit: int
    offset: int


class DataExportRequest(Schema):
    """Request schema for data export."""

    schema_id: uuid.UUID
    format: FileFormat = Field(default=FileFormat.JSON)
    filters: dict[str, Any] = Field(default_factory=dict)


# --- Tracecat Integration Schemas ---


class TracecatIngestRequest(Schema):
    """Request schema for Tracecat webhook ingestion."""

    source_id: uuid.UUID | None = None
    schema_id: uuid.UUID | None = None
    data: list[dict[str, Any]] | dict[str, Any]


class TracecatIngestResponse(Schema):
    """Response schema for Tracecat webhook ingestion."""

    job_id: uuid.UUID
    records_received: int


class TracecatQueryRequest(Schema):
    """Request schema for Tracecat workflow query."""

    schema_id: uuid.UUID
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)


class TracecatQueryResponse(Schema):
    """Response schema for Tracecat workflow query."""

    records: list[dict[str, Any]]
    total_count: int
