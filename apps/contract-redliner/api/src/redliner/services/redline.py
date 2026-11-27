"""Redline rendering: tracked-changes DOCX, annotated PDF, Markdown, JSON.

DOCX uses real OOXML ``w:ins``/``w:del`` elements so recipients can accept or
reject each change in Word. The source PDF is converted to a clean DOCX first;
formatting fidelity is best-effort and documented as a v1 limitation.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from redliner.observability import get_logger

logger = get_logger(__name__)

SEVERITY_COLORS = {
    "critical": "C0392B",
    "high": "D35400",
    "medium": "B7950B",
    "low": "2E86C1",
    "info": "7F8C8D",
}


@dataclass
class RenderFinding:
    id: str
    rule_id: str
    title: str
    severity: str
    page: int
    quote: str
    suggested_text: str
    rationale: str
    market_standard: str
    status: str


@dataclass
class RenderInput:
    title: str
    pages: list[dict[str, Any]]
    findings: list[RenderFinding]
    reviewer_role: str = "customer"


# ------------------------------------------------------------------ DOCX
def _set_run_props(
    run: Any, *, bold: bool = False, color: str | None = None, size: int = 10
) -> None:
    run.bold = bold
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _del_element(text: str, author: str, date: str) -> Any:
    node = OxmlElement("w:del")
    node.set(qn("w:author"), author)
    node.set(qn("w:date"), date)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    strike = OxmlElement("w:strike")
    props.append(strike)
    run.append(props)
    deleted = OxmlElement("w:delText")
    deleted.set(qn("xml:space"), "preserve")
    deleted.text = text
    run.append(deleted)
    node.append(run)
    return node


def _ins_element(text: str, author: str, date: str) -> Any:
    node = OxmlElement("w:ins")
    node.set(qn("w:author"), author)
    node.set(qn("w:date"), date)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    run.append(props)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    node.append(run)
    return node


def _apply_tracked_replace(paragraph: Any, old: str, new: str, author: str, date: str) -> bool:
    text = paragraph.text
    if old not in text:
        return False
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    before, after = text.split(old, 1)
    if before:
        paragraph.add_run(before)
    paragraph._p.append(_del_element(old, author, date))
    if new:
        paragraph._p.append(_ins_element(new, author, date))
    if after:
        paragraph.add_run(after)
    return True


def _add_summary_table(document: Document, data: RenderInput) -> None:
    document.add_heading("Review Summary", level=1)
    intro = document.add_paragraph(
        f"Reviewer role: {data.reviewer_role}. "
        "This document contains tracked changes. Open in Word to accept or reject each change."
    )
    intro.runs[0].italic = True
    if not data.findings:
        document.add_paragraph("No findings were produced.")
        return
    table = document.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    for index, label in enumerate(["#", "Severity", "Clause", "Page", "Proposed change"]):
        header[index].text = label
    for index, finding in enumerate(data.findings, start=1):
        cells = table.add_row().cells
        cells[0].text = str(index)
        cells[1].text = finding.severity.upper()
        cells[2].text = finding.title
        cells[3].text = str(finding.page)
        cells[4].text = finding.suggested_text or "Flag only — see comments"


def _build_base_docx(data: RenderInput) -> Document:
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)
    title = document.add_heading(data.title, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_summary_table(document, data)
    document.add_page_break()

    for page in data.pages:
        heading = document.add_paragraph()
        run = heading.add_run(f"Page {page.get('page', '?')}")
        _set_run_props(run, bold=True, color="566573", size=9)
        for block in page.get("blocks") or [{"text": page.get("text", "")}]:
            text = str(block.get("text", "")).strip()
            if not text:
                continue
            paragraph = document.add_paragraph()
            paragraph.add_run(text)
    return document


def render_docx(data: RenderInput) -> bytes:
    document = _build_base_docx(data)
    author = "ClauseGuard"
    date = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    for finding in data.findings:
        if finding.status in {"rejected", "dismissed"}:
            continue
        changed = False
        for paragraph in document.paragraphs:
            candidates = [finding.quote, finding.quote.strip()]
            if finding.suggested_text and any(c and c in paragraph.text for c in candidates):
                old = next(c for c in candidates if c and c in paragraph.text)
                changed = _apply_tracked_replace(
                    paragraph, old, finding.suggested_text, author, date
                )
                if changed:
                    break
        if not changed and finding.suggested_text:
            paragraph = document.add_paragraph()
            paragraph._p.append(
                _ins_element(f"[{finding.title}] {finding.suggested_text}", author, date)
            )
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------ PDF
def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleX", parent=base["Title"], fontSize=20, spaceAfter=10, alignment=TA_LEFT
        ),
        "h1": ParagraphStyle("H1X", parent=base["Heading1"], fontSize=14, spaceBefore=10),
        "body": ParagraphStyle(
            "BodyX", parent=base["BodyText"], fontSize=9.5, leading=13, spaceAfter=4
        ),
        "small": ParagraphStyle("SmallX", parent=base["BodyText"], fontSize=8, leading=10),
    }


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    )


def render_pdf(data: RenderInput) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=data.title,
        author="ClauseGuard",
    )
    styles = _pdf_styles()
    story: list[Any] = [
        Paragraph(_escape(data.title), styles["title"]),
        Paragraph(
            f"Reviewer role: {_escape(data.reviewer_role)} · Generated "
            f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["small"],
        ),
        Spacer(1, 8),
        Paragraph("Summary of proposed changes", styles["h1"]),
    ]
    if data.findings:
        rows = [["#", "Severity", "Clause", "Page", "Proposed change"]]
        for index, finding in enumerate(data.findings, start=1):
            rows.append(
                [
                    str(index),
                    finding.severity.upper(),
                    _escape(finding.title)[:70],
                    str(finding.page),
                    _escape(finding.suggested_text or "Flag only")[:90],
                ]
            )
        table = Table(rows, colWidths=[0.3 * inch, 0.8 * inch, 1.8 * inch, 0.5 * inch, 3.1 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No findings were produced.", styles["body"]))
    story.append(PageBreak())

    for page in data.pages:
        story.append(Paragraph(f"Page {page.get('page', '?')}", styles["h1"]))
        for block in page.get("blocks") or [{"text": page.get("text", "")}]:
            text = str(block.get("text", "")).strip()
            if not text:
                continue
            marked = _escape(text)
            for finding in data.findings:
                if finding.status in {"rejected", "dismissed"}:
                    continue
                quote = _escape(finding.quote)
                if quote and quote in marked:
                    marked = marked.replace(
                        quote,
                        f"<strike color='#C0392B'>{quote}</strike> "
                        f"<u color='#1F618D'>{_escape(finding.suggested_text)}</u>",
                        1,
                    )
            story.append(Paragraph(marked, styles["body"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    return buffer.getvalue()


# ------------------------------------------------------------------ Markdown / JSON
def render_markdown(data: RenderInput) -> str:
    lines = [
        f"# {data.title}",
        "",
        f"**Reviewer role:** {data.reviewer_role}  ",
        f"**Generated:** {datetime.now(UTC).isoformat()}  ",
        f"**Findings:** {len(data.findings)}",
        "",
        "## Summary",
        "",
    ]
    if not data.findings:
        lines.append("No findings were produced.")
    for index, finding in enumerate(data.findings, start=1):
        lines.extend(
            [
                f"### {index}. [{finding.severity.upper()}] {finding.title}",
                "",
                f"- **Rule:** `{finding.rule_id}`",
                f"- **Page:** {finding.page}",
                f"- **Market standard:** {finding.market_standard or '—'}",
                f"- **Status:** {finding.status}",
                "",
                "> " + finding.quote.replace("\n", " "),
                "",
                f"**Proposed:** {finding.suggested_text or '_Flag only_'}"
                if finding.suggested_text
                else "**Proposed:** _Flag only_",
                "",
                f"**Rationale:** {finding.rationale or '—'}",
                "",
            ]
        )
    lines.extend(["---", "*Generated by ClauseGuard. Not legal advice.*", ""])
    return "\n".join(lines)


def render_json(data: RenderInput) -> bytes:
    payload = {
        "title": data.title,
        "reviewer_role": data.reviewer_role,
        "generated_at": datetime.now(UTC).isoformat(),
        "findings": [finding.__dict__ for finding in data.findings],
        "pages": data.pages,
    }
    return json.dumps(payload, indent=2, default=str).encode()


def render(fmt: str, data: RenderInput) -> tuple[bytes, str]:
    if fmt == "docx":
        return render_docx(data), (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    if fmt == "pdf":
        return render_pdf(data), "application/pdf"
    if fmt == "md":
        return render_markdown(data).encode(), "text/markdown; charset=utf-8"
    if fmt == "json":
        return render_json(data), "application/json"
    raise ValueError(f"unsupported export format: {fmt}")
