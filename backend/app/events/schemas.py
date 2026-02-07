"""Event schema definitions for Base Camp OS NATS integration."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    INGESTION_COMPLETE = "ingestion.complete"
    INGESTION_FAILED = "ingestion.failed"
    INGESTION_STARTED = "ingestion.started"
    ENRICHMENT_COMPLETE = "enrichment.complete"
    ENRICHMENT_FAILED = "enrichment.failed"
    ENRICHMENT_STARTED = "enrichment.started"
    ENTITY_CREATED = "entity.created"
    ENTITY_UPDATED = "entity.updated"
    ENTITY_DELETED = "entity.deleted"
    CONNECTOR_FETCH = "connector.fetch"
    CONNECTOR_ERROR = "connector.error"


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: None)
    event_type: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="basecamp")
    correlation_id: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        if self.event_id is None:
            import uuid
            object.__setattr__(self, "event_id", str(uuid.uuid4()))


class IngestionCompleteEvent(BaseEvent):
    event_type: str = Field(default=EventType.INGESTION_COMPLETE)
    file_id: str = Field(...)
    file_name: str = Field(...)
    record_count: int = Field(...)
    schema_id: Optional[str] = Field(default=None)
    bucket: str = Field(default="raw")
    duration_ms: Optional[int] = Field(default=None)

    @property
    def subject(self) -> str:
        return "basecamp.ingestion.complete"


class IngestionFailedEvent(BaseEvent):
    event_type: str = Field(default=EventType.INGESTION_FAILED)
    file_name: str = Field(...)
    error_message: str = Field(...)
    error_type: str = Field(...)

    @property
    def subject(self) -> str:
        return "basecamp.ingestion.failed"


class EnrichmentCompleteEvent(BaseEvent):
    event_type: str = Field(default=EventType.ENRICHMENT_COMPLETE)
    entity_id: str = Field(...)
    entity_type: str = Field(...)
    enrichment_sources: List[str] = Field(default_factory=list)
    fields_enriched: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @property
    def subject(self) -> str:
        return "basecamp.enrichment.complete"


class EnrichmentFailedEvent(BaseEvent):
    event_type: str = Field(default=EventType.ENRICHMENT_FAILED)
    entity_id: str = Field(...)
    entity_type: str = Field(...)
    error_message: str = Field(...)
    source: str = Field(...)

    @property
    def subject(self) -> str:
        return "basecamp.enrichment.failed"


class EntityCreatedEvent(BaseEvent):
    event_type: str = Field(default=EventType.ENTITY_CREATED)
    entity_id: str = Field(...)
    entity_type: str = Field(...)
    entity_data: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = Field(default=None)

    @property
    def subject(self) -> str:
        return "basecamp.entity.created"


class EntityUpdatedEvent(BaseEvent):
    event_type: str = Field(default=EventType.ENTITY_UPDATED)
    entity_id: str = Field(...)
    entity_type: str = Field(...)
    changes: Dict[str, Any] = Field(default_factory=dict)
    updated_by: Optional[str] = Field(default=None)

    @property
    def subject(self) -> str:
        return "basecamp.entity.updated"


class EntityDeletedEvent(BaseEvent):
    event_type: str = Field(default=EventType.ENTITY_DELETED)
    entity_id: str = Field(...)
    entity_type: str = Field(...)
    deleted_by: Optional[str] = Field(default=None)

    @property
    def subject(self) -> str:
        return "basecamp.entity.deleted"


class ConnectorFetchEvent(BaseEvent):
    event_type: str = Field(default=EventType.CONNECTOR_FETCH)
    connector_type: str = Field(...)
    query: str = Field(...)
    results_count: int = Field(...)
    target_entity_id: Optional[str] = Field(default=None)
    rate_limit_remaining: Optional[int] = Field(default=None)

    @property
    def subject(self) -> str:
        return "basecamp.connector.fetch"


class ConnectorErrorEvent(BaseEvent):
    event_type: str = Field(default=EventType.CONNECTOR_ERROR)
    connector_type: str = Field(...)
    query: str = Field(...)
    error_message: str = Field(...)
    is_rate_limited: bool = Field(default=False)

    @property
    def subject(self) -> str:
        return "basecamp.connector.error"


class PublishEventRequest(BaseModel):
    subject: str = Field(...)
    data: Dict[str, Any] = Field(...)
    headers: Optional[Dict[str, str]] = Field(default=None)


class PublishEventResponse(BaseModel):
    success: bool
    sequence: Optional[str] = None
    message: Optional[str] = None


class WebhookSubscription(BaseModel):
    id: Optional[str] = None
    subject: str = Field(...)
    webhook_url: str = Field(...)
    headers: Optional[Dict[str, str]] = Field(default=None)
    active: bool = Field(default=True)
    created_at: Optional[datetime] = None


class SubjectInfo(BaseModel):
    pattern: str
    description: str
    example_event: str
