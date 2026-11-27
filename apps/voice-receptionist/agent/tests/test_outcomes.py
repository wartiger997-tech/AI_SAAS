"""Tests for outcome normalization."""

from __future__ import annotations

from receptionist_agent.outcomes import OUTCOMES, normalize_outcome


def test_aliases() -> None:
    assert normalize_outcome("Booked") == "booked"
    assert normalize_outcome("callback_requested") == "callback_requested"
    assert normalize_outcome("not interested") == "not_interested"


def test_unknown_is_rejected() -> None:
    assert normalize_outcome("maybe") is None
    assert normalize_outcome("") is None
    assert "transferred" in OUTCOMES
