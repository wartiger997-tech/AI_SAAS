"""Tests for export rendering."""

from __future__ import annotations

import io
import json
import zipfile

from redliner.services.redline import (
    RenderFinding,
    RenderInput,
    render,
    render_docx,
    render_pdf,
)


def _input() -> RenderInput:
    return RenderInput(
        title="Master Services Agreement",
        reviewer_role="customer",
        pages=[
            {
                "page": 1,
                "text": "Liability shall not exceed three (3) months of fees.",
                "blocks": [{"text": "Liability shall not exceed three (3) months of fees."}],
            }
        ],
        findings=[
            RenderFinding(
                id="f1",
                rule_id="liability_cap_low",
                title="Liability cap below market",
                severity="high",
                page=1,
                quote="Liability shall not exceed three (3) months of fees.",
                suggested_text="Liability shall not exceed twelve (12) months of fees.",
                rationale="Below market.",
                market_standard="12 months",
                status="open",
            )
        ],
    )


def test_docx_is_zip_with_tracked_changes() -> None:
    data = render_docx(_input())
    assert data[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document_xml = archive.read("word/document.xml")
    assert b"w:ins" in document_xml
    assert b"w:del" in document_xml


def test_pdf_renders() -> None:
    data = render_pdf(_input())
    assert data.startswith(b"%PDF")


def test_markdown_contains_finding() -> None:
    content, _ = render("md", _input())
    text = content.decode()
    assert "Liability cap below market" in text
    assert "Page:** 1" in text or "**Page:** 1" in text


def test_json_roundtrip() -> None:
    content, _ = render("json", _input())
    payload = json.loads(content)
    assert payload["findings"][0]["rule_id"] == "liability_cap_low"


def test_unknown_format() -> None:
    try:
        render("doc", _input())
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
