"""JSON parser for file ingestion."""

from __future__ import annotations

import json
from typing import Any

from app.basecamp.enums import FileFormat
from app.basecamp.ingestion.parsers.base import BaseParser
from app.basecamp.types import (
    InferredSchema,
    ParsedRecord,
    ParseResult,
    ValidationError,
)


class JSONParser(BaseParser):
    """Parser for JSON files.

    Supports both JSON arrays and JSON Lines (NDJSON) formats.
    """

    @property
    def supported_formats(self) -> list[FileFormat]:
        return [FileFormat.JSON]

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        schema: list[dict[str, Any]] | None = None,
    ) -> ParseResult:
        """Parse JSON content into records.

        Args:
            content: Raw JSON bytes.
            filename: Optional filename.
            schema: Optional schema for validation.

        Returns:
            ParseResult with parsed records.
        """
        records: list[ParsedRecord] = []
        errors: list[ValidationError] = []

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            return ParseResult(
                records=[],
                errors=[
                    ValidationError(
                        field="",
                        row=None,
                        message=f"Failed to decode content as UTF-8: {e}",
                        severity="error",
                    )
                ],
                total_rows=0,
            )

        # Try parsing as JSON array first
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        record = ParsedRecord(data=item, row_number=i + 1)
                        records.append(record)
                    else:
                        errors.append(
                            ValidationError(
                                field="",
                                row=i + 1,
                                message=f"Expected object, got {type(item).__name__}",
                                severity="error",
                            )
                        )
            elif isinstance(data, dict):
                # Single object - wrap in list
                records.append(ParsedRecord(data=data, row_number=1))
            else:
                errors.append(
                    ValidationError(
                        field="",
                        row=None,
                        message=f"Expected array or object at root, got {type(data).__name__}",
                        severity="error",
                    )
                )
        except json.JSONDecodeError:
            # Try JSON Lines format
            records, line_errors = self._parse_json_lines(text)
            errors.extend(line_errors)

        # Infer schema from parsed records
        inferred_schema = None
        if records:
            sample_data = [r.data for r in records[:100]]
            inferred_schema = self._infer_from_records(sample_data)

        return ParseResult(
            records=records,
            inferred_schema=inferred_schema,
            errors=errors,
            total_rows=len(records),
        )

    def _parse_json_lines(
        self, text: str
    ) -> tuple[list[ParsedRecord], list[ValidationError]]:
        """Parse JSON Lines (NDJSON) format.

        Args:
            text: Text content with one JSON object per line.

        Returns:
            Tuple of (records, errors).
        """
        records: list[ParsedRecord] = []
        errors: list[ValidationError] = []

        for line_num, line in enumerate(text.strip().split("\n"), start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    records.append(ParsedRecord(data=data, row_number=line_num))
                else:
                    errors.append(
                        ValidationError(
                            field="",
                            row=line_num,
                            message=f"Expected object, got {type(data).__name__}",
                            severity="error",
                        )
                    )
            except json.JSONDecodeError as e:
                errors.append(
                    ValidationError(
                        field="",
                        row=line_num,
                        message=f"Invalid JSON: {e}",
                        severity="error",
                    )
                )

        return records, errors

    def infer_schema(
        self,
        content: bytes,
        *,
        sample_size: int = 100,
    ) -> InferredSchema:
        """Infer schema from JSON content.

        Args:
            content: Raw JSON bytes.
            sample_size: Number of records to sample.

        Returns:
            InferredSchema with field definitions.
        """
        result = self.parse(content)
        if not result.records:
            return InferredSchema(
                fields=[],
                record_count=0,
                source_format=FileFormat.JSON,
            )

        sample_data = [r.data for r in result.records[:sample_size]]
        return self._infer_from_records(sample_data)

    def _infer_from_records(self, records: list[dict[str, Any]]) -> InferredSchema:
        """Infer schema from a list of record dictionaries.

        Args:
            records: List of record dictionaries.

        Returns:
            InferredSchema with field definitions.
        """
        if not records:
            return InferredSchema(
                fields=[],
                record_count=0,
                source_format=FileFormat.JSON,
            )

        # Collect all unique field names
        all_fields: set[str] = set()
        for record in records:
            all_fields.update(record.keys())

        # Collect values for each field
        field_values: dict[str, list[Any]] = {field: [] for field in all_fields}
        for record in records:
            for field in all_fields:
                value = record.get(field)
                field_values[field].append(value)

        # Create inferred fields
        inferred_fields = [
            self._create_inferred_field(name, values)
            for name, values in sorted(field_values.items())
        ]

        return InferredSchema(
            fields=inferred_fields,
            record_count=len(records),
            source_format=FileFormat.JSON,
        )
