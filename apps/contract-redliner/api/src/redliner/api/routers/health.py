"""Health and readiness probes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from redliner.config import get_settings
from redliner.db import engine
from redliner.observability import get_logger
from redliner.schemas import HealthResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)
settings = get_settings()


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/readyz", response_model=HealthResponse)
async def readyz(response: Response) -> HealthResponse:
    checks: dict[str, str] = {}
    started = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
    checks["latency_ms"] = str(int((time.perf_counter() - started) * 1000))
    healthy = all(v == "ok" for k, v in checks.items() if k in {"database", "redis"})
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="ok" if healthy else "degraded", version="0.1.0", checks=checks)
