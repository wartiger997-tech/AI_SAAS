"""Availability endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import Appointment, Business
from voice_api.schemas import AvailabilityQuery, AvailabilityResponse, SlotOut
from voice_api.services.bookings import generate_slots

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=AvailabilityResponse)
async def availability(
    session: Session,
    user: UserDep,
    business_id: uuid.UUID,
    date: str = Query(description="YYYY-MM-DD"),
    days: int = Query(default=1, ge=1, le=14),
    slot_minutes: int = Query(default=30, ge=5, le=240),
    service: str | None = None,
) -> AvailabilityResponse:
    business = await session.get(Business, business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
    try:
        start_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc

    query = AvailabilityQuery(
        business_id=business_id,
        date=start_date,
        days=days,
        slot_minutes=slot_minutes,
        service=service,
    )
    end = datetime.combine(query.date + timedelta(days=query.days + 1), datetime.min.time())
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
        start_date=query.date,
        days=query.days,
        slot_minutes=query.slot_minutes,
        service=query.service,
    )
    return AvailabilityResponse(
        business_id=business.id,
        timezone=business.timezone,
        slots=[SlotOut(**slot.as_dict()) for slot in slots[:100]],
    )
