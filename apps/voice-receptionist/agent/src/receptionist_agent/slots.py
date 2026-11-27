"""Session-scoped offered-slot tracking.

The agent may only book a slot it has already offered, which prevents the model
from hallucinating a time and closes the most common double-booking race.
"""

from __future__ import annotations

from datetime import datetime


def _key(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value.strip()


class OfferedSlots:
    def __init__(self) -> None:
        self._offered: dict[str, str] = {}

    def offer(self, slots: list[dict[str, str]]) -> list[str]:
        offered: list[str] = []
        for slot in slots:
            starts_at = str(slot.get("starts_at", "")).strip()
            if not starts_at:
                continue
            key = _key(starts_at)
            self._offered[key] = starts_at
            offered.append(starts_at)
        return offered

    def is_offered(self, starts_at: str) -> bool:
        return _key(starts_at) in self._offered

    def take(self, starts_at: str) -> bool:
        key = _key(starts_at)
        if key not in self._offered:
            return False
        self._offered.pop(key, None)
        return True

    def remaining(self) -> list[str]:
        return list(self._offered.values())
