"""In-process pub/sub for SSE fan-out, keyed by job_id.

Late subscribers replay buffered events on connect — the frontend often opens
the SSE stream a few hundred ms after `POST /outreach` returns 202, and we
don't want to miss the early `parse_started` / `match_progress` events.

Single-replica only. For multi-replica we'd swap this for Redis Streams or
similar; documented limitation for the demo.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator

from app.logging import get_logger

log = get_logger(__name__)

_MAX_BUFFERED_EVENTS = 2000


@dataclass
class _Channel:
    events: list[dict] = field(default_factory=list)
    subscribers: list[asyncio.Queue[dict]] = field(default_factory=list)
    closed: bool = False


_channels: dict[str, _Channel] = {}
_lock = asyncio.Lock()


async def _get_or_create(job_id: str) -> _Channel:
    async with _lock:
        ch = _channels.get(job_id)
        if ch is None:
            ch = _Channel()
            _channels[job_id] = ch
        return ch


async def publish(job_id: str, event: dict) -> None:
    """Publish an event to all current and future subscribers of `job_id`."""
    ch = await _get_or_create(job_id)
    if len(ch.events) < _MAX_BUFFERED_EVENTS:
        ch.events.append(event)
    for q in list(ch.subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("events.queue_full_dropping", job_id=job_id)
    if event.get("type") == "done":
        ch.closed = True


async def subscribe(job_id: str) -> AsyncIterator[dict]:
    """Yield buffered events first, then live events. Exits on `done` event."""
    ch = await _get_or_create(job_id)
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=_MAX_BUFFERED_EVENTS)
    # Replay everything so far.
    for e in ch.events:
        q.put_nowait(e)
    ch.subscribers.append(q)
    try:
        # If the channel was already closed (job finished before subscriber connected),
        # the replay above includes the `done` event and we'll exit naturally below.
        while True:
            evt = await q.get()
            yield evt
            if evt.get("type") == "done":
                return
    finally:
        try:
            ch.subscribers.remove(q)
        except ValueError:
            pass


async def reset(job_id: str) -> None:
    """Clear a job channel. Useful for tests or when re-running outreach."""
    async with _lock:
        _channels.pop(job_id, None)
