"""Cross-encoder reranking for retrieved chunks (Phase 3)."""
from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path

from app.config import PROJECT_ROOT, get_settings


logger = logging.getLogger(__name__)


def _local_model_path(model_id: str) -> str | None:
    """Resolve a cached HuggingFace snapshot when weights are already on disk."""
    settings = get_settings()
    hf_home = Path(settings.hf_home)
    if not hf_home.is_absolute():
        hf_home = (PROJECT_ROOT / hf_home).resolve()
    snapshots_dir = hf_home / "hub" / f"models--{model_id.replace('/', '--')}" / "snapshots"
    bundled = PROJECT_ROOT / "data" / "models" / model_id.split("/")[-1]
    if bundled.is_dir() and (bundled / "config.json").exists():
        return str(bundled)
    if not snapshots_dir.is_dir():
        return None
    candidates = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for snap in candidates:
        weights = snap / "model.safetensors"
        if weights.exists() or weights.resolve().exists():
            return str(snap)
        legacy = snap / "pytorch_model.bin"
        if legacy.exists() or legacy.resolve().exists():
            return str(snap)
    return None


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@lru_cache(maxsize=1)
def _load_cross_encoder():
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    model_id = settings.cross_encoder_model
    local = _local_model_path(model_id)
    load_path = local or model_id
    kwargs: dict = {"max_length": 512}
    if local:
        kwargs["local_files_only"] = True
    logger.info("Loading cross-encoder reranker: %s", load_path)
    try:
        return CrossEncoder(load_path, **kwargs)
    except Exception as exc:
        if local:
            logger.warning("Local CE load failed (%s); retrying from hub id", exc)
            return CrossEncoder(model_id, max_length=512)
        raise


_ce_disabled = False


def cross_encoder_scores(query: str, passages: list[str]) -> list[float]:
    """Return relevance scores in [0, 1] for each passage."""
    global _ce_disabled
    if not passages or _ce_disabled:
        return [0.5] * len(passages)
    try:
        model = _load_cross_encoder()
        pairs = [(query, p[:2000]) for p in passages]
        raw = model.predict(pairs)
        return [_sigmoid(float(s)) for s in raw]
    except Exception as exc:
        logger.warning("Cross-encoder rerank disabled after load failure: %s", exc)
        _ce_disabled = True
        return [0.5] * len(passages)
