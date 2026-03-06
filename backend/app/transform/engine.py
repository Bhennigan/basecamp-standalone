"""Transformation engine -- applies FieldMapping rules to records."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.transform.models import FieldMapping


def get_nested_value(data: dict, path: str) -> Any:
    """Get a value from nested dict using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def set_nested_value(data: dict, path: str, value: Any) -> None:
    """Set a value in nested dict using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def apply_transform(value: Any, mapping: FieldMapping) -> Any:
    """Apply a single transformation to a value."""
    if value is None and mapping.transform != "default":
        return None

    match mapping.transform:
        case "rename":
            return value
        case "cast":
            return _cast_value(value, mapping.params.get("type", "str"))
        case "format":
            fmt = mapping.params.get("format", "{}")
            return fmt.format(value)
        case "extract":
            pattern = mapping.params.get("pattern", "")
            if pattern and isinstance(value, str):
                match_obj = re.search(pattern, value)
                return match_obj.group(mapping.params.get("group", 0)) if match_obj else None
            return value
        case "default":
            return value if value is not None else mapping.params.get("value")
        case "concat":
            # Handled at transform_record level
            return value
        case "split":
            separator = mapping.params.get("separator", ",")
            index = mapping.params.get("index", None)
            if isinstance(value, str):
                parts = value.split(separator)
                if index is not None:
                    return parts[int(index)] if int(index) < len(parts) else None
                return parts
            return value
        case "lookup":
            table = mapping.params.get("table", {})
            return table.get(str(value), mapping.params.get("default", value))
        case "lower":
            return str(value).lower() if value is not None else None
        case "upper":
            return str(value).upper() if value is not None else None
        case "trim":
            return str(value).strip() if value is not None else None
        case "regex":
            pattern = mapping.params.get("pattern", "")
            replacement = mapping.params.get("replacement", "")
            if isinstance(value, str) and pattern:
                return re.sub(pattern, replacement, value)
            return value
        case _:
            return value


def _cast_value(value: Any, target_type: str) -> Any:
    """Cast a value to the specified type."""
    if value is None:
        return None
    try:
        match target_type:
            case "str":
                return str(value)
            case "int":
                return int(float(value)) if not isinstance(value, int) else value
            case "float":
                return float(value)
            case "bool":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "on")
                return bool(value)
            case "datetime":
                if isinstance(value, datetime):
                    return value.isoformat()
                return str(value)
            case _:
                return value
    except (ValueError, TypeError):
        return None


def transform_record(
    record: dict[str, Any],
    mappings: list[FieldMapping],
    drop_unmapped: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """Apply all mappings to a single record.

    Returns:
        Tuple of (transformed_record, list_of_errors)
    """
    result = {}
    errors = []

    for mapping in mappings:
        try:
            if mapping.transform == "concat":
                fields = mapping.params.get("fields", [mapping.source_field])
                separator = mapping.params.get("separator", " ")
                values = [str(get_nested_value(record, f) or "") for f in fields]
                set_nested_value(result, mapping.target_field, separator.join(values))
            else:
                value = get_nested_value(record, mapping.source_field)
                transformed = apply_transform(value, mapping)
                set_nested_value(result, mapping.target_field, transformed)
        except Exception as e:
            errors.append(f"Field '{mapping.source_field}': {e}")

    if not drop_unmapped:
        mapped_sources = {m.source_field for m in mappings}
        for key, value in record.items():
            if key not in mapped_sources and key not in result:
                result[key] = value

    return result, errors


def transform_batch(
    records: list[dict[str, Any]],
    mappings: list[FieldMapping],
    drop_unmapped: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Transform a batch of records."""
    transformed = []
    all_errors = []

    for i, record in enumerate(records):
        row_result, errors = transform_record(record, mappings, drop_unmapped)
        transformed.append(row_result)
        if errors:
            all_errors.append({"row": i, "errors": errors})

    return transformed, all_errors
