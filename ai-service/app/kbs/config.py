"""KBS configuration loaded from data/kbs/kbs_config.yaml with safe defaults."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml


logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "kbs"

_DEFAULTS: dict = {
    "weights": {
        "fidelity": 0.35,
        "consistency": 0.25,
        "completeness": 0.20,
        "ranges": 0.20,
    },
    "penalties": {"error": 0.35, "warning": 0.12, "info": 0.0},
    "bands": {"low_precision_below": 0.4, "review_below": 0.7},
    "percent_units": ["%", "wtg", "wt.g", "wt g", "w/w", "wt%", "g%", "percent"],
    "consistency": {
        "sum_target": 100.0,
        "sum_warn_tolerance": 3.0,
        "sum_error_tolerance": 10.0,
        "min_percent_coverage": 0.8,
    },
    "completeness": {"min_ingredients": 2},
    "regulatory_markets": ["EU", "US"],
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache
def get_kbs_config() -> dict:
    path = DATA_DIR / "kbs_config.yaml"
    if not path.is_file():
        return dict(_DEFAULTS)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        logger.warning("Invalid YAML in %s; using KBS defaults", path)
        return dict(_DEFAULTS)
    return _merge(_DEFAULTS, loaded)


def clear_config_cache() -> None:
    get_kbs_config.cache_clear()
