"""Golden-record construction (survivorship).

Given the member records of a resolved cluster, build one canonical record by choosing,
per field, the "best" value according to a survivorship strategy:

  - most_recent:     value from the member with the newest ``_updated`` timestamp.
  - most_complete:   the longest / most-populated non-empty value (default).
  - source_priority: value from the highest-priority source per ``source_priority``.
  - most_frequent:   the modal value across members (ties broken by first seen).

Records carry two reserved meta keys used by the strategies:
  - ``_source``  (str): which source system the record came from.
  - ``_updated`` (sortable, e.g. ISO timestamp): when the record was last updated.
The field names are configurable via ``source_priority_field`` / ``updated_field``.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional


@dataclass
class SurvivorshipRule:
    field: str
    strategy: str = "most_complete"
    source_priority: Optional[list[str]] = dc_field(default=None)


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _completeness(v: Any) -> int:
    """Heuristic 'how complete' a value is: longer / present wins."""
    if _is_empty(v):
        return -1
    return len(str(v))


def _pick_most_complete(members: list[dict], field: str):
    best = None
    best_score = -1
    for m in members:
        v = m.get(field)
        score = _completeness(v)
        if score > best_score:
            best, best_score = v, score
    return best


def _pick_most_recent(members: list[dict], field: str, updated_field: str):
    best = None
    best_key = None
    best_complete = -1
    for m in members:
        v = m.get(field)
        if _is_empty(v):
            continue
        key = m.get(updated_field)
        # Prefer the most recent updated; fall back to completeness when no timestamp.
        if best is None or (key is not None and (best_key is None or key > best_key)):
            best, best_key, best_complete = v, key, _completeness(v)
    if best is None:
        return _pick_most_complete(members, field)
    return best


def _pick_source_priority(members: list[dict], field: str, priority: list[str], source_field: str):
    if priority:
        for src in priority:
            for m in members:
                if m.get(source_field) == src and not _is_empty(m.get(field)):
                    return m.get(field)
    # No priority match -> fall back to most complete.
    return _pick_most_complete(members, field)


def _pick_most_frequent(members: list[dict], field: str):
    counter: Counter = Counter()
    first_index: dict[Any, int] = {}
    for i, m in enumerate(members):
        v = m.get(field)
        if _is_empty(v):
            continue
        # Counter keys must be hashable; coerce unhashable to str repr.
        key = v if isinstance(v, (str, int, float, bool, tuple)) else str(v)
        counter[key] += 1
        first_index.setdefault(key, i)
    if not counter:
        return None
    # Sort by (-count, first_seen_index) so ties go to the earliest-seen value.
    best_key = sorted(counter.items(), key=lambda kv: (-kv[1], first_index[kv[0]]))[0][0]
    return best_key


def _all_fields(members: list[dict], source_field: str, updated_field: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in members:
        for k in m.keys():
            if k in (source_field, updated_field):
                continue
            if k not in seen:
                seen[k] = None
    return list(seen.keys())


def build_golden(
    members: list[dict],
    rules: Optional[list[SurvivorshipRule]] = None,
    *,
    source_priority_field: str = "_source",
    updated_field: str = "_updated",
) -> dict:
    """Merge cluster members into one canonical record.

    Fields with an explicit rule use that strategy; all other fields default to
    ``most_complete``. The reserved meta fields (``_source`` / ``_updated``) are not
    emitted into the golden record.
    """
    if not members:
        return {}

    rule_map: dict[str, SurvivorshipRule] = {}
    for r in (rules or []):
        rule_map[r.field] = r

    golden: dict = {}
    for fld in _all_fields(members, source_priority_field, updated_field):
        rule = rule_map.get(fld)
        strategy = rule.strategy if rule else "most_complete"

        if strategy == "most_recent":
            value = _pick_most_recent(members, fld, updated_field)
        elif strategy == "source_priority":
            priority = (rule.source_priority if rule else None) or []
            value = _pick_source_priority(members, fld, priority, source_priority_field)
        elif strategy == "most_frequent":
            value = _pick_most_frequent(members, fld)
        else:  # most_complete (default)
            value = _pick_most_complete(members, fld)

        golden[fld] = value

    return golden
