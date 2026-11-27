"""Hybrid precedent search."""

from __future__ import annotations

from fastapi import APIRouter

from redliner.api.deps import Session
from redliner.schemas import SearchRequest, SearchResponse
from redliner.security import CurrentUser
from redliner.services.search import hybrid_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(session: Session, user: CurrentUser, payload: SearchRequest) -> SearchResponse:
    hits, took_ms = await hybrid_search(
        session,
        tenant_id=str(user.tenant_id),
        query=payload.query,
        limit=payload.limit,
        source=payload.source,
    )
    return SearchResponse(query=payload.query, hits=hits, took_ms=took_ms)
