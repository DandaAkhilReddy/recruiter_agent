from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.events.bus import subscribe

router = APIRouter(prefix="/jobs", tags=["stream"])


@router.get("/{job_id}/stream")
async def stream(job_id: UUID) -> EventSourceResponse:
    async def event_gen():
        async for evt in subscribe(str(job_id)):
            yield {
                "event": evt.get("type", "message"),
                "data": json.dumps(evt),
            }

    return EventSourceResponse(event_gen())
