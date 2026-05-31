"""Parse CSV/XLSX warehouse inventory files."""
from __future__ import annotations

import io
import re
from typing import BinaryIO

_NAME_HINTS = re.compile(
    r"^(material|ingredient|name|description|item|product|raw|component)s?$",
    re.I,
)


def _detect_name_column(columns: list[str]) -> str | None:
    for col in columns:
        if _NAME_HINTS.match(col.strip()):
            return col
    return columns[0] if columns else None


def _detect_optional(columns: list[str], pattern: re.Pattern[str]) -> str | None:
    for col in columns:
        if pattern.match(col.strip()):
            return col
    return None


def parse_inventory_file(
    file_obj: BinaryIO,
    filename: str,
    *,
    name_column: str | None = None,
    max_rows: int = 2000,
) -> list[tuple[str, str | None, float | None]]:
    import pandas as pd

    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_obj, dtype=str)
    else:
        df = pd.read_csv(file_obj, dtype=str)

    df = df.dropna(how="all").head(max_rows)
    if df.empty:
        return []

    columns = [str(c) for c in df.columns]
    name_col = name_column or _detect_name_column(columns)
    if name_col is None or name_col not in df.columns:
        raise ValueError("Could not detect a material name column.")

    sku_col = _detect_optional(columns, re.compile(r"^(sku|code|id|item_?code)$", re.I))
    qty_col = _detect_optional(columns, re.compile(r"^(qty|quantity|amount|stock)$", re.I))

    rows: list[tuple[str, str | None, float | None]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        raw = str(row.get(name_col, "")).strip()
        if not raw or len(raw) < 2:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        sku = str(row[sku_col]).strip() if sku_col and pd.notna(row.get(sku_col)) else None
        qty_val = None
        if qty_col and pd.notna(row.get(qty_col)):
            try:
                qty_val = float(str(row[qty_col]).replace(",", ""))
            except ValueError:
                qty_val = None
        rows.append((raw, sku or None, qty_val))

    if not rows:
        raise ValueError("No valid material rows found in file.")
    return rows


def read_upload_bytes(data: bytes, filename: str) -> list[tuple[str, str | None, float | None]]:
    return parse_inventory_file(io.BytesIO(data), filename)
