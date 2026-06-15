"""Per-record data quality scoring.

Pure functions, no DB access. ``score_record`` evaluates a single data record
against its schema and produces a four-dimension quality breakdown plus a
weighted overall score and a list of human-readable issues.

The four dimensions:

- ``completeness`` — fraction of schema fields present and non-null. Required
  (non-nullable) fields are weighted more heavily than optional ones.
- ``validity``     — fraction of present fields whose value coerces cleanly to
  its declared type (reuses ``coerce_value_to_type``).
- ``consistency``  — internal structural checks. Currently: penalize unexpected
  extra fields not declared in the schema. Reserved to ``1.0`` when N/A.
- ``timeliness``   — if a datetime-typed field is present, freshness vs ``now``
  (<=30d == 1.0, decaying linearly to 0.0 at 365d). ``1.0`` when N/A.

The overall ``score`` is the mean of the four dimensions (each dimension is
itself a 0.0-1.0 normalized value), so every dimension contributes equally to
the headline number while internal weighting (required vs optional) lives
inside ``completeness``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.basecamp.schema.inference import coerce_value_to_type

# --- Tunable weights / thresholds (kept explicit + documented) ---

# Within completeness, a present required field counts this many times a present
# optional field. Higher == missing required fields hurt more.
_REQUIRED_WEIGHT = 2.0
_OPTIONAL_WEIGHT = 1.0

# Overall score = mean of the available dimensions, each weighted equally.
_DIMENSION_WEIGHTS = {
    "completeness": 1.0,
    "validity": 1.0,
    "consistency": 1.0,
    "timeliness": 1.0,
}

# Timeliness decay window: fully fresh at/under FRESH_DAYS, fully stale at STALE_DAYS.
_FRESH_DAYS = 30.0
_STALE_DAYS = 365.0

_DATETIME_TYPES = {"datetime", "date", "timestamp"}


def _normalize_fields(schema_fields: Any) -> list[dict] | None:
    """Coerce the stored ``BaseCampSchema.fields`` value into a list of dicts.

    Returns ``None`` when the schema is unusable (empty / wrong shape), signalling
    the caller to degrade gracefully.
    """
    if not schema_fields:
        return None
    if isinstance(schema_fields, dict):
        # Stored as a dict rather than a list — not the expected shape.
        return None
    if not isinstance(schema_fields, (list, tuple)):
        return None
    normalized: list[dict] = []
    for f in schema_fields:
        if isinstance(f, dict):
            normalized.append(f)
        elif hasattr(f, "name"):  # SchemaFieldRead / Create-like object
            normalized.append(
                {
                    "name": getattr(f, "name", None),
                    "field_type": getattr(f, "field_type", "str"),
                    "nullable": getattr(f, "nullable", True),
                }
            )
    return normalized or None


def _field_name(field: dict) -> str | None:
    return field.get("name")


def _field_type(field: dict) -> str:
    return field.get("field_type") or field.get("type") or "str"


def _is_required(field: dict) -> bool:
    # nullable defaults to True (optional) when unspecified.
    return not bool(field.get("nullable", True))


def _score_completeness(
    data: dict, fields: list[dict], issues: list[str]
) -> float:
    """Weighted fraction of schema fields present and non-null."""
    total_weight = 0.0
    earned = 0.0
    for field in fields:
        name = _field_name(field)
        if not name:
            continue
        required = _is_required(field)
        weight = _REQUIRED_WEIGHT if required else _OPTIONAL_WEIGHT
        total_weight += weight
        present = name in data and data.get(name) is not None
        if present:
            earned += weight
        else:
            if required:
                issues.append(
                    f"completeness: missing required field '{name}'"
                )
            else:
                issues.append(
                    f"completeness: missing optional field '{name}'"
                )
    if total_weight == 0.0:
        return 1.0
    return earned / total_weight


def _coerces(value: Any, target_type: str) -> bool:
    """True if ``value`` round-trips to ``target_type`` without falling back."""
    if value is None:
        return True
    coerced = coerce_value_to_type(value, target_type)
    if target_type in ("int", "float", "bool"):
        # coerce_value_to_type returns the *original* value on failure, so a
        # value that did not change type means coercion failed.
        expected = {"int": int, "float": float, "bool": bool}[target_type]
        return isinstance(coerced, expected)
    # str / datetime / json / unknown: coercion is best-effort string-ish and
    # effectively always succeeds for non-None values.
    return coerced is not None


def _score_validity(data: dict, fields: list[dict], issues: list[str]) -> float:
    """Fraction of present fields whose value coerces to its declared type."""
    checked = 0
    valid = 0
    for field in fields:
        name = _field_name(field)
        if not name or name not in data:
            continue
        value = data.get(name)
        if value is None:
            continue
        checked += 1
        target_type = _field_type(field)
        if _coerces(value, target_type):
            valid += 1
        else:
            issues.append(
                f"validity: field '{name}' value does not coerce to {target_type}"
            )
    if checked == 0:
        return 1.0
    return valid / checked


def _score_consistency(
    data: dict, fields: list[dict], issues: list[str]
) -> float:
    """Penalize fields present in data but not declared in the schema."""
    declared = {_field_name(f) for f in fields if _field_name(f)}
    if not data:
        return 1.0
    extra = [k for k in data if k not in declared]
    if not extra:
        return 1.0
    for k in extra:
        issues.append(f"consistency: unexpected field '{k}' not in schema")
    # Fraction of fields that ARE expected.
    return max(0.0, 1.0 - (len(extra) / len(data)))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _score_timeliness(
    data: dict, fields: list[dict], now: datetime, issues: list[str]
) -> float:
    """Freshness of the most recent datetime-typed field vs ``now``.

    Reserved to ``1.0`` when no datetime field is present/parseable.
    """
    dt_field_names = [
        _field_name(f)
        for f in fields
        if _field_name(f) and _field_type(f) in _DATETIME_TYPES
    ]
    if not dt_field_names:
        return 1.0

    best_age_days: float | None = None
    for name in dt_field_names:
        if name not in data:
            continue
        parsed = _parse_datetime(data.get(name))
        if parsed is None:
            continue
        # Normalize tz so subtraction with a naive ``now`` works.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        ref = now
        if ref.tzinfo is not None:
            ref = ref.astimezone(timezone.utc).replace(tzinfo=None)
        age_days = (ref - parsed).total_seconds() / 86400.0
        if age_days < 0:
            age_days = 0.0
        if best_age_days is None or age_days < best_age_days:
            best_age_days = age_days

    if best_age_days is None:
        # Schema declares datetime fields but record carries none parseable.
        return 1.0

    if best_age_days <= _FRESH_DAYS:
        return 1.0
    if best_age_days >= _STALE_DAYS:
        issues.append("timeliness: record is stale (>1y old)")
        return 0.0
    # Linear decay between FRESH and STALE.
    span = _STALE_DAYS - _FRESH_DAYS
    return max(0.0, 1.0 - (best_age_days - _FRESH_DAYS) / span)


def score_record(
    data: dict,
    schema_fields: list[dict],
    *,
    now: datetime | None = None,
) -> dict:
    """Score a single data record against its schema.

    Args:
        data: The record's data dict.
        schema_fields: The list stored in ``BaseCampSchema.fields`` (each item a
            dict with ``name`` / ``field_type`` / ``nullable``). May also be a
            list of objects exposing those attributes. Empty or non-list inputs
            are handled gracefully (returns score 1.0 with a note).
        now: Reference time for timeliness (defaults to ``datetime.utcnow()``).

    Returns:
        Dict with ``score`` (0.0-1.0), ``dimensions`` (the four sub-scores), and
        ``issues`` (list of human-readable strings).
    """
    if now is None:
        now = datetime.utcnow()
    data = data or {}
    issues: list[str] = []

    fields = _normalize_fields(schema_fields)
    if fields is None:
        # No usable schema — can't assess against anything; treat as pass-through.
        return {
            "score": 1.0,
            "dimensions": {
                "completeness": 1.0,
                "validity": 1.0,
                "consistency": 1.0,
                "timeliness": 1.0,
            },
            "issues": ["schema: no schema fields available; scoring skipped"],
        }

    dimensions = {
        "completeness": _score_completeness(data, fields, issues),
        "validity": _score_validity(data, fields, issues),
        "consistency": _score_consistency(data, fields, issues),
        "timeliness": _score_timeliness(data, fields, now, issues),
    }

    total_weight = sum(_DIMENSION_WEIGHTS[d] for d in dimensions)
    weighted = sum(dimensions[d] * _DIMENSION_WEIGHTS[d] for d in dimensions)
    score = weighted / total_weight if total_weight else 1.0

    return {
        "score": round(score, 4),
        "dimensions": {k: round(v, 4) for k, v in dimensions.items()},
        "issues": issues,
    }
