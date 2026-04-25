"""Unit tests for app.rate_limit — sliding-window per-IP limiter.

Built to replace slowapi (broke FastAPI 0.115 + Pydantic 2 body inference).
This is a custom hot-path dependency on POST /jobs; bugs here either let
abuse through (security/cost) or wrongly 429 real users (UX). Coverage matters.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from app import rate_limit as rl
from fastapi import HTTPException


def _req(ip: str | None = "1.2.3.4"):
    """Build a minimal Request stand-in that exposes `.client.host`."""
    client = SimpleNamespace(host=ip) if ip is not None else None
    return SimpleNamespace(client=client)


@pytest.fixture(autouse=True)
def _reset_buckets_between_tests():
    rl.reset_buckets()
    yield
    rl.reset_buckets()


@pytest.mark.asyncio
async def test_allows_calls_under_the_limit() -> None:
    dep = rl.rate_limit(max_calls=3, window_seconds=60.0)
    req = _req("10.0.0.1")

    # Three calls in the window — all allowed.
    for _ in range(3):
        await dep(req)


@pytest.mark.asyncio
async def test_blocks_at_limit_with_429() -> None:
    dep = rl.rate_limit(max_calls=2, window_seconds=60.0)
    req = _req("10.0.0.2")

    await dep(req)
    await dep(req)
    with pytest.raises(HTTPException) as exc:
        await dep(req)

    assert exc.value.status_code == 429
    assert "rate limit exceeded" in exc.value.detail
    assert "2/60s" in exc.value.detail


@pytest.mark.asyncio
async def test_window_expiry_frees_a_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Advance monotonic time past window — old bucket entries drop, slot reopens."""
    fake_time = {"t": 1000.0}
    monkeypatch.setattr(rl, "monotonic", lambda: fake_time["t"])

    dep = rl.rate_limit(max_calls=1, window_seconds=10.0)
    req = _req("10.0.0.3")

    await dep(req)
    # Same instant — limit hit.
    with pytest.raises(HTTPException):
        await dep(req)

    # 11s later — the prior entry falls outside the window.
    fake_time["t"] += 11.0
    await dep(req)  # must succeed


@pytest.mark.asyncio
async def test_per_ip_isolation() -> None:
    """One IP exhausting its quota must not affect another."""
    dep = rl.rate_limit(max_calls=1, window_seconds=60.0)
    req_a = _req("1.1.1.1")
    req_b = _req("2.2.2.2")

    await dep(req_a)
    with pytest.raises(HTTPException):
        await dep(req_a)

    # IP B is unaffected.
    await dep(req_b)


@pytest.mark.asyncio
async def test_unknown_client_is_bucketed_under_unknown_key() -> None:
    """Requests without `request.client` (e.g. some test transports) get an 'unknown' bucket."""
    dep = rl.rate_limit(max_calls=1, window_seconds=60.0)
    req = _req(ip=None)  # client=None

    await dep(req)
    with pytest.raises(HTTPException):
        await dep(req)


@pytest.mark.asyncio
async def test_reset_buckets_clears_all_state() -> None:
    dep = rl.rate_limit(max_calls=1, window_seconds=60.0)
    req = _req("10.0.0.4")
    await dep(req)
    with pytest.raises(HTTPException):
        await dep(req)

    rl.reset_buckets()

    # After reset, the same IP is fresh again.
    await dep(req)


@pytest.mark.asyncio
async def test_independent_dependencies_share_bucket_state() -> None:
    """The bucket store is module-global — two dependencies on the same IP
    share the same sliding window. This is by design (per-IP, not per-route)
    and worth pinning so a future refactor doesn't silently change semantics.
    """
    dep_a = rl.rate_limit(max_calls=2, window_seconds=60.0)
    dep_b = rl.rate_limit(max_calls=2, window_seconds=60.0)
    req = _req("10.0.0.5")

    await dep_a(req)
    await dep_b(req)
    with pytest.raises(HTTPException):
        await dep_a(req)
