"""Offline test: recruiter system prompt is correctly built from a Job + Candidate."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.recruiter import _job_summary, _system_for


def _job() -> SimpleNamespace:
    parsed = {
        "title": "Senior Backend Engineer",
        "seniority": "senior",
        "min_yoe": 6,
        "must_have_skills": ["python", "fastapi", "postgresql"],
        "nice_to_have": ["rust"],
        "domain": "Backend / Payments",
        "location_pref": "Remote (US)",
        "remote_ok": True,
    }
    return SimpleNamespace(
        parsed_json=parsed,
        title=parsed["title"],
        seniority=parsed["seniority"],
        min_yoe=parsed["min_yoe"],
        must_have_skills=parsed["must_have_skills"],
        nice_to_have=parsed["nice_to_have"],
        domain=parsed["domain"],
        location_pref=parsed["location_pref"],
        remote_ok=True,
    )


def _candidate() -> SimpleNamespace:
    return SimpleNamespace(
        name="Asha Kumari",
        title="Backend Engineer",
        yoe=7,
        skills=["python", "fastapi", "postgresql", "kafka"],
        location="Bengaluru, India",
        remote_ok=True,
    )


def test_job_summary_includes_all_parsed_fields() -> None:
    s = _job_summary(_job())
    assert "Senior Backend Engineer" in s
    assert "senior" in s
    assert "Min YOE: 6" in s
    assert "python, fastapi, postgresql" in s
    assert "Backend / Payments" in s
    assert "Remote (US)" in s


def test_system_prompt_includes_candidate_identity_and_role_summary() -> None:
    s = _system_for(_job(), _candidate())
    assert "Asha Kumari" in s
    assert "Backend Engineer" in s
    assert "7" in s
    assert "python, fastapi, postgresql, kafka" in s
    # job summary content should also be in there
    assert "Senior Backend Engineer" in s
    assert "Backend / Payments" in s


def test_job_summary_falls_back_to_orm_fields_when_parsed_json_empty() -> None:
    """Defensive: if parsed_json is missing fields, fall back to ORM columns."""
    j = _job()
    j.parsed_json = {}  # simulate older row
    s = _job_summary(j)
    assert "Senior Backend Engineer" in s  # from orm.title
    assert "Min YOE: 6" in s               # from orm.min_yoe
    assert "python, fastapi, postgresql" in s  # from orm.must_have_skills
