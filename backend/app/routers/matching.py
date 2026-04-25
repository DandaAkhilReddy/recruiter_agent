from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Job
from app.db.session import get_db
from app.schemas.score import MatchOut
from app.services.matcher import run_match

router = APIRouter(prefix="/jobs", tags=["matching"])


class MatchIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    top_k: int | None = Field(default=None, ge=10, le=200, description="Embedding rerank top-K")
    batch_size: int | None = Field(default=None, ge=1, le=25, description="LLM rerank batch size")
    return_top: int | None = Field(default=None, ge=1, le=100, description="How many to return")


@router.post("/{job_id}/match", response_model=MatchOut)
async def match_job(
    job_id: UUID,
    body: MatchIn | None = None,
    db: AsyncSession = Depends(get_db),
) -> MatchOut:
    settings = get_settings()
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    body = body or MatchIn()
    return await run_match(
        session=db,
        job=job,
        top_k_for_rerank=body.top_k or settings.rerank_top_k,
        batch_size=body.batch_size or settings.rerank_batch_size,
        return_top=body.return_top or settings.outreach_top_k,
    )
