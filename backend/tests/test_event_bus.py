"""Offline tests for the SSE event bus."""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.events import bus


@pytest.mark.asyncio
async def test_subscriber_replays_buffered_events_then_exits_on_done() -> None:
    job_id = str(uuid4())
    await bus.reset(job_id)
    await bus.publish(job_id, {"type": "outreach_started", "candidate_count": 3})
    await bus.publish(job_id, {"type": "turn", "role": "recruiter", "content": "hi"})
    await bus.publish(job_id, {"type": "done"})

    received: list[dict] = []
    async for evt in bus.subscribe(job_id):
        received.append(evt)
    assert [e["type"] for e in received] == ["outreach_started", "turn", "done"]


@pytest.mark.asyncio
async def test_late_subscriber_gets_replay_plus_live_events() -> None:
    job_id = str(uuid4())
    await bus.reset(job_id)
    await bus.publish(job_id, {"type": "early_event"})

    received: list[dict] = []

    async def consume() -> None:
        async for evt in bus.subscribe(job_id):
            received.append(evt)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)  # let subscriber attach
    await bus.publish(job_id, {"type": "live_event"})
    await bus.publish(job_id, {"type": "done"})
    await asyncio.wait_for(task, timeout=2.0)
    assert [e["type"] for e in received] == ["early_event", "live_event", "done"]


@pytest.mark.asyncio
async def test_two_subscribers_both_receive_events() -> None:
    job_id = str(uuid4())
    await bus.reset(job_id)
    received_a: list[dict] = []
    received_b: list[dict] = []

    async def consume(target: list[dict]) -> None:
        async for evt in bus.subscribe(job_id):
            target.append(evt)

    task_a = asyncio.create_task(consume(received_a))
    task_b = asyncio.create_task(consume(received_b))
    await asyncio.sleep(0.05)
    await bus.publish(job_id, {"type": "ping", "n": 1})
    await bus.publish(job_id, {"type": "done"})
    await asyncio.wait_for(task_a, timeout=2.0)
    await asyncio.wait_for(task_b, timeout=2.0)
    assert [e["type"] for e in received_a] == ["ping", "done"]
    assert [e["type"] for e in received_b] == ["ping", "done"]
