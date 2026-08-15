from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from app.ingestion.extract import PageRecord
from app.ingestion.metadata import (
    chunk_type_for,
    detect_section_heading,
    infer_product_types,
    is_teaser_block,
    text_hash,
)
from app.ingestion.formula_detect import is_formula_chunk


@dataclass(slots=True)
class Chunk:
    doc_id: str
    doc_title: str
    pdf_page: int
    printed_page: int | None
    chunk_index: int
    text: str
    is_formula: bool = False
    chunk_type: str = "prose"
    section_title: str | None = None
    product_types: list[str] = field(default_factory=list)
    text_hash: str = ""
    formulation_id: str | None = None
    formula_name: str | None = None
    ingredient_count: int = 0
    extraction_confidence: float = 0.0
    extraction_method: str = ""

    @property
    def page(self) -> int:
        return self.pdf_page


_FORMULA_HEADER = re.compile(
    r"^\s*(\[TABLE\]|ingredients?|inqredients?|raw materials|formula|formulation|parts|composition|w/w|wt\.?|wtg)\b",
    re.IGNORECASE | re.MULTILINE,
)
_WT_COLUMN_HEADER = re.compile(r"^\s*Wt[%\$]?\s*$", re.I)
_INGREDIENTS_HEADER = re.compile(
    r"(?:inqredients?|insredients?|ingredients?|raw materials)\s*:",
    re.I,
)
_AMOUNT_ONLY_LINE = re.compile(
    r"^\s*(?:to\s+100(?:\.\d+)?|qs(?:\s+to\s+100(?:\.\d+)?)?|q\.?\s*s\.?|\d+(?:\.\d+)?)\s*\.?\s*$",
    re.I,
)
_FORMULA_LINE = re.compile(
    r"%|w/w|wt\.?\s*%|\bRecipe\s*:|\|\s*\d|\bPart\s+[A-Z]\b|^\s*[A-Z]\s+[A-Za-z].{3,40}$",
    re.IGNORECASE | re.MULTILINE,
)
_FORMULA_LINE_WITH_AMOUNT = re.compile(
    r"[A-Za-z].*\b\d+\.\d{2}\b|\b\d+\.\d{2}\b.*[A-Za-z]",
    re.IGNORECASE,
)
_NEW_SECTION = re.compile(
    r"^[A-Z][^\n]{2,50}(?:Shampoo|Sham[Dd]oo|Shamwoo|Cream|Lotion|Formula|Formulation)\s*$",
)


def _is_formula_block(text: str) -> bool:
    if "[TABLE]" in text:
        return True
    return is_formula_chunk(text)


