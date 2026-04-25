# Design

See `C:\Users\akhil\.claude\plans\short-answer-yes-most-unified-wolf.md` for the full design (data model, API surface, prompt strategy, infra). This file holds only project-local design notes and decisions.

## Key decisions (locked)

| Topic | Decision | Rationale |
|---|---|---|
| LLM provider | Azure OpenAI (gpt-4o + gpt-4o-mini + text-embedding-3-large) | Native to Azure, easy Key Vault wiring, single tenant for the demo |
| Embedding dims | 1536 (via `dimensions` param on text-embedding-3-large) | pgvector ivfflat works without HNSW gymnastics |
| Hosting | ACA (backend) + Postgres Flex Burstable B1ms + SWA Free | Autoscale-to-0, ≤$30/mo idle |
| Region | East US 2 | Best AOAI model availability |
| IaC | Bicep modules under `infra/`, azd-driven | `azd up` is the single deploy command |
| Secrets | Key Vault, accessed via user-assigned managed identity from ACA | `secretRef:` in container env, never in code |
| DB URL composition | App composes from `POSTGRES_*` env in prod (so password stays a secretRef) | Bicep can't interpolate secretRefs into other env values |
| Frontend hosting | SWA Free with `output: "export"` on Next.js | Static export → cheap hosting, no Node runtime needed |
| Conversation orchestration | `asyncio.Semaphore(5)` cap on parallel candidate conversations | Stay under AOAI TPM, predictable cost |
| Variance source | Forced archetype distribution at seed time (40/30/20/10) | Demo must not look scripted |

## Open questions

- Postgres `azure.extensions = VECTOR,PGCRYPTO` requires a server restart; verify it propagates on first deploy (may need re-run of `alembic upgrade head` after restart).
- AOAI `gpt-4o-mini` 30k TPM is enough for top-20 × 4 turns × 2 roles? Estimated peak ~10k TPM during the outreach phase — fine.
- Add `slowapi` rate limit before public live URL goes in README.

## Data flow (text)

```
client POST /jobs
  → JD parser (gpt-4o, JSON)
  → persist Job + JD embedding
client POST /jobs/{id}/match
  → SQL hard filter
  → pgvector top-50
  → LLM rerank (gpt-4o, batch 10) → per-dim scores + justifications
  → persist Score rows
client POST /jobs/{id}/outreach     → 202
  background:
    for top-20 (Semaphore(5)):
      Recruiter (gpt-4o-mini) ↔ Persona (gpt-4o-mini) × 4 turns
      persist Messages
      publish SSE turn events to /jobs/{id}/stream
      Judge (gpt-4o, JSON) → interest score
      persist into Score row
    publish SSE done event
client GET /jobs/{id}/shortlist?match_w=0.6&interest_w=0.4
  → SQL JOIN, compute final on the fly
```
