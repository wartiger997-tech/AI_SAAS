"""PII redaction for transcripts, logs, and summaries.

Redaction is deliberately conservative: it targets high-confidence identifiers
(email, phone, SSN, payment cards, long account numbers) and leaves ordinary
clause/contract language intact. The raw transcript is stored redacted; the
original audio is governed by the recording retention policy.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")
_ACCOUNT = re.compile(
    r"\b(?:account|acct|policy|member)(?:\s*(?:no\.?|number|#))?\s*[:#]?\s*([A-Z0-9-]{6,})\b",
    re.IGNORECASE,
)


def redact_pii(text: str) -> str:
    if not text:
        return text
    redacted = _EMAIL.sub("[email]", text)
    redacted = _SSN.sub("[ssn]", redacted)
    redacted = _CARD.sub("[card]", redacted)
    redacted = _ACCOUNT.sub(lambda m: m.group(0).replace(m.group(1), "[account]"), redacted)
    redacted = _PHONE.sub("[phone]", redacted)
    return redacted


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 4:
        return "***"
    return f"***-***-{digits[-4:]}"


def contains_pii(text: str) -> bool:
    return redact_pii(text) != text
