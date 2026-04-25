"""Integration test for the /jobs/{id}/stream SSE route.

The underlying event bus is unit-tested elsewhere (test_event_bus.py). This
file pins the *HTTP route* contract:
  - 200 OK with text/event-stream content type
  - sse_starlette emits 'event:' / 'data:' lines per published event
  - the 'done' event closes the stream cleanly
  - replay buffer works end-to-end (subscribe AFTER publish still receives)

These guard the live demo UI which subscribes to this endpoint.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from app.events import bus
from app.main import app
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def http() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _parse_sse_block(block: str) -> dict[str, str]:
    """Parse one SSE event block ('event: foo\\ndata: {...}') into {event, data}."""
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            field, _, value = line.partition(":")
            out[field.strip()] = value.strip()
    return out


async def _read_events_until_done(response, max_wait: float = 5.0) -> list[dict]:
    """Drain SSE chunks from a streaming httpx response until a 'done' event.

    sse_starlette emits CRLF line endings ('event: x\\r\\ndata: y\\r\\n\\r\\n');
    we normalize to LF first so a single split rule catches both conventions.
    """
    events: list[dict] = []
    buffer = ""

    async def drain() -> None:
        nonlocal buffer
        async for chunk in response.aiter_text():
            buffer += chunk.replace("\r\n", "\n")
            while "\n\n" in buffer:
                block, _, buffer = buffer.partition("\n\n")
                if not block.strip():
                    continue
                parsed = _parse_sse_block(block)
                if "data" in parsed:
                    payload = json.loads(parsed["data"])
                    events.append({"event": parsed.get("event", "message"), "payload": payload})
                    if payload.get("type") == "done":
                        return

    await asyncio.wait_for(drain(), timeout=max_wait)
    return events


@pytest.mark.asyncio
async def test_stream_returns_event_stream_content_type(http: AsyncClient) -> None:
    """A late subscriber on a job that has already emitted 'done' should
    replay the buffered events and close immediately. This also pins the
    Content-Type header that the browser EventSource API requires.
    """
    job_id = str(uuid4())
    await bus.reset(job_id)
    await bus.publish(job_id, {"type": "outreach_started", "candidate_count": 2})
    await bus.publish(job_id, {"type": "done"})

    async with http.stream("GET", f"/jobs/{job_id}/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = await _read_events_until_done(r)

    types = [e["payload"]["type"] for e in events]
    assert types == ["outreach_started", "done"]
    # SSE 'event:' field reflects the payload type
    assert events[0]["event"] == "outreach_started"
    assert events[1]["event"] == "done"


@pytest.mark.asyncio
async def test_stream_delivers_live_events_published_after_subscribe(http: AsyncClient) -> None:
    """Subscriber connects first; events published after connect are pushed
    through. This is the primary live-demo path (UI subscribes, then backend
    fires events as the orchestrator runs).
    """
    job_id = str(uuid4())
    await bus.reset(job_id)

    received: list[dict] = []

    async def consume() -> None:
        async with http.stream("GET", f"/jobs/{job_id}/stream") as r:
            assert r.status_code == 200
            received.extend(await _read_events_until_done(r, max_wait=8.0))

    consumer = asyncio.create_task(consume())
    # Give the subscriber a beat to attach to the bus.
    await asyncio.sleep(0.2)
    await bus.publish(job_id, {"type": "turn", "role": "recruiter", "content": "Hi"})
    await bus.publish(job_id, {"type": "judge", "interest_score": 80})
    await bus.publish(job_id, {"type": "done"})
    await asyncio.wait_for(consumer, timeout=10.0)

    types = [e["payload"]["type"] for e in received]
    assert types == ["turn", "judge", "done"]
    assert received[0]["payload"]["role"] == "recruiter"
    assert received[1]["payload"]["interest_score"] == 80


@pytest.mark.asyncio
async def test_two_concurrent_streams_both_receive_all_events(http: AsyncClient) -> None:
    """Two simultaneous SSE clients on the same job both see every event in
    order. Required for the demo where one tab is the recruiter view and a
    second tab might tail the same job for inspection.
    """
    job_id = str(uuid4())
    await bus.reset(job_id)

    received_a: list[dict] = []
    received_b: list[dict] = []

    async def consume(target: list[dict]) -> None:
        async with http.stream("GET", f"/jobs/{job_id}/stream") as r:
            target.extend(await _read_events_until_done(r, max_wait=8.0))

    a = asyncio.create_task(consume(received_a))
    b = asyncio.create_task(consume(received_b))
    await asyncio.sleep(0.2)
    await bus.publish(job_id, {"type": "turn", "n": 1})
    await bus.publish(job_id, {"type": "turn", "n": 2})
    await bus.publish(job_id, {"type": "done"})
    await asyncio.wait_for(asyncio.gather(a, b), timeout=10.0)

    types_a = [e["payload"]["type"] for e in received_a]
    types_b = [e["payload"]["type"] for e in received_b]
    assert types_a == ["turn", "turn", "done"]
    assert types_b == ["turn", "turn", "done"]
