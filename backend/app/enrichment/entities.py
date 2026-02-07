"""Entity types for digital persona protection"""
from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    EMAIL = "email"
    PHONE = "phone"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    SOCIAL_HANDLE = "social_handle"
    USERNAME = "username"
    PHYSICAL_ADDRESS = "address"
    CREDENTIAL = "credential"
    DOCUMENT = "document"
    IMAGE = "image"
    URL = "url"


class ThreatLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Entity(BaseModel):
    id: Optional[str] = None
    type: EntityType
    value: str
    normalized_value: str
    confidence: float = 1.0
    threat_level: Optional[ThreatLevel] = None
    source: str
    source_record_id: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    first_seen: datetime = datetime.utcnow()
    last_seen: datetime = datetime.utcnow()

    class Config:
        use_enum_values = True


class EntityRelationship(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = {}
