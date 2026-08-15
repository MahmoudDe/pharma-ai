from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import FormulationRecord


logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ingredient_prices.csv"


@dataclass(slots=True)
class CostEstimate:
    cost_per_kg: float | None
    covered_percent: float
    missing_ingredients: list[str] = field(default_factory=list)
    currency: str = "USD"


@lru_cache(maxsize=1)
def load_price_table() -> dict[str, float]:
    if not _DATA_PATH.is_file():
        return {}
    prices: dict[str, float] = {}
    with _DATA_PATH.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("ingredient") or "").strip().lower()
            raw_price = row.get("price_per_kg_usd") or row.get("price_per_kg")
            if not name or not raw_price:
                continue
            try:
                prices[name] = float(raw_price)
            except ValueError:
                continue
            norm = normalize_ingredient_name(name)
            if norm:
                prices[norm.lower()] = float(raw_price)
    return prices


def reload_price_table() -> None:
    load_price_table.cache_clear()


def price_table_stats() -> dict:
    prices = load_price_table()
    return {"ingredient_count": len(prices), "currency": "USD", "path": str(_DATA_PATH)}


def merge_price_rows(rows: list[tuple[str, float]]) -> int:
    """Upsert ingredient prices and persist to CSV. Returns rows written."""
    existing: dict[str, float] = {}
    if _DATA_PATH.is_file():
        with _DATA_PATH.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                name = (row.get("ingredient") or "").strip().lower()
                raw_price = row.get("price_per_kg_usd") or row.get("price_per_kg")
                if name and raw_price:
                    try:
                        existing[name] = float(raw_price)
                    except ValueError:
                        continue
    for name, price in rows:
        key = name.strip().lower()
        if not key or price < 0:
            continue
        existing[key] = float(price)

    _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _DATA_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ingredient", "price_per_kg_usd"])
        for name in sorted(existing):
            writer.writerow([name, existing[name]])

    reload_price_table()
    return len(existing)


def parse_price_csv(text: str) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames:
        for row in reader:
            name = (row.get("ingredient") or row.get("name") or "").strip()
            raw = row.get("price_per_kg_usd") or row.get("price_per_kg") or row.get("price")
            if not name or not raw:
                continue
            try:
                rows.append((name, float(raw)))
            except ValueError:
                continue
    return rows


def _price_for_ingredient(raw: str, norm: str | None, prices: dict[str, float]) -> float | None:
    candidates = [
        (norm or "").lower(),
        raw.lower().strip(),
        normalize_ingredient_name(raw) or "",
    ]
    for key in candidates:
        if key and key in prices:
            return prices[key]
    for key in candidates:
        if not key:
            continue
        for price_key, price in prices.items():
            if price_key in key or key in price_key:
                return price
    return None


def estimate_formulation_cost(record: FormulationRecord) -> CostEstimate:
    prices = load_price_table()
    if not prices:
        return CostEstimate(cost_per_kg=None, covered_percent=0.0)

    total_pct = 0.0
    covered_pct = 0.0
    cost_sum = 0.0
    missing: list[str] = []

    for ing in record.ingredients:
        if ing.unit != "%" or ing.amount is None or ing.amount <= 0:
            continue
        total_pct += ing.amount
        price = _price_for_ingredient(
            ing.raw_name,
            ing.normalized_name,
            prices,
        )
        if price is None:
            missing.append(ing.raw_name)
            continue
        covered_pct += ing.amount
        cost_sum += (ing.amount / 100.0) * price

    if total_pct <= 0:
        return CostEstimate(cost_per_kg=None, covered_percent=0.0, missing_ingredients=missing)

    covered_share = covered_pct / total_pct
    cost_per_kg = cost_sum if covered_pct > 0 else None

    return CostEstimate(
        cost_per_kg=round(cost_per_kg, 4) if cost_per_kg is not None else None,
        covered_percent=round(covered_share, 4),
        missing_ingredients=missing[:12],
    )
