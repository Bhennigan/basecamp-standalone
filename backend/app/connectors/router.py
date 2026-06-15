"""FastAPI Router for OSINT Connector endpoints"""
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .base import ConnectorConfig, ConnectorResult
from .manager import get_connector_manager, ConnectorManager
from app.db.dependencies import get_db
from app.db.models import (
    BaseCampSchema as DBSchema,
    DataRecord,
    IngestionJob,
    ExtractedEntity,
)
from app.compliance.models import DataLineage
from app.basecamp.enums import IngestionState, SchemaStatus
from app.enrichment.service import EnrichmentService
from app.quality.scoring import score_record
from app.auth.credentials import get_workspace_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


class ConnectorCreateRequest(BaseModel):
    """Request model for creating a new connector"""
    name: str
    connector_type: str
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    enabled: bool = True
    poll_interval_seconds: int = 3600
    config: Dict[str, Any] = {}


class ConnectorResponse(BaseModel):
    """Response model for connector information"""
    name: str
    type: str
    status: str
    enabled: bool
    last_run: Optional[datetime] = None


class FetchRequest(BaseModel):
    """Request model for fetching data"""
    query: Optional[str] = None


class TestRequest(BaseModel):
    """Request model for testing a connector"""
    test_query: Optional[str] = None


def get_manager() -> ConnectorManager:
    """Dependency to get the connector manager"""
    return get_connector_manager()


@router.get("", response_model=List[ConnectorResponse])
async def list_connectors(manager: ConnectorManager = Depends(get_manager)):
    """
    List all registered connectors.
    
    Returns a list of all connectors with their current status.
    """
    connectors = manager.list_connectors()
    return [
        ConnectorResponse(
            name=c["name"],
            type=c["type"],
            status=c["status"].value if hasattr(c["status"], "value") else c["status"],
            enabled=c["enabled"],
            last_run=c.get("last_run")
        )
        for c in connectors
    ]


@router.get("/types")
async def list_connector_types():
    """
    List available connector types.
    
    Returns the types of connectors that can be registered.
    """
    return {
        "types": ConnectorManager.get_available_types(),
        "descriptions": {
            "shodan": "Shodan API for infrastructure reconnaissance",
            "zerofox": "ZeroFox API for impersonation and threat alerts",
            "sherlock": "Sherlock CLI for username searches",
            "harvester": "TheHarvester CLI for email and domain reconnaissance",
            "netcraft": "Netcraft API for takedown intelligence and brand protection"
        }
    }


