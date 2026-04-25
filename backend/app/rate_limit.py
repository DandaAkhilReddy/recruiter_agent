"""Tiny in-process rate limiter as a FastAPI dependency.

Replaces slowapi (0.1.9) which breaks Pydantic body inference under FastAPI
0.115 + Pydantic 2 — see jobs router note. This implementation is intentionally
minimal: per-IP sliding window, single-replica only. Documented limitation;
acceptable for the demo.
"""
from __future__ import annotations

from collections import defaultdict
from time import monotonic

from fastapi import HTTPException, Request, status

_buckets: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_calls: int, window_seconds: float):
    """Return a FastAPI dependency that enforces `max_calls` per `window_seconds` per client IP."""

    async def _dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = monotonic()
        bucket = _buckets[ip]
        # Drop entries outside the window in-place (keeps the dict bounded over time).
        bucket[:] = [t for t in bucket if now - t < window_seconds]
        if len(bucket) >= max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded ({max_calls}/{int(window_seconds)}s)",
            )
        bucket.append(now)

    return _dep


def reset_buckets() -> None:
    """Clear all buckets — useful in tests."""
    _buckets.clear()
