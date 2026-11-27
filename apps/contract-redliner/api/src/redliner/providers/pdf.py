"""PDF extraction with page-anchored blocks and tables.

Local extraction uses PyMuPDF for fast page text and block geometry, plus
pdfplumber for tables. Optional hosted parsers (LlamaParse, Unstructured) are
used when configured; they return page-tagged markdown/elements that are
normalized into the same structure so downstream citations stay valid.
"""

from __future__ import annotations

import asyncio
import io
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from redliner.config import get_settings
from redliner.observability import get_logger

logger = get_logger(__name__)
settings = get_settings()

_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SOFT_HYPHEN = "\u00ad"
_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}


@dataclass
class PageBlock:
    block_id: str
    text: str
    bbox: dict[str, float]
    kind: str = "text"


@dataclass
class Page:
    page: int
    text: str
    width: float
    height: float
    blocks: list[PageBlock] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Extraction:
    pages: list[Page]
    provider: str
    took_ms: int
    warnings: list[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


def normalize_text(text: str) -> str:
    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)
    text = text.replace(_SOFT_HYPHEN, "")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_local(data: bytes) -> Extraction:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    pages: list[Page] = []
    for index, pdf_page in enumerate(doc):
        raw = pdf_page.get_text("text")
        blocks: list[PageBlock] = []
        for number, block in enumerate(pdf_page.get_text("blocks")):
            x0, y0, x1, y1, text, block_no, block_type = block[:7]
            cleaned = normalize_text(str(text))
            if not cleaned:
                continue
            blocks.append(
                PageBlock(
                    block_id=f"p{index + 1}-b{block_no or number}",
                    text=cleaned,
                    bbox={"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1)},
                    kind="image" if int(block_type) == 1 else "text",
                )
            )
        tables: list[dict[str, Any]] = []
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as plumber:
                plumber_page = plumber.pages[index]
                for table in plumber_page.extract_tables() or []:
                    tables.append({"rows": table})
        except Exception as exc:  # noqa: BLE001 - tables are best effort
            logger.warning(
                "table extraction failed", extra={"context": {"page": index + 1, "error": str(exc)}}
            )
        pages.append(
            Page(
                page=index + 1,
                text=normalize_text(raw),
                width=float(pdf_page.rect.width),
                height=float(pdf_page.rect.height),
                blocks=blocks,
                tables=tables,
            )
        )
    return Extraction(pages=pages, provider="local", took_ms=0)


def _split_markdown_pages(markdown: str) -> list[str]:
    parts = re.split(r"\n\s*-{3,}\s*\n|\n\s*<!--\s*page\s*\d+\s*-->\s*\n", markdown)
    return [p for p in parts if p.strip()]


async def _extract_llamaparse(data: bytes, filename: str) -> Extraction:
    async with httpx.AsyncClient(timeout=300) as client:
        upload = await client.post(
            "https://api.cloud.llamaindex.ai/api/parsing/upload",
            headers={"Authorization": f"Bearer {settings.llamacloud_api_key}"},
            files={"file": (filename, data, "application/pdf")},
        )
        upload.raise_for_status()
        job_id = upload.json()["id"]
        for _ in range(120):
            status = await client.get(
                f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}",
                headers={"Authorization": f"Bearer {settings.llamacloud_api_key}"},
            )
            status.raise_for_status()
            body = status.json()
            if body.get("status") == "SUCCESS":
                break
            if body.get("status") in {"ERROR", "CANCELED"}:
                raise RuntimeError(f"LlamaParse failed: {body}")
            await asyncio.sleep(2)
        else:
            raise TimeoutError("LlamaParse timed out")
        result = await client.get(
            f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}/result/markdown",
            headers={"Authorization": f"Bearer {settings.llamacloud_api_key}"},
        )
        result.raise_for_status()
        markdown = result.text
    pages = []
    for index, chunk in enumerate(_split_markdown_pages(markdown) or [markdown]):
        pages.append(
            Page(
                page=index + 1,
                text=normalize_text(chunk),
                width=612.0,
                height=792.0,
                blocks=[
                    PageBlock(
                        block_id=f"p{index + 1}-b0",
                        text=normalize_text(chunk),
                        bbox={"x0": 0, "y0": 0, "x1": 612, "y1": 792},
                    )
                ],
            )
        )
    return Extraction(pages=pages, provider="llamaparse", took_ms=0)


async def _extract_unstructured(data: bytes, filename: str) -> Extraction:
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            "https://api.unstructured.io/general/v0/general",
            headers={"unstructured-api-key": settings.unstructured_api_key or ""},
            files={"files": (filename, data, "application/pdf")},
            data={"strategy": "hi_res", "coordinates": "true"},
        )
        response.raise_for_status()
        elements: list[dict[str, Any]] = response.json()
    by_page: dict[int, list[dict[str, Any]]] = {}
    for element in elements:
        page = int(element.get("metadata", {}).get("page_number", 1))
        by_page.setdefault(page, []).append(element)
    pages = []
    for page_number in sorted(by_page):
        texts = [str(e.get("text", "")) for e in by_page[page_number]]
        text = normalize_text("\n\n".join(texts))
        pages.append(
            Page(
                page=page_number,
                text=text,
                width=612.0,
                height=792.0,
                blocks=[
                    PageBlock(
                        block_id=f"p{page_number}-b{i}",
                        text=normalize_text(str(e.get("text", ""))),
                        bbox={"x0": 0, "y0": 0, "x1": 612, "y1": 792},
                    )
                    for i, e in enumerate(by_page[page_number])
                    if str(e.get("text", "")).strip()
                ],
            )
        )
    return Extraction(pages=pages, provider="unstructured", took_ms=0)


async def extract_pdf(data: bytes, filename: str = "contract.pdf") -> Extraction:
    started = time.perf_counter()
    warnings: list[str] = []
    provider = settings.pdf_provider
    try:
        if provider == "llamaparse" and settings.llamacloud_api_key:
            extraction = await _extract_llamaparse(data, filename)
        elif provider == "unstructured" and settings.unstructured_api_key:
            extraction = await _extract_unstructured(data, filename)
        else:
            extraction = await asyncio.to_thread(_extract_local, data)
            if provider != "local":
                warnings.append(f"{provider} not configured; fell back to local extraction")
    except Exception as exc:  # noqa: BLE001 - degrade to local
        logger.warning(
            "hosted extraction failed; using local", extra={"context": {"error": str(exc)}}
        )
        warnings.append(f"hosted extraction failed: {exc}")
        extraction = await asyncio.to_thread(_extract_local, data)
    extraction.took_ms = int((time.perf_counter() - started) * 1000)
    extraction.warnings.extend(warnings)
    if extraction.page_count > settings.max_pages:
        raise ValueError(f"document exceeds {settings.max_pages} page limit")
    return extraction
