"""Vector operations API router"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .qdrant_client import VectorClient
from .embeddings import EmbeddingGenerator


router = APIRouter()

# Initialize clients
vector_client = VectorClient()
embedding_generator = EmbeddingGenerator()


class EntityPayload(BaseModel):
    """Entity data for indexing"""
    id: str = Field(..., description="Unique entity identifier")
    type: str = Field(..., description="Entity type (e.g., IP, domain, hash)")
    value: str = Field(..., description="Entity value")
    tags: Optional[List[str]] = Field(default=None, description="Entity tags")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class IndexRequest(BaseModel):
    """Request to index entities"""
    entities: List[EntityPayload] = Field(..., description="Entities to index")


class SearchRequest(BaseModel):
    """Request to search similar entities"""
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    filter_type: Optional[str] = Field(default=None, description="Filter by entity type")


class IndexResponse(BaseModel):
    """Response for index operation"""
    indexed: int
    failed: int
    errors: List[str]


class SearchResult(BaseModel):
    """Single search result"""
    entity_id: str
    score: float
    payload: Dict[str, Any]


class SearchResponse(BaseModel):
    """Response for search operation"""
    results: List[SearchResult]
    total: int


class EntityVectorResponse(BaseModel):
    """Response for get entity vector"""
    entity_id: str
    vector: List[float]
    payload: Dict[str, Any]


class StatsResponse(BaseModel):
    """Collection statistics response"""
    collection_name: str
    vector_size: int
    points_count: int
    indexed_vectors_count: int
    status: str


@router.post("/index", response_model=IndexResponse, status_code=status.HTTP_201_CREATED)
async def index_entities(request: IndexRequest):
    """Index entities in Qdrant vector database"""
    try:
        await vector_client.ensure_collection()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Qdrant: {str(e)}"
        )
    
    indexed = 0
    failed = 0
    errors = []
    
    for entity in request.entities:
        try:
            # Convert entity to text and generate embedding
            entity_dict = entity.model_dump()
            text = embedding_generator.entity_to_text(entity_dict)
            vector = embedding_generator.generate(text)
            
            # Prepare payload
            payload = {
                "type": entity.type,
                "value": entity.value,
                "tags": entity.tags or [],
                "metadata": entity.metadata or {},
            }
            
            # Upsert to Qdrant
            await vector_client.upsert_entity(
                entity_id=entity.id,
                vector=vector,
                payload=payload,
            )
            indexed += 1
        except Exception as e:
            failed += 1
            errors.append(f"Entity {entity.id}: {str(e)}")
    
    return IndexResponse(indexed=indexed, failed=failed, errors=errors)


@router.post("/search", response_model=SearchResponse)
async def search_similar(request: SearchRequest):
    """Search for similar entities by text query"""
    try:
        await vector_client.ensure_collection()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Qdrant: {str(e)}"
        )
    
    try:
        # Generate query embedding
        query_vector = embedding_generator.generate(request.query)
        
        # Build filter conditions
        filter_conditions = None
        if request.filter_type:
            filter_conditions = {"type": request.filter_type}
        
        # Search
        results = await vector_client.search_similar(
            vector=query_vector,
            limit=request.limit,
            filter_conditions=filter_conditions,
        )
        
        search_results = [
            SearchResult(
                entity_id=r["payload"].get("entity_id", str(r["id"])),
                score=r["score"],
                payload=r["payload"],
            )
            for r in results
        ]
        
        return SearchResponse(results=search_results, total=len(search_results))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/entity/{entity_id}", response_model=EntityVectorResponse)
async def get_entity_vector(entity_id: str):
    """Get entity vector by ID"""
    try:
        await vector_client.ensure_collection()
        result = await vector_client.get_entity(entity_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_id} not found"
            )
        
        return EntityVectorResponse(
            entity_id=entity_id,
            vector=result["vector"],
            payload=result["payload"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entity: {str(e)}"
        )


@router.delete("/entity/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity_vector(entity_id: str):
    """Delete entity vector by ID"""
    try:
        await vector_client.ensure_collection()
        await vector_client.delete_entity(entity_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete entity: {str(e)}"
        )


@router.get("/stats", response_model=StatsResponse)
async def get_collection_stats():
    """Get vector collection statistics"""
    try:
        await vector_client.ensure_collection()
        stats = await vector_client.get_collection_stats()
        return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get stats: {str(e)}"
        )
