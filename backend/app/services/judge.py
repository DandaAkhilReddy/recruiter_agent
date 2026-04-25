from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Message, Score
from app.logging import get_logger
from app.schemas.judge import JudgeResult
from app.services.aoai import get_aoai

log = get_logger(__name__)

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "judge.md").read_text(encoding="utf-8")


class JudgeError(ValueError):
    """Raised when the judge cannot produce a valid JudgeResult."""


async def judge_transcript(messages: list[Message]) -> JudgeResult:
    """Score interest 0-100 from a transcript. Pure function — does not persist."""
    s = get_settings()
    client = get_aoai()
    transcript = [{"role": m.role, "content": m.content} for m in messages]
    payload = {"transcript": transcript}
    resp = await client.chat.completions.create(
        model=s.aoai_gpt4o_deployment,
        temperature=0.0,
        seed=42,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("judge.invalid_json", raw=raw[:300])
        raise JudgeError("Judge LLM returned invalid JSON") from exc
    try:
        return JudgeResult.model_validate(data)
    except ValueError as exc:
        log.error("judge.schema_violation", payload=data, error=str(exc))
        raise JudgeError(f"Judge JSON did not match schema: {exc}") from exc


async def persist_interest(
    session: AsyncSession,
    job_id: UUID,
    candidate_id: UUID,
    result: JudgeResult,
) -> None:
    """Update the Score row's interest_* fields. Score row is created by matcher."""
    stmt = (
        update(Score)
        .where(Score.job_id == job_id, Score.candidate_id == candidate_id)
        .values(
            interest_score=result.interest_score,
            interest_signals=result.signals,
            interest_concerns=result.concerns,
            interest_reasoning=result.reasoning,
        )
    )
    await session.execute(stmt)
    await session.commit()
