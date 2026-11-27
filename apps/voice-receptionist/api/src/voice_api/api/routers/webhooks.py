"""Twilio webhooks: inbound routing, status callbacks, and recordings.

All webhook handlers verify ``X-Twilio-Signature`` and are idempotent on
``(provider, event_id)`` so carrier retries cannot duplicate side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from voice_api.api.deps import Session
from voice_api.config import get_settings
from voice_api.models import Call, PhoneNumber, TranscriptTurn, WebhookEvent
from voice_api.observability import get_logger
from voice_api.services.redaction import redact_pii
from voice_api.services.summaries import summarize_call
from voice_api.services.twilio import (
    say_twiml,
    sip_dial_twiml,
    validate_twilio_signature,
)

router = APIRouter(prefix="/webhooks/twilio", tags=["webhooks"])
settings = get_settings()
logger = get_logger(__name__)


async def _params(request: Request) -> dict[str, Any]:
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


def _verify(request: Request, params: dict[str, Any]) -> None:
    signature = request.headers.get("X-Twilio-Signature")
    if not validate_twilio_signature(str(request.url), params, signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")


async def _seen(session: Session, event_id: str) -> bool:
    result = await session.execute(
        select(WebhookEvent).where(
            WebhookEvent.provider == "twilio", WebhookEvent.event_id == event_id
        )
    )
    event = result.scalar_one_or_none()
    if event:
        return True
    session.add(WebhookEvent(provider="twilio", event_id=event_id, payload={}))
    return False


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


@router.post("/inbound")
async def inbound(request: Request, session: Session) -> Response:
    params = await _params(request)
    _verify(request, params)
    to_number = params.get("To", "")
    from_number = params.get("From", "")
    call_sid = params.get("CallSid", "")
    speech = params.get("SpeechResult", "").strip()

    result = await session.execute(select(PhoneNumber).where(PhoneNumber.e164 == to_number))
    number = result.scalar_one_or_none()
    if not number:
        return _xml(
            say_twiml("This number is not configured. Please check the number and try again.")
        )

    call_result = await session.execute(select(Call).where(Call.provider_call_sid == call_sid))
    call = call_result.scalar_one_or_none()
    if not call:
        call = Call(
            tenant_id=number.tenant_id,
            business_id=number.business_id,
            direction="inbound",
            provider_call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            contact_phone=from_number,
            status="in-progress",
            started_at=datetime.now(UTC),
        )
        session.add(call)
        await session.flush()

    if speech:
        count = await session.execute(
            select(func.count(TranscriptTurn.id)).where(TranscriptTurn.call_id == call.id)
        )
        seq = int(count.scalar() or 0) + 1
        session.add(
            TranscriptTurn(
                call_id=call.id,
                seq=seq,
                role="user",
                content=redact_pii(speech)[:4000],
                ts_ms=0,
                redacted=True,
            )
        )
        await session.commit()
        return _xml(say_twiml("Thanks. Connecting you with the receptionist now."))

    await session.commit()
    return _xml(sip_dial_twiml(settings.livekit_sip_uri, settings.twilio_from_number))


@router.post("/status")
async def status_callback(request: Request, session: Session) -> Response:
    params = await _params(request)
    _verify(request, params)
    event_id = params.get("CallStatus", "") + ":" + params.get("CallSid", "")
    if await _seen(session, event_id):
        return _xml("<Response/>")
    call_sid = params.get("CallSid", "")
    result = await session.execute(select(Call).where(Call.provider_call_sid == call_sid))
    call = result.scalar_one_or_none()
    if call:
        call.status = params.get("CallStatus", call.status)
        duration = params.get("CallDuration", "0")
        call.duration_s = int(duration) if duration.isdigit() else 0
        if call.status in {"completed", "failed", "busy", "no-answer", "canceled"}:
            call.ended_at = datetime.now(UTC)
            turn_result = await session.execute(
                select(TranscriptTurn)
                .where(TranscriptTurn.call_id == call.id)
                .order_by(TranscriptTurn.seq)
            )
            turns = [{"role": turn.role, "content": turn.content} for turn in turn_result.scalars()]
            summary = await summarize_call(turns, "the business")
            call.summary = summary["summary"]
            call.outcome = summary["outcome"]
    await session.commit()
    return _xml("<Response/>")


@router.post("/recording")
async def recording(request: Request, session: Session) -> Response:
    params = await _params(request)
    _verify(request, params)
    event_id = "recording:" + params.get("RecordingSid", params.get("CallSid", ""))
    if await _seen(session, event_id):
        return _xml("<Response/>")
    call_sid = params.get("CallSid", "")
    result = await session.execute(select(Call).where(Call.provider_call_sid == call_sid))
    call = result.scalar_one_or_none()
    if call:
        call.recording_url = params.get("RecordingUrl", "")
        await session.commit()
    return _xml("<Response/>")


@router.get("/health")
async def webhook_health() -> dict[str, Any]:
    return {"status": "ok", "signature_required": True}
