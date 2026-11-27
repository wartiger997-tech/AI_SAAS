"""Tests for outcome normalization and fallback summaries."""

from __future__ import annotations

from voice_api.services.summaries import (
    OUTCOMES,
    fallback_summary,
    normalize_outcome,
    transcript_text,
)


def test_normalize_outcome_aliases() -> None:
    assert normalize_outcome("Booked") == "booked"
    assert normalize_outcome("callback-requested") == "callback_requested"
    assert normalize_outcome("not interested") == "not_interested"
    assert normalize_outcome("voicemail") == "voicemail"


def test_normalize_outcome_rejects_unknown() -> None:
    assert normalize_outcome("maybe") is None
    assert normalize_outcome(None) is None
    assert set(OUTCOMES) >= {"booked", "transferred", "abandoned"}


def test_transcript_text() -> None:
    turns = [
        {"role": "agent", "content": "Thanks for calling."},
        {"role": "user", "content": "I need a cleaning."},
    ]
    text = transcript_text(turns)
    assert "AGENT: Thanks for calling." in text
    assert "USER: I need a cleaning." in text


def test_fallback_summary_is_bounded() -> None:
    turns = [{"role": "user", "content": "I need an appointment. " * 100}]
    summary = fallback_summary(turns, "Bright Dental")
    assert summary.startswith("Bright Dental:")
    assert len(summary) <= 810
