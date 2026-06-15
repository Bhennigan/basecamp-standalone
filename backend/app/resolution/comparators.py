"""Pure string/value similarity comparators (no external dependencies).

Each comparator takes two raw values and returns a float in [0.0, 1.0]. They are
hand-rolled on purpose — entity resolution must run in DDIL / air-gapped contexts,
so we don't pull in jellyfish / rapidfuzz / python-Levenshtein.

``compare(name, a, b)`` is the scoring-facing entry point: it normalizes inputs
(``str``, lowercase, strip) and returns ``None`` when either side is missing so the
weighted scorer can skip the field rather than counting a spurious 0.0.
"""
from __future__ import annotations

from typing import Callable, Optional


def _norm(v) -> Optional[str]:
    """Normalize a raw value to a lowercased/stripped string, or None if empty."""
    if v is None:
        return None
    s = str(v).strip().lower()
    return s if s else None


def exact(a: str, b: str) -> float:
    """1.0 if the (normalized) strings are identical, else 0.0."""
    return 1.0 if a == b else 0.0


def levenshtein_distance(a: str, b: str) -> int:
    """Classic edit distance (insert/delete/substitute), O(len(a)*len(b)) space-optimized."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Two-row dynamic programming.
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(
                prev[j] + 1,       # deletion
                cur[j - 1] + 1,    # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = cur
    return prev[-1]


def levenshtein_ratio(a: str, b: str) -> float:
    """Normalized similarity: 1 - distance / max(len). Empty/empty -> 1.0."""
    if not a and not b:
        return 1.0
    maxlen = max(len(a), len(b))
    if maxlen == 0:
        return 1.0
    return 1.0 - (levenshtein_distance(a, b) / maxlen)


def jaro(a: str, b: str) -> float:
    """Jaro similarity in [0, 1]."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0

    len_a, len_b = len(a), len(b)
    match_distance = max(len_a, len_b) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    a_matches = [False] * len_a
    b_matches = [False] * len_b

    matches = 0
    for i in range(len_a):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len_b)
        for j in range(start, end):
            if b_matches[j]:
                continue
            if a[i] != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    # Count transpositions.
    transpositions = 0
    k = 0
    for i in range(len_a):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2

    m = matches
    return (m / len_a + m / len_b + (m - transpositions) / m) / 3.0


def jaro_winkler(a: str, b: str, *, prefix_weight: float = 0.1, max_prefix: int = 4) -> float:
    """Jaro-Winkler: Jaro boosted for a shared leading prefix (up to ``max_prefix``)."""
    j = jaro(a, b)
    if j == 0.0 or a == b:
        return j if not a == b else 1.0
    prefix = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            prefix += 1
            if prefix == max_prefix:
                break
        else:
            break
    return j + prefix * prefix_weight * (1.0 - j)


# Registry of normalized comparators (operate on already-normalized strings).
COMPARATORS: dict[str, Callable[[str, str], float]] = {
    "exact": exact,
    "levenshtein": levenshtein_ratio,
    "jaro_winkler": jaro_winkler,
}


def compare(name: str, a, b) -> Optional[float]:
    """Run comparator ``name`` over raw values ``a`` and ``b``.

    Normalizes (str/lower/strip). Returns ``None`` if either side is missing so the
    weighted scorer can skip the field. Raises KeyError for an unknown comparator.
    """
    na, nb = _norm(a), _norm(b)
    if na is None or nb is None:
        return None
    fn = COMPARATORS[name]
    return fn(na, nb)
