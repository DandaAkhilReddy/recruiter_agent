from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.db.models import Candidate
from app.services.aoai import get_aoai

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "persona.md").read_text(encoding="utf-8")


def _system_for(c: Candidate) -> str:
    return (
        _PROMPT.replace("{{name}}", c.name)
        .replace("{{title}}", c.title)
        .replace("{{yoe}}", str(c.yoe))
        .replace("{{location}}", c.location or "Unknown")
        .replace("{{remote_ok}}", str(c.remote_ok).lower())
        .replace("{{skills}}", ", ".join(c.skills or []))
        .replace("{{summary}}", c.summary)
        .replace("{{motivations}}", c.motivations)
        .replace("{{archetype}}", c.interest_archetype)
    )


async def respond(candidate: Candidate, history: list[dict]) -> str:
    """Generate the candidate's next message given the conversation so far.

    `history` is a list of {role, content} where role ∈ {recruiter, candidate}.
    We translate to OpenAI chat shape: candidate-replies become "assistant",
    recruiter messages become "user".
    """
    s = get_settings()
    client = get_aoai()
    messages = [{"role": "system", "content": _system_for(candidate)}]
    for m in history:
        role = "assistant" if m["role"] == "candidate" else "user"
        messages.append({"role": role, "content": m["content"]})
    resp = await client.chat.completions.create(
        model=s.aoai_gpt4o_mini_deployment,
        temperature=s.persona_temperature,
        max_tokens=200,
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()
