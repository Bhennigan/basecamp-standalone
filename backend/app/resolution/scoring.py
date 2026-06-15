"""Weighted match scoring over a candidate record pair.

A pair's match score is the weighted average of per-field comparator scores. Fields
that are missing in *either* record are skipped entirely — their weight is removed
from the denominator — so absent data neither helps nor hurts the score.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.resolution.comparators import compare


@dataclass
class FieldRule:
    """How to compare one field, and how much it counts.

    threshold (optional): if set, a per-field comparator score below it is treated as
    a hard 0 for that field (still counted in the denominator). Useful to require a
    near-exact match on, e.g., a national id before it contributes signal.
    """
    field: str
    comparator: str
    weight: float = 1.0
    threshold: Optional[float] = None


@dataclass
class ScoreConfig:
    """A ruleset plus the band thresholds used by ``classify``."""
    rules: list[FieldRule]
    match: float = 0.85
    review_low: float = 0.6
    review_high: float = 0.85


def score_pair(a: dict, b: dict, rules: list[FieldRule]) -> float:
    """Weighted average of per-field comparator scores in [0, 1].

    Returns 0.0 if no field could be compared (all skipped or zero total weight).
    """
    total_weight = 0.0
    accumulated = 0.0
    for rule in rules:
        s = compare(rule.comparator, a.get(rule.field), b.get(rule.field))
        if s is None:
            # Field missing on at least one side -> skip; don't count its weight.
            continue
        if rule.threshold is not None and s < rule.threshold:
            s = 0.0
        total_weight += rule.weight
        accumulated += s * rule.weight
    if total_weight == 0.0:
        return 0.0
    return accumulated / total_weight


def classify(score: float, config: ScoreConfig) -> str:
    """Bucket a score into 'match' | 'review' | 'no_match'.

    - score >= match                  -> "match"
    - review_low <= score < match     -> "review"  (queued for human approval)
    - score < review_low              -> "no_match"
    """
    if score >= config.match:
        return "match"
    if score >= config.review_low:
        return "review"
    return "no_match"
