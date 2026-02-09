"""REST API endpoints for entity enrichment"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.enrichment.entities import Entity, EntityType, ThreatLevel
from app.enrichment.service import EnrichmentService


router = APIRouter()


class ExtractRequest(BaseModel):
    """Request model for entity extraction"""
    data: dict | str
    source: str = "api"


class EnrichRequest(BaseModel):
    """Request model for entity enrichment"""
    entities: List[Entity]


class TagRequest(BaseModel):
    """Request model for tagging entities"""
    entities: List[Entity]
    tags: List[str]


class DeduplicateRequest(BaseModel):
    """Request model for deduplication"""
    entities: List[Entity]


class ExtractResponse(BaseModel):
    """Response model for extraction"""
    entities: List[Entity]
    count: int


class EntityListResponse(BaseModel):
    """Response model for entity listing"""
    entities: List[dict]
    total: int
    limit: int
    offset: int


@router.post("/extract", response_model=ExtractResponse)
async def extract_entities(request: ExtractRequest):
    """Extract entities from text or JSON data"""
    entities = EnrichmentService.extract_entities(request.data, request.source)
    return ExtractResponse(entities=entities, count=len(entities))


@router.post("/enrich", response_model=ExtractResponse)
async def enrich_entities(request: EnrichRequest):
    """Enrich extracted entities with additional context"""
    enriched = [EnrichmentService.enrich_entity(e) for e in request.entities]
    return ExtractResponse(entities=enriched, count=len(enriched))


@router.post("/deduplicate", response_model=ExtractResponse)
async def deduplicate_entities(request: DeduplicateRequest):
    """Deduplicate entity list"""
    deduplicated = EnrichmentService.deduplicate_entities(request.entities)
    return ExtractResponse(entities=deduplicated, count=len(deduplicated))


@router.post("/tag", response_model=ExtractResponse)
async def tag_entities(request: TagRequest):
    """Tag entities and recalculate threat levels"""
    tagged = [EnrichmentService.tag_entity(e, request.tags) for e in request.entities]
    return ExtractResponse(entities=tagged, count=len(tagged))


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    workspace_id: str = Query(..., description="Workspace ID"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    threat_level: Optional[ThreatLevel] = Query(None, description="Filter by threat level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
):
    """List extracted entities with optional filtering"""
    entities = await EnrichmentService.get_entities(
        db=db,
        workspace_id=workspace_id,
        entity_type=entity_type,
        threat_level=threat_level,
        limit=limit,
        offset=offset,
    )
    return EntityListResponse(
        entities=[{
            "id": e.id,
            "type": e.entity_type,
            "value": e.value,
            "normalized_value": e.normalized_value,
            "confidence": e.confidence,
            "threat_level": e.threat_level,
            "source": e.source,
            "tags": e.tags,
            "metadata": e.entity_metadata,
            "first_seen": e.first_seen.isoformat(),
            "last_seen": e.last_seen.isoformat(),
        } for e in entities],
        total=len(entities),
        limit=limit,
        offset=offset,
    )


@router.post("/store")
async def store_entities(
    workspace_id: str,
    request: EnrichRequest,
    db: AsyncSession = Depends(get_db),
):
    """Store extracted entities in database"""
    stored = []
    for entity in request.entities:
        enriched = EnrichmentService.enrich_entity(entity)
        db_entity = await EnrichmentService.store_entity(db, enriched, workspace_id)
        stored.append({"id": db_entity.id, "normalized_value": db_entity.normalized_value})
    return {"stored": stored, "count": len(stored)}


@router.post("/extract-and-store")
async def extract_and_store(
    workspace_id: str,
    request: ExtractRequest,
    db: AsyncSession = Depends(get_db),
):
    """Extract entities from data and store in database"""
    entities = EnrichmentService.extract_entities(request.data, request.source)
    deduplicated = EnrichmentService.deduplicate_entities(entities)
    stored = []
    for entity in deduplicated:
        enriched = EnrichmentService.enrich_entity(entity)
        db_entity = await EnrichmentService.store_entity(db, enriched, workspace_id)
        stored.append({"id": db_entity.id, "type": db_entity.entity_type, "value": db_entity.normalized_value})
    return {"extracted": len(entities), "deduplicated": len(deduplicated), "stored": stored}
