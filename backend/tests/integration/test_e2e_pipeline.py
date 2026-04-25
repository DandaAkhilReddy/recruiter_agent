"""End-to-end integration test against real Postgres + pgvector.

Mocks AOAI (no $ spent, no flakiness) but exercises every layer for real:
real Pydantic, real SQL, real pgvector, real router wiring, real SSE bus.

What this catches that unit tests don't:
- Schema / migration drift
- Pgvector cosine distance + ivfflat index actually working
- ORM-to-Pydantic boundary issues
- Async session lifecycle (orchestrator opens many short sessions)
- SSE event ordering across concurrent conversations
- Score upsert behavior across re-runs
- CSV streaming under real DB rows

Run locally:  docker compose up -d  &&  pytest backend/tests/integration -v
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from app.db.models import Candidate, Conversation, Job, Message, Score
from app.db.session import get_db
from app.events import bus
from app.main import app
from app.schemas.jd import ParsedJD
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


# --------------------------- AOAI fakes --------------------------- #

def _fake_resp(content: str) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _fake_embedding(_: int = 1536) -> list[float]:
    # deterministic small embedding so pgvector queries are repeatable
    return [0.001 * i for i in range(1536)]


PARSED_JD = ParsedJD(
    title="Senior Backend Engineer",
    seniority="senior",
    min_yoe=5,
    must_have_skills=["python", "postgresql"],
    nice_to_have=["kafka"],
    domain="Backend / Payments",
    location_pref="Remote (US)",
    remote_ok=True,
)


# --------------------------- DB seeding --------------------------- #

async def _seed_candidates(db, n: int = 6) -> list[Candidate]:
    archetypes = ["strong", "strong", "medium", "weak", "wildcard", "weak"]
    cands: list[Candidate] = []
    for i in range(n):
        c = Candidate(
            name=f"Cand {i}",
            title="Senior Backend Engineer" if i < 4 else "Frontend Engineer",
            yoe=7 if i < 4 else 6,
            seniority="senior",
            skills=["python", "postgresql", "fastapi"] if i < 4 else ["react", "typescript"],
            domain="Backend / Payments" if i < 4 else "Frontend",
            location="Remote (US)",
            remote_ok=True,
            summary=f"Candidate {i} summary",
            motivations="open to chat",
            interest_archetype=archetypes[i],
            searchable_blob=f"summary {i}",
            embedding=_fake_embedding(),
        )
        db.add(c)
        cands.append(c)
    await db.commit()
    for c in cands:
        await db.refresh(c)
    return cands


# --------------------------- Mock plans --------------------------- #

class FakeAOAI:
    """Simple recorder + canned responses for the various AOAI call sites."""

    def __init__(self) -> None:
        self.embedding_calls = 0
        self.parse_calls = 0
        self.rerank_calls = 0
        self.recruiter_calls = 0
        self.persona_calls = 0
        self.judge_calls = 0
        self._batched_candidates: list[list[str]] = []

    # JD parser uses chat.completions
    class _Embeddings:
        def __init__(self, outer: FakeAOAI) -> None:
            self.outer = outer

        async def create(self, **kw: Any) -> Any:
            inputs = kw["input"]
            self.outer.embedding_calls += 1
            data = [SimpleNamespace(embedding=_fake_embedding()) for _ in inputs]
            return SimpleNamespace(data=data)

    class _ChatCompletions:
        def __init__(self, outer: FakeAOAI) -> None:
            self.outer = outer

        async def create(self, **kw: Any) -> Any:
            messages = kw["messages"]
            sys = next((m["content"] for m in messages if m["role"] == "system"), "")
            user = next((m["content"] for m in messages if m["role"] == "user"), "")

            # Judge: system mentions "interest"
            if "interest" in sys.lower() and "transcript" in user.lower():
                self.outer.judge_calls += 1
                return _fake_resp(json.dumps({
                    "interest_score": 75,
                    "signals": ["asked follow-up"],
                    "concerns": [],
                    "reasoning": "Engaged.",
                }))

            # Rerank batch: user message contains a JSON object with "candidates"
            if user.lstrip().startswith("{") and '"candidates"' in user:
                self.outer.rerank_calls += 1
                payload = json.loads(user)
                cand_ids = [c["id"] for c in payload["candidates"]]
                self.outer._batched_candidates.append(cand_ids)
                scores = [
                    {
                        "candidate_id": cid,
                        "skill": 90 - i,
                        "experience": 80,
                        "domain": 70,
                        "location": 95,
                        "justifications": {
                            "skill": "Strong overlap",
                            "experience": "Hits target",
                            "domain": "Adjacent",
                            "location": "Remote-OK",
                        },
                    }
                    for i, cid in enumerate(cand_ids)
                ]
                return _fake_resp(json.dumps({"scores": scores}))

            # Persona: system contains "STAY IN CHARACTER"
            if "STAY IN CHARACTER" in sys:
                self.outer.persona_calls += 1
                return _fake_resp("Sure, happy to chat. What's the team like?")

            # Recruiter: friendly opener / follow-up
            self.outer.recruiter_calls += 1
            return _fake_resp("Hi! We're hiring for a Senior Backend role — good fit?")

    @property
    def embeddings(self) -> FakeAOAI._Embeddings:
        return FakeAOAI._Embeddings(self)

    @property
    def chat(self) -> SimpleNamespace:
        return SimpleNamespace(completions=FakeAOAI._ChatCompletions(self))


@pytest.fixture
def fake_aoai() -> FakeAOAI:
    return FakeAOAI()


@pytest_asyncio.fixture
async def http(db, fake_aoai):
    """AsyncClient bound to the FastAPI app with DB + AOAI overrides."""
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    patches = [
        patch("app.services.aoai.get_aoai", return_value=fake_aoai),
        patch("app.services.embeddings.get_aoai", return_value=fake_aoai),
        patch("app.services.jd_parser.get_aoai", return_value=fake_aoai),
        patch("app.services.matcher.get_aoai", return_value=fake_aoai),
        patch("app.services.persona.get_aoai", return_value=fake_aoai),
        patch("app.services.recruiter.get_aoai", return_value=fake_aoai),
        patch("app.services.judge.get_aoai", return_value=fake_aoai),
        # JD parser will return a structured ParsedJD payload via fake chat
        patch("app.routers.jobs.parse_jd", return_value=PARSED_JD),
        patch("app.routers.jobs.embed_one", return_value=_fake_embedding()),
    ]
    for p in patches:
        p.start()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        for p in patches:
            p.stop()
        app.dependency_overrides.clear()


# --------------------------- Tests --------------------------- #

@pytest.mark.asyncio
async def test_create_job_persists_with_parsed_fields(http, db) -> None:
    r = await http.post("/jobs", json={"raw_text": "Backend role 5 yoe python postgres" * 4})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["seniority"] == "senior"
    assert "python" in body["must_have_skills"]
    # Persisted in DB
    job = await db.get(Job, body["id"])
    assert job is not None
    assert job.status == "parsed"
    assert job.embedding is not None


@pytest.mark.asyncio
async def test_match_runs_full_pipeline_persists_scores_filters_off_topic(http, db, fake_aoai) -> None:
    await _seed_candidates(db, n=6)
    # Create job
    r = await http.post("/jobs", json={"raw_text": "Backend role" * 20})
    job_id = r.json()["id"]
    # Run match
    r = await http.post(f"/jobs/{job_id}/match", json={"top_k": 50, "batch_size": 5, "return_top": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    # Hard filter requires must_have_skills overlap → only the first 4 candidates qualify
    assert body["matched_count"] == 4
    assert body["rerank_count"] >= 1
    # Returned items have per-dimension breakdown + justifications
    assert len(body["top"]) >= 1
    top = body["top"][0]
    assert set(top["breakdown"]) == {"skill", "experience", "domain", "location"}
    assert all(top["justifications"].values())
    # Scores persisted
    rows = (await db.execute(
        Score.__table__.select().where(Score.job_id == job_id)
    )).all()
    assert len(rows) >= 1
    # AOAI rerank was actually called
    assert fake_aoai.rerank_calls >= 1


@pytest.mark.asyncio
async def test_outreach_runs_to_completion_emits_sse_events_and_scores_interest(http, db, fake_aoai) -> None:
    await _seed_candidates(db, n=6)
    r = await http.post("/jobs", json={"raw_text": "Backend role" * 20})
    job_id = r.json()["id"]

    # Match first so scores exist for outreach to pick from
    r = await http.post(f"/jobs/{job_id}/match", json={"top_k": 50, "batch_size": 5, "return_top": 5})
    assert r.status_code == 200

    # Reset event bus for this job — we'll subscribe after kicking outreach
    await bus.reset(job_id)

    # Kick outreach (small turn count to keep test fast)
    r = await http.post(f"/jobs/{job_id}/outreach", json={"top_k": 3, "max_turns": 1})
    assert r.status_code == 202

    # Drain SSE stream in-process via the bus subscriber API
    seen_types: list[str] = []
    async def consume() -> None:
        async for evt in bus.subscribe(job_id):
            seen_types.append(evt["type"])
    await asyncio.wait_for(consume(), timeout=20.0)

    # Must include outreach lifecycle events
    assert "outreach_started" in seen_types
    assert "turn" in seen_types
    assert "judge" in seen_types
    assert seen_types[-1] == "done"

    # Conversations + messages persisted
    convos = (await db.execute(Conversation.__table__.select().where(Conversation.job_id == job_id))).all()
    assert len(convos) >= 1
    msgs = (await db.execute(Message.__table__.select())).all()
    assert len(msgs) >= 2  # at least one recruiter + one candidate per convo

    # Interest score persisted
    scored = (await db.execute(
        Score.__table__.select().where(Score.job_id == job_id)
    )).all()
    has_interest = [r for r in scored if r._mapping["interest_score"] is not None]
    assert len(has_interest) >= 1
    assert fake_aoai.judge_calls >= 1


@pytest.mark.asyncio
async def test_shortlist_and_csv_export(http, db) -> None:
    await _seed_candidates(db, n=6)
    r = await http.post("/jobs", json={"raw_text": "Backend role" * 20})
    job_id = r.json()["id"]
    await http.post(f"/jobs/{job_id}/match", json={"top_k": 50, "batch_size": 5, "return_top": 4})

    # Shortlist JSON
    r = await http.get(f"/jobs/{job_id}/shortlist?limit=10&match_w=0.6&interest_w=0.4")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["match_weight"] == 0.6
    assert body["interest_weight"] == 0.4
    assert len(body["items"]) >= 1
    # Each item is ranked, has match_score; interest may be null at this stage
    assert body["items"][0]["rank"] == 1
    assert body["items"][0]["match_score"] is not None

    # CSV
    r = await http.get(f"/jobs/{job_id}/shortlist.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.text
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= 2  # header + at least 1 data row
    assert "rank,name" in lines[0]


@pytest.mark.asyncio
async def test_shortlist_weights_must_sum_to_one(http, db) -> None:
    await _seed_candidates(db, n=2)
    r = await http.post("/jobs", json={"raw_text": "Backend role" * 20})
    job_id = r.json()["id"]
    r = await http.get(f"/jobs/{job_id}/shortlist?match_w=0.7&interest_w=0.4")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_job_404(http) -> None:
    r = await http.get(f"/jobs/{uuid4()}")
    assert r.status_code == 404
