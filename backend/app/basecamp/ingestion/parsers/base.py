"""Base parser protocol for file ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.basecamp.enums import FileFormat
from app.basecamp.types import InferredField, InferredSchema, ParseResult


class BaseParser(ABC):
    """Abstract base class for file parsers.

    All parsers must implement parse() and infer_schema() methods
    to handle file ingestion consistently.
    """

    @property
    @abstractmethod
    def supported_formats(self) -> list[FileFormat]:
        """Return list of file formats this parser can handle."""
        ...

    @abstractmethod
    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        schema: list[dict[str, Any]] | None = None,
    ) -> ParseResult:
        """Parse file content into structured records.

        Args:
            content: Raw file bytes to parse.
            filename: Optional filename for format detection.
            schema: Optional schema to validate against.

        Returns:
            ParseResult containing records and any errors.
        """
        ...

    @abstractmethod
    def infer_schema(
        self,
        content: bytes,
        *,
        sample_size: int = 100,
    ) -> InferredSchema:
        """Infer schema from file content.

        Args:
            content: Raw file bytes to analyze.
            sample_size: Number of records to sample for inference.

        Returns:
            InferredSchema with field definitions.
        """
        ...

    def _infer_field_type(self, values: list[Any]) -> tuple[str, float]:
        """Infer the most likely type from a list of values.

        Args:
            values: Sample values for a field.

        Returns:
            Tuple of (inferred_type, confidence).
        """
        if not values:
            return "str", 0.5

        # Filter out None values for type detection
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return "str", 0.5

        # Count type occurrences
        type_counts: dict[str, int] = {
            "int": 0,
            "float": 0,
            "bool": 0,
            "datetime": 0,
            "str": 0,
        }

        for value in non_null_values:
            detected_type = self._detect_single_value_type(value)
            type_counts[detected_type] += 1

        # Find most common type
        total = len(non_null_values)
        best_type = max(type_counts, key=lambda k: type_counts[k])
        confidence = type_counts[best_type] / total if total > 0 else 0.5

        return best_type, confidence

    def _detect_single_value_type(self, value: Any) -> str:
        """Detect the type of a single value.

        Args:
            value: The value to analyze.

        Returns:
            String type name.
        """
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return self._detect_string_type(value)
        return "str"

    def _detect_string_type(self, value: str) -> str:
        """Detect if a string represents another type.

        Args:
            value: String value to analyze.

        Returns:
            Detected type name.
        """
        value = value.strip()

        # Check for boolean
        if value.lower() in ("true", "false", "yes", "no", "1", "0"):
            return "bool"

        # Check for integer
        try:
            int(value)
            return "int"
        except ValueError:
            pass

        # Check for float
        try:
            float(value)
            return "float"
        except ValueError:
            pass

        # Check for datetime patterns
        datetime_patterns = [
            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO 8601
            r"^\d{2}/\d{2}/\d{4}$",  # MM/DD/YYYY
            r"^\d{2}-\d{2}-\d{4}$",  # DD-MM-YYYY
        ]
        import re

        for pattern in datetime_patterns:
            if re.match(pattern, value):
                return "datetime"

        return "str"

    def _create_inferred_field(
        self,
        name: str,
        values: list[Any],
    ) -> InferredField:
        """Create an InferredField from column name and sample values.

        Args:
            name: Field name.
            values: Sample values for the field.

        Returns:
            InferredField with type inference.
        """
        inferred_type, confidence = self._infer_field_type(values)
        nullable = any(v is None or v == "" for v in values)

        # Take up to 5 sample values
        sample_values = [v for v in values[:5] if v is not None and v != ""]

        return InferredField(
            name=name,
            inferred_type=inferred_type,
            nullable=nullable,
            sample_values=sample_values,
            confidence=confidence,
        )
