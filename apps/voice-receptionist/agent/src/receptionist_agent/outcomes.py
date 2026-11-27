"""Outcome normalization shared with the control plane."""

from __future__ import annotations

import re

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

_ALIASES = {
    "booked": "booked",
    "appointment": "booked",
    "scheduled": "booked",
    "transferred": "transferred",
    "transfer": "transferred",
    "message": "message_taken",
    "message_taken": "message_taken",
    "callback": "callback_requested",
    "callback_requested": "callback_requested",
    "not interested": "not_interested",
    "wrong number": "wrong_number",
    "voicemail": "voicemail",
    "abandoned": "abandoned",
    "no answer": "abandoned",
}


def normalize_outcome(value: str | None) -> str | None:
    if not value:
        return None
    key = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", value.strip().lower()))
    if key in _ALIASES:
        return _ALIASES[key]
    compact = key.replace(" ", "_")
    return compact if compact in OUTCOMES else None