@router.post("", response_model=ConnectorResponse)
async def create_connector(
    request: ConnectorCreateRequest,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Register a new connector.
    
    Creates and registers a new OSINT connector with the provided configuration.
    """
    try:
        config = ConnectorConfig(
            name=request.name,
            connector_type=request.connector_type,
            api_key=request.api_key,
            api_url=request.api_url,
            enabled=request.enabled,
            poll_interval_seconds=request.poll_interval_seconds,
            config=request.config
        )
        
        connector = manager.register_connector(config)
        status = connector.get_status()
        
        return ConnectorResponse(
            name=status["name"],
            type=status["type"],
            status=status["status"].value,
            enabled=status["enabled"],
            last_run=status.get("last_run")
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}")
async def delete_connector(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Unregister a connector.
    
    Removes a connector and stops any polling tasks.
    """
    if not manager.unregister_connector(name):
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    return {"message": f"Connector {name} unregistered successfully"}


@router.get("/{name}/status")
async def get_connector_status(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Get connector status.
    
    Returns detailed status information for a specific connector.
    """
    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    status = connector.get_status()
    status["status"] = status["status"].value if hasattr(status["status"], "value") else status["status"]
    
    return status


@router.get("/{name}/health")
async def get_connector_health(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Get connector health.
    
    Performs a health check on the connector and returns detailed health info.
    """
    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    try:
        health = await connector.health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/fetch")
async def fetch_from_connector(
    name: str,
    request: FetchRequest,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Trigger manual fetch from connector.
    
    Fetches data from the specified connector with an optional query.
    """
    try:
        result = await manager.fetch_from(name, request.query)
        return {
            "connector_name": result.connector_name,
            "timestamp": result.timestamp.isoformat(),
            "success": result.success,
            "records_count": result.records_count,
            "data": result.data,
            "errors": result.errors
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/test")
async def test_connector(
    name: str,
    request: TestRequest,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Test connector.
    
    Runs connection, health, and optionally fetch tests on the connector.
    """
    try:
        result = await manager.test_connector(name, request.test_query)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/connect")
async def connect_connector(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Connect a connector.
    
    Establishes connection/verifies credentials for the connector.
    """
    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    try:
        success = await connector.connect()
        return {
            "connector": name,
            "connected": success,
            "status": connector.status.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/all")
async def health_check_all(manager: ConnectorManager = Depends(get_manager)):
    """
    Health check all connectors.
    
    Performs health checks on all registered connectors.
    """
    return await manager.health_check_all()


@router.post("/polling/start")
async def start_polling(manager: ConnectorManager = Depends(get_manager)):
    """
    Start polling for all connectors.
    
    Begins scheduled polling for all enabled connectors.
    """
    await manager.start_polling()
    return {"message": "Polling started for all enabled connectors"}


@router.post("/polling/stop")
async def stop_polling(manager: ConnectorManager = Depends(get_manager)):
    """
    Stop polling for all connectors.
    
    Stops all scheduled polling tasks.
    """
    await manager.stop_polling()
    return {"message": "Polling stopped"}


class IngestRequest(BaseModel):
    """Request model for connector ingest"""
    query: Optional[str] = None


@router.post("/{name}/ingest")
async def ingest_from_connector(
    name: str,
    request: IngestRequest = IngestRequest(),
    manager: ConnectorManager = Depends(get_manager),
    workspace=Depends(get_workspace_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch data from a connector and store it in the database.

    Creates an ingestion job, stores all records, and extracts entities.
    """
    workspace_id = str(workspace.workspace_id)

    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")

    # 1. Fetch data from connector
    result = await connector.fetch(request.query)
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"Connector fetch failed: {result.errors}",
        )

    if result.records_count == 0:
        return {
            "message": "No records returned from connector",
            "connector": name,
            "records_stored": 0,
            "entities_extracted": 0,
        }

    # 2. Find or create a schema for this connector's data
    schema_name = f"connector_{name}"
    stmt = select(DBSchema).where(
        DBSchema.workspace_id == workspace_id,
        DBSchema.name == schema_name,
    )
    schema_result = await db.execute(stmt)
    schema = schema_result.scalar_one_or_none()

    if not schema:
        schema = DBSchema(
            workspace_id=workspace_id,
            name=schema_name,
            description=f"Auto-created schema for {name} connector data",
            version=1,
            status=SchemaStatus.ACTIVE,
            fields=[],
        )
        db.add(schema)
        await db.flush()
        await db.refresh(schema)
        logger.info(f"Created schema for connector {name} | schema_id={schema.id}")

    # 3. Create an ingestion job
    job = IngestionJob(
        workspace_id=workspace_id,
        schema_id=schema.id,
        state=IngestionState.LOADING,
        file_name=f"{name}_connector_fetch",
        total_records=result.records_count,
        processed_records=0,
        failed_records=0,
        job_metadata={"connector": name, "query": request.query},
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # 4. Store records and extract entities
    records_stored = 0
    entities_extracted = 0
    failed = 0

    # Load existing entities for upsert
    existing_stmt = select(ExtractedEntity).where(
        ExtractedEntity.workspace_id == workspace_id
    )
    existing_result = await db.execute(existing_stmt)
    existing_map: dict[str, ExtractedEntity] = {
        f"{e.entity_type}:{e.normalized_value}": e
        for e in existing_result.scalars().all()
    }

    # Schema fields for quality scoring (connector schemas often start empty).
    schema_fields = schema.fields if isinstance(schema.fields, list) else []

    for record_data in result.data:
        try:
            record_metadata = {
                "source_type": "connector",
                "connector": name,
                "job_id": str(job.id),
            }
            # Store as DataRecord
            record = DataRecord(
                workspace_id=workspace_id,
                schema_id=schema.id,
                ingestion_job_id=job.id,
                job_id=job.id,
                data=record_data,
                record_metadata=record_metadata,
                quality=(
                    score_record(
                        record_data, schema_fields, now=datetime.utcnow()
                    )
                    if schema_fields
                    else {}
                ),
            )
            db.add(record)

            # Durable lineage row in the SAME transaction (committed below).
            db.add(
                DataLineage(
                    workspace_id=workspace_id,
                    record_id=str(record.id),
                    source_type="connector",
                    source_id=str(job.id),
                    transformation=None,
                    parent_record_id=None,
                    lineage_metadata=record_metadata,
                )
            )
            records_stored += 1

            # Extract entities from this record
            try:
                entities = EnrichmentService.extract_entities(record_data, name)
                deduplicated = EnrichmentService.deduplicate_entities(entities)
                for entity in deduplicated:
                    enriched = EnrichmentService.enrich_entity(entity)
                    key = f"{enriched.type}:{enriched.normalized_value}"
                    existing = existing_map.get(key)
                    if existing:
                        existing.last_seen = datetime.utcnow()
                        existing.confidence = max(
                            existing.confidence, enriched.confidence
                        )
                        if enriched.threat_level:
                            existing.threat_level = enriched.threat_level
                        existing.tags = list(
                            set((existing.tags or []) + enriched.tags)
                        )
                        existing.entity_metadata = {
                            **(existing.entity_metadata or {}),
                            **enriched.metadata,
                        }
                    else:
                        db_entity = ExtractedEntity(
                            workspace_id=workspace_id,
                            entity_type=enriched.type,
                            value=enriched.value,
                            normalized_value=enriched.normalized_value,
                            confidence=enriched.confidence,
                            threat_level=enriched.threat_level,
                            source=name,
                            tags=enriched.tags,
                            entity_metadata=enriched.metadata,
                        )
                        db.add(db_entity)
                        existing_map[key] = db_entity
                    entities_extracted += 1
            except Exception as ent_err:
                logger.warning(
                    f"Entity extraction failed for record: {ent_err}"
                )

            # Flush in batches of 500
            if records_stored % 500 == 0:
                await db.flush()

        except Exception as rec_err:
            logger.warning(f"Failed to store record: {rec_err}")
            failed += 1

    # Final flush
    await db.flush()

    # 5. Update job status
    job.state = IngestionState.COMPLETE
    job.processed_records = records_stored
    job.failed_records = failed
    job.completed_at = datetime.utcnow()
    await db.flush()

    await db.commit()

    logger.info(
        f"Connector ingest complete | connector={name} "
        f"records={records_stored} entities={entities_extracted} failed={failed}"
    )

    return {
        "message": "Connector data ingested successfully",
        "connector": name,
        "job_id": job.id,
        "schema_id": schema.id,
        "records_stored": records_stored,
        "entities_extracted": entities_extracted,
        "failed": failed,
    }
