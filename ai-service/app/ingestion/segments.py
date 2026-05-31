"""Unified page segmentation: formula artifacts + prose blocks from one pass."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.formulation.parsers import parse_formula_block
from app.formulation.parsers.column_wt import _ING_HEADER
from app.formulation.parsers.procedure import parse_procedure
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
    embedded = _EMBEDDED_FORMULA_NAME.search(block_text)
    if embedded:
        return embedded.group(1).strip()[:120]
    if section and len(section.strip()) < 120:
        sec = section.strip().split("\n")[0]
        if not re.search(r"\bproducts?\s*$", sec, re.I):
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
    ingredients, method, confidence = parse_formula_block(block_text)
    procedure = parse_procedure(block_text)
    name = _title_from_block(block_text, section)
    product_types = infer_product_types(block_text, name)

    if len(ingredients) < 2:
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
    r"(?=\n(?:Baby|Anti|Hand|Tube|Clear|Natural)\s+[^\n]{2,70}\s*\n|"
    r"\nShampoo\s*\n\s*Starting\s+formulation)",
    re.I,
)


def _split_formula_subblocks(block_text: str) -> list[str]:
    """Split a page block that contains multiple distinct formulas."""
    if len(re.findall(r"\bwt[%\$]\s*", block_text, re.I)) < 2:
        return [block_text]
    parts = _SUBFORMULA_BOUNDARY.split(block_text)
    return [
        p.strip()
        for p in parts
        if p.strip()
        and (_ING_HEADER.search(p) or re.search(r"\bwt[%\$]\s*", p, re.I))
    ]


def segment_page(page: PageRecord, section_hint: str | None = None) -> PageSegments:
    """Split one page into formula artifacts and prose blocks."""
    result = PageSegments()
    current_section = section_hint

    for block_text, is_formula, section in _split_into_blocks(page.text, current_section):
        if section:
            current_section = section
        if is_formula:
            subblocks = _split_formula_subblocks(block_text)
            for sub in subblocks:
                artifact = _artifact_from_block(page, sub, section or current_section)
                if artifact is not None:
                    result.formulas.append(artifact)
            else:
                result.prose_blocks.append(
                    ProseSegment(text=block_text, section_title=section or current_section)
                )
        else:
            if block_text.strip():
                result.prose_blocks.append(
                    ProseSegment(text=block_text, section_title=section or current_section)
                )

    return result
