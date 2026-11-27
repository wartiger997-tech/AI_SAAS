"""Tests for prompt construction."""

from __future__ import annotations

from receptionist_agent.prompts import (
    CONSENT_PREAMBLE,
    OUTCOMES,
    build_instructions,
    build_voicemail_instructions,
)

BUSINESS = {
    "name": "Bright Dental",
    "hours": {"mon": [["09:00", "17:00"]], "tue": [["09:00", "17:00"]]},
    "services": [
        {"name": "Cleaning", "duration_minutes": 45},
        {"name": "Consultation", "duration_minutes": 30},
    ],
}


def test_instructions_include_business_context() -> None:
    prompt = build_instructions(BUSINESS)
    assert "Bright Dental" in prompt
    assert "Cleaning" in prompt
    assert "09:00-17:00" in prompt


def test_instructions_include_guardrails() -> None:
    prompt = build_instructions(BUSINESS)
    assert CONSENT_PREAMBLE in prompt
    assert "AI receptionist" in prompt
    assert "Only book a time you have already offered" in prompt
    for outcome in OUTCOMES:
        assert outcome in prompt


def test_agent_persona_overrides_default() -> None:
    prompt = build_instructions(BUSINESS, {"prompt": "You are a pirate receptionist."})
    assert "You are a pirate receptionist." in prompt


def test_voicemail_instructions() -> None:
    prompt = build_voicemail_instructions(BUSINESS)
    assert "Bright Dental" in prompt
    assert "name, number" in prompt
