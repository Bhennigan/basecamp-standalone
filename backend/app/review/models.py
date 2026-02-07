"""Review queue database models"""
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.models import Base
from uuid import uuid4
from enum import Enum


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECLASSIFIED = "reclassified"


class ReviewPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewItem(Base):
    __tablename__ = "review_item"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("extracted_entity.id"), nullable=True)
    record_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=True)
    item_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING)
    priority: Mapped[ReviewPriority] = mapped_column(SQLEnum(ReviewPriority), default=ReviewPriority.MEDIUM)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    assigned_to: Mapped[str] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(255), nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class ReviewDecision(Base):
    __tablename__ = "review_decision"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    review_item_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("review_item.id"), nullable=False)
    decision: Mapped[ReviewStatus] = mapped_column(SQLEnum(ReviewStatus), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    corrections: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
