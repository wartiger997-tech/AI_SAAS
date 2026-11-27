"""Embedding provider with deterministic offline fallback.

Production uses OpenAI embeddings. Without a key, we derive a stable hashed
embedding so hybrid search and unit tests still work; results are lower quality
but the interface and storage format are identical.
"""

from __future__ import annotations

import hashlib
import math
import re

from redliner.config import get_settings
from redliner.observability import get_logger

logger = get_logger(__name__)
settings = get_settings()
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _hash_embedding(text: str, dim: int) -> list[float]:
    vector = [0.0] * dim
    tokens = _TOKEN.findall(text.lower())
    if not tokens:
        tokens = ["empty"]
    for token in tokens:
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not settings.embeddings_configured:
        return [_hash_embedding(t, settings.embedding_dim) for t in texts]
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=2)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), settings.embedding_batch_size):
        batch = texts[start : start + settings.embedding_batch_size]
        response = await client.embeddings.create(model=settings.embedding_model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
