"""Webhook dispatch for consumer notifications."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Consumer

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10.0  # seconds


async def dispatch_webhooks(
    session: AsyncSession,
    workspace_id: str,
    schema_id: str,
    records: list[dict[str, Any]],
) -> None:
    """POST new records to all consumers with active webhooks for this schema.

    Fire-and-forget: webhook failures are logged but never fail ingestion.
    """
    stmt = select(Consumer).where(
        and_(
            Consumer.workspace_id == workspace_id,
            Consumer.active == True,  # noqa: E712
            Consumer.callback_url.isnot(None),
            Consumer.callback_url != "",
        )
    )
    result = await session.execute(stmt)
    consumers = result.scalars().all()

    if not consumers:
        return

    for consumer in consumers:
        # Skip if consumer subscribes to specific schemas and this isn't one
        if consumer.schema_ids and schema_id not in consumer.schema_ids:
            continue

        try:
            await _post_webhook(
                url=consumer.callback_url,
                api_key=consumer.api_key,
                payload={
                    "event": "records.created",
                    "consumer_id": consumer.id,
                    "schema_id": schema_id,
                    "record_count": len(records),
                    "records": records,
                },
            )
            logger.info(
                "Webhook delivered to %s (%s) — %d records",
                consumer.name,
                consumer.callback_url,
                len(records),
            )
        except Exception as e:
            logger.warning(
                "Webhook failed for %s (%s): %s",
                consumer.name,
                consumer.callback_url,
                str(e),
            )


async def _post_webhook(url: str, api_key: str, payload: dict) -> None:
    """POST payload to webhook URL with authentication headers."""
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-BaseCamp-Key": api_key,
                "X-BaseCamp-Event": payload.get("event", "unknown"),
            },
        )
        response.raise_for_status()
