from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Job
from app.db.session import get_db
from app.services.orchestrator import run_outreach

router = APIRouter(prefix="/jobs", tags=["outreach"])


class OutreachIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    top_k: int | None = Field(default=None, ge=1, le=50)
    max_turns: int | None = Field(default=None, ge=1, le=10)


class OutreachAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID
    started: bool
    top_k: int
    max_turns: int


@router.post("/{job_id}/outreach", response_model=OutreachAccepted, status_code=status.HTTP_202_ACCEPTED)
async def start_outreach(job_id: UUID, body: OutreachIn | None = None, db: AsyncSession = Depends(get_db)) -> OutreachAccepted:
    s = get_settings()
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    body = body or OutreachIn()
    top_k = body.top_k or s.outreach_top_k
    max_turns = body.max_turns or s.max_conversation_turns

    # Fire and forget — orchestrator manages its own DB sessions.
    asyncio.create_task(run_outreach(job.id, top_k=top_k, max_turns=max_turns))
    return OutreachAccepted(job_id=job.id, started=True, top_k=top_k, max_turns=max_turns)
