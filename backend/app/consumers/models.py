"""Consumer subscription models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConsumerCreate(BaseModel):
    """Register a new consumer/subscriber."""

    name: str = Field(..., min_length=1, max_length=255, description="Consumer name (e.g., 'ascension-prod')")
    description: str | None = None
    callback_url: str | None = Field(default=None, description="Webhook URL — Base Camp POSTs new records here")
    schema_ids: list[str] = Field(default_factory=list, description="Schema IDs to subscribe to (empty = all)")
    mapping_profile_id: str | None = Field(default=None, description="Mapping profile for egress transformation")
    active: bool = True


class ConsumerRead(ConsumerCreate):
    """Consumer with metadata.

    Never exposes a stored secret: only the short, non-secret ``api_key_prefix``
    for display. The raw token is returned once at creation via ``ConsumerCreated``.
    """

    id: str
    workspace_id: str
    api_key_prefix: str = Field(description="Non-secret API key prefix for display (e.g. 'bc_a1b2c3d4')")
    last_poll: str | None = None
    created_at: str
    updated_at: str


class ConsumerCreated(ConsumerRead):
    """Create-only response: includes the one-time raw API key.

    Returned ONLY from the POST create endpoint. The raw ``api_key`` is shown
    once and never persisted in plaintext or re-shown by any other endpoint.
    """

    api_key: str = Field(description="One-time raw API key — shown once, store it securely now")


class ConsumerUpdate(BaseModel):
    """Update a consumer."""

    name: str | None = None
    description: str | None = None
    callback_url: str | None = None
    schema_ids: list[str] | None = None
    mapping_profile_id: str | None = None
    active: bool | None = None


class ChangeFeedResponse(BaseModel):
    """Response for the change feed endpoint."""

    records: list[dict[str, Any]]
    cursor: str = Field(description="Cursor for next poll (ISO timestamp of last record)")
    has_more: bool
    count: int


class SchemaRegistryEntry(BaseModel):
    """Schema available for consumption."""

    id: str
    name: str
    description: str | None
    version: int
    fields: list[dict[str, Any]]
    record_count: int
