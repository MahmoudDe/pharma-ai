"""Cross-encoder reranking for retrieved chunks (Phase 3)."""
from __future__ import annotations

import logging
import math
from functools import lru_cache

from app.config import get_settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_cross_encoder():
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    logger.info("Loading cross-encoder reranker: %s", settings.cross_encoder_model)
    return CrossEncoder(settings.cross_encoder_model, max_length=512)


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def cross_encoder_scores(query: str, passages: list[str]) -> list[float]:
    """Return relevance scores in [0, 1] for each passage."""
    if not passages:
        return []
    model = _load_cross_encoder()
    pairs = [(query, p[:2000]) for p in passages]
    raw = model.predict(pairs)
    return [_sigmoid(float(s)) for s in raw]
