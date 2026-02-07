"""REST API endpoints for review queues"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.review.models import ReviewStatus, ReviewPriority
from app.review.service import ReviewService

router = APIRouter()

class AssignRequest(BaseModel):
    assignee: str

class DecisionRequest(BaseModel):
    decision: ReviewStatus
    reviewer_id: str
    notes: Optional[str] = None
    corrections: Optional[dict] = None

class ThresholdUpdate(BaseModel):
    item_type: str
    threshold: float

class TrainingExportRequest(BaseModel):
    item_type: Optional[str] = None
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None
    limit: int = 10000

@router.get("/queue")
async def get_review_queue(
    workspace_id: str = Query(..., description="Workspace ID"),
    status: Optional[ReviewStatus] = None,
    priority: Optional[ReviewPriority] = None,
    item_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    items = await ReviewService.get_queue(
        db=db, workspace_id=workspace_id, status=status, priority=priority,
        item_type=item_type, assigned_to=assigned_to, limit=limit, offset=offset,
    )
    return {"items": items, "count": len(items)}

@router.get("/item/{item_id}")
async def get_review_item(item_id: str, db: AsyncSession = Depends(get_db)):
    item = await ReviewService.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item

@router.post("/item/{item_id}/assign")
async def assign_review_item(
    item_id: str,
    request: AssignRequest,
    db: AsyncSession = Depends(get_db),
):
    item = await ReviewService.assign_item(db, item_id, request.assignee)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item

@router.post("/item/{item_id}/decision")
async def submit_review_decision(
    item_id: str,
    request: DecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    decision = await ReviewService.submit_decision(
        db, item_id, request.decision, request.reviewer_id,
        notes=request.notes, corrections=request.corrections,
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Review item not found")
    return decision

@router.get("/stats")
async def get_review_stats(
    workspace_id: str = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    return await ReviewService.get_stats(db, workspace_id)

@router.post("/training-data/export")
async def export_training_data(
    workspace_id: str = Query(..., description="Workspace ID"),
    request: TrainingExportRequest = TrainingExportRequest(),
    db: AsyncSession = Depends(get_db),
):
    data = await ReviewService.get_training_data(
        db, workspace_id, item_type=request.item_type,
        min_date=request.min_date, max_date=request.max_date, limit=request.limit,
    )
    return {"data": data, "count": len(data)}

@router.patch("/threshold")
async def update_confidence_threshold(
    workspace_id: str = Query(..., description="Workspace ID"),
    request: ThresholdUpdate = None,
    db: AsyncSession = Depends(get_db),
):
    if not request:
        raise HTTPException(status_code=400, detail="Request body required")
    return await ReviewService.update_threshold(
        db, workspace_id, request.item_type, request.threshold,
    )
