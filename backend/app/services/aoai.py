from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


class _ParamStrippingChatCompletions:
    """Wraps chat.completions.create() and strips parameters that gpt-5.x
    reasoning models reject (temperature, seed, top_p when not at default).

    The error from AOAI is HTTP 400 'Unsupported value: temperature does not
    support X with this model. Only the default (1) value is supported.' We
    transparently retry once, dropping the offending parameter, until the call
    succeeds. This lets the rest of the codebase keep its determinism /
    variance hints for legacy models without forking call sites.
    """

    _STRIPPABLE = ("temperature", "seed", "top_p", "frequency_penalty", "presence_penalty")
    # Old API param -> new API param under gpt-5.x reasoning models.
    _RENAMES = {"max_tokens": "max_completion_tokens"}

    def __init__(self, inner) -> None:
        self._inner = inner

    async def create(self, **kwargs: Any) -> Any:
        # Try the call. On 400 errors for known-incompatible params, either rename
        # (e.g. max_tokens -> max_completion_tokens) or strip (temperature/seed),
        # and retry. Loop until we run out of known fixes or get a non-matching error.
        attempt_kwargs = dict(kwargs)
        for _ in range(len(self._STRIPPABLE) + len(self._RENAMES) + 1):
            try:
                return await self._inner.create(**attempt_kwargs)
            except Exception as exc:  # noqa: BLE001 — we re-raise non-matching
                msg = str(exc)
                if "unsupported" not in msg.lower():
                    raise
                handled = False
                # Rename first (preserves intent). For max_tokens specifically:
                # gpt-5.x reasoning models burn the budget on hidden reasoning,
                # so multiply 10x and add reasoning_effort=minimal to leave room
                # for actual visible output. Without this, persona/recruiter
                # turns return empty strings.
                for old, new in self._RENAMES.items():
                    if old in attempt_kwargs and (f"'{old}'" in msg or f'"{old}"' in msg):
                        log.warning("aoai.renamed_param", old=old, new=new, model=attempt_kwargs.get("model"))
                        old_value = attempt_kwargs.pop(old)
                        if old == "max_tokens":
                            attempt_kwargs[new] = max(int(old_value) * 10, 2000)
                            # openai sdk 1.57 doesn't accept reasoning_effort
                            # as a top-level kwarg — pass through extra_body.
                            extra = attempt_kwargs.setdefault("extra_body", {})
                            extra.setdefault("reasoning_effort", "minimal")
                        else:
                            attempt_kwargs[new] = old_value
                        handled = True
                        break
                if not handled:
                    for p in self._STRIPPABLE:
                        if p in attempt_kwargs and (f"'{p}'" in msg or f'"{p}"' in msg):
                            log.warning("aoai.stripped_param", param=p, model=attempt_kwargs.get("model"))
                            attempt_kwargs.pop(p, None)
                            handled = True
                            break
                if not handled:
                    raise
        return await self._inner.create(**attempt_kwargs)


class _ChatProxy:
    def __init__(self, inner) -> None:
        self.completions = _ParamStrippingChatCompletions(inner.completions)


class _AOAIProxy:
    """Proxies AsyncAzureOpenAI but wraps `chat.completions` to auto-strip
    unsupported params on retry. All other attributes pass through untouched.
    """

    def __init__(self, inner: AsyncAzureOpenAI) -> None:
        self._inner = inner
        self.chat = _ChatProxy(inner.chat)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@lru_cache(maxsize=1)
def get_aoai() -> _AOAIProxy:
    """Return a process-wide AsyncAzureOpenAI client wrapped to auto-strip
    unsupported params (gpt-5.x reasoning models reject custom temperature/seed).

    Lazy-cached so we don't pay handshake cost more than once per process.
    """
    s = get_settings()
    if not s.aoai_endpoint or not s.aoai_api_key:
        raise RuntimeError("AOAI_ENDPOINT and AOAI_API_KEY must be set")

    # 180s read timeout — gpt-5.x batch-generate calls can exceed 60s
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(180.0, connect=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    inner = AsyncAzureOpenAI(
        azure_endpoint=s.aoai_endpoint,
        api_key=s.aoai_api_key,
        api_version=s.aoai_api_version,
        http_client=http_client,
        max_retries=3,
    )
    return _AOAIProxy(inner)
