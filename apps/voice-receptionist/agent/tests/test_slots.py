"""Tests for offered-slot tracking."""

from __future__ import annotations

from receptionist_agent.slots import OfferedSlots

SLOTS = [
    {"starts_at": "2026-01-05T14:00:00+00:00", "ends_at": "2026-01-05T14:30:00+00:00"},
    {"starts_at": "2026-01-05T14:30:00+00:00", "ends_at": "2026-01-05T15:00:00+00:00"},
]


def test_offer_and_take() -> None:
    offered = OfferedSlots()
    assert offered.offer(SLOTS) == [slot["starts_at"] for slot in SLOTS]
    assert offered.is_offered("2026-01-05T14:00:00Z")
    assert offered.take("2026-01-05T14:00:00Z")
    assert not offered.is_offered("2026-01-05T14:00:00Z")
    assert offered.remaining() == ["2026-01-05T14:30:00+00:00"]


def test_cannot_take_unoffered_slot() -> None:
    offered = OfferedSlots()
    assert not offered.take("2026-01-05T16:00:00Z")
    assert offered.remaining() == []


def test_offer_skips_malformed_slots() -> None:
    offered = OfferedSlots()
    assert offered.offer([{"starts_at": ""}, {"ends_at": "x"}]) == []
