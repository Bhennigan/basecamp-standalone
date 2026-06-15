"""Candidate generation (blocking) to avoid the O(n^2) all-pairs comparison.

Rather than compare every record against every other, we partition records into
"blocks" keyed by cheap deterministic tokens (a field prefix, an exact field value,
or a soundex code). Two records are only considered a candidate pair if they share at
least one block token. This trades a small recall risk (records that should match but
share no block token) for a large efficiency win.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Optional


@dataclass
class BlockingKey:
    """One blocking strategy over a single field.

    strategy:
      - "prefix": first ``length`` chars of the (normalized) field value.
      - "exact":  the whole normalized field value.
      - "soundex": phonetic code of the field value (good for misspelled names).
    """
    field: str
    strategy: str = "prefix"
    length: int = 4


def soundex(s: str) -> str:
    """Pure-python Soundex: a 4-char phonetic code (e.g. 'Robert' -> 'R163')."""
    if not s:
        return ""
    s = "".join(ch for ch in s.upper() if ch.isalpha())
    if not s:
        return ""

    codes = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }

    first = s[0]
    result = first
    prev_code = codes.get(first, "")

    for ch in s[1:]:
        code = codes.get(ch, "")
        if ch in ("H", "W"):
            # H and W are transparent: don't reset prev_code, don't emit.
            continue
        if code:
            if code != prev_code:
                result += code
                if len(result) == 4:
                    break
        prev_code = code

    return (result + "000")[:4]


def _norm_field(record_data: dict, field: str) -> Optional[str]:
    v = record_data.get(field)
    if v is None:
        return None
    s = str(v).strip().lower()
    return s if s else None


def blocking_key(record_data: dict, keys: list[BlockingKey]) -> list[str]:
    """Produce the list of block tokens a single record belongs to.

    A record may land in multiple blocks (one per key it can satisfy). Tokens are
    namespaced by field+strategy so a name-prefix never collides with an email-prefix.
    """
    tokens: list[str] = []
    for key in keys:
        val = _norm_field(record_data, key.field)
        if val is None:
            continue
        if key.strategy == "prefix":
            token = val[: key.length]
        elif key.strategy == "exact":
            token = val
        elif key.strategy == "soundex":
            token = soundex(val)
        else:
            continue
        if token:
            tokens.append(f"{key.field}:{key.strategy}:{token}")
    return tokens


def build_blocks(records: list[dict], keys: list[BlockingKey]) -> dict[str, list[int]]:
    """Map each block token to the list of record indices that carry it."""
    blocks: dict[str, list[int]] = {}
    for idx, rec in enumerate(records):
        for token in blocking_key(rec, keys):
            blocks.setdefault(token, []).append(idx)
    return blocks


def candidate_pairs(blocks: dict[str, list[int]]) -> set[tuple[int, int]]:
    """Unique (i, j) index pairs (i < j) that co-occur in at least one block."""
    pairs: set[tuple[int, int]] = set()
    for indices in blocks.values():
        if len(indices) < 2:
            continue
        for i, j in combinations(sorted(set(indices)), 2):
            pairs.add((i, j))
    return pairs
