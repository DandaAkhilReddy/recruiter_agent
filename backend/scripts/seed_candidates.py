"""Generate a synthetic candidate pool with forced interest-archetype variance.

Usage:
    python scripts/seed_candidates.py --count 500
    python scripts/seed_candidates.py --count 100 --dry-run

Strategy:
    1. Walk a fixed list of (domain, seniority, count) tuples that sums to `count`.
    2. For each (domain, seniority) bucket, ask gpt-4o-mini for `batch_size` candidates
       in JSON mode, in parallel with a Semaphore.
    3. Sample `interest_archetype` per candidate from {strong:.40, medium:.30, weak:.20, wildcard:.10}.
    4. Mutate `motivations` text to reinforce the archetype so the Persona Agent can role-play it later.
    5. Embed `searchable_blob = title + " | " + summary + " | " + ", ".join(skills)`.
    6. Bulk-insert into `candidates`.

Idempotency: this script does NOT truncate. Re-running adds more rows. Use
`scripts/reset_db.py` (or `alembic downgrade base && upgrade head`) to wipe.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.db.models import Candidate
from app.db.session import SessionLocal
from app.logging import configure_logging, get_logger
from app.services.aoai import get_aoai
from app.services.embeddings import embed_texts
from sqlalchemy import insert

log = get_logger("seed")

# (domain, seniority, weight) — weights are normalized so any --count works.
ARCHETYPES: list[tuple[str, str, int]] = [
    ("backend", "junior", 50), ("backend", "mid", 60), ("backend", "senior", 50),
    ("frontend", "mid", 40), ("frontend", "senior", 30),
    ("ml", "mid", 40), ("ml", "senior", 40), ("ml", "staff", 20),
    ("data", "mid", 40), ("data", "senior", 30),
    ("devops", "mid", 30), ("devops", "senior", 20),
    ("mobile", "mid", 30), ("mobile", "senior", 20),
]

INTEREST_BUCKETS: dict[str, float] = {
    "strong": 0.40,
    "medium": 0.30,
    "weak": 0.20,
    "wildcard": 0.10,
}

YOE_RANGES: dict[str, tuple[int, int]] = {
    "junior": (1, 3),
    "mid": (3, 6),
    "senior": (6, 10),
    "staff": (10, 15),
}

ARCHETYPE_TO_DOMAIN: dict[str, str] = {
    "backend": "Backend / Distributed Systems",
    "frontend": "Frontend / Web UI",
    "ml": "Machine Learning",
    "data": "Data Engineering",
    "devops": "DevOps / Platform / SRE",
    "mobile": "Mobile (iOS / Android)",
}

ARCHETYPE_MOTIVATION_TWISTS: dict[str, list[str]] = {
    "strong": [
        " I'm actively interviewing and would love to hear about exciting opportunities.",
        " I'm planning a move in the next 1-2 months and open to talk now.",
        " I've been waiting for the right role and could start interviewing this week.",
    ],
    "medium": [
        " I'm not actively looking but could be tempted by the right team and mission.",
        " Open to a quick chat if the role is genuinely a step up.",
        " Casually exploring; happy to learn more before committing.",
    ],
    "weak": [
        " I'm currently very happy and not really looking right now.",
        " My runway at my current company is at least 12 more months; not urgent.",
        " Honestly hard to pull me away unless comp is exceptional.",
    ],
    "wildcard": [
        " I might say yes immediately, or I might pass on principle. Hard to predict.",
        " Mood-driven on this one — let's see.",
        " If you can convince me in one message, I'm in. Otherwise probably not.",
    ],
}

PROMPT_PATH = Path(__file__).resolve().parent.parent / "app" / "prompts" / "seed_candidates.md"
_PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


def _scale_archetype_counts(total: int) -> list[tuple[str, str, int]]:
    raw_total = sum(w for _, _, w in ARCHETYPES)
    scaled = [
        (d, s, max(1, math.floor(w * total / raw_total))) for d, s, w in ARCHETYPES
    ]
    diff = total - sum(c for _, _, c in scaled)
    i = 0
    while diff != 0 and scaled:
        d, s, c = scaled[i % len(scaled)]
        if diff > 0:
            scaled[i % len(scaled)] = (d, s, c + 1)
            diff -= 1
        elif c > 1:
            scaled[i % len(scaled)] = (d, s, c - 1)
            diff += 1
        i += 1
    return scaled


def _archetype_for_index(i: int, total: int) -> str:
    """Return interest_archetype for index `i` of `total`, honoring INTEREST_BUCKETS."""
    cumulative = 0.0
    for arch, frac in INTEREST_BUCKETS.items():
        cumulative += frac
        if i < int(cumulative * total):
            return arch
    return "wildcard"


def _twist_motivations(text: str, archetype: str) -> str:
    twist = random.choice(ARCHETYPE_MOTIVATION_TWISTS[archetype])
    return text.rstrip(".") + "." + twist


async def _generate_batch(domain: str, seniority: str, batch_size: int) -> list[dict]:
    s = get_settings()
    client = get_aoai()
    yoe_low, yoe_high = YOE_RANGES[seniority]
    prompt = (
        _PROMPT_TEMPLATE.replace("{{batch_size}}", str(batch_size))
        .replace("{{domain}}", domain)
        .replace("{{seniority}}", seniority)
        .replace("{{yoe_low}}", str(yoe_low))
        .replace("{{yoe_high}}", str(yoe_high))
    )
    resp = await client.chat.completions.create(
        model=s.aoai_gpt4o_mini_deployment,
        temperature=0.8,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    candidates = data.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("LLM did not return a 'candidates' list")
    return candidates[:batch_size]


async def _generate_all(buckets: Sequence[tuple[str, str, int]], gen_batch_size: int) -> list[dict]:
    sem = asyncio.Semaphore(5)

    async def gen(domain: str, seniority: str, n: int) -> list[dict]:
        out: list[dict] = []
        remaining = n
        while remaining > 0:
            take = min(gen_batch_size, remaining)
            async with sem:
                try:
                    batch = await _generate_batch(domain, seniority, take)
                except (ValueError, KeyError, json.JSONDecodeError) as exc:
                    log.warning("generate.batch_failed", domain=domain, seniority=seniority, error=str(exc))
                    batch = []
            for c in batch:
                c["_meta_domain"] = domain
                c["_meta_seniority"] = seniority
            out.extend(batch)
            remaining -= len(batch) if batch else take  # avoid infinite loop on persistent failure
        return out

    tasks = [gen(d, s, n) for d, s, n in buckets]
    chunks = await asyncio.gather(*tasks)
    return [c for chunk in chunks for c in chunk]


def _to_searchable_blob(c: dict) -> str:
    skills = ", ".join(c.get("skills", []))
    return f"{c.get('title', '')} | {c.get('summary', '')} | {skills}"


async def main(count: int, gen_batch_size: int, dry_run: bool, seed: int) -> None:
    random.seed(seed)
    s = get_settings()
    configure_logging(env=s.env, level=s.log_level)
    log.info("seed.start", count=count, batch=gen_batch_size, dry_run=dry_run)

    buckets = _scale_archetype_counts(count)
    log.info("seed.buckets", buckets=[(d, sn, c) for d, sn, c in buckets])

    raw = await _generate_all(buckets, gen_batch_size)
    log.info("seed.generated", got=len(raw), wanted=count)
    if not raw:
        log.error("seed.no_candidates")
        return

    # Trim or pad — generation can drift slightly.
    raw = raw[:count]

    # Shuffle so archetype assignment is uncorrelated with generation order.
    random.shuffle(raw)
    total = len(raw)
    rows: list[dict] = []
    for i, c in enumerate(raw):
        archetype = _archetype_for_index(i, total)
        motivations = _twist_motivations(c.get("motivations", "Open to interesting opportunities."), archetype)
        domain_label = ARCHETYPE_TO_DOMAIN.get(c.get("_meta_domain", ""), c.get("_meta_domain", ""))
        skills = c.get("skills") or []
        if not isinstance(skills, list):
            skills = [str(skills)]
        rows.append({
            "id": uuid4(),
            "name": str(c.get("name", "Anonymous"))[:200],
            "title": str(c.get("title", ""))[:200],
            "yoe": int(c.get("yoe", 3)),
            "seniority": c.get("_meta_seniority", "mid"),
            "skills": [str(x) for x in skills][:20],
            "domain": domain_label,
            "location": str(c.get("location", "Remote (US)"))[:120],
            "remote_ok": bool(c.get("remote_ok", True)),
            "summary": str(c.get("summary", "")),
            "motivations": motivations,
            "interest_archetype": archetype,
            "searchable_blob": _to_searchable_blob(c),
        })

    blobs = [r["searchable_blob"] for r in rows]
    embeddings = await embed_texts(blobs)
    for r, vec in zip(rows, embeddings, strict=True):
        r["embedding"] = vec

    if dry_run:
        log.info("seed.dry_run", sample=rows[0] | {"embedding": f"<{len(rows[0]['embedding'])} floats>"})
        return

    async with SessionLocal() as session:
        await session.execute(insert(Candidate), rows)
        await session.commit()
    log.info("seed.inserted", n=len(rows))


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=500)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=20)
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    asyncio.run(main(count=args.count, gen_batch_size=args.batch_size, dry_run=args.dry_run, seed=args.seed))


if __name__ == "__main__":
    _cli()
