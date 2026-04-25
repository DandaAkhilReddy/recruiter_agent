"""Conversation orchestrator — runs Recruiter ↔ Persona for top-N candidates.

For each selected candidate we run up to `max_turns` rounds of dialog (where
1 round = recruiter says + persona replies). Messages are persisted as they're
generated; SSE events are published per turn so the UI can render in real time.

Concurrency is bounded by `asyncio.Semaphore(_PARALLEL_CONVERSATIONS)` to keep
us under AOAI TPM during a demo.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate, Conversation, Job, Message, Score
from app.db.session import SessionLocal
from app.events.bus import publish
from app.logging import get_logger
from app.services import persona, recruiter
from app.services.judge import JudgeError, judge_transcript, persist_interest

log = get_logger(__name__)

_PARALLEL_CONVERSATIONS = 5


async def _select_top_candidates(session: AsyncSession, job_id: UUID, limit: int) -> list[Candidate]:
    """Read top-N from scores table by match_score desc."""
    stmt = (
        select(Candidate)
        .join(Score, Score.candidate_id == Candidate.id)
        .where(Score.job_id == job_id)
        .order_by(Score.match_score.desc().nullslast())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def _ensure_conversation(session: AsyncSession, job_id: UUID, candidate_id: UUID) -> Conversation:
    """Create the conversation row if missing, else return the existing one."""
    existing = await session.scalar(
        select(Conversation).where(Conversation.job_id == job_id, Conversation.candidate_id == candidate_id)
    )
    if existing is not None:
        return existing
    convo = Conversation(job_id=job_id, candidate_id=candidate_id, status="in_progress")
    session.add(convo)
    await session.commit()
    await session.refresh(convo)
    return convo


async def _persist_message(session: AsyncSession, conversation_id: UUID, role: str, content: str, turn_index: int) -> None:
    msg = Message(conversation_id=conversation_id, role=role, content=content, turn_index=turn_index)
    session.add(msg)
    await session.commit()


async def _emit_turn(job_id: str, candidate: Candidate, role: str, content: str, turn_index: int) -> None:
    await publish(
        job_id,
        {
            "type": "turn",
            "candidate_id": str(candidate.id),
            "candidate_name": candidate.name,
            "role": role,
            "content": content,
            "turn_index": turn_index,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )


async def run_conversation(job: Job, candidate: Candidate, max_turns: int) -> None:
    """Run a single Recruiter ↔ Persona conversation, persist + emit per turn."""
    job_id_s = str(job.id)
    async with SessionLocal() as session:
        convo = await _ensure_conversation(session, job.id, candidate.id)

    history: list[dict] = []

    # Recruiter opening turn.
    opening = await recruiter.opening_message(job, candidate)
    history.append({"role": "recruiter", "content": opening})
    async with SessionLocal() as session:
        await _persist_message(session, convo.id, "recruiter", opening, 0)
    await _emit_turn(job_id_s, candidate, "recruiter", opening, 0)

    turn_idx = 1
    for _ in range(max_turns):
        # Candidate reply.
        cand_reply = await persona.respond(candidate, history)
        history.append({"role": "candidate", "content": cand_reply})
        async with SessionLocal() as session:
            await _persist_message(session, convo.id, "candidate", cand_reply, turn_idx)
        await _emit_turn(job_id_s, candidate, "candidate", cand_reply, turn_idx)
        turn_idx += 1

        # Stop one turn early so the conversation ends on the candidate.
        if turn_idx >= max_turns * 2:
            break

        # Recruiter follow-up.
        rec_reply = await recruiter.respond(job, candidate, history)
        history.append({"role": "recruiter", "content": rec_reply})
        async with SessionLocal() as session:
            await _persist_message(session, convo.id, "recruiter", rec_reply, turn_idx)
        await _emit_turn(job_id_s, candidate, "recruiter", rec_reply, turn_idx)
        turn_idx += 1

    # Mark conversation done.
    async with SessionLocal() as session:
        c = await session.get(Conversation, convo.id)
        if c is not None:
            c.status = "completed"
            c.completed_at = datetime.now(timezone.utc)
            await session.commit()

    await publish(
        job_id_s,
        {"type": "conversation_done", "candidate_id": str(candidate.id), "candidate_name": candidate.name},
    )

    # Run Judge on the full transcript and persist interest_* into the Score row.
    async with SessionLocal() as session:
        msgs = list(
            (await session.scalars(
                select(Message).where(Message.conversation_id == convo.id).order_by(Message.turn_index)
            )).all()
        )
        try:
            judged = await judge_transcript(msgs)
        except JudgeError as exc:
            log.warning("orchestrator.judge_failed", candidate_id=str(candidate.id), error=str(exc))
            await publish(
                job_id_s,
                {"type": "judge_failed", "candidate_id": str(candidate.id), "error": str(exc)},
            )
            return
        await persist_interest(session, job.id, candidate.id, judged)
    await publish(
        job_id_s,
        {
            "type": "judge",
            "candidate_id": str(candidate.id),
            "candidate_name": candidate.name,
            "interest_score": judged.interest_score,
            "signals": judged.signals,
            "concerns": judged.concerns,
            "reasoning": judged.reasoning,
        },
    )


async def run_outreach(job_id: UUID, top_k: int, max_turns: int) -> None:
    """Background task — orchestrates conversations for top-K candidates by match score."""
    job_id_s = str(job_id)
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None:
            log.error("orchestrator.job_missing", job_id=job_id_s)
            await publish(job_id_s, {"type": "error", "message": "job not found"})
            return
        candidates = await _select_top_candidates(session, job_id, top_k)

    if not candidates:
        await publish(job_id_s, {"type": "error", "message": "no matched candidates — run /match first"})
        await publish(job_id_s, {"type": "done"})
        return

    await publish(
        job_id_s,
        {
            "type": "outreach_started",
            "candidate_count": len(candidates),
            "max_turns": max_turns,
        },
    )

    sem = asyncio.Semaphore(_PARALLEL_CONVERSATIONS)

    async def run_one(c: Candidate) -> None:
        async with sem:
            try:
                await run_conversation(job, c, max_turns=max_turns)
            except Exception as exc:  # noqa: BLE001 — boundary, log and surface
                log.exception("orchestrator.conversation_failed", candidate_id=str(c.id), error=str(exc))
                await publish(
                    job_id_s,
                    {"type": "conversation_failed", "candidate_id": str(c.id), "error": str(exc)},
                )

    await asyncio.gather(*(run_one(c) for c in candidates))

    # Update job status.
    async with SessionLocal() as session:
        j = await session.get(Job, job_id)
        if j is not None:
            j.status = "outreached"
            await session.commit()

    await publish(job_id_s, {"type": "done"})
    log.info("orchestrator.complete", job_id=job_id_s, candidates=len(candidates))
