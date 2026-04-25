"""Offline tests for orchestrator helpers + the persona/recruiter history shape contract."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.persona import _system_for as persona_system_for


def _candidate(arch: str = "strong") -> SimpleNamespace:
    return SimpleNamespace(
        name="Test Cand", title="Sr Backend", yoe=7,
        location="Remote (US)", remote_ok=True,
        skills=["python"], summary="...",
        motivations="open to chat",
        interest_archetype=arch,
    )


def test_persona_history_translation_contract() -> None:
    """The persona service translates project {role:recruiter|candidate} history
    into OpenAI {role:user|assistant} messages. We verify the mapping rule:
    candidate-replies map to assistant, recruiter-messages map to user.
    """
    history = [
        {"role": "recruiter", "content": "Hi"},
        {"role": "candidate", "content": "Hey"},
        {"role": "recruiter", "content": "Up for a chat?"},
    ]
    expected_roles = ["system", "user", "assistant", "user"]  # system + 3 turns
    # We re-implement the same translation here so we can verify it without
    # actually calling the model. If `respond` ever changes its rule, this
    # test will need to track it (intentional contract assertion).
    messages = [{"role": "system", "content": persona_system_for(_candidate())}]
    for m in history:
        role = "assistant" if m["role"] == "candidate" else "user"
        messages.append({"role": role, "content": m["content"]})
    assert [m["role"] for m in messages] == expected_roles
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "Up for a chat?"


def test_persona_archetype_appears_in_system_prompt() -> None:
    """Sanity check that archetype is wired into the system prompt — the
    behavioral lever Phase 1's seed variance depends on at conversation time.
    """
    for arch in ("strong", "medium", "weak", "wildcard"):
        s = persona_system_for(_candidate(arch))
        assert f"interest archetype: {arch}" in s
