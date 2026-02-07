"""Graph API router for Neo4j operations"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.graph.neo4j_client import Neo4jClient, get_neo4j_client
from app.graph.exporter import GraphExporter
from app.graph.schema import NodeLabel, RelationshipType, GraphSchema

router = APIRouter()


class ExportRequest(BaseModel):
    workspace_id: str = Field(..., description="Workspace ID to export")
    entity_types: Optional[List[str]] = Field(None, description="Entity types to filter")
    batch_size: int = Field(100, description="Batch size for processing")
    

class ExportResponse(BaseModel):
    entities_exported: int
    relationships_created: int
    errors: List[str]
    started_at: str
    completed_at: Optional[str]
    

class EntityResponse(BaseModel):
    entity: Dict[str, Any]
    relationships: List[Dict[str, Any]]
    

class CypherQueryRequest(BaseModel):
    query: str = Field(..., description="Cypher query to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    

class CypherQueryResponse(BaseModel):
    results: List[Dict[str, Any]]
    count: int
    execution_time_ms: float
    

class GraphStatsResponse(BaseModel):
    node_count: int
    relationship_count: int
    labels: Dict[str, int]
    relationship_types: Dict[str, int]


class CreateRelationshipRequest(BaseModel):
    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Type of relationship")
    properties: Dict[str, Any] = Field(default_factory=dict)


class CreateRelationshipResponse(BaseModel):
    success: bool
    source_id: str
    target_id: str
    relationship_type: str


class CreateEntityRequest(BaseModel):
    entity_id: str
    entity_type: str
    value: str
    workspace_id: str
    confidence: float = 1.0
    threat_level: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class CreateEntityResponse(BaseModel):
    entity_id: str
    entity_type: str
    label: str


async def get_client() -> Neo4jClient:
    try:
        client = await get_neo4j_client()
        return client
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j connection failed: {str(e)}")


@router.post("/export", response_model=ExportResponse)
async def export_entities_to_graph(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_client)
):
    """Export entities from PostgreSQL to Neo4j graph database"""
    exporter = GraphExporter(neo4j)
    result = await exporter.export_entities(
        db=db, workspace_id=request.workspace_id,
        entity_types=request.entity_types, batch_size=request.batch_size
    )
    return ExportResponse(**result)


@router.get("/entity/{entity_id}", response_model=EntityResponse)
async def get_entity_with_relationships(
    entity_id: str,
    neo4j: Neo4jClient = Depends(get_client)
):
    """Get entity and all its relationships from the graph"""
    query = "MATCH (n {id: $entity_id}) RETURN n, labels(n) as labels"
    results = await neo4j.search_graph(query, {"entity_id": entity_id})
    if not results:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity_data = dict(results[0]["n"])
    entity_data["labels"] = results[0]["labels"]
    relationships = await neo4j.get_entity_relationships(entity_id)
    return EntityResponse(entity=entity_data, relationships=relationships)


@router.post("/query", response_model=CypherQueryResponse)
async def execute_cypher_query(
    request: CypherQueryRequest,
    neo4j: Neo4jClient = Depends(get_client)
):
    """Execute a Cypher query against the graph database"""
    query_upper = request.query.upper()
    for keyword in ["DELETE", "REMOVE", "DROP", "DETACH"]:
        if keyword in query_upper:
            raise HTTPException(status_code=400, detail=f"Query contains blocked keyword: {keyword}")
    start_time = time.time()
    try:
        results = await neo4j.search_graph(request.query, request.params)
        execution_time = (time.time() - start_time) * 1000
        return CypherQueryResponse(results=results, count=len(results), execution_time_ms=round(execution_time, 2))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_statistics(neo4j: Neo4jClient = Depends(get_client)):
    """Get statistics about the graph database"""
    stats = await neo4j.get_stats()
    labels = stats.get("labels", {})
    rel_types = stats.get("relationship_types", {})
    if isinstance(labels, list):
        labels = {l: 0 for l in labels if isinstance(l, str)}
    if isinstance(rel_types, list):
        rel_types = {r: 0 for r in rel_types if isinstance(r, str)}
    return GraphStatsResponse(
        node_count=stats.get("node_count", 0),
        relationship_count=stats.get("relationship_count", 0),
        labels=labels, relationship_types=rel_types
    )


@router.post("/relationships", response_model=CreateRelationshipResponse)
async def create_relationship(
    request: CreateRelationshipRequest,
    neo4j: Neo4jClient = Depends(get_client)
):
    """Create a relationship between two entities"""
    success = await neo4j.create_relationship(
        source_id=request.source_id, target_id=request.target_id,
        relationship_type=request.relationship_type, properties=request.properties
    )
    if not success:
        raise HTTPException(status_code=404, detail="One or both entities not found")
    return CreateRelationshipResponse(
        success=True, source_id=request.source_id,
        target_id=request.target_id, relationship_type=request.relationship_type
    )


@router.post("/entity", response_model=CreateEntityResponse)
async def create_entity(
    request: CreateEntityRequest,
    neo4j: Neo4jClient = Depends(get_client)
):
    """Create an entity node in the graph"""
    label = GraphSchema.entity_type_to_label(request.entity_type)
    entity_data = {
        "id": request.entity_id, "entity_type": label.value,
        "value": request.value, "normalized_value": request.value.lower().strip(),
        "workspace_id": request.workspace_id, "confidence": request.confidence,
        "threat_level": request.threat_level, "source": request.metadata.get("source", "api"),
        "metadata": request.metadata, "tags": request.tags,
    }
    await neo4j.create_entity_node(entity_data)
    return CreateEntityResponse(entity_id=request.entity_id, entity_type=request.entity_type, label=label.value)


@router.delete("/entity/{entity_id}")
async def delete_entity(entity_id: str, neo4j: Neo4jClient = Depends(get_client)):
    """Delete an entity and all its relationships from the graph"""
    success = await neo4j.delete_entity(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"deleted": True, "entity_id": entity_id}


@router.delete("/workspace/{workspace_id}")
async def clear_workspace_graph(workspace_id: str, neo4j: Neo4jClient = Depends(get_client)):
    """Delete all entities for a workspace from the graph"""
    deleted_count = await neo4j.clear_workspace(workspace_id)
    return {"deleted": True, "workspace_id": workspace_id, "nodes_deleted": deleted_count}


@router.get("/schema/labels")
async def get_schema_labels():
    """Get all available node labels from the schema"""
    return {
        "labels": [label.value for label in NodeLabel],
        "descriptions": {
            label.value: GraphSchema.get_node_definition(label).description
            if GraphSchema.get_node_definition(label) else ""
            for label in NodeLabel
        }
    }


@router.get("/schema/relationships")
async def get_schema_relationships():
    """Get all available relationship types from the schema"""
    return {
        "relationship_types": [rel.value for rel in RelationshipType],
        "definitions": {
            rel.value: {
                "source_labels": [l.value for l in GraphSchema.get_relationship_definition(rel).source_labels]
                if GraphSchema.get_relationship_definition(rel) else [],
                "target_labels": [l.value for l in GraphSchema.get_relationship_definition(rel).target_labels]
                if GraphSchema.get_relationship_definition(rel) else [],
            }
            for rel in RelationshipType
        }
    }


@router.get("/search")
async def search_entities(
    q: str = Query(..., description="Search term"),
    entity_type: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    neo4j: Neo4jClient = Depends(get_client)
):
    """Search for entities in the graph by value"""
    where_clauses = ["n.value CONTAINS $search OR n.normalized_value CONTAINS $search"]
    params = {"search": q.lower(), "limit": limit}
    if workspace_id:
        where_clauses.append("n.workspace_id = $workspace_id")
        params["workspace_id"] = workspace_id
    label_filter = ""
    if entity_type:
        label = GraphSchema.entity_type_to_label(entity_type)
        label_filter = f":{label.value}"
    where_clause = " AND ".join(where_clauses)
    query = f"MATCH (n{label_filter}) WHERE {where_clause} RETURN n, labels(n) as labels LIMIT $limit"
    results = await neo4j.search_graph(query, params)
    entities = []
    for record in results:
        entity = dict(record["n"])
        entity["labels"] = record["labels"]
        entities.append(entity)
    return {"query": q, "count": len(entities), "entities": entities}


@router.get("/neighbors/{entity_id}")
async def get_entity_neighbors(
    entity_id: str,
    depth: int = Query(1, le=3),
    relationship_types: Optional[str] = Query(None),
    neo4j: Neo4jClient = Depends(get_client)
):
    """Get neighboring entities up to a specified depth"""
    rel_filter = ""
    if relationship_types:
        types = relationship_types.split(",")
        rel_filter = ":" + "|".join(types)
    query = f"MATCH path = (start {{id: $entity_id}})-[r{rel_filter}*1..{depth}]-(neighbor) RETURN neighbor.id as id, neighbor.value as value, labels(neighbor)[0] as type, length(path) as distance LIMIT 100"
    results = await neo4j.search_graph(query, {"entity_id": entity_id})
    return {"entity_id": entity_id, "depth": depth, "neighbors": results}


@router.post("/init")
async def initialize_schema(neo4j: Neo4jClient = Depends(get_client)):
    """Initialize graph schema with constraints and indexes"""
    results = {"constraints_created": 0, "indexes_created": 0, "errors": []}
    for constraint in GraphSchema.get_cypher_constraints():
        try:
            await neo4j.search_graph(constraint, {})
            results["constraints_created"] += 1
        except Exception as e:
            if "already exists" not in str(e).lower():
                results["errors"].append(str(e))
    for index in GraphSchema.get_cypher_indexes():
        try:
            await neo4j.search_graph(index, {})
            results["indexes_created"] += 1
        except Exception as e:
            if "already exists" not in str(e).lower():
                results["errors"].append(str(e))
    return results
