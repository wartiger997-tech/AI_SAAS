"""Prompt construction and consent/outcome guardrails."""

from __future__ import annotations

from typing import Any

OUTCOMES = (
    "booked",
    "transferred",
    "message_taken",
    "callback_requested",
    "not_interested",
    "wrong_number",
    "voicemail",
    "abandoned",
)

CONSENT_PREAMBLE = (
    "Before we continue: this call may be recorded for quality and training. Is that okay?"
)

NO_HUMAN_CLAIM = (
    "You are an AI receptionist. If asked whether you are human or a bot, say clearly "
    "that you are an automated assistant and offer to transfer to a human."
)

TOOL_RULES = """\
Tool rules:
- Only offer appointment times returned by check_availability.
- Only book a time you have already offered in this call.
- Read back the date and time and ask for explicit confirmation before booking.
- If booking fails because the slot was taken, apologize and offer the next alternatives.
- Never invent prices, insurance rules, or medical advice. Use lookup_knowledge.
- Keep turns short (1-2 sentences). Ask one question at a time.
- If the caller asks for a human, use transfer_call with a one-line reason.
"""


def build_instructions(business: dict[str, Any], agent: dict[str, Any] | None = None) -> str:
    name = business.get("name", "the business")
    hours = business.get("hours") or {}
    services = business.get("services") or []
    service_lines = [
        f"- {item.get('name', 'service')}: {item.get('duration_minutes', 30)} minutes"
        for item in services
    ]
    hours_lines = [
        f"- {day}: {', '.join('-'.join(w) for w in windows)}" for day, windows in hours.items()
    ]
    persona = (agent or {}).get("prompt") or (
        "You are warm, concise, and professional. You help callers book appointments and "
        "answer common questions."
    )
    return "\n".join(
        [
            f"You are the AI receptionist for {name}.",
            persona,
            "",
            "Business hours (local time):",
            *(hours_lines or ["- Hours unavailable; ask the caller to confirm a weekday."]),
            "",
            "Services:",
            *(service_lines or ["- General appointment"]),
            "",
            CONSENT_PREAMBLE,
            NO_HUMAN_CLAIM,
            "",
            "Call outcomes (use exactly one when wrapping up): " + ", ".join(OUTCOMES) + ".",
            "",
            TOOL_RULES,
        ]
    )


def build_voicemail_instructions(business: dict[str, Any]) -> str:
    return (
        f"You reached {business.get('name', 'the business')} after hours. "
        "Leave a brief message with your name, number, and the reason for calling. "
        "We will call you back during business hours."
    )
