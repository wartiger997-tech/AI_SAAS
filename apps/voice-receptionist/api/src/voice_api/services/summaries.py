"""Call summarization and outcome normalization.

The LLM is optional: without credentials we produce a deterministic extractive
summary from the transcript. Outcomes are constrained to a fixed vocabulary so
downstream analytics and CRM sync stay clean.
"""

from __future__ import annotations

import re
from typing import Any

from voice_api.config import get_settings
from voice_api.observability import get_logger

settings = get_settings()
logger = get_logger(__name__)

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

_OUTCOME_ALIASES = {
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
    "not_interested": "not_interested",
    "wrong number": "wrong_number",
    "wrong_number": "wrong_number",
    "voicemail": "voicemail",
    "abandoned": "abandoned",
    "no answer": "abandoned",
}


def normalize_outcome(value: str | None) -> str | None:
    if not value:
        return None
    key = re.sub(r"[_-]+", " ", value.strip().lower())
    key = re.sub(r"\s+", " ", key)
    if key in _OUTCOME_ALIASES:
        return _OUTCOME_ALIASES[key]
    compact = key.replace(" ", "_")
    return compact if compact in OUTCOMES else None


def transcript_text(turns: list[dict[str, Any]]) -> str:
    lines = []
    for turn in turns:
        role = str(turn.get("role", "agent")).upper()
        content = str(turn.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def fallback_summary(turns: list[dict[str, Any]], business_name: str) -> str:
    text = transcript_text(turns)
    if not text:
        return "No transcript captured."
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return f"{business_name}: " + " ".join(sentences[:4])[:800]


async def summarize_call(
    turns: list[dict[str, Any]],
    business_name: str,
    *,
    outcome_hint: str | None = None,
) -> dict[str, Any]:
    transcript = transcript_text(turns)
    outcome = normalize_outcome(outcome_hint)
    summary = ""
    if settings.openai_api_key and transcript:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_s)
            response = await client.chat.completions.create(
                model=settings.openai_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Summarize a receptionist phone call in 3 sentences. Return JSON with "
                            'keys "summary" and "outcome". Outcome must be one of: '
                            + ", ".join(OUTCOMES)
                            + ". Never invent details."
                        ),
                    },
                    {"role": "user", "content": transcript[:8000]},
                ],
            )
            import json

            payload = json.loads(response.choices[0].message.content or "{}")
            summary = str(payload.get("summary", "")).strip()
            outcome = normalize_outcome(payload.get("outcome")) or outcome
        except Exception as exc:  # noqa: BLE001 - summarization must never fail a call
            logger.warning("summary generation failed", extra={"context": {"error": str(exc)}})
    if not summary:
        summary = fallback_summary(turns, business_name)
    return {"summary": summary[:4000], "outcome": outcome}
