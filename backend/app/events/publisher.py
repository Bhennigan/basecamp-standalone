"""Event publisher wrapper for typed event publishing."""
from typing import Optional, Dict, Any, List

from app.events.nats_client import NATSClient, get_nats_client
from app.events.schemas import (
    BaseEvent,
    IngestionCompleteEvent,
    IngestionFailedEvent,
    EnrichmentCompleteEvent,
    EnrichmentFailedEvent,
    EntityCreatedEvent,
    EntityUpdatedEvent,
    EntityDeletedEvent,
    ConnectorFetchEvent,
    ConnectorErrorEvent,
)


class EventPublisher:
    """High-level event publisher with typed event methods."""

    def __init__(self, client: Optional[NATSClient] = None):
        self._client = client
        self._initialized = False

    async def _ensure_client(self) -> NATSClient:
        if self._client is None:
            self._client = await get_nats_client()
        return self._client

    async def publish(self, event: BaseEvent) -> str:
        client = await self._ensure_client()
        subject = event.subject if hasattr(event, "subject") else f"basecamp.{event.event_type}"
        return await client.publish_event(subject, event.model_dump(mode="json"))

    async def publish_raw(self, subject: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        client = await self._ensure_client()
        return await client.publish_event(subject, data, headers)

    async def ingestion_complete(
        self,
        file_id: str,
        file_name: str,
        record_count: int,
        schema_id: Optional[str] = None,
        bucket: str = "raw",
        duration_ms: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = IngestionCompleteEvent(
            file_id=file_id,
            file_name=file_name,
            record_count=record_count,
            schema_id=schema_id,
            bucket=bucket,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def ingestion_failed(
        self,
        file_name: str,
        error_message: str,
        error_type: str,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = IngestionFailedEvent(
            file_name=file_name,
            error_message=error_message,
            error_type=error_type,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def enrichment_complete(
        self,
        entity_id: str,
        entity_type: str,
        enrichment_sources: List[str],
        fields_enriched: List[str],
        confidence_score: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = EnrichmentCompleteEvent(
            entity_id=entity_id,
            entity_type=entity_type,
            enrichment_sources=enrichment_sources,
            fields_enriched=fields_enriched,
            confidence_score=confidence_score,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def enrichment_failed(
        self,
        entity_id: str,
        entity_type: str,
        error_message: str,
        source: str,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = EnrichmentFailedEvent(
            entity_id=entity_id,
            entity_type=entity_type,
            error_message=error_message,
            source=source,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def entity_created(
        self,
        entity_id: str,
        entity_type: str,
        entity_data: Dict[str, Any],
        created_by: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = EntityCreatedEvent(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_data=entity_data,
            created_by=created_by,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def entity_updated(
        self,
        entity_id: str,
        entity_type: str,
        changes: Dict[str, Any],
        updated_by: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = EntityUpdatedEvent(
            entity_id=entity_id,
            entity_type=entity_type,
            changes=changes,
            updated_by=updated_by,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def entity_deleted(
        self,
        entity_id: str,
        entity_type: str,
        deleted_by: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = EntityDeletedEvent(
            entity_id=entity_id,
            entity_type=entity_type,
            deleted_by=deleted_by,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def connector_fetch(
        self,
        connector_type: str,
        query: str,
        results_count: int,
        target_entity_id: Optional[str] = None,
        rate_limit_remaining: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = ConnectorFetchEvent(
            connector_type=connector_type,
            query=query,
            results_count=results_count,
            target_entity_id=target_entity_id,
            rate_limit_remaining=rate_limit_remaining,
            correlation_id=correlation_id,
        )
        return await self.publish(event)

    async def connector_error(
        self,
        connector_type: str,
        query: str,
        error_message: str,
        is_rate_limited: bool = False,
        correlation_id: Optional[str] = None,
    ) -> str:
        event = ConnectorErrorEvent(
            connector_type=connector_type,
            query=query,
            error_message=error_message,
            is_rate_limited=is_rate_limited,
            correlation_id=correlation_id,
        )
        return await self.publish(event)


_event_publisher: Optional[EventPublisher] = None


async def get_event_publisher() -> EventPublisher:
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = EventPublisher()
    return _event_publisher
