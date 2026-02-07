"""Qdrant client for vector operations"""
import os
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models


class VectorClient:
    COLLECTION_NAME = "entities"
    VECTOR_SIZE = 384  # For sentence-transformers/all-MiniLM-L6-v2
    
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self.client = QdrantClient(host=self.host, port=self.port)
        
    async def ensure_collection(self) -> bool:
        """Create collection if not exists"""
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.COLLECTION_NAME not in collection_names:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    ),
                )
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to ensure collection: {e}")
        
    async def upsert_entity(self, entity_id: str, vector: List[float], 
                            payload: Dict[str, Any]) -> bool:
        """Upsert entity vector"""
        try:
            # Convert entity_id to a consistent numeric ID using UUID
            point_id = uuid.uuid5(uuid.NAMESPACE_DNS, entity_id).int % (2**63)
            
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={**payload, "entity_id": entity_id},
                    )
                ],
            )
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to upsert entity: {e}")
        
    async def search_similar(self, vector: List[float], limit: int = 10,
                             filter_conditions: Optional[Dict] = None) -> List[Dict]:
        """Search for similar entities"""
        try:
            query_filter = None
            if filter_conditions:
                must_conditions = []
                for key, value in filter_conditions.items():
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value),
                        )
                    )
                query_filter = models.Filter(must=must_conditions)
            
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=vector,
                limit=limit,
                query_filter=query_filter,
            )
            
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to search similar entities: {e}")
        
    async def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity by ID"""
        try:
            point_id = uuid.uuid5(uuid.NAMESPACE_DNS, entity_id).int % (2**63)
            
            results = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[point_id],
                with_vectors=True,
            )
            
            if results:
                point = results[0]
                return {
                    "id": point.id,
                    "entity_id": entity_id,
                    "vector": point.vector,
                    "payload": point.payload,
                }
            return None
        except Exception as e:
            raise RuntimeError(f"Failed to get entity: {e}")
        
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity vector"""
        try:
            point_id = uuid.uuid5(uuid.NAMESPACE_DNS, entity_id).int % (2**63)
            
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=models.PointIdsList(points=[point_id]),
            )
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to delete entity: {e}")
            
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "collection_name": self.COLLECTION_NAME,
                "vector_size": self.VECTOR_SIZE,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": info.status.value,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get collection stats: {e}")
