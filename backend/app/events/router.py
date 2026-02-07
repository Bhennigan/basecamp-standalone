"""FastAPI router for NATS event bus endpoints."""
import uuid
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.events.nats_client import NATSClient, get_nats_client
from app.events.publisher import get_event_publisher
from app.events.schemas import (
    PublishEventRequest,
    PublishEventResponse,
    WebhookSubscription,
    SubjectInfo,
)

router = APIRouter()

_webhook_subscriptions: Dict[str, WebhookSubscription] = {}

AVAILABLE_SUBJECTS: List[SubjectInfo] = [
    SubjectInfo(pattern="basecamp.ingestion.complete", description="Emitted when data ingestion completes", example_event="file_id: abc123"),
    SubjectInfo(pattern="basecamp.ingestion.failed", description="Emitted when data ingestion fails", example_event="error: Invalid format"),
    SubjectInfo(pattern="basecamp.ingestion.*", description="Wildcard for all ingestion events", example_event="Matches: complete, failed"),
    SubjectInfo(pattern="basecamp.enrichment.complete", description="Emitted when enrichment completes", example_event="entity_id: ent123"),
    SubjectInfo(pattern="basecamp.enrichment.*", description="Wildcard for all enrichment events", example_event="Matches: complete, failed"),
    SubjectInfo(pattern="basecamp.entity.created", description="Emitted when entity is created", example_event="entity_id: ent123"),
    SubjectInfo(pattern="basecamp.entity.updated", description="Emitted when entity is updated", example_event="entity_id: ent123"),
    SubjectInfo(pattern="basecamp.entity.*", description="Wildcard for all entity events", example_event="Matches: created, updated"),
    SubjectInfo(pattern="basecamp.connector.fetch", description="Emitted when connector fetches", example_event="connector: twitter"),
    SubjectInfo(pattern="basecamp.connector.error", description="Emitted on connector error", example_event="error: Rate limited"),
]

@router.post("/publish", response_model=PublishEventResponse)
async def publish_event(request: PublishEventRequest):
    """Publish an event to the NATS message bus."""
    try:
        client = await get_nats_client()
        sequence = await client.publish_event(subject=request.subject, data=request.data, headers=request.headers)
        return PublishEventResponse(success=True, sequence=sequence)
    except Exception as e:
        return PublishEventResponse(success=False, message=f"Failed to publish event: {str(e)}")


@router.get("/subjects", response_model=List[SubjectInfo])
async def list_subjects():
    """List all available event subjects."""
    return AVAILABLE_SUBJECTS


@router.post("/subscriptions", response_model=WebhookSubscription)
async def create_subscription(subscription: WebhookSubscription, background_tasks: BackgroundTasks):
    """Create a webhook subscription for events."""
    if not subscription.id:
        subscription.id = str(uuid.uuid4())
    subscription.created_at = datetime.utcnow()
    _webhook_subscriptions[subscription.id] = subscription
    try:
        client = await get_nats_client()
        async def webhook_callback(data: Dict[str, Any]):
            await forward_to_webhook(subscription, data)
        await client.subscribe(subject=subscription.subject, callback=webhook_callback, durable=f"webhook_{subscription.id}")
    except Exception as e:
        del _webhook_subscriptions[subscription.id]
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {str(e)}")
    return subscription

@router.get("/subscriptions", response_model=List[WebhookSubscription])
async def list_subscriptions():
    """List all webhook subscriptions."""
    return list(_webhook_subscriptions.values())


@router.get("/subscriptions/{subscription_id}", response_model=WebhookSubscription)
async def get_subscription(subscription_id: str):
    """Get a specific webhook subscription by ID."""
    if subscription_id not in _webhook_subscriptions:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return _webhook_subscriptions[subscription_id]


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """Delete a webhook subscription."""
    if subscription_id not in _webhook_subscriptions:
        raise HTTPException(status_code=404, detail="Subscription not found")
    try:
        client = await get_nats_client()
        subscription = _webhook_subscriptions[subscription_id]
        sub_id = f"{subscription.subject}_webhook_{subscription_id}"
        await client.unsubscribe(sub_id)
    except Exception:
        pass
    del _webhook_subscriptions[subscription_id]
    return {"status": "deleted", "subscription_id": subscription_id}

@router.get("/health")
async def events_health():
    """Check NATS connection health."""
    try:
        client = await get_nats_client()
        return {
            "status": "healthy" if client.is_connected else "disconnected",
            "nats_url": client.nats_url,
            "active_subscriptions": len(client.get_subscriptions()),
            "webhook_subscriptions": len(_webhook_subscriptions),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def forward_to_webhook(subscription: WebhookSubscription, data: Dict[str, Any]):
    """Forward event data to webhook URL."""
    try:
        headers = {"Content-Type": "application/json"}
        if subscription.headers:
            headers.update(subscription.headers)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                subscription.webhook_url,
                json={
                    "subscription_id": subscription.id,
                    "subject": subscription.subject,
                    "event": data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                headers=headers,
                timeout=30.0,
            )
            if response.status_code >= 400:
                print(f"Webhook delivery failed: {response.status_code}")
    except Exception as e:
        print(f"Failed to deliver webhook: {e}")
