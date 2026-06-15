"""Entity-resolution persistence models (on the shared declarative Base).

An ``EntityCluster`` is a resolved real-world entity: a set of ``DataRecord`` rows that
were judged to be the same entity, plus the merged golden record (``canonical``). Each
``ClusterMember`` links one source ``DataRecord`` into a cluster with the match score
that brought it in.

Reserved-name caution: SQLAlchemy's declarative API reserves the attribute name
``metadata`` on mapped classes, so any JSONB blob here is named explicitly (e.g.
``canonical``) and never ``metadata``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.models import Base  # same declarative Base as DataRecord


class EntityCluster(Base):
    __tablename__ = "entity_cluster"
    __table_args__ = (
        Index("ix_entity_cluster_ws_schema", "workspace_id", "schema_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    schema_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # The golden / canonical merged record for this entity.
    canonical: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members: Mapped[list["ClusterMember"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class ClusterMember(Base):
    __tablename__ = "cluster_member"
    __table_args__ = (
        Index("ix_cluster_member_cluster", "cluster_id"),
        Index("ix_cluster_member_record", "workspace_id", "record_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("entity_cluster.id", ondelete="CASCADE"), nullable=False
    )
    record_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cluster: Mapped["EntityCluster"] = relationship(back_populates="members")
