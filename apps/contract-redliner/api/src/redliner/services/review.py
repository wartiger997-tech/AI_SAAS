"""Review orchestration: extract -> segment -> evaluate -> enrich -> persist."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from redliner.config import get_settings
from redliner.db import SessionFactory
from redliner.models import (
    AuditEvent,
    Clause,
    Document,
    Finding,
    Playbook,
    Redline,
    Review,
)
from redliner.observability import get_logger
from redliner.providers.llm import get_llm
from redliner.providers.pdf import extract_pdf
from redliner.schemas import RuleOut
from redliner.services.extraction import extract_clauses, extract_quote, placeholders_in
from redliner.services.playbook import evaluate_clause, severity_rank
from redliner.services.search import hybrid_search
from redliner.storage import get_bytes

logger = get_logger(__name__)
settings = get_settings()


class Suggestion(BaseModel):
    index: int
    title: str = ""
    severity: str = ""
    suggested_text: str = ""
    rationale: str = ""
    market_standard: str = ""


class SuggestionBatch(BaseModel):
    items: list[Suggestion] = Field(default_factory=list)


@dataclass
class Candidate:
    clause: Clause
    rule: RuleOut
    quote: str
    missing_terms: list[str]


_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+")


def detect_doc_type(filename: str, pages_text: str) -> str:
    haystack = f"{filename}\n{pages_text[:4000]}".lower()
    if "non-disclosure" in haystack or "nda" in haystack or "confidentiality agreement" in haystack:
        return "nda"
    if "employment" in haystack or "offer letter" in haystack:
        return "employment"
    return "saas"


async def _enrich(candidates: list[Candidate], doc_type: str) -> dict[int, Suggestion]:
    if not candidates:
        return {}
    payload = [
        {
            "index": index,
            "doc_type": doc_type,
            "rule": c.rule.model_dump(),
            "clause": c.clause.text[:2200],
            "matched_quote": c.quote,
            "missing_terms": c.missing_terms,
        }
        for index, c in enumerate(candidates)
    ]
    try:
        result, _ = await get_llm().complete_json(
            system=(
                "You are a senior commercial contracts lawyer. For each item, produce a "
                "lawyer-ready redline suggestion. Be specific and concise. If the clause "
                "already complies, still return a short rationale explaining why it is flagged "
                "for verification. Never invent facts. Use plain English."
            ),
            user=str(payload),
            schema=SuggestionBatch,
            max_tokens=4000,
        )
        return {item.index: item for item in result.items if 0 <= item.index < len(candidates)}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "enrichment failed; using rule defaults", extra={"context": {"error": str(exc)}}
        )
        return {}


async def _attach_precedent(
    session: AsyncSession, tenant_id: uuid.UUID, candidates: list[Candidate]
) -> dict[str, list[dict[str, Any]]]:
    """Run one hybrid search per rule category and attach top hits."""
    evidence: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.rule.id
        if key in seen:
            continue
        seen.add(key)
        query = f"{candidate.rule.title} {candidate.rule.category} market standard"
        try:
            hits, _ = await hybrid_search(session, str(tenant_id), query, limit=3)
        except Exception as exc:  # noqa: BLE001
            logger.warning("precedent search failed", extra={"context": {"error": str(exc)}})
            continue
        evidence[key] = [
            {"title": hit.title, "source": hit.source, "snippet": hit.snippet, "score": hit.score}
            for hit in hits
        ]
    return evidence


async def run_review(
    review_id: uuid.UUID, factory: async_sessionmaker[AsyncSession] = SessionFactory
) -> None:
    async with factory() as session:
        review = await session.get(Review, review_id)
        if not review:
            logger.error("review not found", extra={"context": {"review_id": str(review_id)}})
            return
        document = await session.get(Document, review.document_id)
        playbook = await session.get(Playbook, review.playbook_id)
        if not document or not playbook:
            review.status = "failed"
            review.error = "document or playbook missing"
            await session.commit()
            return

        try:
            review.status = "extracting"
            review.progress = 5
            await session.commit()

            data = get_bytes(document.storage_key)
            extraction = await extract_pdf(data, document.filename)
            document.page_count = extraction.page_count
            document.status = "extracted"
            document.extracted = {
                "provider": extraction.provider,
                "warnings": extraction.warnings,
                "pages": [
                    {
                        "page": page.page,
                        "text": page.text,
                        "width": page.width,
                        "height": page.height,
                        "blocks": [block.__dict__ for block in page.blocks],
                        "tables": page.tables,
                    }
                    for page in extraction.pages
                ],
            }
            await session.commit()

            raw_clauses = await extract_clauses(extraction)
            clauses: list[Clause] = []
            for raw in raw_clauses:
                clause = Clause(
                    document_id=document.id,
                    block_id=raw.block_id,
                    page=raw.page,
                    heading=raw.heading[:300],
                    text=raw.text,
                    clause_type=raw.clause_type,
                    char_start=raw.char_start,
                    char_end=raw.char_end,
                    bbox=raw.bbox,
                    confidence=raw.confidence,
                )
                session.add(clause)
                clauses.append(clause)
            await session.flush()

            review.status = "reviewing"
            review.progress = 35
            review.model = get_llm().model
            await session.commit()

            rules = [RuleOut.model_validate(rule) for rule in playbook.rules]
            doc_type = detect_doc_type(
                document.filename, "\n".join(p.text for p in extraction.pages[:3])
            )
            candidates: list[Candidate] = []
            for clause in clauses:
                for match in evaluate_clause(clause.text, rules):
                    if not match.is_violation:
                        continue
                    quote = extract_quote(clause.text, match.rule.patterns)
                    candidates.append(
                        Candidate(
                            clause=clause,
                            rule=match.rule,
                            quote=quote,
                            missing_terms=match.missing_terms,
                        )
                    )
            # Placeholder findings (blank fields / missing exhibits).
            for clause in clauses:
                placeholders = placeholders_in(clause.text)
                if placeholders:
                    rule = RuleOut(
                        id="placeholder_blank_field",
                        title="Blank field or placeholder",
                        category="general",
                        severity="medium",
                        description="The clause contains an unfilled placeholder.",
                        market_standard="All material fields completed before signature",
                        guidance="Complete or remove the placeholder before execution.",
                        suggested_text="",
                    )
                    candidates.append(
                        Candidate(
                            clause=clause,
                            rule=rule,
                            quote=extract_quote(clause.text, [r"\$|_{2,}|\[[^\]]+\]|TBD"]),
                            missing_terms=[],
                        )
                    )

            review.progress = 55
            await session.commit()

            suggestions = await _enrich(candidates, doc_type)
            precedent = await _attach_precedent(session, document.tenant_id, candidates)

            candidates.sort(key=lambda c: (-severity_rank(c.rule.severity), c.clause.page))
            findings: list[Finding] = []
            for index, candidate in enumerate(candidates):
                suggestion = suggestions.get(index)
                severity = (
                    suggestion.severity
                    if suggestion and suggestion.severity
                    else candidate.rule.severity
                )
                if severity not in {"critical", "high", "medium", "low", "info"}:
                    severity = candidate.rule.severity
                finding = Finding(
                    review_id=review.id,
                    clause_id=candidate.clause.id,
                    rule_id=candidate.rule.id,
                    title=(
                        suggestion.title
                        if suggestion and suggestion.title
                        else candidate.rule.title
                    )[:300],
                    severity=severity,
                    status="open",
                    quote=candidate.quote,
                    page=candidate.clause.page,
                    suggested_text=(
                        suggestion.suggested_text
                        if suggestion and suggestion.suggested_text
                        else candidate.rule.suggested_text
                    ),
                    rationale=(
                        suggestion.rationale
                        if suggestion and suggestion.rationale
                        else candidate.rule.guidance
                    ),
                    market_standard=(
                        suggestion.market_standard
                        if suggestion and suggestion.market_standard
                        else candidate.rule.market_standard
                    ),
                    confidence=round(candidate.clause.confidence, 3),
                    evidence={
                        "rule": candidate.rule.model_dump(),
                        "missing_terms": candidate.missing_terms,
                        "precedent": precedent.get(candidate.rule.id, []),
                        "extractor": extraction.provider,
                        "doc_type": doc_type,
                    },
                )
                session.add(finding)
                findings.append(finding)
            await session.flush()

            for finding in findings:
                rule = next((r for r in rules if r.id == finding.rule_id), None)
                strategy = rule.redline_strategy if rule else "flag"
                if strategy == "replace" and finding.suggested_text:
                    session.add(
                        Redline(
                            finding_id=finding.id,
                            kind="replace",
                            old_text=finding.quote,
                            new_text=finding.suggested_text,
                            anchor=finding.quote,
                        )
                    )
                elif strategy == "insert_after" and finding.suggested_text:
                    session.add(
                        Redline(
                            finding_id=finding.id,
                            kind="insert_after",
                            old_text="",
                            new_text=finding.suggested_text,
                            anchor=finding.quote,
                        )
                    )
                elif strategy == "delete":
                    session.add(
                        Redline(
                            finding_id=finding.id,
                            kind="delete",
                            old_text=finding.quote,
                            new_text="",
                            anchor=finding.quote,
                        )
                    )

            review.status = "completed"
            review.progress = 100
            review.usage = {
                "clauses": len(clauses),
                "findings": len(findings),
                "by_severity": {
                    severity: sum(1 for f in findings if f.severity == severity)
                    for severity in ("critical", "high", "medium", "low", "info")
                },
                "extraction_ms": extraction.took_ms,
                "provider": extraction.provider,
            }
            session.add(
                AuditEvent(
                    tenant_id=document.tenant_id,
                    actor="system",
                    action="review.completed",
                    subject=str(review.id),
                    meta={"document_id": str(document.id), "findings": len(findings)},
                )
            )
            await session.commit()
            logger.info(
                "review completed",
                extra={
                    "context": {
                        "review_id": str(review.id),
                        "findings": len(findings),
                        "clauses": len(clauses),
                    }
                },
            )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            review = await session.get(Review, review_id)
            if review:
                review.status = "failed"
                review.error = str(exc)[:2000]
                await session.commit()
            logger.exception("review failed", extra={"context": {"review_id": str(review_id)}})
            raise


async def build_export_data(session: AsyncSession, review_id: uuid.UUID) -> dict[str, Any]:
    review = await session.get(Review, review_id)
    if not review:
        raise LookupError("review not found")
    document = await session.get(Document, review.document_id)
    if not document:
        raise LookupError("document not found")
    result = await session.execute(
        select(Finding, Clause)
        .join(Clause, Finding.clause_id == Clause.id)
        .where(Finding.review_id == review_id)
        .order_by(Finding.page, Finding.severity)
    )
    rows = result.all()
    findings = []
    pages: dict[int, dict[str, Any]] = {}
    for finding, clause in rows:
        findings.append(
            {
                "id": str(finding.id),
                "rule_id": finding.rule_id,
                "title": finding.title,
                "severity": finding.severity,
                "page": finding.page,
                "quote": finding.quote,
                "suggested_text": finding.suggested_text,
                "rationale": finding.rationale,
                "market_standard": finding.market_standard,
                "status": finding.status,
            }
        )
        pages.setdefault(
            clause.page,
            {"page": clause.page, "text": "", "blocks": []},
        )
    if document.extracted:
        for page in document.extracted.get("pages", []):
            if page.get("page") in pages:
                pages[page["page"]] = page
    return {
        "title": document.filename,
        "reviewer_role": review.reviewer_role,
        "findings": findings,
        "pages": [pages[key] for key in sorted(pages)],
    }


async def ensure_playbook(
    session: AsyncSession, tenant_id: uuid.UUID, playbook_id: uuid.UUID
) -> Playbook:
    playbook = await session.get(Playbook, playbook_id)
    if not playbook or str(playbook.tenant_id) != str(tenant_id):
        raise LookupError("playbook not found")
    return playbook
