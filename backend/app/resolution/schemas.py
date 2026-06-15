"""Pydantic request/response models for the resolution API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Config payloads (mirror the dataclasses in service.py / scoring.py / etc.) ---

class BlockingKeyIn(BaseModel):
    field: str
    strategy: str = "prefix"
    length: int = 4


class FieldRuleIn(BaseModel):
    field: str
    comparator: str
    weight: float = 1.0
    threshold: Optional[float] = None


class SurvivorshipRuleIn(BaseModel):
    field: str
    strategy: str = "most_complete"
    source_priority: Optional[list[str]] = None


class ResolutionConfigIn(BaseModel):
    blocking_keys: Optional[list[BlockingKeyIn]] = None
    rules: Optional[list[FieldRuleIn]] = None
    survivorship: Optional[list[SurvivorshipRuleIn]] = None
    match: float = 0.85
    review_low: float = 0.6
    review_high: float = 0.85
    entity_type: Optional[str] = None


# --- Endpoint bodies ---

class ResolveRequest(BaseModel):
    schema_id: str
    config: Optional[ResolutionConfigIn] = None


class ResolveResponse(BaseModel):
    records: int
    pairs_compared: int
    clusters: int
    merged: int
    queued_for_review: int


class MergeRequest(BaseModel):
    schema_id: str
    record_ids: list[str] = Field(..., min_length=1)
    entity_type: Optional[str] = None


# --- Read models ---

class ClusterMemberOut(BaseModel):
    id: str
    record_id: str
    source: Optional[str] = None
    match_score: float
    linked_at: Optional[datetime] = None


class ClusterOut(BaseModel):
    id: str
    workspace_id: str
    schema_id: str
    entity_type: Optional[str] = None
    canonical: dict[str, Any]
    member_count: int
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ClusterDetailOut(ClusterOut):
    members: list[ClusterMemberOut] = []


class ClusterListOut(BaseModel):
    clusters: list[ClusterOut]
    count: int
