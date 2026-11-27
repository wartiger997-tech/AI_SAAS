"""Booking creation with alternatives on conflict."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import Appointment, Business
from voice_api.schemas import BookingCreate, BookingCreated
from voice_api.services.bookings import (
    SlotUnavailable,
    book_appointment,
    generate_slots,
    issue_booking_link,
    normalize_phone,
)
from voice_api.services.twilio import send_sms

router = APIRouter(prefix="/bookings", tags=["bookings"])


async def _alternatives(
    session: Session, business: Business, after: datetime
) -> list[dict[str, str]]:
    result = await session.execute(
        select(Appointment).where(
            Appointment.business_id == business.id,
            Appointment.status != "cancelled",
            Appointment.starts_at < after + timedelta(days=7),
        )
    )
    slots = generate_slots(
        timezone=business.timezone,
        hours=business.hours or {},
        services=business.services or [],
        appointments=result.scalars().all(),
        start_date=after.date(),
        days=3,
        now=after,
    )
    return [slot.as_dict() for slot in slots[:3]]


@router.post("", response_model=BookingCreated, status_code=status.HTTP_201_CREATED)
async def create_booking(session: Session, user: UserDep, payload: BookingCreate) -> BookingCreated:
    business = await session.get(Business, payload.business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
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
        alternatives = await _alternatives(session, business, payload.starts_at)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "that time is no longer available", "alternatives": alternatives},
        ) from None

    token, url = await issue_booking_link(session, appointment)
    message = (
        f"Hi {payload.contact_name}, your appointment at {business.name} is confirmed for "
        f"{appointment.starts_at.isoformat()}. Manage or cancel: {url}"
    )
    with suppress(Exception):
        await send_sms(phone, message, business.phone or None)
    await session.commit()
    await session.refresh(appointment)

    out = BookingCreated.model_validate(appointment)
    out.booking_url = url
    return out
