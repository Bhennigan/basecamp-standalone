"""Pure-unit tests for app.quality.scoring.score_record (no DB, no async)."""

from datetime import datetime

from app.quality.scoring import score_record


SCHEMA = [
    {"name": "email", "field_type": "str", "nullable": False},
    {"name": "age", "field_type": "int", "nullable": False},
    {"name": "nickname", "field_type": "str", "nullable": True},
    {"name": "signup_at", "field_type": "datetime", "nullable": True},
]

NOW = datetime(2026, 6, 12, 12, 0, 0)


def test_complete_valid_record_scores_high():
    data = {
        "email": "a@b.com",
        "age": 30,
        "nickname": "ace",
        "signup_at": "2026-06-01T00:00:00",
    }
    result = score_record(data, SCHEMA, now=NOW)

    assert result["score"] >= 0.95
    dims = result["dimensions"]
    assert dims["completeness"] == 1.0
    assert dims["validity"] == 1.0
    assert dims["consistency"] == 1.0
    assert dims["timeliness"] == 1.0
    assert result["issues"] == []


def test_missing_required_field_penalizes_completeness():
    data = {"age": 30}  # missing required 'email'
    result = score_record(data, SCHEMA, now=NOW)

    assert result["dimensions"]["completeness"] < 1.0
    assert any(
        "missing required field 'email'" in issue for issue in result["issues"]
    )
    assert result["score"] < 1.0


def test_wrong_typed_field_penalizes_validity():
    data = {
        "email": "a@b.com",
        "age": "not-a-number",  # cannot coerce to int
    }
    result = score_record(data, SCHEMA, now=NOW)

    assert result["dimensions"]["validity"] < 1.0
    assert any("validity" in issue and "age" in issue for issue in result["issues"])


def test_empty_schema_degrades_to_one():
    data = {"anything": 1}

    for empty in ([], {}, None):
        result = score_record(data, empty, now=NOW)
        assert result["score"] == 1.0
        assert result["dimensions"]["completeness"] == 1.0
        assert result["dimensions"]["validity"] == 1.0
        assert result["dimensions"]["consistency"] == 1.0
        assert result["dimensions"]["timeliness"] == 1.0


def test_extra_field_penalizes_consistency():
    data = {
        "email": "a@b.com",
        "age": 30,
        "surprise": "extra",  # not in schema
    }
    result = score_record(data, SCHEMA, now=NOW)

    assert result["dimensions"]["consistency"] < 1.0
    assert any("surprise" in issue for issue in result["issues"])


def test_stale_datetime_penalizes_timeliness():
    data = {
        "email": "a@b.com",
        "age": 30,
        "signup_at": "2024-01-01T00:00:00",  # >1y before NOW
    }
    result = score_record(data, SCHEMA, now=NOW)

    assert result["dimensions"]["timeliness"] < 1.0
