"""Availability generation and race-safe appointment booking.

Availability is computed from business hours minus existing appointments. The
write path takes a Postgres transaction-scoped advisory lock keyed by business,
re-checks for conflicts, and relies on a partial unique index as the final
backstop. A losing writer gets ``SlotUnavailable`` and the agent offers the next
slots instead of double-booking.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from voice_api.config import get_settings
from voice_api.models import Appointment, BookingLink

settings = get_settings()

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class SlotUnavailable(RuntimeError):
    """Raised when the requested start is no longer free."""


class BusinessLike(Protocol):
    id: Any
    timezone: str
    hours: dict[str, Any]
    services: list[dict[str, Any]]


@dataclass(frozen=True)
class Slot:
    starts_at: datetime
    ends_at: datetime
    service: str

    def as_dict(self) -> dict[str, str]:
        return {
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "service": self.service,
        }


def default_hours() -> dict[str, list[list[str]]]:
    weekday = [["09:00", "17:00"]]
    return {day: [list(window) for window in weekday] for day in WEEKDAYS}


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    return f"+{digits}" if digits else ""


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _localize(value: datetime, zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def _windows(hours: dict[str, Any], day_index: int) -> list[tuple[time, time]]:
    raw = hours.get(WEEKDAYS[day_index]) or []
    windows: list[tuple[time, time]] = []
    for window in raw:
        if not window or len(window) < 2:
            continue
        try:
            start, end = parse_hhmm(str(window[0])), parse_hhmm(str(window[1]))
        except (ValueError, TypeError):
            continue
        if end > start:
            windows.append((start, end))
    return windows


def _service_duration(services: list[dict[str, Any]], name: str | None, fallback: int) -> int:
    if name:
        for service in services:
            if str(service.get("name", "")).lower() == name.lower():
                return int(service.get("duration_minutes", fallback))
    return fallback


def _overlaps(start: datetime, end: datetime, appointments: Iterable[Any]) -> bool:
    for appointment in appointments:
        if getattr(appointment, "status", "confirmed") == "cancelled":
            continue
        starts_at = appointment.starts_at
        ends_at = appointment.ends_at
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=UTC)
        if start < ends_at and end > starts_at:
            return True
    return False


def generate_slots(
    *,
    timezone: str,
    hours: dict[str, Any],
    services: list[dict[str, Any]],
    appointments: Iterable[Any],
    start_date: date,
    days: int = 1,
    slot_minutes: int | None = None,
    service: str | None = None,
    now: datetime | None = None,
    lead_minutes: int | None = None,
) -> list[Slot]:
    """Return bookable slots in the business timezone, ascending."""
    zone = _zone(timezone)
    now = now or datetime.now(UTC)
    lead = settings.booking_lead_minutes if lead_minutes is None else lead_minutes
    earliest = now.astimezone(zone) + timedelta(minutes=lead)
    step = slot_minutes or settings.default_slot_minutes
    duration = _service_duration(services, service, settings.default_service_minutes)
    appointments = list(appointments)
    slots: list[Slot] = []
    for offset in range(max(days, 1)):
        day = start_date + timedelta(days=offset)
        for start_time, end_time in _windows(hours, day.weekday()):
            cursor = datetime.combine(day, start_time, tzinfo=zone)
            last = datetime.combine(day, end_time, tzinfo=zone)
            while cursor + timedelta(minutes=duration) <= last:
                end = cursor + timedelta(minutes=duration)
                if cursor >= earliest and not _overlaps(cursor, end, appointments):
                    slots.append(
                        Slot(starts_at=cursor, ends_at=end, service=service or "appointment")
                    )
                cursor += timedelta(minutes=step)
    return slots


async def book_appointment(
    session: AsyncSession,
    business: BusinessLike,
    *,
    starts_at: datetime,
    service: str,
    contact_name: str,
    contact_phone: str,
    call_id: Any | None = None,
    notes: str = "",
    duration_minutes: int | None = None,
) -> Appointment:
    """Atomically create an appointment, or raise ``SlotUnavailable``."""
    zone = _zone(business.timezone)
    start = _localize(starts_at, zone)
    duration = duration_minutes or _service_duration(
        business.services, service, settings.default_service_minutes
    )
    end = start + timedelta(minutes=duration)

    # Serialize writers for this business; the unique index is the final guard.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"relay-booking:{business.id}"},
    )
    result = await session.execute(
        select(Appointment).where(
            Appointment.business_id == business.id,
            Appointment.status != "cancelled",
            Appointment.starts_at < end,
            Appointment.ends_at > start,
        )
    )
    if result.scalars().first() is not None:
        raise SlotUnavailable("that time was just taken")

    appointment = Appointment(
        business_id=business.id,
        call_id=call_id,
        starts_at=start,
        ends_at=end,
        service=service,
        contact_name=contact_name,
        contact_phone=contact_phone,
        notes=notes,
        status="confirmed",
    )
    session.add(appointment)
    await session.flush()
    return appointment


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_booking_link(
    session: AsyncSession,
    appointment: Appointment,
    *,
    ttl_minutes: int | None = None,
) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    link = BookingLink(
        appointment_id=appointment.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC)
        + timedelta(minutes=ttl_minutes or settings.booking_link_ttl_minutes),
    )
    session.add(link)
    await session.flush()
    return token, f"{settings.booking_link_base_url.rstrip('/')}/b/{token}"


async def redeem_booking_link(session: AsyncSession, token: str) -> Appointment | None:
    result = await session.execute(
        select(BookingLink).where(BookingLink.token_hash == hash_token(token))
    )
    link = result.scalar_one_or_none()
    if not link or link.expires_at <= datetime.now(UTC):
        return None
    if link.redeemed_at is None:
        link.redeemed_at = datetime.now(UTC)
    return await session.get(Appointment, link.appointment_id)
