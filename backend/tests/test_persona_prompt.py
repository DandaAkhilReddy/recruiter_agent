"""Offline test: persona system prompt is correctly populated from a Candidate."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.persona import _system_for


def _make_candidate(archetype: str) -> SimpleNamespace:
    return SimpleNamespace(
        name="Asha Kumari",
        title="Senior Backend Engineer",
        yoe=7,
        location="Bengaluru, India",
        remote_ok=True,
        skills=["python", "fastapi", "postgresql", "kafka", "aws"],
        summary="Built payments at a B2B SaaS unicorn.",
        motivations="Wants strong async culture and equity upside.",
        interest_archetype=archetype,
    )


def test_persona_prompt_includes_archetype_and_identity() -> None:
    p = _system_for(_make_candidate("strong"))
    assert "Asha Kumari" in p
    assert "Senior Backend Engineer" in p
    assert "python, fastapi, postgresql, kafka, aws" in p
    assert "interest archetype: strong" in p
    assert "STAY IN CHARACTER" in p


def test_persona_prompt_distinct_per_archetype() -> None:
    s = _system_for(_make_candidate("strong"))
    w = _system_for(_make_candidate("weak"))
    # The archetype string ends up in the rendered prompt, so they differ.
    assert s != w
    assert "strong" in s and "strong" not in w.split("interest archetype: ", 1)[1].split("\n", 1)[0]
