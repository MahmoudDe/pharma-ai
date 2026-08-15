from __future__ import annotations

import logging
from functools import lru_cache
from typing import Sequence

import numpy as np

from app.config import get_settings
from app.formulation.normalize import normalize_ingredient_name


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _corpus_embedding_index() -> tuple[tuple[str, ...], np.ndarray] | None:
    from app.warehouse.corpus_index import corpus_ingredient_names

    corpus = corpus_ingredient_names()
    if not corpus:
        return None
    labels = tuple(c[1] for c in corpus)
    try:
        from app.ingestion.embed import embed_passages

        vectors = embed_passages(list(labels))
        return labels, vectors
    except Exception as exc:
        logger.warning("Corpus embedding index failed: %s", exc)
        return None


def embedding_canonical(raw: str, threshold: float | None = None) -> tuple[str, float] | None:
    """Match raw trade name to corpus ingredient via BGE cosine similarity."""
    settings = get_settings()
    min_score = threshold if threshold is not None else settings.warehouse_embed_threshold

    index = _corpus_embedding_index()
    if index is None:
        return None
    labels, vectors = index
    if not labels:
        return None

    query_text = normalize_ingredient_name(raw) or raw.strip()
    if not query_text:
        return None

    try:
        from app.ingestion.embed import embed_query

        query_vec = embed_query(query_text)
    except Exception as exc:
        logger.warning("Embedding query failed: %s", exc)
        return None

    scores = vectors @ query_vec
    idx = int(np.argmax(scores))
    score = float(scores[idx])
    if score < min_score:
        return None
    return labels[idx], min(0.90, score)


def best_embedding_matches(
    raw_names: Sequence[str],
    threshold: float | None = None,
) -> dict[str, tuple[str, float]]:
    """Batch-friendly map of lower(raw) -> (canonical, confidence)."""
    out: dict[str, tuple[str, float]] = {}
    for raw in raw_names:
        hit = embedding_canonical(raw, threshold=threshold)
        if hit:
            out[raw.lower().strip()] = hit
    return out
