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
    """Consumer with metadata."""

    id: str
    workspace_id: str
    api_key: str = Field(description="API key for external feed authentication")
    last_poll: str | None = None
    created_at: str
    updated_at: str


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
