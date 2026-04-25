from __future__ import annotations

import asyncio
from collections.abc import Sequence

from app.config import get_settings
from app.logging import get_logger
from app.services.aoai import get_aoai

log = get_logger(__name__)

_EMBED_BATCH = 100
_EMBED_CONCURRENCY = 5


async def _embed_one_batch(inputs: Sequence[str]) -> list[list[float]]:
    s = get_settings()
    client = get_aoai()
    resp = await client.embeddings.create(
        model=s.aoai_embedding_deployment,
        input=list(inputs),
        dimensions=s.aoai_embedding_dimensions,
    )
    return [d.embedding for d in resp.data]


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed `texts` in batches with bounded concurrency.

    Returns embeddings in the same order as inputs.
    """
    if not texts:
        return []

    sem = asyncio.Semaphore(_EMBED_CONCURRENCY)
    batches: list[list[str]] = [list(texts[i : i + _EMBED_BATCH]) for i in range(0, len(texts), _EMBED_BATCH)]

    async def run(batch: list[str]) -> list[list[float]]:
        async with sem:
            return await _embed_one_batch(batch)

    log.info("embedding.start", total=len(texts), batches=len(batches))
    results = await asyncio.gather(*(run(b) for b in batches))
    flat: list[list[float]] = [vec for sub in results for vec in sub]
    log.info("embedding.done", total=len(flat))
    return flat


async def embed_one(text: str) -> list[float]:
    out = await embed_texts([text])
    return out[0]
