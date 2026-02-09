"""Review queue service for human-in-the-loop processing"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, update
from app.review.models import ReviewItem, ReviewDecision, ReviewStatus, ReviewPriority


class ReviewService:
    DEFAULT_THRESHOLDS = {
        "entity": 0.7,
        "classification": 0.8,
        "enrichment": 0.75,
    }
    PRIORITY_THRESHOLDS = {
        0.3: ReviewPriority.CRITICAL,
        0.5: ReviewPriority.HIGH,
        0.7: ReviewPriority.MEDIUM,
    }

    @classmethod
    def calculate_confidence(cls, predictions, weights=None):
        """Calculate weighted confidence from a list of prediction scores."""
        if not predictions:
            return 0.0
        if weights and len(weights) == len(predictions):
            total_weight = sum(weights)
            if total_weight == 0:
                return 0.0
            return sum(p * w for p, w in zip(predictions, weights)) / total_weight
        return sum(predictions) / len(predictions)

    @classmethod
    def _score_to_priority(cls, confidence_score: float) -> ReviewPriority:
        """Map a confidence score to a review priority."""
        for threshold, priority in sorted(cls.PRIORITY_THRESHOLDS.items()):
            if confidence_score < threshold:
                return priority
        return ReviewPriority.LOW

    @classmethod
    async def queue_for_review(
        cls,
        db: AsyncSession,
        workspace_id: str,
        item_type: str,
        confidence_score: float,
        data: Dict[str, Any],
        *,
        entity_id: Optional[str] = None,
        record_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ReviewItem:
        """Create a ReviewItem in the database."""
        threshold = cls.DEFAULT_THRESHOLDS.get(item_type, 0.7)
        priority = cls._score_to_priority(confidence_score)

        item = ReviewItem(
            id=str(uuid4()),
            workspace_id=workspace_id,
            entity_id=entity_id,
            record_id=record_id,
            item_type=item_type,
            status=ReviewStatus.PENDING,
            priority=priority,
            confidence_score=confidence_score,
            confidence_threshold=threshold,
            reason=reason or f"Confidence {confidence_score:.2f} below threshold {threshold:.2f}",
            data=data,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    @classmethod
    async def get_queue(
        cls,
        db: AsyncSession,
        workspace_id: str,
        *,
        status: Optional[ReviewStatus] = None,
        priority: Optional[ReviewPriority] = None,
        item_type: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ReviewItem]:
        """List review items with optional filtering."""
        conditions = [ReviewItem.workspace_id == workspace_id]
        if status is not None:
            conditions.append(ReviewItem.status == status)
        if priority is not None:
            conditions.append(ReviewItem.priority == priority)
        if item_type is not None:
            conditions.append(ReviewItem.item_type == item_type)
        if assigned_to is not None:
            conditions.append(ReviewItem.assigned_to == assigned_to)

        query = (
            select(ReviewItem)
            .where(and_(*conditions))
            .order_by(ReviewItem.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_item(cls, db: AsyncSession, item_id: str) -> Optional[ReviewItem]:
        """Get a single review item by ID."""
        result = await db.execute(
            select(ReviewItem).where(ReviewItem.id == item_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def assign_item(
        cls, db: AsyncSession, item_id: str, assignee: str
    ) -> Optional[ReviewItem]:
        """Assign a review item to a reviewer."""
        item = await cls.get_item(db, item_id)
        if not item:
            return None
        item.assigned_to = assignee
        item.status = ReviewStatus.IN_REVIEW
        item.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(item)
        return item

    @classmethod
    async def submit_decision(
        cls,
        db: AsyncSession,
        item_id: str,
        decision: ReviewStatus,
        reviewer_id: str,
        *,
        notes: Optional[str] = None,
        corrections: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReviewDecision]:
        """Submit a review decision (approve/reject/reclassify)."""
        item = await cls.get_item(db, item_id)
        if not item:
            return None

        # Update the review item
        item.status = decision
        item.reviewed_by = reviewer_id
        item.review_notes = notes
        item.reviewed_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()

        # Create a decision record
        review_decision = ReviewDecision(
            id=str(uuid4()),
            review_item_id=item_id,
            decision=decision,
            reviewer_id=reviewer_id,
            notes=notes,
            corrections=corrections or {},
        )
        db.add(review_decision)
        await db.flush()
        await db.refresh(review_decision)
        return review_decision

    @classmethod
    async def get_stats(
        cls, db: AsyncSession, workspace_id: str
    ) -> Dict[str, Any]:
        """Get counts of review items by status."""
        result = await db.execute(
            select(ReviewItem.status, func.count(ReviewItem.id))
            .where(ReviewItem.workspace_id == workspace_id)
            .group_by(ReviewItem.status)
        )
        rows = result.all()
        counts = {status.value: 0 for status in ReviewStatus}
        total = 0
        for status_val, count in rows:
            key = status_val.value if hasattr(status_val, "value") else status_val
            counts[key] = count
            total += count
        counts["total"] = total
        return counts

    @classmethod
    async def get_training_data(
        cls,
        db: AsyncSession,
        workspace_id: str,
        *,
        item_type: Optional[str] = None,
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Export reviewed items as training data."""
        conditions = [
            ReviewItem.workspace_id == workspace_id,
            ReviewItem.status.in_([ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.RECLASSIFIED]),
        ]
        if item_type:
            conditions.append(ReviewItem.item_type == item_type)
        if min_date:
            conditions.append(ReviewItem.reviewed_at >= min_date)
        if max_date:
            conditions.append(ReviewItem.reviewed_at <= max_date)

        query = (
            select(ReviewItem)
            .where(and_(*conditions))
            .order_by(ReviewItem.reviewed_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        items = result.scalars().all()

        return [
            {
                "id": item.id,
                "item_type": item.item_type,
                "data": item.data,
                "confidence_score": item.confidence_score,
                "decision": item.status.value if hasattr(item.status, "value") else item.status,
                "reviewer": item.reviewed_by,
                "notes": item.review_notes,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            }
            for item in items
        ]

    @classmethod
    async def update_threshold(
        cls,
        db: AsyncSession,
        workspace_id: str,
        item_type: str,
        new_threshold: float,
    ) -> Dict[str, Any]:
        """Update the confidence threshold for a given item type."""
        cls.DEFAULT_THRESHOLDS[item_type] = new_threshold
        return {
            "item_type": item_type,
            "new_threshold": new_threshold,
            "thresholds": dict(cls.DEFAULT_THRESHOLDS),
        }
