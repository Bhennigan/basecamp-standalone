"""Audit and compliance service"""
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog, DataLineage, AuditAction


class AuditService:
    """Service for audit logging and compliance tracking"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _compute_checksum(self, data: Dict[str, Any]) -> str:
        """Compute SHA-256 checksum for data integrity verification"""
        # Create deterministic JSON string
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    async def log_action(
        self,
        workspace_id: str,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log an audit action with integrity checksum"""
        log_id = str(uuid4())
        timestamp = datetime.utcnow()
        details = details or {}
        
        # Compute checksum for integrity verification
        checksum_data = {
            "id": log_id,
            "workspace_id": workspace_id,
            "timestamp": timestamp.isoformat(),
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "user_email": user_email,
            "details": details
        }
        checksum = self._compute_checksum(checksum_data)
        
        audit_log = AuditLog(
            id=log_id,
            workspace_id=workspace_id,
            timestamp=timestamp,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            details=details,
            checksum=checksum
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)
        
        return audit_log
    
    async def get_audit_log(
        self,
        workspace_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Query audit logs with filters"""
        conditions = [AuditLog.workspace_id == workspace_id]
        
        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        
        query = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_audit_entry(self, workspace_id: str, log_id: str) -> Optional[AuditLog]:
        """Get a specific audit log entry"""
        query = select(AuditLog).where(
            and_(
                AuditLog.workspace_id == workspace_id,
                AuditLog.id == log_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def verify_integrity(self, workspace_id: str, log_id: Optional[str] = None) -> Dict[str, Any]:
        """Verify log checksums for integrity"""
        if log_id:
            logs = [await self.get_audit_entry(workspace_id, log_id)]
            logs = [l for l in logs if l is not None]
        else:
            logs = await self.get_audit_log(workspace_id, limit=10000)
        
        results = {
            "total": len(logs),
            "valid": 0,
            "invalid": 0,
            "invalid_entries": []
        }
        
        for log in logs:
            checksum_data = {
                "id": log.id,
                "workspace_id": log.workspace_id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action.value if isinstance(log.action, AuditAction) else log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "details": log.details
            }
            computed_checksum = self._compute_checksum(checksum_data)
            
            if computed_checksum == log.checksum:
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["invalid_entries"].append({
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "expected": log.checksum,
                    "computed": computed_checksum
                })
        
        results["integrity_verified"] = results["invalid"] == 0
        return results
    
    async def export_audit_log(
        self,
        workspace_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export audit log for compliance (WORM-compatible format)"""
        logs = await self.get_audit_log(
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            limit=100000
        )
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "workspace_id": workspace_id,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "record_count": len(logs),
            "records": []
        }
        
        for log in logs:
            export_data["records"].append({
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action.value if isinstance(log.action, AuditAction) else log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "ip_address": log.ip_address,
                "details": log.details,
                "checksum": log.checksum
            })
        
        # Add export checksum for WORM verification
        export_data["export_checksum"] = self._compute_checksum(export_data)
        
        return export_data
    
    async def track_lineage(
        self,
        workspace_id: str,
        record_id: str,
        source_type: str,
        source_id: Optional[str] = None,
        transformation: Optional[str] = None,
        parent_record_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataLineage:
        """Track data lineage for a record"""
        lineage = DataLineage(
            id=str(uuid4()),
            workspace_id=workspace_id,
            record_id=record_id,
            source_type=source_type,
            source_id=source_id,
            transformation=transformation,
            parent_record_id=parent_record_id,
            metadata=metadata or {}
        )
        
        self.db.add(lineage)
        await self.db.commit()
        await self.db.refresh(lineage)
        
        return lineage
    
    async def get_lineage(
        self,
        workspace_id: str,
        record_id: str,
        include_ancestors: bool = True
    ) -> Dict[str, Any]:
        """Get lineage for a record, optionally including ancestors"""
        # Get direct lineage entries for this record
        query = select(DataLineage).where(
            and_(
                DataLineage.workspace_id == workspace_id,
                DataLineage.record_id == record_id
            )
        ).order_by(DataLineage.created_at)
        
        result = await self.db.execute(query)
        entries = list(result.scalars().all())
        
        lineage_data = {
            "record_id": record_id,
            "entries": [],
            "ancestors": []
        }
        
        parent_ids = set()
        for entry in entries:
            lineage_data["entries"].append({
                "id": entry.id,
                "source_type": entry.source_type,
                "source_id": entry.source_id,
                "transformation": entry.transformation,
                "parent_record_id": entry.parent_record_id,
                "created_at": entry.created_at.isoformat(),
                "metadata": entry.metadata
            })
            if entry.parent_record_id:
                parent_ids.add(entry.parent_record_id)
        
        # Recursively get ancestors
        if include_ancestors and parent_ids:
            for parent_id in parent_ids:
                ancestor_lineage = await self.get_lineage(
                    workspace_id=workspace_id,
                    record_id=parent_id,
                    include_ancestors=True
                )
                lineage_data["ancestors"].append(ancestor_lineage)
        
        return lineage_data
    
    async def generate_compliance_report(
        self,
        workspace_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate a compliance summary report"""
        logs = await self.get_audit_log(
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            limit=100000
        )
        
        # Aggregate statistics
        action_counts = {}
        resource_counts = {}
        user_counts = {}
        hourly_activity = {}
        
        for log in logs:
            # Count by action
            action = log.action.value if isinstance(log.action, AuditAction) else log.action
            action_counts[action] = action_counts.get(action, 0) + 1
            
            # Count by resource type
            resource_counts[log.resource_type] = resource_counts.get(log.resource_type, 0) + 1
            
            # Count by user
            if log.user_id:
                user_counts[log.user_id] = user_counts.get(log.user_id, 0) + 1
            
            # Hourly activity
            hour_key = log.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_activity[hour_key] = hourly_activity.get(hour_key, 0) + 1
        
        # Verify integrity
        integrity = await self.verify_integrity(workspace_id)
        
        return {
            "workspace_id": workspace_id,
            "report_generated": datetime.utcnow().isoformat(),
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "summary": {
                "total_events": len(logs),
                "unique_users": len(user_counts),
                "unique_resources": len(resource_counts)
            },
            "action_breakdown": action_counts,
            "resource_breakdown": resource_counts,
            "top_users": dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "hourly_activity": dict(sorted(hourly_activity.items())),
            "integrity_status": {
                "verified": integrity["integrity_verified"],
                "total_checked": integrity["total"],
                "valid": integrity["valid"],
                "invalid": integrity["invalid"]
            }
        }
