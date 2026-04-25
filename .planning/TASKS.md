# Tasks (atomic — one commit each)

Sourced from `C:\Users\akhil\.claude\plans\short-answer-yes-most-unified-wolf.md`. Each task ends in a green commit.

## Phase 0 — Scaffold ✅ (this commit)

- [x] T0.1 Repo + folder tree + .gitignore + LICENSE
- [x] T0.2 Backend FastAPI hello-world + `/health` + structlog
- [x] T0.3 Frontend Next.js skeleton (landing + job stub + shortlist stub)
- [x] T0.4 Bicep modules + `azure.yaml` + `main.parameters.json`
- [x] T0.5 docker-compose for local pgvector
- [x] T0.6 CI workflow (ruff + pytest + next build) and deploy workflow (azd)
- [x] T0.7 .planning docs

## Phase 1 — Data + synthetic pool

- [ ] T1.1 Alembic init + `0001_initial.py` (jobs, candidates, conversations, messages, scores; pgvector + pgcrypto extensions; ivfflat + GIN indexes)
- [ ] T1.2 `app/services/aoai.py` — `AsyncAzureOpenAI` factory, retries, timeout
- [ ] T1.3 `app/services/embeddings.py` — batch embed with Semaphore
- [ ] T1.4 `scripts/seed_candidates.py --count 500` — archetype × seniority generator with forced variance
- [ ] T1.5 Smoke test: variance distribution; nearest-neighbor query

## Phase 2 — JD parser

- [ ] T2.1 `app/prompts/jd_parser.md` + `app/services/jd_parser.py`
- [ ] T2.2 `app/schemas/jd.py` (Pydantic v2 strict `JobIn`, `ParsedJD`, `JobOut`)
- [ ] T2.3 `app/routers/jobs.py` — POST /jobs, GET /jobs/{id}
- [ ] T2.4 Smoke test against `samples/jd_senior_backend.txt`

## Phase 3 — Matching pipeline

- [ ] T3.1 `app/services/matcher.py` — hard filter SQL, pgvector top-50, LLM rerank
- [ ] T3.2 `app/routers/matching.py` — POST /jobs/{id}/match
- [ ] T3.3 Smoke test: top result is right archetype; per-dim justifications non-empty

## Phase 4 — Conversation orchestrator + SSE

- [ ] T4.1 `app/events/bus.py` — per-job asyncio.Queue
- [ ] T4.2 `app/prompts/{persona,recruiter}.md`
- [ ] T4.3 `app/services/{persona,recruiter,orchestrator}.py`
- [ ] T4.4 `app/routers/{outreach,stream}.py` — SSE via `sse-starlette`
- [ ] T4.5 Smoke test: orchestrator persists messages and emits events

## Phase 5 — Judge + ranking + CSV

- [ ] T5.1 `app/prompts/judge.md` + `app/services/judge.py`
- [ ] T5.2 `app/services/ranker.py` — final composite + CSV streamer
- [ ] T5.3 `app/routers/jobs.py` — GET /jobs/{id}/shortlist + .csv
- [ ] T5.4 Smoke test: archetype → interest score buckets

## Phase 6 — Frontend

- [ ] T6.1 `lib/api.ts` + `types/api.ts`
- [ ] T6.2 `app/page.tsx` — JdInputForm
- [ ] T6.3 `app/jobs/[id]/page.tsx` — PipelineTimeline + ConversationStream + SSE hook
- [ ] T6.4 `app/jobs/[id]/shortlist/page.tsx` — ShortlistTable + CandidateCard + WeightSliders + CSV export

## Phase 7 — Deploy + deliverables

- [ ] T7.1 `azd up` end-to-end on a fresh sub
- [ ] T7.2 Architecture diagram (Mermaid in `docs/architecture.mmd`, embedded in README)
- [ ] T7.3 `samples/` populated (2 JDs + candidate snippet + shortlist JSON)
- [ ] T7.4 Demo video recorded (3-5 min, script in plan §Deliverables)
- [ ] T7.5 README live URL + final polish
