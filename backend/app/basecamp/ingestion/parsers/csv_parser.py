"""CSV parser for file ingestion."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.basecamp.enums import FileFormat
from app.basecamp.ingestion.parsers.base import BaseParser
from app.basecamp.types import (
    InferredSchema,
    ParsedRecord,
    ParseResult,
    ValidationError,
)


class CSVParser(BaseParser):
    """Parser for CSV files.

    Supports various CSV dialects with automatic detection.
    """

    @property
    def supported_formats(self) -> list[FileFormat]:
        return [FileFormat.CSV]

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        schema: list[dict[str, Any]] | None = None,
        delimiter: str | None = None,
        has_header: bool = True,
    ) -> ParseResult:
        """Parse CSV content into records.

        Args:
            content: Raw CSV bytes.
            filename: Optional filename.
            schema: Optional schema for validation.
            delimiter: Optional delimiter override.
            has_header: Whether first row is header.

        Returns:
            ParseResult with parsed records.
        """
        records: list[ParsedRecord] = []
        errors: list[ValidationError] = []

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except UnicodeDecodeError as e:
                return ParseResult(
                    records=[],
                    errors=[
                        ValidationError(
                            field="",
                            row=None,
                            message=f"Failed to decode content: {e}",
                            severity="error",
                        )
                    ],
                    total_rows=0,
                )

        # Detect delimiter if not provided
        if delimiter is None:
            delimiter = self._detect_delimiter(text)

        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
        except csv.Error as e:
            return ParseResult(
                records=[],
                errors=[
                    ValidationError(
                        field="",
                        row=None,
                        message=f"CSV parsing error: {e}",
                        severity="error",
                    )
                ],
                total_rows=0,
            )

        if not rows:
            return ParseResult(
                records=[],
                errors=[],
                total_rows=0,
            )

        # Extract headers
        if has_header:
            headers = [self._clean_header(h) for h in rows[0]]
            data_rows = rows[1:]
            header_row = 1
        else:
            # Generate column names
            max_cols = max(len(row) for row in rows) if rows else 0
            headers = [f"column_{i}" for i in range(max_cols)]
            data_rows = rows
            header_row = 0

        # Parse data rows
        for row_idx, row in enumerate(data_rows, start=header_row + 1):
            try:
                # Handle rows with different column counts
                if len(row) < len(headers):
                    # Pad short rows with empty strings
                    row = row + [""] * (len(headers) - len(row))
                elif len(row) > len(headers):
                    errors.append(
                        ValidationError(
                            field="",
                            row=row_idx,
                            message=f"Row has {len(row)} columns, expected {len(headers)}",
                            severity="warning",
                        )
                    )
                    row = row[: len(headers)]

                # Create record dictionary
                data = {
                    headers[i]: self._convert_value(row[i]) for i in range(len(headers))
                }
                records.append(ParsedRecord(data=data, row_number=row_idx))
            except Exception as e:
                errors.append(
                    ValidationError(
                        field="",
                        row=row_idx,
                        message=f"Error parsing row: {e}",
                        severity="error",
                    )
                )

        # Infer schema from parsed records
        inferred_schema = None
        if records:
            sample_data = [r.data for r in records[:100]]
            inferred_schema = self._infer_from_csv_records(sample_data, headers)

        return ParseResult(
            records=records,
            inferred_schema=inferred_schema,
            errors=errors,
            total_rows=len(records),
        )

    def infer_schema(
        self,
        content: bytes,
        *,
        sample_size: int = 100,
    ) -> InferredSchema:
        """Infer schema from CSV content.

        Args:
            content: Raw CSV bytes.
            sample_size: Number of records to sample.

        Returns:
            InferredSchema with field definitions.
        """
        result = self.parse(content)
        if result.inferred_schema:
            return result.inferred_schema

        return InferredSchema(
            fields=[],
            record_count=0,
            source_format=FileFormat.CSV,
        )

    def _detect_delimiter(self, text: str) -> str:
        """Detect the most likely delimiter.

        Args:
            text: CSV text content.

        Returns:
            Detected delimiter character.
        """
        # Sample first few lines
        sample = "\n".join(text.split("\n")[:10])

        # Count occurrences of common delimiters
        delimiters = [",", ";", "\t", "|"]
        counts = {d: sample.count(d) for d in delimiters}

        # Use csv.Sniffer as backup
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="".join(delimiters))
            return dialect.delimiter
        except csv.Error:
            pass

        # Fall back to most common delimiter
        return max(counts, key=lambda k: counts[k]) if any(counts.values()) else ","

    def _clean_header(self, header: str) -> str:
        """Clean and normalize a header name.

        Args:
            header: Raw header string.

        Returns:
            Cleaned header name.
        """
        # Strip whitespace and quotes
        header = header.strip().strip('"').strip("'")

        # Replace spaces and special chars with underscores
        cleaned = ""
        for char in header:
            if char.isalnum() or char == "_":
                cleaned += char
            elif char in " -./":
                cleaned += "_"

        # Remove consecutive underscores
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")

        # Remove leading/trailing underscores
        cleaned = cleaned.strip("_")

        # Ensure non-empty
        return cleaned if cleaned else "unnamed"

    def _convert_value(self, value: str) -> Any:
        """Convert a string value to appropriate Python type.

        Args:
            value: String value to convert.

        Returns:
            Converted value.
        """
        if value == "" or value is None:
            return None

        value = value.strip()

        # Try boolean
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False

        # Try integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        return value

    def _infer_from_csv_records(
        self, records: list[dict[str, Any]], headers: list[str]
    ) -> InferredSchema:
        """Infer schema from CSV records.

        Args:
            records: List of record dictionaries.
            headers: List of header names in order.

        Returns:
            InferredSchema with field definitions.
        """
        if not records:
            return InferredSchema(
                fields=[],
                record_count=0,
                source_format=FileFormat.CSV,
            )

        # Collect values for each field
        field_values: dict[str, list[Any]] = {field: [] for field in headers}
        for record in records:
            for field in headers:
                value = record.get(field)
                field_values[field].append(value)

        # Create inferred fields in header order
        inferred_fields = [
            self._create_inferred_field(name, field_values[name]) for name in headers
        ]

        return InferredSchema(
            fields=inferred_fields,
            record_count=len(records),
            source_format=FileFormat.CSV,
        )
