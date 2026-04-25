"""Offline tests for judge service — patches AOAI client, no live calls."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from app.services.judge import JudgeError, judge_transcript


def _fake(content: str) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _make_message(role: str, text: str, idx: int) -> SimpleNamespace:
    return SimpleNamespace(role=role, content=text, turn_index=idx)


@pytest.mark.asyncio
async def test_judge_happy_path_parses_full_payload() -> None:
    payload = {
        "interest_score": 82,
        "signals": ["asked about team size", "available next week"],
        "concerns": [],
        "reasoning": "Engaged early; soft commit on availability.",
    }

    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake(json.dumps(payload))

    msgs = [
        _make_message("recruiter", "Hi! Are you open to a chat?", 0),
        _make_message("candidate", "Sure, what's the role?", 1),
    ]
    with patch("app.services.judge.get_aoai", return_value=FakeClient()):
        result = await judge_transcript(msgs)
    assert result.interest_score == 82
    assert "asked about team size" in result.signals
    assert result.concerns == []


@pytest.mark.asyncio
async def test_judge_invalid_json_raises_judge_error() -> None:
    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake("not json {")

    with (
        patch("app.services.judge.get_aoai", return_value=FakeClient()),
        pytest.raises(JudgeError),
    ):
        await judge_transcript([_make_message("recruiter", "hi", 0)])


@pytest.mark.asyncio
async def test_judge_schema_violation_raises_judge_error() -> None:
    """Score above 100 must fail validation."""
    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake(json.dumps({"interest_score": 150}))

    with (
        patch("app.services.judge.get_aoai", return_value=FakeClient()),
        pytest.raises(JudgeError),
    ):
        await judge_transcript([_make_message("recruiter", "hi", 0)])


@pytest.mark.asyncio
async def test_judge_handles_missing_optional_fields() -> None:
    """Only interest_score is required; signals/concerns/reasoning default."""
    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake(json.dumps({"interest_score": 50}))

    with patch("app.services.judge.get_aoai", return_value=FakeClient()):
        result = await judge_transcript([_make_message("recruiter", "hi", 0)])
    assert result.interest_score == 50
    assert result.signals == []
    assert result.concerns == []
    assert result.reasoning == ""
