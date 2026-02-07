"""NATS Event Bus integration for Base Camp OS."""
from app.events.nats_client import NATSClient, get_nats_client
from app.events.publisher import EventPublisher, get_event_publisher
from app.events.schemas import (
    IngestionCompleteEvent,
    EnrichmentCompleteEvent,
    EntityCreatedEvent,
    EntityUpdatedEvent,
    ConnectorFetchEvent,
)

__all__ = [
    "NATSClient",
    "get_nats_client",
    "EventPublisher",
    "get_event_publisher",
    "IngestionCompleteEvent",
    "EnrichmentCompleteEvent",
    "EntityCreatedEvent",
    "EntityUpdatedEvent",
    "ConnectorFetchEvent",
]
