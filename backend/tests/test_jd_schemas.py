"""Schema-only tests — no live LLM, no DB."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.jd import JobIn, ParsedJD


class TestJobIn:
    def test_accepts_valid_text(self) -> None:
        body = JobIn(raw_text="A" * 100)
        assert len(body.raw_text) == 100

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValidationError):
            JobIn(raw_text="too short")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValidationError):
            JobIn(raw_text="A" * 20_001)

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            JobIn.model_validate({"raw_text": "A" * 100, "evil": "field"})


class TestParsedJD:
    def test_full_valid_payload_roundtrips(self) -> None:
        payload = {
            "title": "Senior Backend Engineer",
            "seniority": "senior",
            "min_yoe": 6,
            "must_have_skills": ["python", "postgresql", "aws"],
            "nice_to_have": ["rust", "grpc"],
            "domain": "Backend / Payments",
            "location_pref": "Remote (US)",
            "remote_ok": True,
        }
        parsed = ParsedJD.model_validate(payload)
        assert parsed.seniority == "senior"
        assert parsed.must_have_skills == ["python", "postgresql", "aws"]

    def test_rejects_unknown_seniority(self) -> None:
        with pytest.raises(ValidationError):
            ParsedJD.model_validate({
                "title": "X", "seniority": "godlike", "min_yoe": 5,
            })

    def test_rejects_negative_yoe(self) -> None:
        with pytest.raises(ValidationError):
            ParsedJD.model_validate({
                "title": "X", "seniority": "junior", "min_yoe": -1,
            })

    def test_rejects_yoe_above_40(self) -> None:
        with pytest.raises(ValidationError):
            ParsedJD.model_validate({
                "title": "X", "seniority": "senior", "min_yoe": 50,
            })

    def test_skills_default_empty(self) -> None:
        parsed = ParsedJD.model_validate({"title": "X", "seniority": "mid", "min_yoe": 3})
        assert parsed.must_have_skills == []
        assert parsed.nice_to_have == []
        assert parsed.remote_ok is True
        assert parsed.domain is None

    def test_ignores_extra_fields_from_llm(self) -> None:
        # LLMs sometimes add bonus keys; we ignore them rather than 422.
        parsed = ParsedJD.model_validate({
            "title": "X", "seniority": "mid", "min_yoe": 3,
            "salary_band": "$180k-220k",  # not in schema
            "extra_notes": "ignored",
        })
        assert parsed.title == "X"
