"""Hybrid retrieval: Postgres full-text search + pgvector, fused with RRF.

Reciprocal Rank Fusion is computed in SQL so the whole query is one round trip.
If pgvector is unavailable (e.g. SQLite test DB), the function degrades to
keyword search instead of failing the request.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from redliner.config import get_settings
from redliner.observability import get_logger
from redliner.providers.embeddings import embed_query, embed_texts
from redliner.schemas import SearchHit

logger = get_logger(__name__)
settings = get_settings()

_RRF_SQL = """
WITH kw AS (
    SELECT id,
           row_number() OVER (
               ORDER BY ts_rank(
                   to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,'')),
                   plainto_tsquery('english', :query)
               ) DESC
           ) AS rnk
    FROM precedent_chunks
    WHERE tenant_id = CAST(:tenant_id AS uuid)
      AND (:source IS NULL OR source = :source)
      AND to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))
          @@ plainto_tsquery('english', :query)
    ORDER BY rnk
    LIMIT :k
),
vec AS (
    SELECT id,
           row_number() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rnk
    FROM precedent_chunks
    WHERE tenant_id = CAST(:tenant_id AS uuid)
      AND embedding IS NOT NULL
      AND (:source IS NULL OR source = :source)
    ORDER BY embedding <=> CAST(:embedding AS vector)
    LIMIT :k
)
SELECT p.id, p.title, p.source, p.content,
       (COALESCE(1.0 / (:rrf_k + kw.rnk), 0.0)
        + COALESCE(1.0 / (:rrf_k + vec.rnk), 0.0)) AS score
FROM precedent_chunks p
LEFT JOIN kw ON kw.id = p.id
LEFT JOIN vec ON vec.id = p.id
WHERE kw.id IS NOT NULL OR vec.id IS NOT NULL
ORDER BY score DESC
LIMIT :limit
"""

_KEYWORD_SQL = """
SELECT id, title, source, content,
       ts_rank(
           to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,'')),
           plainto_tsquery('english', :query)
       ) AS score
FROM precedent_chunks
WHERE tenant_id = CAST(:tenant_id AS uuid)
  AND (:source IS NULL OR source = :source)
  AND to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))
      @@ plainto_tsquery('english', :query)
ORDER BY score DESC
LIMIT :limit
"""


def _row_to_hit(row: Any) -> SearchHit:
    return SearchHit(
        id=row.id,
        title=row.title,
        source=row.source,
        score=float(row.score or 0.0),
        snippet=(row.content or "")[:400],
    )


async def hybrid_search(
    session: AsyncSession,
    tenant_id: str,
    query: str,
    limit: int = 10,
    source: str | None = None,
) -> tuple[list[SearchHit], int]:
    started = time.perf_counter()
    params: dict[str, Any] = {
        "query": query,
        "tenant_id": tenant_id,
        "source": source,
        "k": max(limit * 4, 20),
        "rrf_k": settings.rrf_k,
        "limit": limit,
    }
    try:
        embedding = await embed_query(query)
        params["embedding"] = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"
        result = await session.execute(text(_RRF_SQL), params)
        hits = [_row_to_hit(row) for row in result]
    except Exception as exc:  # noqa: BLE001 - vector index may not exist
        logger.warning("hybrid search fell back to keyword", extra={"context": {"error": str(exc)}})
        result = await session.execute(text(_KEYWORD_SQL), params)
        hits = [_row_to_hit(row) for row in result]
    took_ms = int((time.perf_counter() - started) * 1000)
    return hits, took_ms


async def index_precedent(
    session: AsyncSession,
    tenant_id: str,
    source: str,
    title: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> None:
    from redliner.models import PrecedentChunk

    vectors = await embed_texts([f"{title}\n{content}"])
    session.add(
        PrecedentChunk(
            tenant_id=tenant_id,  # type: ignore[arg-type]
            source=source,
            title=title,
            content=content,
            embedding=vectors[0] if vectors else None,
            meta=meta,
        )
    )
