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
    source_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    schema_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("basecamp_schema.id"), nullable=True)
    state: Mapped[IngestionState] = mapped_column(SQLEnum(IngestionState), default=IngestionState.RECEIVED)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_format: Mapped[Optional[FileFormat]] = mapped_column(SQLEnum(FileFormat), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    total_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_records: Mapped[int] = mapped_column(Integer, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    job_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    job_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schema: Mapped["BaseCampSchema"] = relationship(back_populates="data_records")
    ingestion_job: Mapped[Optional["IngestionJob"]] = relationship(back_populates="data_records")


# Transformation & Consumer Models

class MappingProfile(Base):
    """Transformation mapping profile for normalizing data between schemas."""
    __tablename__ = "mapping_profile"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_schema_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    target_schema_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    mappings: Mapped[list] = mapped_column(JSONB, default=list)
    drop_unmapped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Consumer(Base):
    """Registered downstream consumer/subscriber."""
    __tablename__ = "consumer"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    callback_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_ids: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mapping_profile_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("mapping_profile.id"), nullable=True)
    last_poll: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
