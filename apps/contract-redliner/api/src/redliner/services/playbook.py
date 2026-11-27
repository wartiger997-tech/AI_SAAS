"""Playbook loading, seeding, and deterministic rule matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from redliner.models import Playbook, Tenant
from redliner.observability import get_logger
from redliner.schemas import RuleOut

logger = get_logger(__name__)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "playbooks"


@dataclass
class RuleMatch:
    rule: RuleOut
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)

    @property
    def is_violation(self) -> bool:
        return bool(self.missing_terms)


def load_seed_playbooks() -> list[tuple[str, dict[str, Any]]]:
    playbooks: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(_DATA_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw.setdefault("name", path.stem)
        playbooks.append((path.name, raw))
    return playbooks


async def seed_default_playbooks(session: AsyncSession, tenant: Tenant) -> list[Playbook]:
    created: list[Playbook] = []
    for _, raw in load_seed_playbooks():
        existing = await session.execute(
            select(Playbook).where(
                Playbook.tenant_id == tenant.id,
                Playbook.name == raw["name"],
                Playbook.version == int(raw.get("version", 1)),
            )
        )
        if existing.scalar_one_or_none():
            continue
        rules = [RuleOut.model_validate(rule).model_dump() for rule in raw.get("rules", [])]
        playbook = Playbook(
            tenant_id=tenant.id,
            name=str(raw["name"]),
            version=int(raw.get("version", 1)),
            description=str(raw.get("description", "")),
            rules=rules,
        )
        session.add(playbook)
        created.append(playbook)
    if created:
        await session.flush()
        logger.info("seeded playbooks", extra={"context": {"count": len(created)}})
    return created


def _pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# A match inside a negated/“silent” clause is not a risk signal on its own.
_NEGATED = re.compile(
    r"\b(?:silent|no|not|never|without|nothing|neither|nor)\b[^.;:]{0,40}$",
    re.IGNORECASE,
)


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 60) : start]
    return bool(_NEGATED.search(prefix))


def match_clause(clause_text: str, rule: RuleOut) -> RuleMatch | None:
    """Return a match when any pattern fires. Missing must_include terms make it a violation."""
    matched: list[str] = []
    for pattern in rule.patterns:
        try:
            found = _pattern(pattern).search(clause_text)
        except re.error:
            logger.warning(
                "invalid rule pattern", extra={"context": {"rule": rule.id, "pattern": pattern}}
            )
            continue
        if found and not _is_negated(clause_text, found.start()):
            matched.append(pattern)
    if not matched:
        return None
    lowered = clause_text.lower()
    missing = [term for term in rule.must_include if term.lower() not in lowered]
    return RuleMatch(rule=rule, matched_terms=matched, missing_terms=missing)


def evaluate_clause(clause_text: str, rules: list[RuleOut]) -> list[RuleMatch]:
    return [m for rule in rules if (m := match_clause(clause_text, rule))]


def severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(severity, 0)
