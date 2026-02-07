"""Domain types for Base Camp OS module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from app.basecamp.enums import FileFormat


@dataclass(frozen=True)
class InferredField:
    """Represents an inferred field from data analysis."""

    name: str
    inferred_type: str
    nullable: bool = True
    sample_values: list[Any] = field(default_factory=list)
    confidence: float = 1.0


@dataclass(frozen=True)
class InferredSchema:
    """Schema inferred from data source."""

    fields: list[InferredField]
    record_count: int
    source_format: FileFormat


@dataclass(frozen=True)
class ValidationError:
    """Represents a validation error during ingestion."""

    field: str
    row: int | None
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    records_validated: int = 0
    records_passed: int = 0


@dataclass(frozen=True)
class ParsedRecord:
    """A single record parsed from a data source."""

    data: dict[str, Any]
    row_number: int | None = None
    source_sheet: str | None = None


@dataclass
class ParseResult:
    """Result of parsing a file."""

    records: list[ParsedRecord]
    inferred_schema: InferredSchema | None = None
    errors: list[ValidationError] = field(default_factory=list)
    total_rows: int = 0


@dataclass(frozen=True)
class TransformationRule:
    """A rule for transforming field values."""

    source_field: str
    target_field: str
    transform_type: Literal["rename", "cast", "format", "extract"]
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionProgress:
    """Progress tracking for an ingestion job."""

    total_records: int
    processed_records: int
    failed_records: int
    current_stage: str
    started_at: datetime
    updated_at: datetime
    estimated_completion: datetime | None = None


@runtime_checkable
class Parser(Protocol):
    """Protocol for file parsers."""

    def parse(self, content: bytes, *, filename: str | None = None) -> ParseResult:
        """Parse file content and return structured records."""
        ...

    def infer_schema(self, content: bytes, *, sample_size: int = 100) -> InferredSchema:
        """Infer schema from file content."""
        ...

    @property
    def supported_formats(self) -> list[FileFormat]:
        """Return list of supported file formats."""
        ...


# Type aliases for common patterns
type FieldMapping = dict[str, str]
type RecordData = dict[str, Any]
type SchemaDefinition = dict[str, dict[str, Any]]
