"""Entity extractors for various data types"""
import re
from typing import List, Dict, Any
from app.enrichment.entities import Entity, EntityType


class EntityExtractor:
    """Base extractor with regex patterns for common entities"""
    
    PATTERNS = {
        EntityType.EMAIL: r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        EntityType.PHONE: r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}',
        EntityType.IP_ADDRESS: r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        EntityType.DOMAIN: r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
        EntityType.URL: r'https?://[^\s<>"{}|\^`\[\]]+',
        EntityType.SOCIAL_HANDLE: r'@[a-zA-Z0-9_]{1,50}',
        EntityType.USERNAME: r'(?:user(?:name)?|handle|account)[:\s]+([a-zA-Z0-9_.-]+)',
    }
    
    @classmethod
    def extract_all(cls, text: str, source: str) -> List[Entity]:
        """Extract all entity types from text"""
        entities = []
        for entity_type, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in set(matches):
                entities.append(Entity(
                    type=entity_type,
                    value=match,
                    normalized_value=cls.normalize(entity_type, match),
                    source=source
                ))
        return entities
    
    @classmethod
    def extract_type(cls, text: str, entity_type: EntityType, source: str) -> List[Entity]:
        """Extract specific entity type from text"""
        entities = []
        pattern = cls.PATTERNS.get(entity_type)
        if pattern:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in set(matches):
                entities.append(Entity(
                    type=entity_type,
                    value=match,
                    normalized_value=cls.normalize(entity_type, match),
                    source=source
                ))
        return entities
    
    @classmethod
    def normalize(cls, entity_type: EntityType, value: str) -> str:
        """Normalize entity value based on type"""
        if entity_type == EntityType.EMAIL:
            return value.lower().strip()
        elif entity_type == EntityType.DOMAIN:
            return value.lower().strip().lstrip('www.')
        elif entity_type == EntityType.IP_ADDRESS:
            return value.strip()
        elif entity_type == EntityType.PHONE:
            return re.sub(r'[^\d+]', '', value)
        elif entity_type == EntityType.SOCIAL_HANDLE:
            return value.lower().lstrip('@')
        elif entity_type == EntityType.URL:
            return value.strip().rstrip('/')
        elif entity_type == EntityType.USERNAME:
            return value.lower().strip()
        return value.strip()
    
    @classmethod
    def extract_from_dict(cls, data: Dict[str, Any], source: str, key_prefix: str = "") -> List[Entity]:
        """Recursively extract entities from a dictionary"""
        entities = []
        for key, value in data.items():
            full_key = f"{key_prefix}.{key}" if key_prefix else key
            if isinstance(value, str):
                entities.extend(cls.extract_all(value, f"{source}:{full_key}"))
            elif isinstance(value, dict):
                entities.extend(cls.extract_from_dict(value, source, full_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        entities.extend(cls.extract_all(item, f"{source}:{full_key}[{i}]"))
                    elif isinstance(item, dict):
                        entities.extend(cls.extract_from_dict(item, source, f"{full_key}[{i}]"))
        return entities
