"""Tests for playbook rules and seed loading."""

from __future__ import annotations

from redliner.schemas import RuleOut
from redliner.services.playbook import (
    evaluate_clause,
    load_seed_playbooks,
    match_clause,
    severity_rank,
)

RULE = RuleOut(
    id="liability_cap_low",
    title="Liability cap below market",
    category="liability",
    severity="high",
    patterns=["liab", "cap on liability"],
    must_include=["12", "twelve"],
    market_standard="12 months' fees",
    suggested_text="Twelve months.",
)


def test_match_detects_violation() -> None:
    match = match_clause("Liability shall not exceed three (3) months of fees.", RULE)
    assert match is not None
    assert match.is_violation
    assert "12" in match.missing_terms


def test_match_detects_compliant() -> None:
    match = match_clause("Liability shall not exceed twelve (12) months of fees.", RULE)
    assert match is not None
    assert not match.is_violation


def test_no_match() -> None:
    assert match_clause("This agreement is silent on liability.", RULE) is None


def test_evaluate_clause() -> None:
    matches = evaluate_clause("Our aggregate liability is capped at 3 months.", [RULE])
    assert len(matches) == 1


def test_seed_playbooks_load() -> None:
    playbooks = load_seed_playbooks()
    assert len(playbooks) >= 2
    names = {raw["name"] for _, raw in playbooks}
    assert any("SaaS" in name for name in names)
    assert any("NDA" in name for name in names)


def test_severity_rank() -> None:
    assert severity_rank("critical") > severity_rank("high") > severity_rank("low")


def test_invalid_pattern_is_skipped() -> None:
    rule = RULE.model_copy(update={"patterns": ["[invalid"]})
    assert match_clause("liability cap", rule) is None
