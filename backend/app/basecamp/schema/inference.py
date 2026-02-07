"""Schema inference engine for Base Camp OS."""

from __future__ import annotations

from typing import Any

from app.basecamp.enums import FileFormat
from app.basecamp.schemas import SchemaFieldCreate, SchemaFieldRead
from app.basecamp.types import InferredField, InferredSchema


def inferred_field_to_schema_field(field: InferredField) -> SchemaFieldRead:
    """Convert an InferredField to a SchemaFieldRead.

    Args:
        field: The inferred field from parsing.

    Returns:
        SchemaFieldRead suitable for API response.
    """
    return SchemaFieldRead(
        name=field.name,
        field_type=field.inferred_type,
        nullable=field.nullable,
        default=None,
        description=None,
    )


def inferred_schema_to_schema_fields(
    schema: InferredSchema,
) -> list[SchemaFieldRead]:
    """Convert an InferredSchema to a list of SchemaFieldRead.

    Args:
        schema: The inferred schema from parsing.

    Returns:
        List of SchemaFieldRead suitable for API response.
    """
    return [inferred_field_to_schema_field(field) for field in schema.fields]


def calculate_schema_confidence(schema: InferredSchema) -> float:
    """Calculate overall confidence score for an inferred schema.

    Args:
        schema: The inferred schema.

    Returns:
        Float confidence score between 0 and 1.
    """
    if not schema.fields:
        return 0.0

    total_confidence = sum(field.confidence for field in schema.fields)
    return total_confidence / len(schema.fields)


def merge_inferred_schemas(schemas: list[InferredSchema]) -> InferredSchema:
    """Merge multiple inferred schemas into one.

    Useful when processing multiple files that should share a schema.

    Args:
        schemas: List of schemas to merge.

    Returns:
        Merged InferredSchema.
    """
    if not schemas:
        return InferredSchema(
            fields=[],
            record_count=0,
            source_format=FileFormat.JSON,
        )

    if len(schemas) == 1:
        return schemas[0]

    # Collect all fields by name
    all_fields: dict[str, list[InferredField]] = {}
    total_records = 0
    source_format = schemas[0].source_format

    for schema in schemas:
        total_records += schema.record_count
        for field in schema.fields:
            if field.name not in all_fields:
                all_fields[field.name] = []
            all_fields[field.name].append(field)

    # Merge each field
    merged_fields: list[InferredField] = []
    for name, fields in all_fields.items():
        merged_field = _merge_fields(name, fields)
        merged_fields.append(merged_field)

    return InferredSchema(
        fields=merged_fields,
        record_count=total_records,
        source_format=source_format,
    )


def _merge_fields(name: str, fields: list[InferredField]) -> InferredField:
    """Merge multiple InferredFields with the same name.

    Args:
        name: The field name.
        fields: List of fields to merge.

    Returns:
        Merged InferredField.
    """
    if len(fields) == 1:
        return fields[0]

    # Collect type votes
    type_votes: dict[str, float] = {}
    total_confidence = 0.0
    all_sample_values: list[Any] = []
    is_nullable = False

    for field in fields:
        vote_weight = field.confidence
        type_votes[field.inferred_type] = (
            type_votes.get(field.inferred_type, 0) + vote_weight
        )
        total_confidence += field.confidence
        all_sample_values.extend(field.sample_values)
        if field.nullable:
            is_nullable = True

    # Select type with highest weighted vote
    best_type = max(type_votes, key=lambda k: type_votes[k])
    avg_confidence = total_confidence / len(fields)

    # Deduplicate and limit sample values
    unique_samples = []
    seen = set()
    for val in all_sample_values:
        str_val = str(val)
        if str_val not in seen:
            seen.add(str_val)
            unique_samples.append(val)
            if len(unique_samples) >= 5:
                break

    return InferredField(
        name=name,
        inferred_type=best_type,
        nullable=is_nullable,
        sample_values=unique_samples,
        confidence=avg_confidence,
    )


def validate_data_against_schema(
    data: dict[str, Any],
    schema_fields: list[SchemaFieldCreate],
) -> list[str]:
    """Validate a data record against a schema definition.

    Args:
        data: The data record to validate.
        schema_fields: The schema field definitions.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors: list[str] = []
    field_names = {f.name for f in schema_fields}

    # Check for required fields
    for field in schema_fields:
        if not field.nullable and field.name not in data:
            errors.append(f"Missing required field: {field.name}")
        elif field.name in data:
            value = data[field.name]
            if value is None and not field.nullable:
                errors.append(f"Field '{field.name}' cannot be null")

    # Check for unknown fields (warning level, not blocking)
    for key in data:
        if key not in field_names:
            # This is typically allowed - schema can be extended
            pass

    return errors


def coerce_value_to_type(value: Any, target_type: str) -> Any:
    """Attempt to coerce a value to a target type.

    Args:
        value: The value to coerce.
        target_type: The target type name.

    Returns:
        Coerced value or original if coercion fails.
    """
    if value is None:
        return None

    try:
        if target_type == "int":
            return int(value)
        elif target_type == "float":
            return float(value)
        elif target_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1")
            return bool(value)
        elif target_type == "str":
            return str(value)
        elif target_type == "datetime":
            # Return as-is for datetime strings
            return str(value) if value else None
    except (ValueError, TypeError):
        pass

    return value
