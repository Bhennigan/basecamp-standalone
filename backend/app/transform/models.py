"""Transformation rule models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldMapping(BaseModel):
    """Maps a source field to a target field with optional transformation."""

    source_field: str = Field(..., description="Source field name (dot notation for nested)")
    target_field: str = Field(..., description="Target field name")
    transform: Literal[
        "rename", "cast", "format", "extract", "default", "concat",
        "split", "lookup", "lower", "upper", "trim", "regex",
    ] = Field(default="rename")
    params: dict[str, Any] = Field(default_factory=dict, description="Transform-specific parameters")


class MappingProfile(BaseModel):
    """A complete field mapping profile from source schema to target schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    source_schema_id: str | None = Field(default=None, description="Source schema ID (optional)")
    target_schema_id: str = Field(..., description="Target schema ID to map into")
    mappings: list[FieldMapping] = Field(default_factory=list)
    drop_unmapped: bool = Field(default=False, description="Drop fields not in mappings")


class MappingProfileRead(MappingProfile):
    """Read model with ID and timestamps."""

    id: str
    workspace_id: str
    created_at: str
    updated_at: str


class TransformPreviewRequest(BaseModel):
    """Request to preview a transformation on sample data."""

    mapping_profile_id: str | None = None
    mappings: list[FieldMapping] | None = None
    sample_records: list[dict[str, Any]] = Field(..., min_length=1, max_length=10)


class TransformPreviewResponse(BaseModel):
    """Result of a transformation preview."""

    transformed_records: list[dict[str, Any]]
    errors: list[dict[str, Any]] = Field(default_factory=list)
    fields_mapped: int
    fields_dropped: int
