"""Neo4j client for graph operations"""
import os
import uuid as _uuid
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase


class Neo4jClient:
    """Async Neo4j client for graph database operations"""
    
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "basecamp123")
        self.driver = None
        
    async def connect(self):
        self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))
        await self.driver.verify_connectivity()
        
    async def close(self):
        if self.driver:
            await self.driver.close()
            self.driver = None
            
    @staticmethod
    def _sanitize(props: Dict[str, Any]) -> Dict[str, Any]:
        """Convert UUID objects and other non-native types to Neo4j-safe values."""
        clean: Dict[str, Any] = {}
        for k, v in props.items():
            if isinstance(v, _uuid.UUID):
                clean[k] = str(v)
            elif isinstance(v, list):
                clean[k] = [str(i) if isinstance(i, _uuid.UUID) else i for i in v]
            elif isinstance(v, dict):
                # Neo4j doesn't support nested maps — skip or flatten
                continue
            elif v is None:
                continue
            else:
                clean[k] = v
        return clean

    async def create_entity_node(self, entity: Dict[str, Any]) -> str:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        label = entity.get("entity_type", "Entity").replace(" ", "_")
        properties = {
            "id": entity["id"],
            "value": entity["value"],
            "normalized_value": entity.get("normalized_value", entity["value"]),
            "confidence": entity.get("confidence", 1.0),
            "threat_level": entity.get("threat_level"),
            "source": entity.get("source", "unknown"),
            "workspace_id": entity.get("workspace_id"),
        }
        metadata = entity.get("metadata", {})
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                properties[f"meta_{key}"] = value
        tags = entity.get("tags", [])
        if tags:
            properties["tags"] = tags
        properties = self._sanitize(properties)
        node_id = str(entity["id"])
        query = f"MERGE (n:{label} {{id: $id}}) SET n += $properties RETURN n.id as id"
        async with self.driver.session() as session:
            result = await session.run(query, id=node_id, properties=properties)
            record = await result.single()
            return record["id"] if record else entity["id"]
        
    async def create_relationship(self, source_id: str, target_id: str, relationship_type: str, properties: Dict = {}) -> bool:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        rel_type = relationship_type.upper().replace(" ", "_")
        query = f"MATCH (a {{id: $source_id}}) MATCH (b {{id: $target_id}}) MERGE (a)-[r:{rel_type}]->(b) SET r += $properties RETURN type(r)"
        clean_props = self._sanitize(properties)
        async with self.driver.session() as session:
            result = await session.run(query, source_id=str(source_id), target_id=str(target_id), properties=clean_props)
            record = await result.single()
            return record is not None
        
    async def find_entity(self, entity_type: str, value: str) -> Optional[Dict]:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        label = entity_type.replace(" ", "_")
        query = f"MATCH (n:{label}) WHERE n.normalized_value = $value OR n.value = $value RETURN n LIMIT 1"
        async with self.driver.session() as session:
            result = await session.run(query, value=value)
            record = await result.single()
            return dict(record["n"]) if record else None
        
    async def get_entity_relationships(self, entity_id: str) -> List[Dict]:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        query = "MATCH (n {id: $entity_id})-[r]-(m) RETURN n.id as source_id, labels(n)[0] as source_type, type(r) as relationship_type, m.id as target_id, labels(m)[0] as target_type"
        async with self.driver.session() as session:
            result = await session.run(query, entity_id=entity_id)
            return await result.data()
        
    async def search_graph(self, query: str, params: Dict = {}) -> List[Dict]:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            return await result.data()
            
    async def get_stats(self) -> Dict[str, Any]:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        query = "CALL apoc.meta.stats() YIELD nodeCount, relCount, labels, relTypes RETURN nodeCount, relCount, labels, relTypes"
        async with self.driver.session() as session:
            try:
                result = await session.run(query)
                record = await result.single()
                if record:
                    return {"node_count": record["nodeCount"], "relationship_count": record["relCount"], "labels": record["labels"], "relationship_types": record["relTypes"]}
            except:
                pass
        return {"node_count": 0, "relationship_count": 0, "labels": [], "relationship_types": []}
        
    async def delete_entity(self, entity_id: str) -> bool:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        query = "MATCH (n {id: $entity_id}) DETACH DELETE n RETURN count(n) as deleted"
        async with self.driver.session() as session:
            result = await session.run(query, entity_id=entity_id)
            record = await result.single()
            return record and record["deleted"] > 0
            
    async def clear_workspace(self, workspace_id: str) -> int:
        if not self.driver:
            raise RuntimeError("Neo4j client not connected")
        query = "MATCH (n {workspace_id: $workspace_id}) DETACH DELETE n RETURN count(n) as deleted"
        async with self.driver.session() as session:
            result = await session.run(query, workspace_id=workspace_id)
            record = await result.single()
            return record["deleted"] if record else 0


_neo4j_client: Optional[Neo4jClient] = None

async def get_neo4j_client() -> Neo4jClient:
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
        await _neo4j_client.connect()
    return _neo4j_client

async def close_neo4j_client():
    global _neo4j_client
    if _neo4j_client:
        await _neo4j_client.close()
        _neo4j_client = None
