"""API contract tests using FastAPI TestClient + dependency overrides.

We override `get_db` to return a fake AsyncSession-like surface for the routes
we want to exercise *without* hitting a real database. For routes whose
behavior is database-heavy (matcher, ranker), this only tests the request /
response contract, not the SQL — that's what the integration test is for.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from app.db.models import Job
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient


class _FakeSession:
    """Minimal AsyncSession surrogate for contract tests."""

    def __init__(self, jobs: dict[UUID, Job] | None = None):
        self._jobs = jobs or {}
        self.added: list[Any] = []
        self.committed = False
        self.refreshed = False

    async def get(self, model: type, key: Any) -> Any:
        if model is Job:
            return self._jobs.get(key)
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        self.refreshed = True


def _override_db(session: _FakeSession):
    async def _gen():
        yield session
    return _gen


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_create_job_rejects_too_short_body(client: TestClient) -> None:
    r = client.post("/jobs", json={"raw_text": "tiny"})
    assert r.status_code == 422


def test_create_job_rejects_extra_fields(client: TestClient) -> None:
    r = client.post("/jobs", json={"raw_text": "A" * 100, "evil": "field"})
    assert r.status_code == 422


def test_create_job_happy_path_with_mocked_pipeline(client: TestClient) -> None:
    """Mock parse_jd + embed_one + DB so we exercise the route end-to-end."""
    from app.schemas.jd import ParsedJD

    fake_session = _FakeSession()
    parsed = ParsedJD(
        title="Senior Backend Engineer",
        seniority="senior",
        min_yoe=6,
        must_have_skills=["python"],
        nice_to_have=[],
        domain=None,
        location_pref=None,
        remote_ok=True,
    )

    job_id = uuid4()
    created_at = datetime.now(UTC)

    def _add(obj: Any) -> None:
        # Stamp id + created_at on the Job before commit/refresh
        obj.id = job_id
        obj.created_at = created_at
        fake_session.added.append(obj)

    fake_session.add = _add  # type: ignore[method-assign]

    app.dependency_overrides[get_db] = _override_db(fake_session)
    try:
        with (
            patch("app.routers.jobs.parse_jd", new=AsyncMock(return_value=parsed)),
            patch("app.routers.jobs.embed_one", new=AsyncMock(return_value=[0.0] * 1536)),
        ):
            r = client.post("/jobs", json={"raw_text": "A" * 200})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["title"] == "Senior Backend Engineer"
        assert body["seniority"] == "senior"
        assert body["min_yoe"] == 6
        assert body["must_have_skills"] == ["python"]
        assert fake_session.committed is True
    finally:
        app.dependency_overrides.clear()


def test_get_job_returns_404_when_missing(client: TestClient) -> None:
    fake_session = _FakeSession(jobs={})
    app.dependency_overrides[get_db] = _override_db(fake_session)
    try:
        r = client.get(f"/jobs/{uuid4()}")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_match_route_returns_404_for_missing_job(client: TestClient) -> None:
    fake_session = _FakeSession(jobs={})
    app.dependency_overrides[get_db] = _override_db(fake_session)
    try:
        r = client.post(f"/jobs/{uuid4()}/match", json={})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_outreach_route_returns_404_for_missing_job(client: TestClient) -> None:
    fake_session = _FakeSession(jobs={})
    app.dependency_overrides[get_db] = _override_db(fake_session)
    try:
        r = client.post(f"/jobs/{uuid4()}/outreach", json={})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_shortlist_rejects_weights_that_dont_sum_to_one(client: TestClient) -> None:
    job_id = uuid4()
    fake_job = Job(raw_text="x", title="t", seniority="mid", min_yoe=3,
                   must_have_skills=[], nice_to_have=[], parsed_json={})
    fake_job.id = job_id  # type: ignore[assignment]
    fake_session = _FakeSession(jobs={job_id: fake_job})
    app.dependency_overrides[get_db] = _override_db(fake_session)
    try:
        r = client.get(f"/jobs/{job_id}/shortlist?match_w=0.7&interest_w=0.4")
        assert r.status_code == 422
        assert "must sum to 1.0" in r.text
    finally:
        app.dependency_overrides.clear()
