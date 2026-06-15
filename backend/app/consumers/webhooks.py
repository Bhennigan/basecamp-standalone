"""Webhook dispatch for consumer notifications."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Consumer

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10.0  # seconds
WEBHOOK_MAX_ATTEMPTS = 3
WEBHOOK_BACKOFF_SECONDS = (0.5, 1.0, 2.0)  # sleep AFTER attempt n (last entry unused)

# Type of an async "post" callable: (url, payload, headers) -> status_code.
PostFn = Callable[[str, dict, dict], Awaitable[int]]


async def dispatch_webhooks(
    session: AsyncSession,
    workspace_id: str,
    schema_id: str,
    records: list[dict[str, Any]],
) -> None:
    """POST new records to all consumers with active webhooks for this schema.

    Fire-and-forget: webhook failures are logged (and dead-lettered) but never
    fail ingestion.
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

        # Identify the consumer via the non-secret prefix. NOTE: this is an
        # identifier, not an authenticator. Callback authenticity via a shared
        # HMAC secret (signed body digest header) is a future enhancement.
        headers = {
            "Content-Type": "application/json",
            "X-BaseCamp-Consumer": consumer.api_key_prefix or "",
            "X-BaseCamp-Event": "records.created",
        }
        payload = {
            "event": "records.created",
            "consumer_id": consumer.id,
            "schema_id": schema_id,
            "record_count": len(records),
            "records": records,
        }

        delivered = await deliver_with_retry(
            url=consumer.callback_url,
            payload=payload,
            headers=headers,
        )

        if delivered:
            logger.info(
                "Webhook delivered to %s (%s) — %d records",
                consumer.name,
                consumer.callback_url,
                len(records),
            )
        else:
            # Dead-letter: structured record of the final failure. A logged
            # dead-letter is sufficient — no DB table required.
            logger.error(
                "Webhook dead-letter — consumer_id=%s callback_url=%s schema_id=%s "
                "record_count=%d attempts=%d",
                consumer.id,
                consumer.callback_url,
                schema_id,
                len(records),
                WEBHOOK_MAX_ATTEMPTS,
            )


async def deliver_with_retry(
    url: str,
    payload: dict,
    headers: dict,
    *,
    post_fn: PostFn | None = None,
    max_attempts: int = WEBHOOK_MAX_ATTEMPTS,
    backoff: tuple[float, ...] = WEBHOOK_BACKOFF_SECONDS,
) -> bool:
    """Attempt delivery up to ``max_attempts`` times with exponential backoff.

    Retries on connect/transport error or any non-2xx status. Returns True on
    a 2xx response, False if all attempts are exhausted. Never raises — webhook
    delivery must not propagate into the caller (ingestion).

    ``post_fn`` is injectable for testing; defaults to a real httpx POST.
    """
    poster = post_fn or _httpx_post

    for attempt in range(1, max_attempts + 1):
        try:
            status = await poster(url, payload, headers)
            if 200 <= status < 300:
                return True
            last_error: str = f"HTTP {status}"
        except Exception as e:  # noqa: BLE001 — fire-and-forget, swallow everything
            last_error = f"{type(e).__name__}: {e}"

        if attempt < max_attempts:
            logger.warning(
                "Webhook attempt %d/%d failed for %s: %s — retrying",
                attempt,
                max_attempts,
                url,
                last_error,
            )
            # backoff[attempt-1] is the sleep after this attempt
            idx = min(attempt - 1, len(backoff) - 1)
            await asyncio.sleep(backoff[idx])
        else:
            logger.warning(
                "Webhook attempt %d/%d failed for %s: %s — giving up",
                attempt,
                max_attempts,
                url,
                last_error,
            )

    return False


async def _httpx_post(url: str, payload: dict, headers: dict) -> int:
    """Real POST: returns the HTTP status code (no raise_for_status)."""
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        return response.status_code
