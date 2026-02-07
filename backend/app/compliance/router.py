"""Compliance and audit trail API endpoints"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from .models import AuditAction
from .service import AuditService


router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class AuditLogResponse(BaseModel):
    id: str
    workspace_id: str
    timestamp: datetime
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    ip_address: Optional[str] = None
    details: dict
    checksum: Optional[str] = None
    
    class Config:
        from_attributes = True


class ExportRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    format: str = "json"


def get_workspace_id() -> str:
    """Get workspace ID from context - simplified for now"""
    return "default-workspace"


@router.get("/audit")
async def query_audit_logs(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id)
):
    """Query audit logs with optional filters"""
    service = AuditService(db)
    
    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    logs = await service.get_audit_log(
        workspace_id=workspace_id,
        start_date=start_date,
        end_date=end_date,
        action=action_enum,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    
    return {"logs": [AuditLogResponse.model_validate(log) for log in logs], "count": len(logs)}


@router.get("/audit/{log_id}")
async def get_audit_entry(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id)
):
    """Get a specific audit log entry"""
    service = AuditService(db)
    entry = await service.get_audit_entry(workspace_id, log_id)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    
    return AuditLogResponse.model_validate(entry)


@router.post("/audit/export")
async def export_audit_log(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id)
):
    """Export audit log in WORM-compatible format"""
    service = AuditService(db)
    export_data = await service.export_audit_log(
        workspace_id=workspace_id,
        start_date=request.start_date,
        end_date=request.end_date,
        format=request.format
    )
    
    return export_data


@router.get("/lineage/{record_id}")
async def get_data_lineage(
    record_id: str,
    include_ancestors: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id)
):
    """Get data lineage for a record"""
    service = AuditService(db)
    lineage = await service.get_lineage(
        workspace_id=workspace_id,
        record_id=record_id,
        include_ancestors=include_ancestors
    )
    
    return lineage


@router.get("/integrity/verify")
async def verify_integrity(
    log_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id)
):
    """Verify audit log integrity via checksums"""
    service = AuditService(db)
    result = await service.verify_integrity(workspace_id, log_id)
    
    return result


@router.get("/report")
async def generate_compliance_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id)
):
    """Generate a compliance summary report"""
    service = AuditService(db)
    report = await service.generate_compliance_report(
        workspace_id=workspace_id,
        start_date=start_date,
        end_date=end_date
    )
    
    return report
