from __future__ import annotations

from functools import lru_cache

import httpx
from openai import AsyncAzureOpenAI

from app.config import get_settings


@lru_cache(maxsize=1)
def get_aoai() -> AsyncAzureOpenAI:
    """Return a process-wide AsyncAzureOpenAI client.

    Lazy-cached so we don't pay handshake cost more than once per process. The
    underlying httpx client gets a 60s read timeout (LLM calls are slow) and a
    sane connection pool.
    """
    s = get_settings()
    if not s.aoai_endpoint or not s.aoai_api_key:
        raise RuntimeError("AOAI_ENDPOINT and AOAI_API_KEY must be set")

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    return AsyncAzureOpenAI(
        azure_endpoint=s.aoai_endpoint,
        api_key=s.aoai_api_key,
        api_version=s.aoai_api_version,
        http_client=http_client,
        max_retries=3,
    )
