"""Build chunks + formulation records from unified page segmentation."""
from __future__ import annotations

from typing import Iterator

from app.formulation.schemas import FormulationRecord
from app.ingestion.chunk import FORMULA_MAX_CHARS, Chunk, _make_chunk, _split_prose
from app.ingestion.extract import PageRecord
from app.ingestion.segments import FormulaArtifact, segment_page


def artifact_to_record(artifact: FormulaArtifact) -> FormulationRecord:
    return FormulationRecord(
        id=artifact.id,
        name=artifact.formula_name,
        product_types=artifact.product_types,
        doc_id=artifact.doc_id,
        doc_title=artifact.doc_title,
        pdf_page=artifact.pdf_page,
        printed_page=artifact.printed_page,
        source_text=artifact.raw_text[:8000],
        ingredients=artifact.ingredients,
        procedure=artifact.procedure,
        vector_text=artifact.vector_text,
        extraction_method=artifact.extraction_method,  # type: ignore[arg-type]
        confidence=artifact.confidence,
    )


def _merge_formulation(
    store: dict[str, FormulationRecord],
    record: FormulationRecord,
) -> None:
    prev = store.get(record.id)
    if prev is None or len(record.ingredients) > len(prev.ingredients):
        store[record.id] = record


def _formula_chunk_from_artifact(page: PageRecord, artifact: FormulaArtifact, chunk_index: int) -> Chunk:
    text = artifact.vector_text
    if len(text) > FORMULA_MAX_CHARS:
        text = text[:FORMULA_MAX_CHARS]
    return _make_chunk(
        page,
        chunk_index,
        text,
        is_formula=True,
        section_title=artifact.formula_name,
        formulation_id=artifact.id,
        product_types=artifact.product_types,
        formula_name=artifact.formula_name,
        ingredient_count=len(artifact.ingredients),
        extraction_confidence=artifact.confidence,
        extraction_method=artifact.extraction_method,
    )


def process_pages(
    pages: list[PageRecord],
    *,
    prose_size: int,
    prose_overlap: int,
) -> tuple[list[FormulationRecord], list[Chunk]]:
    """Segment pages into formulations (SQLite) and chunks (Qdrant)."""
    formulation_by_id: dict[str, FormulationRecord] = {}
    formula_chunks_by_id: dict[str, Chunk] = {}
    prose_chunks: list[Chunk] = []
    last_doc: str | None = None
    chunk_index = 0
    page_section: str | None = None

    for page in pages:
        if page.doc_id != last_doc:
            chunk_index = 0
            last_doc = page.doc_id
            page_section = None

        segments = segment_page(page, page_section)
        for artifact in segments.formulas:
            _merge_formulation(formulation_by_id, artifact_to_record(artifact))
            chunk = _formula_chunk_from_artifact(page, artifact, chunk_index)
            prev = formula_chunks_by_id.get(artifact.id)
            if prev is None or chunk.ingredient_count > prev.ingredient_count:
                formula_chunks_by_id[artifact.id] = chunk
            chunk_index += 1

        for prose in segments.prose_blocks:
            if prose.section_title:
                page_section = prose.section_title
            for piece in _split_prose(prose.text, size=prose_size, overlap=prose_overlap):
                prose_chunks.append(
                    _make_chunk(
                        page,
                        chunk_index,
                        piece,
                        is_formula=False,
                        section_title=prose.section_title or page_section,
                    )
                )
                chunk_index += 1

    chunks = list(formula_chunks_by_id.values()) + prose_chunks
    return list(formulation_by_id.values()), chunks


def iter_unified_ingest(
    pages: Iterator[PageRecord],
    *,
    prose_size: int,
    prose_overlap: int,
) -> Iterator[tuple[list[FormulationRecord], list[Chunk]]]:
    """Batch pages by document for memory efficiency."""
    buffer: list[PageRecord] = []
    current_doc: str | None = None
    for page in pages:
        if current_doc is not None and page.doc_id != current_doc:
            yield process_pages(buffer, prose_size=prose_size, prose_overlap=prose_overlap)
            buffer = []
        current_doc = page.doc_id
        buffer.append(page)
    if buffer:
        yield process_pages(buffer, prose_size=prose_size, prose_overlap=prose_overlap)
