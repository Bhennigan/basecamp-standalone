"""Pure-unit tests for the entity-resolution logic (no DB, no async)."""
from app.resolution.comparators import (
    exact,
    levenshtein_ratio,
    jaro_winkler,
    compare,
)
from app.resolution.blocking import (
    BlockingKey,
    soundex,
    build_blocks,
    candidate_pairs,
)
from app.resolution.scoring import FieldRule, ScoreConfig, score_pair, classify
from app.resolution.clustering import cluster
from app.resolution.survivorship import SurvivorshipRule, build_golden


# --- comparators -------------------------------------------------------------

def test_exact():
    assert exact("a", "a") == 1.0
    assert exact("a", "b") == 0.0


def test_levenshtein_ratio_sanity():
    assert levenshtein_ratio("kitten", "kitten") == 1.0
    # kitten -> sitting is 3 edits over maxlen 7 -> ~0.571
    r = levenshtein_ratio("kitten", "sitting")
    assert 0.5 < r < 0.65
    assert levenshtein_ratio("abc", "xyz") == 0.0


def test_jaro_winkler_sanity():
    assert jaro_winkler("martha", "martha") == 1.0
    # Classic Jaro-Winkler example: martha/marhta ~ 0.961
    jw = jaro_winkler("martha", "marhta")
    assert 0.9 < jw < 1.0
    # Shared prefix boosts similar strings.
    assert jaro_winkler("dwayne", "duane") > 0.7
    assert jaro_winkler("abc", "xyz") == 0.0


def test_compare_none_handling():
    # Missing on either side -> None so the scorer can skip.
    assert compare("exact", None, "x") is None
    assert compare("exact", "x", None) is None
    assert compare("exact", "", "x") is None
    # Normalization: case + whitespace insensitive.
    assert compare("exact", "  Alice ", "alice") == 1.0


# --- blocking ----------------------------------------------------------------

def test_soundex():
    assert soundex("Robert") == "R163"
    assert soundex("Rupert") == "R163"
    assert soundex("Tymczak").startswith("T")


def test_blocking_shared_prefix_pairs():
    records = [
        {"name": "Jonathan"},
        {"name": "Jonas"},      # shares prefix "jona"
        {"name": "Zachary"},    # unrelated
    ]
    keys = [BlockingKey(field="name", strategy="prefix", length=4)]
    blocks = build_blocks(records, keys)
    pairs = candidate_pairs(blocks)
    assert (0, 1) in pairs        # Jonathan + Jonas share "jona"
    assert (0, 2) not in pairs    # Zachary does not block with anyone
    assert (1, 2) not in pairs


def test_blocking_exact_strategy():
    records = [
        {"email": "a@x.com"},
        {"email": "a@x.com"},
        {"email": "b@x.com"},
    ]
    keys = [BlockingKey(field="email", strategy="exact")]
    pairs = candidate_pairs(build_blocks(records, keys))
    assert pairs == {(0, 1)}


# --- scoring + classify ------------------------------------------------------

_RULES = [
    FieldRule(field="email", comparator="exact", weight=3.0),
    FieldRule(field="name", comparator="jaro_winkler", weight=2.0),
]
_CFG = ScoreConfig(rules=_RULES, match=0.85, review_low=0.6, review_high=0.85)


def test_score_identical_is_match():
    a = {"email": "alice@x.com", "name": "Alice Smith"}
    b = {"email": "alice@x.com", "name": "Alice Smith"}
    s = score_pair(a, b, _RULES)
    assert s == 1.0
    assert classify(s, _CFG) == "match"


def test_score_partial_is_review():
    # Same name (high jw) but different email (exact=0). Weighted avg lands mid-band.
    a = {"email": "alice@x.com", "name": "Alice Smith"}
    b = {"email": "alice@y.com", "name": "Alice Smith"}
    s = score_pair(a, b, _RULES)
    # email exact=0*3 + name jw=1*2 over weight 5 -> 0.4 ... too low. Tune rule weights:
    rules = [
        FieldRule(field="email", comparator="exact", weight=1.0),
        FieldRule(field="name", comparator="jaro_winkler", weight=2.0),
    ]
    cfg = ScoreConfig(rules=rules, match=0.85, review_low=0.6, review_high=0.85)
    s2 = score_pair(a, b, rules)
    # 0*1 + 1*2 over 3 = 0.667 -> review band.
    assert classify(s2, cfg) == "review"


def test_score_different_is_no_match():
    a = {"email": "alice@x.com", "name": "Alice Smith"}
    b = {"email": "bob@y.com", "name": "Zane Power"}
    s = score_pair(a, b, _RULES)
    assert classify(s, _CFG) == "no_match"


def test_score_skips_missing_fields():
    # name missing on b -> only email counts; identical email -> 1.0.
    a = {"email": "alice@x.com", "name": "Alice"}
    b = {"email": "alice@x.com"}
    s = score_pair(a, b, _RULES)
    assert s == 1.0


# --- clustering --------------------------------------------------------------

def test_clustering_transitive_closure():
    # A-B and B-C should yield one cluster {A, B, C} (= {0,1,2}).
    pairs = [(0, 1), (1, 2)]
    clusters = cluster(pairs)
    assert len(clusters) == 1
    assert clusters[0] == {0, 1, 2}


def test_clustering_separate_components():
    pairs = [(0, 1), (2, 3)]
    clusters = cluster(pairs)
    assert {frozenset(c) for c in clusters} == {frozenset({0, 1}), frozenset({2, 3})}


# --- survivorship ------------------------------------------------------------

def test_survivorship_most_complete_picks_longest():
    members = [
        {"name": "Al"},
        {"name": "Alice Smith"},
        {"name": ""},
    ]
    golden = build_golden(members, [SurvivorshipRule(field="name", strategy="most_complete")])
    assert golden["name"] == "Alice Smith"


def test_survivorship_source_priority_respects_order():
    members = [
        {"name": "Alice", "_source": "crm"},
        {"name": "Alicia", "_source": "billing"},
    ]
    rules = [
        SurvivorshipRule(
            field="name", strategy="source_priority", source_priority=["billing", "crm"]
        )
    ]
    golden = build_golden(members, rules)
    assert golden["name"] == "Alicia"  # billing wins over crm


def test_survivorship_most_recent():
    members = [
        {"phone": "111", "_updated": "2020-01-01T00:00:00"},
        {"phone": "222", "_updated": "2023-06-01T00:00:00"},
    ]
    golden = build_golden(members, [SurvivorshipRule(field="phone", strategy="most_recent")])
    assert golden["phone"] == "222"


def test_survivorship_default_is_most_complete():
    members = [{"name": "Bob"}, {"name": "Bob Roberts"}]
    golden = build_golden(members)  # no rules -> default most_complete
    assert golden["name"] == "Bob Roberts"


def test_survivorship_drops_meta_fields():
    members = [{"name": "Bob", "_source": "crm", "_updated": "2023-01-01"}]
    golden = build_golden(members)
    assert "_source" not in golden
    assert "_updated" not in golden
