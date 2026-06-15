"""Base Camp OS Database Models"""
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, UniqueConstraint, Index
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
    __table_args__ = (
        # Composite index backing the consumer change feed keyset pagination
        # (ORDER BY updated_at, id within a workspace). See consumers/external_router.py.
        Index("ix_data_record_feed", "workspace_id", "updated_at", "id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    schema_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("basecamp_schema.id"), nullable=False)
    ingestion_job_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("ingestion_job.id"), nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Canonical record envelope: inline lineage (_meta) + quality scores (_quality).
    record_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    quality: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
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
    # API key is never stored in plaintext: only a sha256 hash (for lookup) plus a short
    # non-secret prefix (for display, e.g. "bc_a1b2c3"). The raw token is returned once at
    # creation and never again. See consumers/auth.py for the resolution path.
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    api_key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    mapping_profile_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("mapping_profile.id"), nullable=True)
    last_poll: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExtractedEntity(Base):
    """An entity extracted/enriched from ingested data (email, domain, IP, person, etc.).

    Consumed by the enrichment, graph, and connectors modules. The JSONB metadata column is
    exposed as ``entity_metadata`` because SQLAlchemy's declarative API reserves the attribute
    name ``metadata``; the source pydantic ``Entity.metadata`` maps onto it.
    """
    __tablename__ = "extracted_entity"
    __table_args__ = (
        Index("ix_extracted_entity_ws_type_value", "workspace_id", "entity_type", "normalized_value"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    threat_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    entity_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
