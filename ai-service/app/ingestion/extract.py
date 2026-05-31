"""PDF -> per-page text using PyMuPDF with table extraction and printed page detection."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import fitz


logger = logging.getLogger(__name__)
_LAYOUT_ACTIVATED = False


def _activate_layout_extraction() -> None:
    """Use pymupdf_layout when installed for better reading order."""
    global _LAYOUT_ACTIVATED
    if _LAYOUT_ACTIVATED:
        return
    try:
        import pymupdf.layout  # type: ignore[import-untyped]

        pymupdf.layout.activate()
        _LAYOUT_ACTIVATED = True
        logger.info("PyMuPDF layout extraction enabled (pymupdf.layout)")
    except ImportError:
        logger.debug("pymupdf-layout not installed; using default text extraction")


@dataclass(slots=True)
class PageRecord:
    doc_id: str
    doc_title: str
    pdf_page: int
    printed_page: int | None
    text: str

    @property
    def page(self) -> int:
        return self.pdf_page


_WHITESPACE_RE = re.compile(r"[ \t\u00a0]+")
_NEWLINES_RE = re.compile(r"\n{3,}")
_PRINTED_PAGE_PATTERNS = [
    re.compile(r"^\s*(\d{1,4})\s*$"),
    re.compile(r"(?:page|p\.)\s*(\d{1,4})", re.IGNORECASE),
    re.compile(r"-\s*(\d{1,4})\s*-"),
    re.compile(r"^\s*(\d{1,4})\s*/\s*\d{1,4}\s*$"),
]


def _normalize(text: str) -> str:
    text = _WHITESPACE_RE.sub(" ", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    return text.strip()


def doc_id_from_path(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")


def _detect_printed_page(page: fitz.Page) -> int | None:
    rect = page.rect
    h = rect.height
    margin = h * 0.08
    header_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + margin)
    footer_rect = fitz.Rect(rect.x0, rect.y1 - margin, rect.x1, rect.y1)
    candidates: list[int] = []
    for band in (header_rect, footer_rect):
        band_text = page.get_text("text", clip=band) or ""
        for line in band_text.splitlines():
            line = line.strip()
            if not line or len(line) > 30:
                continue
            for pattern in _PRINTED_PAGE_PATTERNS:
                m = pattern.search(line)
                if m:
                    num = int(m.group(1))
                    if 1 <= num <= 9999:
                        candidates.append(num)
    if not candidates:
        return None
    # Prefer footer-like numbers (last band often footer); use most common
    return max(set(candidates), key=candidates.count)


def _table_to_text(page: fitz.Page) -> str:
    lines: list[str] = []
    try:
        finder = page.find_tables()
        tables = finder.tables if finder else []
    except Exception as exc:
        logger.debug("find_tables failed: %s", exc)
        return ""

    for table in tables:
        try:
            data = table.extract()
        except Exception:
            continue
        if not data:
            continue
        lines.append("[TABLE]")
        for row in data:
            cells = [str(c).strip() if c is not None else "" for c in row]
            if any(cells):
                lines.append(" | ".join(cells))
        lines.append("[/TABLE]")
    return "\n".join(lines)


def _blocks_to_text(page: fitz.Page) -> str:
    blocks = page.get_text("blocks") or []
    sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
    parts: list[str] = []
    for block in sorted_blocks:
        if len(block) < 5:
            continue
        text = str(block[4]).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _extract_page_text(page: fitz.Page) -> str:
    table_text = _table_to_text(page)
    block_text = _blocks_to_text(page)
    plain = page.get_text("text") or ""

    if table_text and block_text:
        merged = f"{table_text}\n\n{block_text}"
    elif table_text:
        merged = table_text
    elif block_text:
        merged = block_text
    else:
        merged = plain

    return _normalize(merged)


def extract_pdf(path: Path) -> Iterator[PageRecord]:
    """Yield one PageRecord per non-empty page in `path`."""
    _activate_layout_extraction()
    doc_id = doc_id_from_path(path)
    doc_title = path.stem

    with fitz.open(path) as pdf:
        for page_index in range(pdf.page_count):
            page = pdf.load_page(page_index)
            normalized = _extract_page_text(page)
            if len(normalized) < 40:
                continue
            yield PageRecord(
                doc_id=doc_id,
                doc_title=doc_title,
                pdf_page=page_index + 1,
                printed_page=_detect_printed_page(page),
                text=normalized,
            )


def discover_pdfs(docs_dir: Path) -> list[Path]:
    pdfs = sorted(p for p in docs_dir.glob("*.pdf") if p.is_file())
    logger.info("Found %d PDF(s) in %s", len(pdfs), docs_dir)
    return pdfs