def _is_formula_title_stub(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or len(lines) > 4 or len(text) > 400:
        return False
    joined = " ".join(lines)
    return bool(
        re.search(r"Sham[Dd]oo|Shampoo|Cream|Lotion|Formulation", joined, re.I)
        and not re.search(r"\bRecipe\s*:", joined, re.I)
        and not re.search(r"\bwt[bgs$%]?\b", joined, re.I)
    )


def _block_has_ingredient_column(text: str) -> bool:
    lower = text.lower()
    return bool(
        re.search(r"(?:inqredients?|ingredients?|raw materials)\s*:", lower)
        or re.search(r"\bto\s+100\b", lower)
    )


def _block_is_amount_column(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    return all(
        _AMOUNT_ONLY_LINE.match(ln) or _WT_COLUMN_HEADER.match(ln) for ln in lines
    )


def _ends_column_layout(text: str) -> bool:
    if not text.strip():
        return False
    last = text.rstrip().splitlines()[-1].strip()
    return bool(
        re.match(r"^(?:Blending )?Procedure\s*:", last, re.I)
        or re.match(r"^Formulation No\.?", last, re.I)
        or last.upper().startswith("SOURCE:")
    )


def _merge_formula_fragments(
    blocks: list[tuple[str, bool, str | None]],
) -> list[tuple[str, bool, str | None]]:
    """Glue title/Wt% stubs to the following ingredient-column block."""
    if not blocks:
        return blocks
    merged: list[tuple[str, bool, str | None]] = []
    i = 0
    while i < len(blocks):
        text, is_formula, section = blocks[i]
        while i + 1 < len(blocks):
            ntext, nf, nsec = blocks[i + 1]
            tail = text.rstrip().splitlines()[-1].strip() if text.strip() else ""
            should_merge = (
                _block_has_ingredient_column(text)
                and (
                    _block_is_amount_column(ntext)
                    or _is_formula_title_stub(text)
                    or _WT_COLUMN_HEADER.match(tail)
                )
            ) or (
                _block_has_ingredient_column(ntext)
                and (_block_is_amount_column(text) or _is_formula_title_stub(text))
            )
            if should_merge:
                text = f"{text.strip()}\n\n{ntext.strip()}"
                is_formula = True
                section = section or nsec
                i += 1
                continue
            break
        merged.append((text, is_formula, section))
        i += 1
    return merged


def _merge_teaser_blocks(blocks: list[tuple[str, bool, str | None]]) -> list[tuple[str, bool, str | None]]:
    """Merge title/teaser blocks into the following formula block."""
    if not blocks:
        return blocks
    merged: list[tuple[str, bool, str | None]] = []
    i = 0
    while i < len(blocks):
        text, is_formula, section = blocks[i]
        next_is_formula = i + 1 < len(blocks) and (
            blocks[i + 1][1] or _is_formula_block(blocks[i + 1][0])
        )
        if not is_formula and i + 1 < len(blocks) and next_is_formula and (
            is_teaser_block(text) or _is_formula_title_stub(text)
        ):
            next_text, _, next_section = blocks[i + 1]
            stub_title = next(
                (ln.strip() for ln in text.splitlines() if ln.strip() and _NEW_SECTION.match(ln.strip())),
                None,
            )
            title = stub_title or section or next_section
            combined = f"{text.strip()}\n\n{next_text.strip()}"
            merged.append((combined, True, title))
            i += 2
            continue
        merged.append((text, is_formula, section))
        i += 1
    return merged


def _split_into_blocks(text: str, section_hint: str | None) -> list[tuple[str, bool, str | None]]:
    """Split page text into (block_text, is_formula, section_title) triples."""
    lines = text.split("\n")
    blocks: list[tuple[str, bool, str | None]] = []
    current: list[str] = []
    current_is_formula = False
    current_section = section_hint

    def flush() -> None:
        nonlocal current, current_is_formula, current_section
        if current:
            block_text = "\n".join(current).strip()
            if block_text:
                is_f = current_is_formula or _is_formula_block(block_text)
                blocks.append((block_text, is_f, current_section))
        current = []
        current_is_formula = False

    in_table = False
    in_formula_section = False
    in_column_layout = False

    for line in lines:
        heading = detect_section_heading(line)
        if heading:
            flush()
            current_section = heading
            in_formula_section = False
            in_column_layout = False
            current = [line]
            continue

        if line.strip() == "[TABLE]":
            flush()
            in_table = True
            in_formula_section = True
            current = [line]
            current_is_formula = True
            continue
        if line.strip() == "[/TABLE]":
            current.append(line)
            flush()
            in_table = False
            continue
        if in_table:
            current.append(line)
            continue

        stripped = line.strip()
        if _NEW_SECTION.match(stripped):
            flush()
            current_section = stripped
            in_formula_section = False
            in_column_layout = False
            current = [line]
            continue

        if re.match(r"^(?:Blending )?Procedure\s*:", stripped, re.I):
            in_column_layout = False
        elif re.match(r"^Formulation No\.?", stripped, re.I) or stripped.upper().startswith(
            "SOURCE:"
        ):
            in_column_layout = False
        elif _INGREDIENTS_HEADER.search(stripped) or _WT_COLUMN_HEADER.match(stripped):
            in_column_layout = True
            in_formula_section = True

        if in_column_layout:
            current.append(line)
            current_is_formula = True
            in_formula_section = True
            if _ends_column_layout("\n".join(current)):
                flush()
                in_column_layout = False
            continue

        line_is_formula = bool(_FORMULA_LINE.search(line)) or bool(
            _FORMULA_HEADER.match(stripped)
        )
        if not line_is_formula and _AMOUNT_ONLY_LINE.match(stripped):
            line_is_formula = False
        elif _AMOUNT_ONLY_LINE.match(stripped) or _FORMULA_LINE_WITH_AMOUNT.search(line):
            line_is_formula = True
        if _WT_COLUMN_HEADER.match(stripped):
            line_is_formula = False
        is_procedure = bool(re.match(r"^\s*\d*\.?\s*Procedure\s*:", stripped, re.I))

        if line_is_formula and not current_is_formula and current and not is_procedure:
            flush()
            current_is_formula = True
            in_formula_section = True
        elif (
            not line_is_formula
            and not is_procedure
            and current_is_formula
            and current
            and not stripped
        ):
            flush()
            in_formula_section = False
        elif is_procedure and in_formula_section:
            pass
        elif not line_is_formula and not is_procedure and current_is_formula and current:
            if not stripped and len(current) > 3:
                flush()
                in_formula_section = False

        current.append(line)
        if line_is_formula or is_procedure:
            current_is_formula = True
            in_formula_section = True

    flush()
    if not blocks:
        whole = text.strip()
        if whole:
            blocks.append((whole, _is_formula_block(whole), section_hint))
    return _merge_formula_fragments(_merge_teaser_blocks(blocks))


def _split_prose(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be in [0, size)")
    if len(text) <= size:
        return [text]
    step = size - overlap
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        out.append(text[start:end])
        if end == len(text):
            break
        start += step
    return out


def _make_chunk(
    page: PageRecord,
    chunk_index: int,
    text: str,
    *,
    is_formula: bool,
    section_title: str | None,
    formulation_id: str | None = None,
    product_types: list[str] | None = None,
    formula_name: str | None = None,
    ingredient_count: int = 0,
    extraction_confidence: float = 0.0,
    extraction_method: str = "",
) -> Chunk:
    ctype = chunk_type_for(text, is_formula)
    products = product_types if product_types is not None else infer_product_types(text, section_title)
    return Chunk(
        doc_id=page.doc_id,
        doc_title=page.doc_title,
        pdf_page=page.pdf_page,
        printed_page=page.printed_page,
        chunk_index=chunk_index,
        text=text,
        is_formula=is_formula,
        chunk_type=ctype,
        section_title=section_title,
        product_types=products,
        text_hash=text_hash(text),
        formulation_id=formulation_id,
        formula_name=formula_name,
        ingredient_count=ingredient_count,
        extraction_confidence=extraction_confidence,
        extraction_method=extraction_method,
    )


FORMULA_MAX_CHARS = 6000


def chunk_pages(
    pages: Iterable[PageRecord],
    *,
    size: int,
    overlap: int,
) -> Iterator[Chunk]:
    last_doc: str | None = None
    chunk_index = 0
    page_section: str | None = None

    for page in pages:
        if page.doc_id != last_doc:
            chunk_index = 0
            last_doc = page.doc_id
            page_section = None

        for block_text, is_formula, section in _split_into_blocks(page.text, page_section):
            if section:
                page_section = section
            if is_formula:
                if len(block_text) <= FORMULA_MAX_CHARS:
                    pieces = [block_text]
                else:
                    pieces = _split_prose(block_text, FORMULA_MAX_CHARS, overlap=200)
                for piece in pieces:
                    yield _make_chunk(
                        page,
                        chunk_index,
                        piece,
                        is_formula=True,
                        section_title=section or page_section,
                    )
                    chunk_index += 1
            else:
                for piece in _split_prose(block_text, size=size, overlap=overlap):
                    yield _make_chunk(
                        page,
                        chunk_index,
                        piece,
                        is_formula=False,
                        section_title=section or page_section,
                    )
                    chunk_index += 1
