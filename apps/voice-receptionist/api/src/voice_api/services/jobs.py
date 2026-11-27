"""Background jobs (arq + Redis): outbound calls, SMS, retention."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select

from voice_api.config import get_settings
from voice_api.db import SessionFactory
from voice_api.models import Appointment, Call
from voice_api.observability import configure_logging, get_logger
from voice_api.services.bookings import issue_booking_link
from voice_api.services.twilio import create_outbound_call, send_sms

settings = get_settings()
logger = get_logger(__name__)


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def enqueue_outbound(call_id: uuid.UUID) -> str:
    pool = await create_pool(redis_settings())
    try:
        job = await pool.enqueue_job("outbound_call", str(call_id))
    finally:
        await pool.close()
    if not job:
        raise RuntimeError("failed to enqueue outbound call")
    return job.job_id


async def outbound_call(ctx: dict[str, Any], call_id: str) -> dict[str, Any]:
    async with SessionFactory() as session:
        call = await session.get(Call, uuid.UUID(call_id))
        if not call:
            return {"call_id": call_id, "status": "missing"}
        try:
            webhook = f"{settings.booking_link_base_url.rstrip('/')}/v1/webhooks/twilio/inbound"
            result = await create_outbound_call(call.to_number, call.from_number or None, webhook)
            call.provider_call_sid = str(result.get("sid", ""))
            call.status = str(result.get("status", "queued"))
            call.started_at = datetime.now(UTC)
            await session.commit()
            return {"call_id": call_id, "provider_sid": call.provider_call_sid}
        except Exception as exc:  # noqa: BLE001
            call.status = "failed"
            call.meta = {**(call.meta or {}), "error": str(exc)[:500]}
            await session.commit()
            logger.exception("outbound call failed", extra={"context": {"call_id": call_id}})
            return {"call_id": call_id, "status": "failed", "error": str(exc)}


async def send_booking_link_job(ctx: dict[str, Any], appointment_id: str) -> dict[str, Any]:
    async with SessionFactory() as session:
        appointment = await session.get(Appointment, uuid.UUID(appointment_id))
        if not appointment:
            return {"appointment_id": appointment_id, "status": "missing"}
        token, url = await issue_booking_link(session, appointment)
        try:
            receipt = await send_sms(appointment.contact_phone, f"Your booking link: {url}")
            await session.commit()
            return {"appointment_id": appointment_id, "sid": receipt.get("sid", "")}
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            return {"appointment_id": appointment_id, "status": "failed", "error": str(exc)}


async def retention_sweep(ctx: dict[str, Any]) -> dict[str, Any]:
    """Delete call records older than the configured retention window."""
    cutoff = datetime.now(UTC) - timedelta(days=settings.transcript_retention_days)
    deleted = 0
    async with SessionFactory() as session:
        result = await session.execute(select(Call).where(Call.created_at < cutoff))
        for call in result.scalars().all():
            await session.delete(call)
            deleted += 1
        await session.commit()
    logger.info(
        "retention sweep", extra={"context": {"deleted": deleted, "cutoff": cutoff.isoformat()}}
    )
    return {"deleted": deleted}


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()


class WorkerSettings:
    functions = [outbound_call, send_booking_link_job, retention_sweep]
    redis_settings = redis_settings()
    max_tries = 3
    job_timeout = 300
    on_startup = startup
