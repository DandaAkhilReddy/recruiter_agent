# Requirements

## Problem

Recruiters spend hours sifting profiles and chasing candidate interest. We need an agent that takes a Job Description, discovers and matches candidates, conversationally engages them to assess interest, and outputs a ranked shortlist scored on **Match** and **Interest**.

## Functional

- F1. Accept a JD via paste (text, ≤20k chars). PDF/DOCX upload deferred.
- F2. Parse JD into structured fields (title, seniority, min YOE, must-have skills, nice-to-have, domain, location, remote_ok).
- F3. Generate / store a synthetic candidate pool (500-2000) with explicit interest archetypes (`strong`, `medium`, `weak`, `wildcard`).
- F4. Match candidates with 3-stage hybrid pipeline: hard filter → embedding rerank → LLM rerank with **per-dimension scores** (skill, experience, domain, location) and one-line justifications.
- F5. Run simulated multi-turn conversation (3-5 turns) between Recruiter Agent and Candidate Persona Agent for the top-N candidates.
- F6. Stream conversations live to the UI (SSE).
- F7. Judge the transcript for **Interest Score** (0-100) with `signals[]`, `concerns[]`, and a one-paragraph reasoning.
- F8. Compute `final = w_match·Match + w_interest·Interest` (defaults 0.6 / 0.4) — sliders re-weight client-side without re-calling LLM.
- F9. Export ranked shortlist as CSV.

## Non-functional

- NF1. Total per-JD cost ≤ ~$2 in Azure OpenAI tokens.
- NF2. End-to-end pipeline ≤ 90s for top-20 outreach (with parallelism cap of 5).
- NF3. Autoscale-to-0; idle infra ≤ ~$30/mo.
- NF4. All secrets in Key Vault; no plaintext keys in code, env files, or logs.
- NF5. Pydantic v2 strict, async everywhere, structured logging with redaction.

## Out of scope (v1)

- Real ATS integration (Greenhouse / Lever / Workday)
- Authentication / multi-tenancy
- Real outbound email/SMS to candidates
- MCP server wrapper (deferred to follow-up)
- Mobile-responsive UI

## Acceptance

- Live URL responds; pipeline completes for both sample JDs in `/samples`
- Top match for `jd_senior_backend.txt` is from Backend archetype with relevant skills
- Conversations show visible variance across `interest_archetype`
- Demo video (3-5 min) walks the full flow
- README has architecture diagram + quickstart + `azd up` instructions
