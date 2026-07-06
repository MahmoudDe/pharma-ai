"""Unified page segmentation: formula artifacts + prose blocks from one pass."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.formulation.parsers import parse_formula_block
from app.formulation.parsers.column_wt import _ING_HEADER
from app.formulation.parsers.procedure import parse_procedure
from app.formulation.parsers.reference_filter import is_reference_table_block
from app.formulation.schemas import IngredientLine
from app.ingestion.chunk import _split_into_blocks
from app.ingestion.extract import PageRecord
from app.ingestion.metadata import _EMBEDDED_FORMULA_NAME, infer_product_types, text_hash

_FORMULA_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000002")
_VECTOR_TEXT_MAX = 4000
_PROCEDURE_EXCERPT_STEPS = 5

_TITLE_FROM_BLOCK = re.compile(
    r"(?:^|\n)([A-Z][^\n]{2,80}(?:Shampoo|Sham[Dd]oo|Shamwoo|Cream|Lotion|Bath|Formula|Formulation)[^\n]*)",
    re.I,
)
_PRODUCT_TITLE = re.compile(
    r"(?:^|\n)("
    r"Prescription\s+[\d.]+\s+[^\n]{5,80}|"
    r"Anti[- ]?Persp[^\n]{2,60}|"
    r"Antiperspirant[^\n]{2,60}|"
    r"Deodorant[^\n]{2,60}|"
    r"Moisturis[^\n]{2,60}|"
    r"[^\n]{2,60}(?:Roll-On|Stick|Sunscreen)[^\n]*"
    r")",
    re.I,
)

_JUNK_FORMULA_NAME = re.compile(
    r"(?:"
    r"^SOURCE:|^Cosmetic and Toiletry|^Raw Materials:|^Wt%$|"
    r"^Formula for Lotion|^\[TABLE\]|^Combine items|^This low VOC|"
    r"^0\.\d+%|^\d+\.\d+%\s"
    r")",
    re.I,
)
_LOW_YIELD_METHODS = frozenset(
    {"wtg", "column_wt", "inline_wt", "part_function", "part_labeled", "phase_inline"}
)


def _is_junk_formula_name(name: str) -> bool:
    stripped = name.strip()
    if not stripped or _JUNK_FORMULA_NAME.search(stripped):
        return True
    if len(stripped) > 100 or stripped.count("|") >= 2:
        return True
    return False


@dataclass(slots=True)
class FormulaArtifact:
    id: str
    doc_id: str
    doc_title: str
    pdf_page: int
    printed_page: int | None
    formula_name: str
    product_types: list[str]
    ingredients: list[IngredientLine]
    procedure: list[str]
    raw_text: str
    vector_text: str
    extraction_method: str
    confidence: float
    text_hash: str = ""


@dataclass(slots=True)
class ProseSegment:
    text: str
    section_title: str | None = None


@dataclass(slots=True)
class PageSegments:
    formulas: list[FormulaArtifact] = field(default_factory=list)
    prose_blocks: list[ProseSegment] = field(default_factory=list)


def formulation_id_for(
    doc_id: str,
    formula_name: str,
    pdf_page: int,
    raw_text: str,
) -> str:
    key = f"{doc_id}:{formula_name}:{pdf_page}:{text_hash(raw_text)}"
    return str(uuid.uuid5(_FORMULA_NAMESPACE, key))


def _title_from_block(block_text: str, section: str | None) -> str:
    if re.search(r"pre-blended", block_text, re.I):
        return "Baby Shampoo (pre-blended concentrate)"
    for pattern in (_PRODUCT_TITLE, _EMBEDDED_FORMULA_NAME, _TITLE_FROM_BLOCK):
        match = pattern.search(block_text)
        if match:
            title = match.group(1).strip().split("\n")[0][:120]
            if re.match(r"^\d+$", title):
                continue
            if not re.search(r"\bcosmetic and\b", title, re.I):
                return title
    embedded = _EMBEDDED_FORMULA_NAME.search(block_text)
    if embedded:
        return embedded.group(1).strip()[:120]
    if section and len(section.strip()) < 120:
        sec = section.strip().split("\n")[0]
        if not re.search(r"\bproducts?\s*$", sec, re.I) and not re.search(
            r"\bcosmetic and\b", sec, re.I
        ):
            return sec
    match = _TITLE_FROM_BLOCK.search(block_text)
    if match:
        return match.group(1).strip().split("\n")[0][:120]
    first = next((ln.strip() for ln in block_text.splitlines() if ln.strip()), "")
    return (first[:120] if first else "Untitled formula")


def build_vector_text(
    formula_name: str,
    product_types: list[str],
    ingredients: list[IngredientLine],
    procedure: list[str],
) -> str:
    lines = [f"Formula: {formula_name}"]
    if product_types:
        lines.append(f"Product types: {', '.join(product_types)}")
    lines.append(f"Ingredients ({len(ingredients)}):")
    for ing in ingredients:
        label = ing.normalized_name or ing.raw_name
        amount = ""
        if ing.amount is not None:
            amount = f" {ing.amount}"
            if ing.unit:
                amount += f" {ing.unit}"
        phase = f" phase {ing.phase}" if ing.phase else ""
        lines.append(f"- {label}{amount}{phase}".strip())
    if procedure:
        lines.append("Procedure:")
        for i, step in enumerate(procedure[:_PROCEDURE_EXCERPT_STEPS], start=1):
            lines.append(f"{i}. {step}")
    text = "\n".join(lines)
    return text[:_VECTOR_TEXT_MAX]


def _artifact_from_block(
    page: PageRecord,
    block_text: str,
    section: str | None,
) -> FormulaArtifact | None:
    if is_reference_table_block(block_text):
        return None
    ingredients, method, confidence = parse_formula_block(block_text)
    procedure = parse_procedure(block_text)
    name = _title_from_block(block_text, section)
    product_types = infer_product_types(block_text, name)

    if len(ingredients) < 3:
        return None
    if method in _LOW_YIELD_METHODS and len(ingredients) < 3:
        return None
    if re.search(r"\(continued\)", name, re.I) and len(ingredients) < 4:
        return None
    if name.strip().startswith("[TABLE]") or _is_junk_formula_name(name):
        return None

    fid = formulation_id_for(page.doc_id, name, page.pdf_page, block_text)
    vector_text = build_vector_text(name, product_types, ingredients, procedure)
    return FormulaArtifact(
        id=fid,
        doc_id=page.doc_id,
        doc_title=page.doc_title,
        pdf_page=page.pdf_page,
        printed_page=page.printed_page,
        formula_name=name,
        product_types=product_types,
        ingredients=ingredients,
        procedure=procedure,
        raw_text=block_text,
        vector_text=vector_text,
        extraction_method=method,
        confidence=confidence if ingredients else 0.45,
        text_hash=text_hash(block_text),
    )


_SUBFORMULA_BOUNDARY = re.compile(
    r"(?=\n(?:"
    r"Baby|Anti|Hand|Tube|Clear|Natural|Deodorant|Moisturis|Prescription\s+\d"
    r")[^\n]{0,80}\n|"
    r"\n(?:Anti[- ]?Persp|Antiperspirant|Antiuers|Deodorant)\b[^\n]*\n|"
    r"\nShampoo\s*\n\s*Starting\s+formulation|"
    r"\nFormulation\s+\d+\s+[A-Z]{2}\s*\n)",
    re.I,
)


def _split_formula_subblocks(block_text: str) -> list[str]:
    """Split a page block that contains multiple distinct formulas."""
    wt_count = len(re.findall(r"\bwt[%\$8]\s*", block_text, re.I))
    ing_headers = len(re.findall(r"(?:inqredients?|puredients?)\s*:", block_text, re.I))
    if wt_count < 2 and ing_headers < 2:
        return [block_text]

    parts = _SUBFORMULA_BOUNDARY.split(block_text)
    if len(parts) <= 1:
        # Split on repeated ingredient headers when multiple wt% columns exist
        if ing_headers >= 2:
            parts = re.split(
                r"(?=\n(?:Anti[- ]?Persp|Deodorant|Antiperspirant|Moisturis)[^\n]+\n)",
                block_text,
                flags=re.I,
            )
    return [
        p.strip()
        for p in parts
        if p.strip()
        and (_ING_HEADER.search(p) or re.search(r"\bwt[%\$8]\s*", p, re.I))
        and not is_reference_table_block(p)
    ] or [block_text]


_PRESCRIPTION_CHUNK = re.compile(
    r"(?:^|\n)(Prescription\s+\d+(?:\.\d+)?\s+[^\n]+)",
    re.I | re.M,
)


def _prescription_chunks(block_text: str) -> list[str]:
    """Split text into Prescription-sized chunks for Japan book layouts."""
    matches = list(_PRESCRIPTION_CHUNK.finditer(block_text))
    if not matches:
        return []
    chunks: list[str] = []
    for i, match in enumerate(matches):
        start = match.start(1) if match.lastindex else match.start()
        end = matches[i + 1].start(1) if i + 1 < len(matches) else len(block_text)
        chunk = block_text[start:end].strip()
        if len(chunk) < 80:
            continue
        if not re.search(r"\bIngredient\b|%\s*\(\s*100", chunk, re.I):
            continue
        chunks.append(chunk)
    return chunks


def _merge_prescription_header_blocks(
    blocks: list[tuple[str, bool, str | None]],
) -> list[tuple[str, bool, str | None]]:
    """Glue 'Prescription N.N title' stubs to the following ingredient table block."""
    if not blocks:
        return blocks
    merged: list[tuple[str, bool, str | None]] = []
    i = 0
    while i < len(blocks):
        text, is_formula, section = blocks[i]
        if (
            i + 1 < len(blocks)
            and re.search(r"\bPrescription\s+\d", text, re.I)
            and re.search(r"\bIngredient\b|%\s*\(\s*100", blocks[i + 1][0], re.I)
        ):
            ntext, _, nsec = blocks[i + 1]
            combined = f"{text.strip()}\n{ntext.strip()}"
            merged.append((combined, True, section or nsec))
            i += 2
            continue
        merged.append((text, is_formula, section))
        i += 1
    return merged


def segment_page(page: PageRecord, section_hint: str | None = None) -> PageSegments:
    """Split one page into formula artifacts and prose blocks."""
    result = PageSegments()
    current_section = section_hint

    def _try_add_formula(
        block_text: str,
        section: str | None,
        seen_hashes: set[str],
    ) -> bool:
        found = False
        subblocks = _split_formula_subblocks(block_text)
        for sub in subblocks:
            artifact = _artifact_from_block(page, sub, section or current_section)
            if artifact is not None and artifact.text_hash not in seen_hashes:
                seen_hashes.add(artifact.text_hash)
                result.formulas.append(artifact)
                found = True
        return found

    blocks = _merge_prescription_header_blocks(
        list(_split_into_blocks(page.text, current_section))
    )
    seen_hashes: set[str] = set()
    for block_text, is_formula, section in blocks:
        if section:
            current_section = section
        if is_formula:
            if not _try_add_formula(block_text, section or current_section, seen_hashes):
                result.prose_blocks.append(
                    ProseSegment(text=block_text, section_title=section or current_section)
                )
        else:
            if block_text.strip():
                if not _try_add_formula(block_text, section or current_section, seen_hashes):
                    result.prose_blocks.append(
                        ProseSegment(text=block_text, section_title=section or current_section)
                    )

    for rx_chunk in _prescription_chunks(page.text):
        artifact = _artifact_from_block(page, rx_chunk, current_section)
        if artifact is not None and artifact.text_hash not in seen_hashes:
            seen_hashes.add(artifact.text_hash)
            result.formulas.append(artifact)

    return result
