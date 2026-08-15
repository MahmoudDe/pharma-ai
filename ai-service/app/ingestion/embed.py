from __future__ import annotations

import logging
from functools import lru_cache
from typing import Sequence

import numpy as np

# Ensure HF_HOME is set via Settings BEFORE sentence_transformers / huggingface_hub
# are imported, because those libs latch onto the cache directory at import time.
from app.config import get_settings as _get_settings_for_env

_get_settings_for_env()

from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import get_settings  # noqa: E402


logger = logging.getLogger(__name__)

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    settings = get_settings()
    logger.info("Loading embedding model: %s", settings.embed_model)
    model = SentenceTransformer(settings.embed_model)
    logger.info("Embedding model loaded (dim=%s)", model.get_sentence_embedding_dimension())
    return model


def embed_passages(texts: Sequence[str], batch_size: int = 32) -> np.ndarray:
    """Embed corpus passages. No query instruction prepended."""
    if not texts:
        return np.zeros((0, get_settings().embed_dim), dtype=np.float32)
    model = get_model()
    vectors = model.encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vectors.astype(np.float32)


def embed_query(text: str) -> np.ndarray:
    """Embed a user query. BGE expects an instruction prefix."""
    model = get_model()
    vec = model.encode(
        QUERY_INSTRUCTION + text,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vec.astype(np.float32)
