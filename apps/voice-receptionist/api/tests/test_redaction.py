"""Tests for PII redaction."""

from __future__ import annotations

from voice_api.services.redaction import contains_pii, mask_phone, redact_pii


def test_redacts_email_and_phone() -> None:
    text = "Reach Jane at jane.doe@example.com or +1 (415) 555-0134."
    redacted = redact_pii(text)
    assert "jane.doe@example.com" not in redacted
    assert "555-0134" not in redacted
    assert "[email]" in redacted
    assert "[phone]" in redacted


def test_redacts_ssn_and_card() -> None:
    text = "SSN 123-45-6789 and card 4242 4242 4242 4242."
    redacted = redact_pii(text)
    assert "123-45-6789" not in redacted
    assert "4242" not in redacted
    assert "[ssn]" in redacted
    assert "[card]" in redacted


def test_leaves_ordinary_text_alone() -> None:
    text = "The appointment is at 10am and the service takes 30 minutes."
    assert redact_pii(text) == text
    assert not contains_pii(text)


def test_mask_phone() -> None:
    assert mask_phone("+1 (415) 555-0134") == "***-***-0134"
    assert mask_phone("") == "***"
