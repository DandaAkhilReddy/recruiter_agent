from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate, Conversation, Job, Message, Score
from app.db.session import get_db
from app.schemas.score import CandidateBrief
from app.schemas.shortlist import ConversationDetailOut, ShortlistOut, TranscriptMessage
from app.services.ranker import shortlist_for_job, shortlist_to_csv

router = APIRouter(prefix="/jobs", tags=["shortlist"])


def _check_weights(match_w: float, interest_w: float) -> None:
    if abs((match_w + interest_w) - 1.0) > 0.01:
        raise HTTPException(status_code=422, detail="match_w + interest_w must sum to 1.0")


@router.get("/{job_id}/shortlist", response_model=ShortlistOut)
async def get_shortlist(
    job_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    match_w: float = Query(default=0.6, ge=0.0, le=1.0),
    interest_w: float = Query(default=0.4, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> ShortlistOut:
    if (await db.get(Job, job_id)) is None:
        raise HTTPException(status_code=404, detail="job not found")
    _check_weights(match_w, interest_w)
    items, total = await shortlist_for_job(db, job_id, limit, match_w, interest_w)
    return ShortlistOut(
        job_id=job_id,
        match_weight=match_w,
        interest_weight=interest_w,
        total=total,
        items=items,
    )


@router.get("/{job_id}/shortlist.csv")
async def get_shortlist_csv(
    job_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    match_w: float = Query(default=0.6, ge=0.0, le=1.0),
    interest_w: float = Query(default=0.4, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if (await db.get(Job, job_id)) is None:
        raise HTTPException(status_code=404, detail="job not found")
    _check_weights(match_w, interest_w)
    items, _ = await shortlist_for_job(db, job_id, limit, match_w, interest_w)
    return StreamingResponse(
        shortlist_to_csv(items),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="shortlist-{job_id}.csv"'},
    )


@router.get("/{job_id}/conversations/{candidate_id}", response_model=ConversationDetailOut)
async def get_conversation(
    job_id: UUID,
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailOut:
    convo = await db.scalar(
        select(Conversation).where(
            Conversation.job_id == job_id,
            Conversation.candidate_id == candidate_id,
        )
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    cand = await db.get(Candidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    score = await db.scalar(
        select(Score).where(Score.job_id == job_id, Score.candidate_id == candidate_id)
    )
    msgs = list(
        (await db.scalars(
            select(Message).where(Message.conversation_id == convo.id).order_by(Message.turn_index)
        )).all()
    )
    return ConversationDetailOut(
        job_id=job_id,
        candidate=CandidateBrief(
            id=cand.id, name=cand.name, title=cand.title, yoe=cand.yoe,
            seniority=cand.seniority, skills=list(cand.skills or []),
            location=cand.location, remote_ok=cand.remote_ok,
        ),
        status=convo.status,
        started_at=convo.started_at,
        completed_at=convo.completed_at,
        interest_score=float(score.interest_score) if score and score.interest_score is not None else None,
        interest_signals=score.interest_signals if score else None,
        interest_concerns=score.interest_concerns if score else None,
        interest_reasoning=score.interest_reasoning if score else None,
        messages=[
            TranscriptMessage(role=m.role, content=m.content, turn_index=m.turn_index, created_at=m.created_at)
            for m in msgs
        ],
    )
