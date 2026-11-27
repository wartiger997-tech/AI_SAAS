"""Internal endpoints used by the agent worker.

These routes authenticate with ``X-Internal-Token`` instead of a user JWT. They
are deliberately narrow: the agent can read its business context, check
availability, book, read knowledge, and close a call. It cannot list tenants or
modify configuration.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from voice_api.api.deps import Internal, Session
from voice_api.models import AgentConfig, Appointment, Business, Call, KnowledgeDoc, TranscriptTurn
from voice_api.schemas import (
    AgentOut,
    AvailabilityResponse,
    BookingCreate,
    BookingCreated,
    BusinessOut,
    KnowledgeOut,
    SlotOut,
)
from voice_api.services.bookings import (
    SlotUnavailable,
    book_appointment,
    generate_slots,
    issue_booking_link,
    normalize_phone,
)
from voice_api.services.redaction import redact_pii
from voice_api.services.summaries import normalize_outcome
from voice_api.services.twilio import send_sms

router = APIRouter(prefix="/internal", tags=["internal"])


class TurnCreate(BaseModel):
    role: str = Field(pattern="^(user|agent)$")
    content: str = Field(min_length=1, max_length=4000)


class FinishRequest(BaseModel):
    outcome: str | None = None
    summary: str = Field(default="", max_length=4000)


async def _business(session: Session, business_id: uuid.UUID) -> Business:
    business = await session.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="business not found")
    return business


@router.get("/context")
async def context(session: Session, _: Internal, business_id: uuid.UUID) -> dict[str, object]:
    business = await _business(session, business_id)
    result = await session.execute(
        select(AgentConfig)
        .where(AgentConfig.business_id == business.id, AgentConfig.is_active.is_(True))
        .order_by(AgentConfig.created_at.desc())
    )
    agent = result.scalars().first()
    return {
        "business": BusinessOut.model_validate(business).model_dump(mode="json"),
        "agent": AgentOut.model_validate(agent).model_dump(mode="json") if agent else {},
    }


@router.get("/availability", response_model=AvailabilityResponse)
async def availability(
    session: Session,
    _: Internal,
    business_id: uuid.UUID,
    date: str,
    days: int = 3,
    service: str | None = None,
) -> AvailabilityResponse:
    business = await _business(session, business_id)
    try:
        start_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc
    end = datetime.combine(start_date + timedelta(days=days + 1), datetime.min.time())
    result = await session.execute(
        select(Appointment).where(
            Appointment.business_id == business.id,
            Appointment.status != "cancelled",
            Appointment.starts_at < end,
        )
    )
    slots = generate_slots(
        timezone=business.timezone,
        hours=business.hours or {},
        services=business.services or [],
        appointments=result.scalars().all(),
        start_date=start_date,
        days=days,
        service=service,
    )
    return AvailabilityResponse(
        business_id=business.id,
        timezone=business.timezone,
        slots=[SlotOut(**slot.as_dict()) for slot in slots[:100]],
    )


@router.post("/bookings", response_model=BookingCreated, status_code=status.HTTP_201_CREATED)
async def book(
    session: Session,
    _: Internal,
    payload: BookingCreate,
) -> BookingCreated:
    business = await _business(session, payload.business_id)
    phone = normalize_phone(payload.contact_phone)
    if not phone:
        raise HTTPException(status_code=422, detail="invalid contact phone")
    try:
        appointment = await book_appointment(
            session,
            business,
            starts_at=payload.starts_at,
            service=payload.service,
            contact_name=payload.contact_name,
            contact_phone=phone,
            call_id=payload.call_id,
            notes=payload.notes,
        )
    except SlotUnavailable:
        raise HTTPException(status_code=409, detail="that time is no longer available") from None
    _, url = await issue_booking_link(session, appointment)
    with contextlib.suppress(Exception):
        await send_sms(phone, f"Your booking is confirmed. Manage it here: {url}")
    await session.commit()
    await session.refresh(appointment)
    out = BookingCreated.model_validate(appointment)
    out.booking_url = url
    return out


@router.get("/knowledge", response_model=list[KnowledgeOut])
async def knowledge(session: Session, _: Internal, business_id: uuid.UUID) -> list[KnowledgeOut]:
    result = await session.execute(
        select(KnowledgeDoc)
        .where(KnowledgeDoc.business_id == business_id)
        .order_by(KnowledgeDoc.created_at.desc())
    )
    return [KnowledgeOut.model_validate(doc) for doc in result.scalars()]


@router.post("/calls/{call_id}/turns", status_code=status.HTTP_201_CREATED)
async def add_turn(
    session: Session, _: Internal, call_id: uuid.UUID, payload: TurnCreate
) -> dict[str, object]:
    call = await session.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="call not found")
    result = await session.execute(select(TranscriptTurn).where(TranscriptTurn.call_id == call_id))
    seq = len(result.scalars().all()) + 1
    turn = TranscriptTurn(
        call_id=call_id,
        seq=seq,
        role=payload.role,
        content=redact_pii(payload.content),
        redacted=True,
    )
    session.add(turn)
    await session.commit()
    return {"seq": seq, "redacted": True}


@router.post("/calls/{call_id}/finish")
async def finish(
    session: Session, _: Internal, call_id: uuid.UUID, payload: FinishRequest
) -> dict[str, object]:
    call = await session.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="call not found")
    call.summary = redact_pii(payload.summary)[:4000]
    call.outcome = normalize_outcome(payload.outcome)
    call.status = "completed"
    call.ended_at = datetime.now(UTC)
    await session.commit()
    return {"id": str(call.id), "outcome": call.outcome, "status": call.status}
