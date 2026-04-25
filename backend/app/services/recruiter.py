from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.db.models import Candidate, Job
from app.services.aoai import get_aoai

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "recruiter.md").read_text(encoding="utf-8")


def _job_summary(job: Job) -> str:
    """Compact human-readable job summary for the recruiter prompt."""
    parsed = job.parsed_json or {}
    parts = [
        f"Title: {parsed.get('title') or job.title}",
        f"Seniority: {parsed.get('seniority') or job.seniority}",
        f"Min YOE: {parsed.get('min_yoe') if parsed.get('min_yoe') is not None else job.min_yoe}",
        f"Must-have: {', '.join(parsed.get('must_have_skills') or job.must_have_skills or [])}",
        f"Nice-to-have: {', '.join(parsed.get('nice_to_have') or job.nice_to_have or [])}",
        f"Domain: {parsed.get('domain') or job.domain or '-'}",
        f"Location: {parsed.get('location_pref') or job.location_pref or '-'} (remote_ok={parsed.get('remote_ok') if parsed.get('remote_ok') is not None else job.remote_ok})",
    ]
    return "\n".join(parts)


def _system_for(job: Job, candidate: Candidate) -> str:
    return (
        _PROMPT.replace("{{job_summary}}", _job_summary(job))
        .replace("{{name}}", candidate.name)
        .replace("{{title}}", candidate.title)
        .replace("{{yoe}}", str(candidate.yoe))
        .replace("{{skills}}", ", ".join(candidate.skills or []))
        .replace("{{location}}", candidate.location or "Unknown")
    )


async def opening_message(job: Job, candidate: Candidate) -> str:
    return await _generate(job, candidate, history=[])


async def respond(job: Job, candidate: Candidate, history: list[dict]) -> str:
    return await _generate(job, candidate, history=history)


async def _generate(job: Job, candidate: Candidate, history: list[dict]) -> str:
    s = get_settings()
    client = get_aoai()
    messages = [{"role": "system", "content": _system_for(job, candidate)}]
    if not history:
        # First turn — give an empty "user" nudge so the model produces an opener.
        messages.append({"role": "user", "content": "Send your opening outreach message now."})
    else:
        for m in history:
            role = "user" if m["role"] == "candidate" else "assistant"
            messages.append({"role": role, "content": m["content"]})
    resp = await client.chat.completions.create(
        model=s.aoai_gpt4o_mini_deployment,
        temperature=s.recruiter_temperature,
        seed=42,
        max_tokens=200,
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()
