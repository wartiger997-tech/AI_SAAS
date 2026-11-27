"""Background job queue (arq + Redis)."""

from __future__ import annotations

import uuid
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from redliner.config import get_settings
from redliner.observability import configure_logging, get_logger
from redliner.services.review import run_review

settings = get_settings()
logger = get_logger(__name__)


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def enqueue_review(review_id: uuid.UUID) -> str:
    pool = await create_pool(redis_settings())
    try:
        job = await pool.enqueue_job("review_document", str(review_id))
    finally:
        await pool.close()
    if not job:
        raise RuntimeError("failed to enqueue review job")
    return job.job_id


async def review_document(ctx: dict[str, Any], review_id: str) -> dict[str, Any]:
    logger.info("job.started", extra={"context": {"review_id": review_id}})
    await run_review(uuid.UUID(review_id))
    return {"review_id": review_id, "status": "completed"}


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker.shutdown")


class WorkerSettings:
    functions = [review_document]
    cron_jobs: list[Any] = []
    redis_settings = redis_settings()
    max_tries = 3
    retry_jobs = True
    job_timeout = 900
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = True
