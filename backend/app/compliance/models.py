"""Audit and compliance database models"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.models import Base
from uuid import uuid4
from enum import Enum


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"
    ENRICH = "enrich"
    QUERY = "query"


class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    action: Mapped[AuditAction] = mapped_column(SQLEnum(AuditAction), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    checksum: Mapped[str] = mapped_column(String(64), nullable=True)  # SHA-256 for integrity


class DataLineage(Base):
    __tablename__ = "data_lineage"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=True)
    transformation: Mapped[str] = mapped_column(String(100), nullable=True)
    parent_record_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    lineage_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
