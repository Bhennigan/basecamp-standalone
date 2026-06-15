"""Enrichment service for entity processing"""
import hashlib
import re
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.enrichment.entities import Entity, EntityType, ThreatLevel, EntityRelationship
from app.enrichment.extractors import EntityExtractor
from app.db.models import ExtractedEntity


class EnrichmentService:
    """Service for entity extraction, normalization, and enrichment"""
    
    THREAT_INDICATORS = {
        EntityType.EMAIL: {
            "high": ["protonmail.com", "tutanota.com", "guerrillamail.com", "tempmail.com"],
            "medium": ["yandex.com", "mail.ru"],
        },
        EntityType.DOMAIN: {
            "critical": [".onion", ".i2p"],
            "high": ["pastebin.com", "ghostbin.com"],
        },
        EntityType.IP_ADDRESS: {
            "high": ["192.168.", "10.", "172.16."],
        },
    }
    
    THREAT_TAGS = {
        "critical": ["breach", "leaked", "compromised", "ransomware", "apt"],
        "high": ["malware", "phishing", "botnet", "c2", "tor"],
        "medium": ["suspicious", "proxy", "vpn", "anonymous"],
        "low": ["spam", "advertising"],
    }
    
    @classmethod
    def extract_entities(cls, data: Dict[str, Any], source: str) -> List[Entity]:
        """Extract entities from data dictionary or text"""
        if isinstance(data, str):
            return EntityExtractor.extract_all(data, source)
        return EntityExtractor.extract_from_dict(data, source)
    
    @classmethod
    def deduplicate_entities(cls, entities: List[Entity]) -> List[Entity]:
        """Deduplicate entities based on type and normalized value"""
        seen = {}
        deduplicated = []
        for entity in entities:
            key = f"{entity.type}:{entity.normalized_value}"
            if key not in seen:
                seen[key] = entity
                deduplicated.append(entity)
            else:
                existing = seen[key]
                existing.metadata.update(entity.metadata)
                existing.tags = list(set(existing.tags + entity.tags))
                existing.last_seen = max(existing.last_seen, entity.last_seen)
                if entity.confidence > existing.confidence:
                    existing.confidence = entity.confidence
        return deduplicated
    
    @classmethod
    def enrich_entity(cls, entity: Entity) -> Entity:
        """Enrich entity with additional context (placeholder for external APIs)"""
        if not entity.id:
            entity.id = str(uuid4())
        if not entity.threat_level:
            entity.threat_level = cls.calculate_threat_level(entity)
        entity.metadata["enriched_at"] = datetime.utcnow().isoformat()
        entity.metadata["enrichment_version"] = "1.0.0"
        if entity.type == EntityType.EMAIL:
            parts = entity.normalized_value.split("@")
            if len(parts) == 2:
                entity.metadata["email_domain"] = parts[1]
                entity.metadata["email_local"] = parts[0]
        elif entity.type == EntityType.DOMAIN:
            entity.metadata["domain_hash"] = hashlib.sha256(entity.normalized_value.encode()).hexdigest()[:16]
        elif entity.type == EntityType.IP_ADDRESS:
            octets = entity.normalized_value.split(".")
            if len(octets) == 4:
                entity.metadata["is_private"] = cls._is_private_ip(entity.normalized_value)
        elif entity.type == EntityType.URL:
            match = re.search(r"https?://([^/]+)", entity.normalized_value)
            if match:
                entity.metadata["url_domain"] = match.group(1)
        return entity
    
    @classmethod
    def tag_entity(cls, entity: Entity, tags: List[str]) -> Entity:
        """Add tags to entity and recalculate threat level"""
        entity.tags = list(set(entity.tags + tags))
        entity.threat_level = cls.calculate_threat_level(entity)
        return entity
    
    @classmethod
    def calculate_threat_level(cls, entity: Entity) -> ThreatLevel:
        """Calculate threat level based on entity type, value, and tags"""
        threat_score = 0
        type_indicators = cls.THREAT_INDICATORS.get(entity.type, {})
        for level, patterns in type_indicators.items():
            for pattern in patterns:
                if pattern in entity.normalized_value.lower():
                    if level == "critical":
                        threat_score = max(threat_score, 4)
                    elif level == "high":
                        threat_score = max(threat_score, 3)
                    elif level == "medium":
                        threat_score = max(threat_score, 2)
        for tag in entity.tags:
            tag_lower = tag.lower()
            for level, keywords in cls.THREAT_TAGS.items():
                if any(keyword in tag_lower for keyword in keywords):
                    if level == "critical":
                        threat_score = max(threat_score, 4)
                    elif level == "high":
                        threat_score = max(threat_score, 3)
                    elif level == "medium":
                        threat_score = max(threat_score, 2)
                    elif level == "low":
                        threat_score = max(threat_score, 1)
        if threat_score >= 4:
            return ThreatLevel.CRITICAL
        elif threat_score >= 3:
            return ThreatLevel.HIGH
        elif threat_score >= 2:
            return ThreatLevel.MEDIUM
        elif threat_score >= 1:
            return ThreatLevel.LOW
        return ThreatLevel.INFO
    
    @classmethod
    def _is_private_ip(cls, ip: str) -> bool:
        """Check if IP is in private range"""
        octets = ip.split(".")
        if len(octets) != 4:
            return False
        try:
            first = int(octets[0])
            second = int(octets[1])
            if first == 10:
                return True
            if first == 172 and 16 <= second <= 31:
                return True
            if first == 192 and second == 168:
                return True
            if first == 127:
                return True
        except ValueError:
            pass
        return False
    
    @classmethod
    async def store_entity(cls, db: AsyncSession, entity: Entity, workspace_id: str) -> ExtractedEntity:
        """Store entity in database"""
        db_entity = ExtractedEntity(
            id=entity.id or str(uuid4()),
            workspace_id=workspace_id,
            entity_type=entity.type,
            value=entity.value,
            normalized_value=entity.normalized_value,
            confidence=entity.confidence,
            threat_level=entity.threat_level,
            source=entity.source,
            source_record_id=entity.source_record_id,
            tags=entity.tags,
            entity_metadata=entity.metadata,
            first_seen=entity.first_seen,
            last_seen=entity.last_seen,
        )
        db.add(db_entity)
        await db.commit()
        await db.refresh(db_entity)
        return db_entity
    
    @classmethod
    async def get_entities(cls, db: AsyncSession, workspace_id: str, entity_type: Optional[EntityType] = None, threat_level: Optional[ThreatLevel] = None, limit: int = 100, offset: int = 0) -> List[ExtractedEntity]:
        """Retrieve entities from database with filtering"""
        query = select(ExtractedEntity).where(ExtractedEntity.workspace_id == workspace_id)
        if entity_type:
            query = query.where(ExtractedEntity.entity_type == entity_type)
        if threat_level:
            query = query.where(ExtractedEntity.threat_level == threat_level)
        query = query.order_by(ExtractedEntity.last_seen.desc())
        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def find_entity(cls, db: AsyncSession, workspace_id: str, entity_type: EntityType, normalized_value: str) -> Optional[ExtractedEntity]:
        """Find entity by type and normalized value"""
        query = select(ExtractedEntity).where(
            and_(
                ExtractedEntity.workspace_id == workspace_id,
                ExtractedEntity.entity_type == entity_type,
                ExtractedEntity.normalized_value == normalized_value,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
