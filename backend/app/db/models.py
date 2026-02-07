"""Base Camp OS Database Models"""
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.basecamp.enums import IngestionState, DataSourceType, SchemaStatus, FileFormat


class Base(DeclarativeBase):
    pass


class BaseCampSchema(Base):
    __tablename__ = "basecamp_schema"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", "version", name="uq_schema_workspace_name_version"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[SchemaStatus] = mapped_column(SQLEnum(SchemaStatus), default=SchemaStatus.DRAFT)
    fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    data_sources: Mapped[list["DataSource"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    data_records: Mapped[list["DataRecord"]] = relationship(back_populates="schema", cascade="all, delete-orphan")


class DataSource(Base):
    __tablename__ = "data_source"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[DataSourceType] = mapped_column(SQLEnum(DataSourceType), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    schema_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("basecamp_schema.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schema: Mapped[Optional["BaseCampSchema"]] = relationship(back_populates="data_sources")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="data_source", cascade="all, delete-orphan")


class IngestionJob(Base):
    __tablename__ = "ingestion_job"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    data_source_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("data_source.id"), nullable=True)
    schema_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("basecamp_schema.id"), nullable=True)
    state: Mapped[IngestionState] = mapped_column(SQLEnum(IngestionState), default=IngestionState.RECEIVED)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_format: Mapped[Optional[FileFormat]] = mapped_column(SQLEnum(FileFormat), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    job_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    data_source: Mapped[Optional["DataSource"]] = relationship(back_populates="ingestion_jobs")
    schema: Mapped[Optional["BaseCampSchema"]] = relationship(back_populates="ingestion_jobs")
    data_records: Mapped[list["DataRecord"]] = relationship(back_populates="ingestion_job", cascade="all, delete-orphan")


class DataRecord(Base):
    __tablename__ = "data_record"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    schema_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("basecamp_schema.id"), nullable=False)
    ingestion_job_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("ingestion_job.id"), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    schema: Mapped["BaseCampSchema"] = relationship(back_populates="data_records")
    ingestion_job: Mapped[Optional["IngestionJob"]] = relationship(back_populates="data_records")


# Entity Enrichment Models

class ExtractedEntity(Base):
    """Extracted and enriched entities for OSINT/DP3"""
    __tablename__ = "extracted_entity"
    __table_args__ = (
        UniqueConstraint("workspace_id", "entity_type", "normalized_value", name="uq_entity_workspace_type_value"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    threat_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    entity_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
