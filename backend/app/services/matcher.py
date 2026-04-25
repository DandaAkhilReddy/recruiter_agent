"""3-stage hybrid candidate matcher.

Pipeline:
    1. Hard filter — SQL `WHERE yoe >= min_yoe`. (Skill overlap is required only
       if must_have_skills is non-empty.)
    2. Embedding rerank — pgvector cosine top-K (default 50) against the JD's
       stored embedding.
    3. LLM rerank — gpt-4o scores each candidate on 4 dimensions in batches
       of 10, with one-line justifications per dimension.

Composite Match Score = 0.40·skill + 0.25·experience + 0.20·domain + 0.15·location.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Candidate, Job, Score
from app.logging import get_logger
from app.schemas.score import (
    CandidateBrief,
    DimKey,
    MatchOut,
    PerDimScore,
    RerankBatchResult,
    ScoreOut,
)
from app.services.aoai import get_aoai

log = get_logger(__name__)

WEIGHTS: dict[DimKey, float] = {"skill": 0.40, "experience": 0.25, "domain": 0.20, "location": 0.15}

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "rerank.md"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_RERANK_CONCURRENCY = 5


def composite_match_score(skill: float, experience: float, domain: float, location: float) -> float:
    raw = (
        skill * WEIGHTS["skill"]
        + experience * WEIGHTS["experience"]
        + domain * WEIGHTS["domain"]
        + location * WEIGHTS["location"]
    )
    return round(raw, 2)


async def _hard_filter(session: AsyncSession, job: Job) -> list[Candidate]:
    """Return candidates meeting min YOE and (if any) at least one must-have skill."""
    stmt = select(Candidate).where(Candidate.yoe >= (job.min_yoe or 0))
    if job.must_have_skills:
        # candidate.skills && ARRAY[...] — Postgres array overlap operator.
        stmt = stmt.where(text("candidates.skills && :must")).params(must=list(job.must_have_skills))
    return list((await session.scalars(stmt)).all())


async def _embedding_topk(session: AsyncSession, job: Job, top_k: int, candidate_ids: list[UUID]) -> list[Candidate]:
    """Rank `candidate_ids` by cosine distance to JD embedding, return top_k."""
    if not candidate_ids or job.embedding is None:
        return []
    # `<=>` is pgvector cosine distance.
    stmt = (
        select(Candidate)
        .where(Candidate.id.in_(candidate_ids))
        .order_by(Candidate.embedding.cosine_distance(job.embedding))
        .limit(top_k)
    )
    return list((await session.scalars(stmt)).all())


def _to_rerank_payload(job: Job, batch: list[Candidate]) -> dict:
    return {
        "jd": job.parsed_json,
        "candidates": [
            {
                "id": str(c.id),
                "name": c.name,
                "title": c.title,
                "yoe": c.yoe,
                "seniority": c.seniority,
                "skills": list(c.skills or []),
                "domain": c.domain,
                "location": c.location,
                "remote_ok": c.remote_ok,
                "summary": c.summary,
            }
            for c in batch
        ],
    }


async def _rerank_one_batch(job: Job, batch: list[Candidate]) -> RerankBatchResult:
    s = get_settings()
    client = get_aoai()
    payload = _to_rerank_payload(job, batch)
    resp = await client.chat.completions.create(
        model=s.aoai_gpt4o_deployment,
        temperature=0.0,
        seed=42,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PROMPT_TEMPLATE},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    return RerankBatchResult.model_validate(data)


async def _rerank_all(job: Job, candidates: list[Candidate], batch_size: int) -> list[PerDimScore]:
    sem = asyncio.Semaphore(_RERANK_CONCURRENCY)
    batches = [candidates[i : i + batch_size] for i in range(0, len(candidates), batch_size)]

    async def run(batch: list[Candidate]) -> list[PerDimScore]:
        async with sem:
            try:
                result = await _rerank_one_batch(job, batch)
            except (json.JSONDecodeError, ValueError) as exc:
                log.warning("matcher.rerank_batch_failed", size=len(batch), error=str(exc))
                return []
        # Defensive: keep only scores whose candidate_id was in the batch.
        valid_ids = {c.id for c in batch}
        return [s for s in result.scores if s.candidate_id in valid_ids]

    log.info("matcher.rerank_start", batches=len(batches), candidates=len(candidates))
    chunks = await asyncio.gather(*(run(b) for b in batches))
    flat = [s for chunk in chunks for s in chunk]
    log.info("matcher.rerank_done", scored=len(flat))
    return flat


async def _persist_scores(session: AsyncSession, job_id: UUID, scores: list[PerDimScore]) -> None:
    if not scores:
        return
    # Upsert: re-running /match overwrites prior match-side fields, leaving
    # interest_* untouched.
    rows = [
        {
            "job_id": job_id,
            "candidate_id": s.candidate_id,
            "match_score": composite_match_score(s.skill, s.experience, s.domain, s.location),
            "skill_score": s.skill,
            "experience_score": s.experience,
            "domain_score": s.domain,
            "location_score": s.location,
            "match_justifications": s.justifications,
        }
        for s in scores
    ]
    stmt = pg_insert(Score).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_id", "candidate_id"],
        set_={
            "match_score": stmt.excluded.match_score,
            "skill_score": stmt.excluded.skill_score,
            "experience_score": stmt.excluded.experience_score,
            "domain_score": stmt.excluded.domain_score,
            "location_score": stmt.excluded.location_score,
            "match_justifications": stmt.excluded.match_justifications,
        },
    )
    await session.execute(stmt)


def _to_score_out(rank: int, candidate: Candidate, score: PerDimScore) -> ScoreOut:
    breakdown = {
        "skill": float(score.skill),
        "experience": float(score.experience),
        "domain": float(score.domain),
        "location": float(score.location),
    }
    return ScoreOut(
        rank=rank,
        candidate=CandidateBrief(
            id=candidate.id,
            name=candidate.name,
            title=candidate.title,
            yoe=candidate.yoe,
            seniority=candidate.seniority,
            skills=list(candidate.skills or []),
            location=candidate.location,
            remote_ok=candidate.remote_ok,
        ),
        match_score=composite_match_score(score.skill, score.experience, score.domain, score.location),
        breakdown=breakdown,
        justifications=dict(score.justifications),
    )


async def run_match(session: AsyncSession, job: Job, top_k_for_rerank: int, batch_size: int, return_top: int) -> MatchOut:
    log.info("matcher.start", job_id=str(job.id), top_k=top_k_for_rerank, batch=batch_size)

    filtered = await _hard_filter(session, job)
    log.info("matcher.hard_filter", n=len(filtered))
    if not filtered:
        return MatchOut(job_id=job.id, matched_count=0, rerank_count=0, top=[])

    filtered_ids = [c.id for c in filtered]
    topk = await _embedding_topk(session, job, top_k_for_rerank, filtered_ids)
    log.info("matcher.embedding_topk", n=len(topk))

    scores = await _rerank_all(job, topk, batch_size)

    # Re-key candidates by id for joining.
    by_id = {c.id: c for c in topk}
    scored = [(by_id[s.candidate_id], s) for s in scores if s.candidate_id in by_id]
    scored.sort(key=lambda pair: composite_match_score(*[
        pair[1].skill, pair[1].experience, pair[1].domain, pair[1].location
    ]), reverse=True)

    # Persist before returning so /shortlist can read freshly.
    # Wipe prior match scores for this job to keep results clean.
    await session.execute(
        delete(Score).where(Score.job_id == job.id, Score.candidate_id.in_([c.id for c, _ in scored]))
    )
    await _persist_scores(session, job.id, [s for _, s in scored])

    # Update job status.
    job.status = "matched"
    await session.commit()

    out_top = [_to_score_out(i + 1, c, s) for i, (c, s) in enumerate(scored[:return_top])]
    return MatchOut(
        job_id=job.id,
        matched_count=len(filtered),
        rerank_count=len(scored),
        top=out_top,
    )
