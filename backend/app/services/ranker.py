"""Final ranking — combine Match Score (Phase 3) and Interest Score (Phase 5)
with user-tunable weights. Operates on persisted Score rows; never re-calls LLMs.
"""
from __future__ import annotations

import csv
import io
from typing import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate, Score
from app.schemas.score import CandidateBrief
from app.schemas.shortlist import ShortlistItem


def composite_final_score(
    match_score: float | None,
    interest_score: float | None,
    match_weight: float,
    interest_weight: float,
) -> float | None:
    """Weighted combo. Returns None if both inputs are missing.

    If only one is present, we use it raw (no normalization) so partial data
    still ranks.
    """
    if match_score is None and interest_score is None:
        return None
    if interest_score is None:
        return round(float(match_score), 2)
    if match_score is None:
        return round(float(interest_score), 2)
    return round(float(match_score) * match_weight + float(interest_score) * interest_weight, 2)


async def shortlist_for_job(
    session: AsyncSession,
    job_id: UUID,
    limit: int,
    match_weight: float,
    interest_weight: float,
) -> tuple[list[ShortlistItem], int]:
    """Return ranked shortlist items + total count of scored candidates."""
    rows = (await session.execute(
        select(Score, Candidate)
        .join(Candidate, Candidate.id == Score.candidate_id)
        .where(Score.job_id == job_id)
    )).all()

    items: list[tuple[float | None, ShortlistItem]] = []
    for score, cand in rows:
        match = float(score.match_score) if score.match_score is not None else None
        interest = float(score.interest_score) if score.interest_score is not None else None
        final = composite_final_score(match, interest, match_weight, interest_weight)
        breakdown = None
        if score.skill_score is not None:
            breakdown = {
                "skill": float(score.skill_score or 0),
                "experience": float(score.experience_score or 0),
                "domain": float(score.domain_score or 0),
                "location": float(score.location_score or 0),
            }
        item = ShortlistItem(
            rank=0,  # filled after sort
            candidate=CandidateBrief(
                id=cand.id, name=cand.name, title=cand.title, yoe=cand.yoe,
                seniority=cand.seniority, skills=list(cand.skills or []),
                location=cand.location, remote_ok=cand.remote_ok,
            ),
            match_score=match,
            interest_score=interest,
            final_score=final,
            breakdown=breakdown,
            match_justifications=score.match_justifications,
            interest_signals=score.interest_signals,
            interest_concerns=score.interest_concerns,
            interest_reasoning=score.interest_reasoning,
        )
        items.append((final, item))

    # Sort: rows with no final score sink to the bottom.
    items.sort(key=lambda t: (t[0] is None, -(t[0] or 0.0)))
    ranked = [item for _, item in items[:limit]]
    for i, it in enumerate(ranked, start=1):
        it.rank = i
    return ranked, len(items)


def shortlist_to_csv(items: list[ShortlistItem]) -> AsyncIterator[bytes]:
    """Stream the shortlist as CSV bytes."""

    async def gen() -> AsyncIterator[bytes]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "rank", "name", "title", "yoe", "seniority", "location", "remote_ok",
            "match_score", "interest_score", "final_score",
            "skill", "experience", "domain", "location_score",
            "skill_just", "experience_just", "domain_just", "location_just",
            "interest_signals", "interest_concerns", "interest_reasoning",
            "candidate_id",
        ])
        yield buf.getvalue().encode("utf-8")
        buf.seek(0); buf.truncate(0)

        for it in items:
            b = it.breakdown or {}
            mj = it.match_justifications or {}
            writer.writerow([
                it.rank, it.candidate.name, it.candidate.title, it.candidate.yoe,
                it.candidate.seniority, it.candidate.location or "", it.candidate.remote_ok,
                it.match_score if it.match_score is not None else "",
                it.interest_score if it.interest_score is not None else "",
                it.final_score if it.final_score is not None else "",
                b.get("skill", ""), b.get("experience", ""), b.get("domain", ""), b.get("location", ""),
                mj.get("skill", ""), mj.get("experience", ""), mj.get("domain", ""), mj.get("location", ""),
                "; ".join(it.interest_signals or []),
                "; ".join(it.interest_concerns or []),
                it.interest_reasoning or "",
                str(it.candidate.id),
            ])
            yield buf.getvalue().encode("utf-8")
            buf.seek(0); buf.truncate(0)

    return gen()
