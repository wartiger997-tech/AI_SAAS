"""Clause segmentation and normalization.

Segmentation is deterministic first (headings, numbering, page geometry), then
an LLM normalizes clause types and headings. Determinism matters: citations and
redline anchors must be reproducible across runs and model upgrades.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from redliner.observability import get_logger, trace_span
from redliner.providers.llm import get_llm
from redliner.providers.pdf import Extraction, Page, PageBlock

logger = get_logger(__name__)

_NUMBERED = re.compile(r"^\s*(\d+(?:\.\d+)*|[IVXLC]+\.|[A-Z]\.|\(\d+\)|\([a-z]\))\s+")
_ALL_CAPS = re.compile(r"^[A-Z0-9 ,'&/()\-\.]{4,120}$")
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s*)?\d{1,4}\s*(?:of\s*\d{1,4})?\s*$", re.I)
_PLACEHOLDER = re.compile(r"(\$+_*|_{2,}|\[[^\]]{0,60}\]|TBD|XX+)", re.I)

_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("liability", ("liab", "consequential", "damages", "indemnif")),
    ("indemnification", ("indemnif", "hold harmless", "defend")),
    ("termination", ("terminat", "expiration", "renew")),
    ("confidentiality", ("confidential", "non-disclosure", "proprietary information")),
    ("intellectual_property", ("intellectual property", "copyright", "ownership", "work product")),
    ("payment", ("fees", "payment", "invoice", "price", "compensation")),
    ("warranty", ("warrant", "represent", "as-is")),
    ("data_protection", ("personal data", "data protection", "gdpr", "ccpa", "security")),
    ("dispute_resolution", ("governing law", "jurisdiction", "arbitrat", "venue", "dispute")),
    ("assignment", ("assign", "change of control", "successor")),
    ("non_compete", ("non-compete", "noncompete", "not compete")),
    ("non_solicitation", ("non-solicit", "solicit")),
    ("exclusivity", ("exclusive", "exclusivity")),
    ("sla", ("service level", "uptime", "availability", "sla")),
    ("insurance", ("insurance", "insured")),
    ("audit", ("audit", "inspect")),
    ("publicity", ("publicity", "press release", "public announcement")),
    ("force_majeure", ("force majeure", "act of god")),
    ("general", ()),
]


@dataclass
class RawClause:
    block_id: str
    page: int
    heading: str
    text: str
    clause_type: str
    bbox: dict[str, float] | None
    char_start: int
    char_end: int
    confidence: float = 0.85
    blocks: list[PageBlock] = field(default_factory=list)


class ClauseItem(BaseModel):
    block_id: str
    clause_type: str = "general"
    heading: str = ""
    summary: str = ""


class ClauseBatch(BaseModel):
    items: list[ClauseItem] = Field(default_factory=list)


def detect_type(text: str) -> str:
    lowered = text.lower()
    for clause_type, keywords in _TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return clause_type
    return "general"


def _is_boilerplate(block: PageBlock, page: Page) -> bool:
    text = block.text.strip()
    if not text or _PAGE_NUMBER.match(text):
        return True
    if block.bbox:
        rel_top = block.bbox.get("y0", 0) / max(page.height, 1)
        rel_bottom = block.bbox.get("y1", 0) / max(page.height, 1)
        if (rel_bottom < 0.07 or rel_top > 0.94) and len(text) < 120:
            return True
    return len(text) < 3


def _looks_like_heading(block: PageBlock) -> bool:
    text = block.text.strip()
    if len(text) > 140 or "\n" in text:
        return False
    if _NUMBERED.match(text):
        return True
    return bool(_ALL_CAPS.match(text) and len(text.split()) <= 12)


def segment_pages(pages: list[Page]) -> list[RawClause]:
    clauses: list[RawClause] = []
    current_heading = ""
    buffer: list[PageBlock] = []
    buffer_page: Page | None = None
    buffer_start = 0

    def flush() -> None:
        nonlocal buffer, buffer_page, buffer_start
        if not buffer or buffer_page is None:
            return
        text = "\n".join(b.text for b in buffer).strip()
        if not text:
            buffer = []
            return
        clause_type = detect_type(f"{current_heading}\n{text}")
        clauses.append(
            RawClause(
                block_id=buffer[0].block_id,
                page=buffer_page.page,
                heading=current_heading,
                text=text,
                clause_type=clause_type,
                bbox=buffer[0].bbox,
                char_start=buffer_start,
                char_end=buffer_start + len(text),
                blocks=list(buffer),
                confidence=0.9 if current_heading else 0.7,
            )
        )
        buffer_start += len(text) + 1
        buffer = []

    for page in pages:
        buffer_page = page
        for block in page.blocks:
            if _is_boilerplate(block, page):
                continue
            if _looks_like_heading(block):
                flush()
                current_heading = re.sub(r"\s+", " ", block.text).strip()
                buffer_start += len(block.text) + 1
                continue
            if not buffer:
                buffer_start = 0
            buffer.append(block)
            if len("\n".join(b.text for b in buffer)) > 2400:
                flush()
    flush()

    # Merge tiny fragments into the previous clause when they are clearly continuations.
    merged: list[RawClause] = []
    for clause in clauses:
        if merged and len(clause.text) < 40 and clause.page == merged[-1].page:
            merged[-1].text = f"{merged[-1].text}\n{clause.text}".strip()
            merged[-1].blocks.extend(clause.blocks)
            merged[-1].confidence = min(merged[-1].confidence, clause.confidence)
        else:
            merged.append(clause)
    return merged


async def normalize_clauses(clauses: list[RawClause]) -> list[RawClause]:
    """Use the LLM to refine clause type/heading. Falls back to heuristics."""
    if not clauses:
        return clauses
    with trace_span("normalize_clauses", count=len(clauses)):
        for start in range(0, len(clauses), 20):
            batch = clauses[start : start + 20]
            payload = [
                {"block_id": c.block_id, "heading": c.heading, "text": c.text[:1800]} for c in batch
            ]
            try:
                result, _ = await get_llm().complete_json(
                    system=(
                        "You normalize legal clause metadata. Classify each clause into one of: "
                        "liability, indemnification, termination, confidentiality, "
                        "intellectual_property, payment, warranty, data_protection, "
                        "dispute_resolution, assignment, non_compete, non_solicitation, "
                        "exclusivity, sla, insurance, audit, publicity, force_majeure, general. "
                        "Return a concise heading and one-sentence summary. Do not invent text."
                    ),
                    user=str(payload),
                    schema=ClauseBatch,
                    max_tokens=2000,
                )
                by_id = {item.block_id: item for item in result.items}
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "clause normalization failed", extra={"context": {"error": str(exc)}}
                )
                by_id = {}
            for clause in batch:
                item = by_id.get(clause.block_id)
                if not item:
                    continue
                if item.clause_type:
                    clause.clause_type = item.clause_type
                if item.heading:
                    clause.heading = item.heading
                if item.summary:
                    clause.confidence = min(1.0, clause.confidence + 0.05)
    return clauses


def placeholders_in(text: str) -> list[str]:
    return sorted(set(_PLACEHOLDER.findall(text)))


def extract_quote(text: str, patterns: list[str]) -> str:
    """Return the sentence containing the first matching pattern."""
    flat = re.sub(r"\s+", " ", text).strip()
    for pattern in patterns:
        try:
            match = re.search(pattern, flat, re.IGNORECASE)
        except re.error:
            continue
        if not match:
            continue
        start = max(flat.rfind(".", 0, match.start()), flat.rfind(";", 0, match.start()))
        end_candidates = [
            i for i in (flat.find(".", match.end()), flat.find(";", match.end())) if i >= 0
        ]
        end = min(end_candidates) + 1 if end_candidates else len(flat)
        quote = flat[max(start + 1, 0) : end].strip()
        return quote[:800]
    return flat[:400]


async def extract_clauses(extraction: Extraction) -> list[RawClause]:
    clauses = segment_pages(extraction.pages)
    clauses = await normalize_clauses(clauses)
    logger.info(
        "clauses extracted",
        extra={"context": {"pages": extraction.page_count, "clauses": len(clauses)}},
    )
    return clauses
