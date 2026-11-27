"""Tests for availability generation and phone normalization."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from voice_api.services.bookings import (
    default_hours,
    generate_slots,
    normalize_phone,
    parse_hhmm,
)

MONDAY = date(2026, 1, 5)
NOW = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)  # 03:00 in New York
SERVICES = [{"name": "Consultation", "duration_minutes": 30}]


def test_generate_slots_respects_business_hours() -> None:
    slots = generate_slots(
        timezone="America/New_York",
        hours=default_hours(),
        services=SERVICES,
        appointments=[],
        start_date=MONDAY,
        days=1,
        slot_minutes=30,
        now=NOW,
        lead_minutes=0,
    )
    assert len(slots) == 16
    assert slots[0].starts_at == datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
    assert slots[0].ends_at == datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def test_generate_slots_skips_booked_windows() -> None:
    appointment = SimpleNamespace(
        starts_at=datetime(2026, 1, 5, 15, 0, tzinfo=UTC),
        ends_at=datetime(2026, 1, 5, 15, 30, tzinfo=UTC),
        status="confirmed",
    )
    slots = generate_slots(
        timezone="America/New_York",
        hours=default_hours(),
        services=SERVICES,
        appointments=[appointment],
        start_date=MONDAY,
        days=1,
        slot_minutes=30,
        now=NOW,
        lead_minutes=0,
    )
    assert len(slots) == 15
    assert all(slot.starts_at != appointment.starts_at for slot in slots)


def test_generate_slots_uses_service_duration() -> None:
    slots = generate_slots(
        timezone="America/New_York",
        hours=default_hours(),
        services=[{"name": "Cleaning", "duration_minutes": 45}],
        appointments=[],
        start_date=MONDAY,
        days=1,
        slot_minutes=30,
        service="Cleaning",
        now=NOW,
        lead_minutes=0,
    )
    assert len(slots) == 15
    assert slots[-1].ends_at.hour == 16
    assert slots[-1].ends_at.minute == 45


def test_cancelled_appointments_do_not_block() -> None:
    appointment = SimpleNamespace(
        starts_at=datetime(2026, 1, 5, 15, 0, tzinfo=UTC),
        ends_at=datetime(2026, 1, 5, 15, 30, tzinfo=UTC),
        status="cancelled",
    )
    slots = generate_slots(
        timezone="America/New_York",
        hours=default_hours(),
        services=SERVICES,
        appointments=[appointment],
        start_date=MONDAY,
        days=1,
        slot_minutes=30,
        now=NOW,
        lead_minutes=0,
    )
    assert len(slots) == 16


def test_normalize_phone() -> None:
    assert normalize_phone("(415) 555-0134") == "+14155550134"
    assert normalize_phone("+44 20 7946 0958") == "+442079460958"
    assert normalize_phone("") == ""


def test_parse_hhmm() -> None:
    assert parse_hhmm("09:30").hour == 9
    assert parse_hhmm("09:30").minute == 30
