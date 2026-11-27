"""Tests for deterministic clause segmentation."""

from __future__ import annotations

from redliner.providers.pdf import Page, PageBlock
from redliner.services.extraction import (
    detect_type,
    extract_quote,
    placeholders_in,
    segment_pages,
)


def _page(page: int, blocks: list[tuple[str, tuple[float, float, float, float]]]) -> Page:
    return Page(
        page=page,
        text="\n".join(b[0] for b in blocks),
        width=612,
        height=792,
        blocks=[
            PageBlock(
                block_id=f"p{page}-b{i}",
                text=text,
                bbox=dict(zip(("x0", "y0", "x1", "y1"), bbox, strict=True)),
            )
            for i, (text, bbox) in enumerate(blocks)
        ],
    )


def test_segmentation_uses_headings() -> None:
    pages = [
        _page(
            1,
            [
                ("1. LIMITATION OF LIABILITY", (50, 100, 500, 120)),
                (
                    "Vendor's total liability shall not exceed fees paid in three (3) months.",
                    (50, 130, 500, 160),
                ),
                ("2. TERMINATION", (50, 200, 500, 220)),
                ("Either party may terminate on thirty (30) days notice.", (50, 230, 500, 260)),
            ],
        )
    ]
    clauses = segment_pages(pages)
    assert len(clauses) == 2
    assert clauses[0].heading.startswith("1.")
    assert clauses[0].clause_type == "liability"
    assert clauses[1].clause_type == "termination"


def test_boilerplate_skipped() -> None:
    pages = [
        _page(
            1,
            [
                ("Page 1 of 10", (300, 760, 400, 775)),
                ("Real clause text here.", (50, 100, 500, 130)),
            ],
        )
    ]
    clauses = segment_pages(pages)
    assert len(clauses) == 1


def test_type_detection() -> None:
    assert detect_type("The parties shall indemnify and hold harmless") == "liability"
    assert detect_type("Confidential Information means all non-public data") == "confidentiality"
    assert detect_type("Governing law is Delaware") == "dispute_resolution"


def test_quote_extraction() -> None:
    text = "The vendor may terminate for convenience. This is another sentence."
    quote = extract_quote(text, [r"terminate for convenience"])
    assert quote == "The vendor may terminate for convenience."


def test_placeholders() -> None:
    assert placeholders_in("Fee is $____ and [insert date]") == ["$____", "[insert date]"]


def test_empty_pages() -> None:
    assert segment_pages([]) == []
