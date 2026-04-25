# Recruiter Agent — AI-Powered Talent Scouting & Engagement

> Paste a Job Description → get a ranked shortlist of candidates with **Match Score** (skill/experience/domain/location fit, with per-dimension justifications) and **Interest Score** (assessed from a simulated conversational outreach).

Built on **Azure OpenAI** + **Azure Container Apps** + **Postgres Flexible (pgvector)** + **Next.js on Static Web Apps**. Demo-grade — autoscale-to-0, ~$25/mo idle.

## Live demo

- App: _pending deployment_
- Repo: https://github.com/DandaAkhilReddy/recruiter_agent

## How it works

```
Browser ── Static Web App (Next.js) ──HTTPS──▶ Container App (FastAPI)
                                                       │
                                                       ├─▶ Postgres Flex (pgvector)
                                                       ├─▶ Azure OpenAI (gpt-4o, gpt-4o-mini, embed-3-large)
                                                       ├─▶ Key Vault (secrets via managed identity)
                                                       └─▶ App Insights (OTel)
```

Pipeline:

1. **JD Parser** (gpt-4o, JSON mode) → structured `ParsedJD`
2. **3-stage Matcher** → hard filter → pgvector top-50 → LLM rerank with per-dimension scores
3. **Conversation Orchestrator** → Recruiter Agent ↔ Candidate Persona Agent, 3-5 turns each, streamed live via SSE
4. **Judge** (gpt-4o) → reads transcript, emits Interest Score + signals + concerns
5. **Ranker** → `final = 0.6·match + 0.4·interest` (weights tunable in UI)

## Quickstart (local)

```bash
# 1. Postgres + pgvector
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env                            # fill AOAI_* values
alembic upgrade head
python scripts/seed_candidates.py --count 500
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev   # http://localhost:3000
```

## Deploy to Azure

```bash
# one-time
azd auth login
azd init     # if you cloned without azd context
azd env new recruiter-demo
azd env set AOAI_ENDPOINT "https://your-aoai.openai.azure.com/"
azd env set AOAI_API_KEY  "..."
# ...then
azd up
```

## Project layout

```
backend/   FastAPI + SQLAlchemy 2.0 (async) + Alembic + Azure OpenAI
frontend/  Next.js 14 App Router + shadcn/ui + Tailwind, SSE for live stream
infra/     Bicep modules, azd-compatible
samples/   Sample JDs + sample shortlist JSON
docs/      Architecture diagrams (Mermaid)
.planning/ Spec docs
```

## Cost (demo profile)

- Azure Container Apps: scale-to-0, pennies per demo run
- Postgres Flex Burstable B1ms: ~$15-20/mo
- Static Web App Free, Key Vault, Log Analytics: <$10/mo combined
- Azure OpenAI: ~$1 per full JD run on gpt-4o + gpt-4o-mini

**Total monthly idle: ~$25-30**

## License

MIT
