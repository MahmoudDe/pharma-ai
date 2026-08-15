from __future__ import annotations

from app.formulation.normalize import normalize_ingredient_name


def canonical_key(name: str) -> str:
    """Single normalized key for inventory and alias storage."""
    n = normalize_ingredient_name(name)
    return (n or name).strip().lower()


def expand_inventory(canonical_inv: set[str]) -> set[str]:
    """Expand inventory with normalized keys and token subsets."""
    expanded: set[str] = set()
    for item in canonical_inv:
        key = canonical_key(item)
        if key:
            expanded.add(key)
    return expanded


def ingredient_in_inventory(
    inventory: set[str],
    raw: str,
    norm: str | None = None,
    *,
    fuzzy_threshold: int = 86,
) -> bool:
    if not inventory:
        return False

    candidates: list[str] = []
    if norm:
        candidates.append(canonical_key(norm))
    candidates.append(canonical_key(raw))

    for c in candidates:
        if c and c in inventory:
            return True

    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return False

    choices = list(inventory)
    for c in candidates:
        if not c:
            continue
        match = process.extractOne(c, choices, scorer=fuzz.token_set_ratio)
        if match and match[1] >= fuzzy_threshold:
            return True
    return False
