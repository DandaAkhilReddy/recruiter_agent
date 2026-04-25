from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.logging import get_logger
from app.schemas.jd import ParsedJD
from app.services.aoai import get_aoai

log = get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "jd_parser.md"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


class JDParseError(ValueError):
    """Raised when the parser cannot produce a valid ParsedJD."""


async def parse_jd(raw_text: str) -> ParsedJD:
    s = get_settings()
    client = get_aoai()
    prompt = _PROMPT_TEMPLATE.replace("{{jd_text}}", raw_text)

    resp = await client.chat.completions.create(
        model=s.aoai_gpt4o_deployment,
        temperature=0.0,
        seed=42,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("jd_parser.invalid_json", raw=raw[:500])
        raise JDParseError("LLM returned invalid JSON") from exc

    try:
        parsed = ParsedJD.model_validate(payload)
    except ValueError as exc:
        log.error("jd_parser.schema_violation", payload=payload, error=str(exc))
        raise JDParseError(f"LLM JSON did not match ParsedJD schema: {exc}") from exc

    log.info(
        "jd_parser.ok",
        title=parsed.title,
        seniority=parsed.seniority,
        min_yoe=parsed.min_yoe,
        must=len(parsed.must_have_skills),
    )
    return parsed
