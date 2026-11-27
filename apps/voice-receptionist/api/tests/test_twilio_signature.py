"""Tests for Twilio request signature validation."""

from __future__ import annotations

import base64
import hashlib
import hmac

from voice_api.services.twilio import (
    say_twiml,
    sip_dial_twiml,
    validate_twilio_signature,
)

URL = "https://example.com/v1/webhooks/twilio/inbound"
TOKEN = "test-auth-token"
PARAMS = {"CallSid": "CA123", "From": "+15551234567", "To": "+15557654321"}


def _sign(url: str, params: dict[str, str], token: str) -> str:
    data = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def test_valid_signature() -> None:
    signature = _sign(URL, PARAMS, TOKEN)
    assert validate_twilio_signature(URL, PARAMS, signature, TOKEN)


def test_invalid_signature() -> None:
    assert not validate_twilio_signature(URL, PARAMS, "bad-signature", TOKEN)


def test_missing_token_rejects() -> None:
    assert not validate_twilio_signature(URL, PARAMS, _sign(URL, PARAMS, TOKEN), None)


def test_twiml_is_escaped() -> None:
    body = say_twiml("Hold <now> & call back")
    assert "&lt;now&gt;" in body
    assert "&amp;" in body


def test_sip_dial() -> None:
    body = sip_dial_twiml("sip:relay@sip.livekit.cloud;transport=tcp")
    assert "<Dial" in body
    assert "<Sip>" in body
