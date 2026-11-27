"""Tests for agent-side redaction."""

from __future__ import annotations

from receptionist_agent.redaction import redact_pii


def test_redacts_contact_details() -> None:
    text = "Call me at (415) 555-0134 or jane@example.com."
    redacted = redact_pii(text)
    assert "555-0134" not in redacted
    assert "jane@example.com" not in redacted
    assert "[phone]" in redacted
    assert "[email]" in redacted


def test_redacts_ssn_and_card() -> None:
    text = "SSN 123-45-6789 card 4242 4242 4242 4242"
    redacted = redact_pii(text)
    assert "123-45-6789" not in redacted
    assert "4242" not in redacted
