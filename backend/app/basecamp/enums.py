"""Enumerations for Base Camp OS module."""

from enum import StrEnum


class IngestionState(StrEnum):
    """State machine for ingestion job processing.

    Tracks the lifecycle of an ingestion job from receipt through completion.
    """

    RECEIVED = "received"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    TRANSFORMING = "transforming"
    LOADING = "loading"
    COMPLETE = "complete"
    FAILED = "failed"


class DataSourceType(StrEnum):
    """Types of data sources supported by Base Camp OS."""

    FILE_UPLOAD = "file_upload"
    API = "api"
    FILE_WATCH = "file_watch"
    TRACECAT_TRIGGER = "tracecat_trigger"


class SchemaStatus(StrEnum):
    """Status of a schema definition."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class FileFormat(StrEnum):
    """Supported file formats for ingestion."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
