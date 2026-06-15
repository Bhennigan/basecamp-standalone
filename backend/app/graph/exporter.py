"""Graph exporter for PostgreSQL to Neo4j"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import ExtractedEntity, DataRecord
from app.graph.neo4j_client import Neo4jClient
from app.graph.schema import GraphSchema, NodeLabel, RelationshipType

logger = logging.getLogger(__name__)


class GraphExporter:
    """Export entities from PostgreSQL to Neo4j graph database"""
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j = neo4j_client
        
    async def export_entities(
        self, 
        db: AsyncSession, 
        workspace_id: str,
        entity_types: Optional[List[str]] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Export entities from PostgreSQL to Neo4j"""
        stats = {
            "entities_exported": 0,
            "relationships_created": 0,
            "errors": [],
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
        
        try:
            query = select(ExtractedEntity).where(ExtractedEntity.workspace_id == workspace_id)
            if entity_types:
                query = query.where(ExtractedEntity.entity_type.in_(entity_types))
            result = await db.execute(query)
            entities = result.scalars().all()
            
            for i in range(0, len(entities), batch_size):
                batch = entities[i:i + batch_size]
                for entity in batch:
                    try:
                        node_data = self._entity_to_node(entity)
                        await self.neo4j.create_entity_node(node_data)
                        stats["entities_exported"] += 1
                    except Exception as e:
                        stats["errors"].append(f"Error exporting entity {entity.id}: {str(e)}")
                        
            rel_count = await self._build_relationships(db, workspace_id)
            stats["relationships_created"] = rel_count
            
        except Exception as e:
            stats["errors"].append(f"Export failed: {str(e)}")
            
        stats["completed_at"] = datetime.utcnow().isoformat()
        return stats
        
    def _entity_to_node(self, entity: ExtractedEntity) -> Dict[str, Any]:
        """Convert ExtractedEntity to graph node format"""
        label = GraphSchema.entity_type_to_label(entity.entity_type)
        return {
            "id": entity.id,
            "entity_type": label.value,
            "value": entity.value,
            "normalized_value": entity.normalized_value,
            "confidence": entity.confidence,
            "threat_level": entity.threat_level,
            "source": entity.source,
            "workspace_id": entity.workspace_id,
            "source_record_id": entity.source_record_id,
            "tags": entity.tags or [],
            "metadata": entity.entity_metadata or {},
            "first_seen": entity.first_seen.isoformat() if entity.first_seen else None,
            "last_seen": entity.last_seen.isoformat() if entity.last_seen else None,
        }
        
    async def _build_relationships(self, db: AsyncSession, workspace_id: str) -> int:
        """Build relationships between entities based on metadata"""
        relationship_count = 0
        query = select(ExtractedEntity).where(ExtractedEntity.workspace_id == workspace_id)
        result = await db.execute(query)
        entities = result.scalars().all()
        
        entity_lookup: Dict[str, Dict[str, ExtractedEntity]] = {}
        for entity in entities:
            if entity.entity_type not in entity_lookup:
                entity_lookup[entity.entity_type] = {}
            entity_lookup[entity.entity_type][entity.normalized_value] = entity
            
        source_record_groups: Dict[str, List[ExtractedEntity]] = {}
        for entity in entities:
            if entity.source_record_id:
                if entity.source_record_id not in source_record_groups:
                    source_record_groups[entity.source_record_id] = []
                source_record_groups[entity.source_record_id].append(entity)
                
        for record_id, group_entities in source_record_groups.items():
            if len(group_entities) > 1:
                for i, entity_a in enumerate(group_entities[:-1]):
                    for entity_b in group_entities[i+1:]:
                        try:
                            success = await self.neo4j.create_relationship(
                                source_id=entity_a.id,
                                target_id=entity_b.id,
                                relationship_type=RelationshipType.ASSOCIATED_WITH.value,
                                properties={"reason": "same_source_record", "source_record_id": record_id}
                            )
                            if success:
                                relationship_count += 1
                        except Exception as e:
                            logger.error(f"Error creating association: {e}")
                            
        return relationship_count
        
    async def upsert_entity(
        self, 
        entity_id: str,
        entity_type: str,
        value: str,
        workspace_id: str,
        metadata: Dict = {},
        relationships: List[Dict] = []
    ) -> Dict[str, Any]:
        """Upsert a single entity with optional relationships"""
        label = GraphSchema.entity_type_to_label(entity_type)
        node_data = {
            "id": entity_id,
            "entity_type": label.value,
            "value": value,
            "normalized_value": value.lower().strip(),
            "workspace_id": workspace_id,
            "metadata": metadata,
            "confidence": metadata.get("confidence", 1.0),
            "threat_level": metadata.get("threat_level"),
            "source": metadata.get("source", "manual"),
        }
        await self.neo4j.create_entity_node(node_data)
        
        rel_count = 0
        for rel in relationships:
            try:
                success = await self.neo4j.create_relationship(
                    source_id=entity_id,
                    target_id=rel["target_id"],
                    relationship_type=rel.get("type", RelationshipType.RELATED_TO.value),
                    properties=rel.get("properties", {})
                )
                if success:
                    rel_count += 1
            except Exception as e:
                logger.error(f"Error creating relationship: {e}")
                
        return {"entity_id": entity_id, "relationship_count": rel_count}
