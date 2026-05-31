from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.ingestion.formula_detect import is_formula_chunk
from app.retrieval.search import search


router = APIRouter(prefix="/debug", tags=["debug"])


def _retrieval_enabled() -> bool:
    settings = get_settings()
    if settings.debug_retrieval:
        return True
    return settings.app_env.lower() != "production"


@router.get("/retrieve")
def debug_retrieve(
    q: str = Query(..., min_length=1, description="Query string"),
    top_k: int = Query(10, ge=1, le=30),
    formula_only: bool = Query(False, description="Filter to formula chunks only"),
    product_type: str | None = Query(None, description="e.g. baby, shampoo, anti_dandruff"),
) -> dict:
    if not _retrieval_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    chunks = search(q, top_k=top_k, formula_only=formula_only, product_type=product_type)
    return {
        "query": q,
        "formula_only": formula_only,
        "product_type": product_type,
        "count": len(chunks),
        "chunks": [
            {
                "rank": i,
                "score": c.score,
                "doc_id": c.doc_id,
                "doc_title": c.doc_title,
                "pdf_page": c.pdf_page,
                "printed_page": c.printed_page,
                "chunk_index": c.chunk_index,
                "chunk_type": c.chunk_type,
                "section_title": c.section_title,
                "product_types": c.product_types,
                "is_formula": is_formula_chunk(c.text),
                "text_preview": c.text.replace("\n", " ")[:200],
            }
            for i, c in enumerate(chunks, start=1)
        ],
    }
