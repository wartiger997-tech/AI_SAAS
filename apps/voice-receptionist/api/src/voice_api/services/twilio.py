"""Twilio request signing, TwiML helpers, and outbound call creation."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape

import httpx

from voice_api.config import get_settings
from voice_api.observability import get_logger

settings = get_settings()
logger = get_logger(__name__)


def validate_twilio_signature(
    url: str,
    params: dict[str, Any],
    signature: str | None,
    auth_token: str | None = None,
) -> bool:
    """Validate ``X-Twilio-Signature`` per Twilio's documented algorithm."""
    token = auth_token or settings.twilio_auth_token
    if not token or not signature:
        return False
    data = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def _response(body: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def gather_twiml(prompt: str, action: str, timeout: int = 6) -> str:
    return _response(
        "<Response>"
        f'<Gather input="speech" action="{escape(action)}" method="POST" '
        f'speechTimeout="auto" language="en-US" timeout="{timeout}">'
        f"<Say>{escape(prompt)}</Say>"
        "</Gather>"
        "<Say>Sorry, I didn't catch that. Please call back.</Say>"
        "<Hangup/>"
        "</Response>"
    )


def say_twiml(message: str) -> str:
    return _response(f"<Response><Say>{escape(message)}</Say><Hangup/></Response>")


def sip_dial_twiml(sip_uri: str, caller_id: str | None = None) -> str:
    caller = f' callerId="{escape(caller_id)}"' if caller_id else ""
    return _response(
        "<Response>"
        f"<Say>Connecting you to the receptionist.</Say>"
        f'<Dial answerOnBridge="true"{caller}><Sip>{escape(sip_uri)}</Sip></Dial>'
        "</Response>"
    )


async def create_outbound_call(
    to_number: str,
    from_number: str | None,
    webhook_url: str,
    max_ring_seconds: int = 30,
) -> dict[str, Any]:
    """Place an outbound call through Twilio. Raises on configuration errors."""
    if not settings.twilio_configured:
        raise RuntimeError("Twilio is not configured")
    from_number = from_number or settings.twilio_from_number
    if not from_number:
        raise RuntimeError("no Twilio from-number configured")
    payload = {
        "To": to_number,
        "From": from_number,
        "Url": webhook_url,
        "Method": "POST",
        "Timeout": str(max_ring_seconds),
        "StatusCallback": webhook_url.replace("/inbound", "/status"),
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.twilio_api_base}/Accounts/{settings.twilio_account_sid}/Calls.json",
            data=payload,
            auth=(settings.twilio_account_sid or "", settings.twilio_auth_token or ""),
        )
        response.raise_for_status()
        return dict(response.json())


async def send_sms(to_number: str, body: str, from_number: str | None = None) -> dict[str, Any]:
    """Send an SMS. Returns a simulated receipt when Twilio is not configured."""
    if not settings.twilio_configured:
        logger.info("sms.simulated", extra={"context": {"to": to_number}})
        return {"sid": "", "status": "simulated", "to": to_number, "body": body}
    payload = {
        "To": to_number,
        "From": from_number or settings.twilio_from_number or "",
        "Body": body[:1600],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.twilio_api_base}/Accounts/{settings.twilio_account_sid}/Messages.json",
            data=payload,
            auth=(settings.twilio_account_sid or "", settings.twilio_auth_token or ""),
        )
        response.raise_for_status()
        return dict(response.json())


def booking_link(token: str) -> str:
    return f"{settings.booking_link_base_url.rstrip('/')}/b/{quote(token)}"
