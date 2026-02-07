"""Excel parser for file ingestion."""

from __future__ import annotations

import io
from typing import Any

from app.basecamp.enums import FileFormat
from app.basecamp.ingestion.parsers.base import BaseParser
from app.basecamp.types import (
    InferredField,
    InferredSchema,
    ParsedRecord,
    ParseResult,
    ValidationError,
)


class ExcelParser(BaseParser):
    """Parser for Excel files (.xlsx, .xls).

    Uses openpyxl for .xlsx files. Handles multiple sheets.
    """

    @property
    def supported_formats(self) -> list[FileFormat]:
        return [FileFormat.EXCEL]

    def parse(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        schema: list[dict[str, Any]] | None = None,
        sheet_name: str | None = None,
        has_header: bool = True,
    ) -> ParseResult:
        """Parse Excel content into records.

        Args:
            content: Raw Excel file bytes.
            filename: Optional filename.
            schema: Optional schema for validation.
            sheet_name: Specific sheet to parse (defaults to first sheet).
            has_header: Whether first row is header.

        Returns:
            ParseResult with parsed records.
        """
        try:
            import openpyxl
        except ImportError:
            return ParseResult(
                records=[],
                errors=[
                    ValidationError(
                        field="",
                        row=None,
                        message="openpyxl library required for Excel parsing",
                        severity="error",
                    )
                ],
                total_rows=0,
            )

        records: list[ParsedRecord] = []
        errors: list[ValidationError] = []

        try:
            workbook = openpyxl.load_workbook(
                io.BytesIO(content), read_only=True, data_only=True
            )
        except Exception as e:
            return ParseResult(
                records=[],
                errors=[
                    ValidationError(
                        field="",
                        row=None,
                        message=f"Failed to open Excel file: {e}",
                        severity="error",
                    )
                ],
                total_rows=0,
            )

        # Select sheet
        if sheet_name:
            if sheet_name not in workbook.sheetnames:
                return ParseResult(
                    records=[],
                    errors=[
                        ValidationError(
                            field="",
                            row=None,
                            message=f"Sheet '{sheet_name}' not found. Available: {workbook.sheetnames}",
                            severity="error",
                        )
                    ],
                    total_rows=0,
                )
            sheet = workbook[sheet_name]
        else:
            sheet = workbook.active
            sheet_name = sheet.title if sheet else "Sheet1"

        if sheet is None:
            return ParseResult(
                records=[],
                errors=[
                    ValidationError(
                        field="",
                        row=None,
                        message="No active sheet found in workbook",
                        severity="error",
                    )
                ],
                total_rows=0,
            )

        # Read all rows
        rows = list(sheet.iter_rows(values_only=True))

        if not rows:
            workbook.close()
            return ParseResult(
                records=[],
                errors=[],
                total_rows=0,
            )

        # Extract headers
        if has_header:
            raw_headers = rows[0]
            headers = [self._clean_header(h) for h in raw_headers]
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
                # Convert row to list
                row_values = list(row) if row else []

                # Handle rows with different column counts
                if len(row_values) < len(headers):
                    row_values = row_values + [None] * (len(headers) - len(row_values))
                elif len(row_values) > len(headers):
                    errors.append(
                        ValidationError(
                            field="",
                            row=row_idx,
                            message=f"Row has {len(row_values)} columns, expected {len(headers)}",
                            severity="warning",
                        )
                    )
                    row_values = row_values[: len(headers)]

                # Skip completely empty rows
                if all(v is None or v == "" for v in row_values):
                    continue

                # Create record dictionary
                data = {
                    headers[i]: self._convert_excel_value(row_values[i])
                    for i in range(len(headers))
                }
                records.append(
                    ParsedRecord(
                        data=data,
                        row_number=row_idx,
                        source_sheet=sheet_name,
                    )
                )
            except Exception as e:
                errors.append(
                    ValidationError(
                        field="",
                        row=row_idx,
                        message=f"Error parsing row: {e}",
                        severity="error",
                    )
                )

        workbook.close()

        # Infer schema from parsed records
        inferred_schema = None
        if records:
            sample_data = [r.data for r in records[:100]]
            inferred_schema = self._infer_from_excel_records(sample_data, headers)

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
        """Infer schema from Excel content.

        Args:
            content: Raw Excel file bytes.
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
            source_format=FileFormat.EXCEL,
        )

    def get_sheet_names(self, content: bytes) -> list[str]:
        """Get list of sheet names in the workbook.

        Args:
            content: Raw Excel file bytes.

        Returns:
            List of sheet names.
        """
        try:
            import openpyxl

            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            names = workbook.sheetnames
            workbook.close()
            return names
        except Exception:
            return []

    def _clean_header(self, header: Any) -> str:
        """Clean and normalize a header value.

        Args:
            header: Raw header value (may be any type).

        Returns:
            Cleaned header name.
        """
        if header is None:
            return "unnamed"

        header_str = str(header).strip()

        # Replace spaces and special chars with underscores
        cleaned = ""
        for char in header_str:
            if char.isalnum() or char == "_":
                cleaned += char
            elif char in " -./":
                cleaned += "_"

        # Remove consecutive underscores
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")

        # Remove leading/trailing underscores
        cleaned = cleaned.strip("_")

        return cleaned if cleaned else "unnamed"

    def _convert_excel_value(self, value: Any) -> Any:
        """Convert an Excel cell value to appropriate Python type.

        Args:
            value: Cell value to convert.

        Returns:
            Converted value.
        """
        if value is None:
            return None

        # Handle datetime objects
        from datetime import datetime

        if isinstance(value, datetime):
            return value.isoformat()

        # Handle other types
        if isinstance(value, bool | int | float):
            return value

        # Convert to string and handle
        str_value = str(value).strip()
        if str_value == "":
            return None

        return str_value

    def _infer_from_excel_records(
        self, records: list[dict[str, Any]], headers: list[str]
    ) -> InferredSchema:
        """Infer schema from Excel records.

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
                source_format=FileFormat.EXCEL,
            )

        # Collect values for each field
        field_values: dict[str, list[Any]] = {field: [] for field in headers}
        for record in records:
            for field in headers:
                value = record.get(field)
                field_values[field].append(value)

        # Create inferred fields in header order
        inferred_fields = [
            self._create_excel_inferred_field(name, field_values[name])
            for name in headers
        ]

        return InferredSchema(
            fields=inferred_fields,
            record_count=len(records),
            source_format=FileFormat.EXCEL,
        )

    def _create_excel_inferred_field(
        self,
        name: str,
        values: list[Any],
    ) -> InferredField:
        """Create an InferredField optimized for Excel data.

        Args:
            name: Field name.
            values: Sample values for the field.

        Returns:
            InferredField with type inference.
        """
        # Excel values may already be typed
        if not values:
            return InferredField(
                name=name,
                inferred_type="str",
                nullable=True,
                sample_values=[],
                confidence=0.5,
            )

        # Filter out None values
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return InferredField(
                name=name,
                inferred_type="str",
                nullable=True,
                sample_values=[],
                confidence=0.5,
            )

        # Detect types from actual values
        type_counts: dict[str, int] = {
            "int": 0,
            "float": 0,
            "bool": 0,
            "datetime": 0,
            "str": 0,
        }

        for value in non_null_values:
            if isinstance(value, bool):
                type_counts["bool"] += 1
            elif isinstance(value, int):
                type_counts["int"] += 1
            elif isinstance(value, float):
                type_counts["float"] += 1
            elif isinstance(value, str):
                # Check if it's a datetime string
                if "T" in value or (len(value) == 10 and value.count("-") == 2):
                    type_counts["datetime"] += 1
                else:
                    type_counts["str"] += 1
            else:
                type_counts["str"] += 1

        # Find most common type
        total = len(non_null_values)
        best_type = max(type_counts, key=lambda k: type_counts[k])
        confidence = type_counts[best_type] / total if total > 0 else 0.5

        nullable = any(v is None for v in values)
        sample_values = [v for v in non_null_values[:5] if v is not None]

        return InferredField(
            name=name,
            inferred_type=best_type,
            nullable=nullable,
            sample_values=sample_values,
            confidence=confidence,
        )
