from __future__ import annotations

import random
from dataclasses import dataclass

from app.config import get_settings
from app.formulation.store import list_formulations
from app.ingestion.index import get_client


@dataclass(slots=True)
class CorpusExcerpt:
    source: str
    doc_title: str
    pdf_page: int | None
    product_types: list[str]
    text: str


def _formula_excerpts(limit: int = 25) -> list[CorpusExcerpt]:
    records = list_formulations(limit=400)
    records = [r for r in records if len(r.ingredients) >= 3]
    records.sort(key=lambda r: (len(r.ingredients), r.confidence), reverse=True)

    seen_names: set[str] = set()
    out: list[CorpusExcerpt] = []
    for rec in records:
        key = rec.name.lower()[:60]
        if key in seen_names:
            continue
        seen_names.add(key)
        ing_lines = [
            f"- {i.raw_name}" + (f" {i.amount} {i.unit}" if i.amount is not None else "")
            for i in rec.ingredients[:12]
        ]
        text = f"Formula: {rec.name}\nProduct types: {', '.join(rec.product_types)}\n" + "\n".join(
            ing_lines
        )
        out.append(
            CorpusExcerpt(
                source="sqlite",
                doc_title=rec.doc_title or rec.doc_id,
                pdf_page=rec.pdf_page,
                product_types=list(rec.product_types),
                text=text[:1200],
            )
        )
        if len(out) >= limit:
            break
    return out


def _vector_excerpts(limit: int = 20, *, seed: int = 42) -> list[CorpusExcerpt]:
    settings = get_settings()
    client = get_client()
    collected: list[CorpusExcerpt] = []
    offset = None
    pool: list[CorpusExcerpt] = []

    while True:
        points, offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=128,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        for point in points:
            payload = point.payload or {}
            text = str(payload.get("text", "")).strip()
            if len(text) < 80:
                continue
            products = payload.get("product_types") or []
            if isinstance(products, list):
                product_list = [str(p) for p in products]
            else:
                product_list = []
            pool.append(
                CorpusExcerpt(
                    source="qdrant",
                    doc_title=str(payload.get("doc_title", "")),
                    pdf_page=int(payload.get("pdf_page") or 0) or None,
                    product_types=product_list,
                    text=text[:1400],
                )
            )
        if offset is None:
            break

    if not pool:
        return []

    rng = random.Random(seed)
    rng.shuffle(pool)
    seen_hash: set[str] = set()
    for item in pool:
        key = item.text[:200].lower()
        if key in seen_hash:
            continue
        seen_hash.add(key)
        collected.append(item)
        if len(collected) >= limit:
            break
    return collected


def gather_book_excerpts(*, formula_limit: int = 25, prose_limit: int = 20) -> list[CorpusExcerpt]:
    """Blend structured formulas and vector chunks from the ingested books."""
    formulas = _formula_excerpts(formula_limit)
    vectors = _vector_excerpts(prose_limit)
    return formulas + vectors


def format_excerpts_for_prompt(excerpts: list[CorpusExcerpt]) -> str:
    blocks: list[str] = []
    for i, ex in enumerate(excerpts, start=1):
        tags = ", ".join(ex.product_types) if ex.product_types else "general"
        page = ex.pdf_page if ex.pdf_page is not None else "?"
        blocks.append(
            f"[PASSAGE {i}] ({ex.source}, {ex.doc_title}, page {page}, tags: {tags})\n{ex.text}"
        )
    return "\n\n".join(blocks)
