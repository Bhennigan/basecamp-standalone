"""Pure-unit tests for Wave 1 Agent A consumer hardening.

No database required. Covers:
  - change-feed cursor encode/decode round-trip + malformed handling
  - sha256 API-key hashing helper
  - webhook bounded retry / exponential backoff (injected post fn)

Async tests use asyncio.run so pytest-asyncio is NOT required.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

from app.consumers.external_router import encode_cursor, decode_cursor
from app.consumers.auth import sha256hex
from app.consumers import webhooks


# --- Cursor encode/decode ---------------------------------------------------

def test_cursor_round_trip():
    dt = datetime(2026, 6, 12, 13, 45, 30, 123456)
    rid = "9f8c1d2e-aaaa-bbbb-cccc-000000000001"
    cursor = encode_cursor(dt, rid)
    decoded = decode_cursor(cursor)
    assert decoded is not None
    out_dt, out_id = decoded
    assert out_dt == dt
    assert out_id == rid


def test_cursor_round_trip_naive_and_microseconds_zero():
    dt = datetime(2026, 1, 1, 0, 0, 0)
    rid = "abc"
    assert decode_cursor(encode_cursor(dt, rid)) == (dt, rid)


def test_cursor_splits_on_last_pipe():
    # decode splits on the LAST '|': everything before is the timestamp, the
    # final segment is the id. A valid timestamp + plain id round-trips cleanly.
    dt = datetime(2026, 6, 12, 13, 45, 30)
    rid = "plain-id"
    cursor = encode_cursor(dt, rid)
    assert decode_cursor(cursor) == (dt, rid)

    # If an extra '|' precedes the id, the timestamp segment is no longer a
    # valid ISO timestamp, so decode safely rejects it (returns None) rather
    # than mis-parsing. Ids never contain '|', so this case shouldn't occur,
    # but malformed input must fail closed.
    assert decode_cursor(f"{dt.isoformat()}|left|right") is None


def test_cursor_malformed_returns_none():
    assert decode_cursor("") is None
    assert decode_cursor("no-pipe-here") is None
    assert decode_cursor("|") is None
    assert decode_cursor("not-a-timestamp|some-id") is None
    assert decode_cursor("2026-06-12T13:45:30|") is None  # empty id
    assert decode_cursor("|some-id") is None  # empty timestamp


# --- API key hashing --------------------------------------------------------

def test_sha256hex_matches_hashlib():
    raw = "bc_test-token-123"
    assert sha256hex(raw) == hashlib.sha256(raw.encode()).hexdigest()


def test_sha256hex_is_deterministic_and_64_hex():
    h = sha256hex("bc_abc")
    assert h == sha256hex("bc_abc")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_sha256hex_differs_per_input():
    assert sha256hex("bc_one") != sha256hex("bc_two")


# --- Webhook retry / backoff ------------------------------------------------

def _make_flaky_poster(fail_times: int, status_after: int = 200):
    """Returns (poster, state). Poster fails (raises) fail_times, then returns status_after."""
    state = {"calls": 0}

    async def poster(url, payload, headers):
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise ConnectionError("simulated connect failure")
        return status_after

    return poster, state


def test_webhook_succeeds_first_try():
    poster, state = _make_flaky_poster(fail_times=0)
    ok = asyncio.run(
        webhooks.deliver_with_retry(
            "http://x/cb", {"a": 1}, {}, post_fn=poster, backoff=(0, 0, 0)
        )
    )
    assert ok is True
    assert state["calls"] == 1


def test_webhook_retries_then_succeeds():
    poster, state = _make_flaky_poster(fail_times=2)
    ok = asyncio.run(
        webhooks.deliver_with_retry(
            "http://x/cb", {"a": 1}, {}, post_fn=poster, max_attempts=3, backoff=(0, 0, 0)
        )
    )
    assert ok is True
    assert state["calls"] == 3  # failed twice, succeeded on third


def test_webhook_gives_up_after_max_attempts():
    poster, state = _make_flaky_poster(fail_times=99)  # always fails
    ok = asyncio.run(
        webhooks.deliver_with_retry(
            "http://x/cb", {"a": 1}, {}, post_fn=poster, max_attempts=3, backoff=(0, 0, 0)
        )
    )
    assert ok is False
    assert state["calls"] == 3  # exactly max_attempts


def test_webhook_retries_on_non_2xx_status():
    state = {"calls": 0}

    async def poster(url, payload, headers):
        state["calls"] += 1
        return 500 if state["calls"] < 2 else 204

    ok = asyncio.run(
        webhooks.deliver_with_retry(
            "http://x/cb", {}, {}, post_fn=poster, max_attempts=3, backoff=(0, 0, 0)
        )
    )
    assert ok is True
    assert state["calls"] == 2


def test_webhook_never_raises_into_caller():
    async def always_raise(url, payload, headers):
        raise RuntimeError("boom")

    # Should swallow and return False, not propagate the RuntimeError.
    ok = asyncio.run(
        webhooks.deliver_with_retry(
            "http://x/cb", {}, {}, post_fn=always_raise, max_attempts=2, backoff=(0, 0, 0)
        )
    )
    assert ok is False


def test_webhook_uses_backoff_sleeps_in_order(monkeypatch):
    """Verify exponential backoff sleeps are invoked with the configured durations."""
    sleeps: list[float] = []

    async def fake_sleep(secs):
        sleeps.append(secs)

    monkeypatch.setattr(webhooks.asyncio, "sleep", fake_sleep)

    poster, _ = _make_flaky_poster(fail_times=99)
    asyncio.run(
        webhooks.deliver_with_retry(
            "http://x/cb", {}, {}, post_fn=poster, max_attempts=3, backoff=(0.5, 1.0, 2.0)
        )
    )
    # 3 attempts → sleeps after attempt 1 and 2 only (none after the last)
    assert sleeps == [0.5, 1.0]


if __name__ == "__main__":  # pragma: no cover
    import sys
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
