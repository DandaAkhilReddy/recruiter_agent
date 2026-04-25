"""Offline tests for jd_parser — patches the AOAI call so no live API needed."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.services.jd_parser import JDParseError, parse_jd


def _fake_completion(content: str) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.asyncio
async def test_parse_jd_happy_path() -> None:
    payload = {
        "title": "Senior Backend Engineer",
        "seniority": "senior",
        "min_yoe": 6,
        "must_have_skills": ["python", "postgresql", "aws"],
        "nice_to_have": ["rust"],
        "domain": "Backend / Payments",
        "location_pref": "Remote (US)",
        "remote_ok": True,
    }

    class FakeClient:
        class chat:  # noqa: N801 — mimicking openai client shape
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake_completion(json.dumps(payload))

    with patch("app.services.jd_parser.get_aoai", return_value=FakeClient()):
        result = await parse_jd("A" * 200)
    assert result.title == "Senior Backend Engineer"
    assert result.seniority == "senior"
    assert "python" in result.must_have_skills


@pytest.mark.asyncio
async def test_parse_jd_invalid_json_raises() -> None:
    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake_completion("not json {")

    with patch("app.services.jd_parser.get_aoai", return_value=FakeClient()):
        with pytest.raises(JDParseError):
            await parse_jd("A" * 200)


@pytest.mark.asyncio
async def test_parse_jd_schema_violation_raises() -> None:
    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                async def create(**_: Any) -> Any:
                    return _fake_completion(json.dumps({"title": "X"}))  # missing required fields

    with patch("app.services.jd_parser.get_aoai", return_value=FakeClient()):
        with pytest.raises(JDParseError):
            await parse_jd("A" * 200)
