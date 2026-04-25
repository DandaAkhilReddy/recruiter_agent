from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.db.session import get_db
from app.logging import get_logger
from app.rate_limit import rate_limit
from app.schemas.jd import JobIn, JobOut
from app.services.embeddings import embed_one
from app.services.jd_parser import JDParseError, parse_jd

log = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

_create_job_rate_limit = rate_limit(max_calls=10, window_seconds=60.0)


def _to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        seniority=job.seniority,
        min_yoe=job.min_yoe,
        must_have_skills=list(job.must_have_skills or []),
        nice_to_have=list(job.nice_to_have or []),
        domain=job.domain,
        location_pref=job.location_pref,
        remote_ok=job.remote_ok,
        status=job.status,
        created_at=job.created_at,
    )


@router.post(
    "",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_create_job_rate_limit)],
)
async def create_job(
    request: Request,
    body: Annotated[JobIn, Body()],
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    try:
        parsed = await parse_jd(body.raw_text)
    except JDParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    embed_blob = (
        f"{parsed.title} | seniority={parsed.seniority} | "
        f"must={', '.join(parsed.must_have_skills)} | nice={', '.join(parsed.nice_to_have)} | "
        f"domain={parsed.domain or ''} | location={parsed.location_pref or ''}"
    )
    embedding = await embed_one(embed_blob)

    job = Job(
        raw_text=body.raw_text,
        title=parsed.title,
        seniority=parsed.seniority,
        min_yoe=parsed.min_yoe,
        must_have_skills=parsed.must_have_skills,
        nice_to_have=parsed.nice_to_have,
        domain=parsed.domain,
        location_pref=parsed.location_pref,
        remote_ok=parsed.remote_ok,
        parsed_json=parsed.model_dump(),
        embedding=embedding,
        status="parsed",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    log.info("jobs.created", job_id=str(job.id), title=job.title)
    return _to_out(job)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> JobOut:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_out(job)
