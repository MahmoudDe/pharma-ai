from __future__ import annotations

import io
import re
from collections import defaultdict
from typing import BinaryIO

from app.warehouse.arabic_aliases import has_arabic, normalize_arabic_key


_NAME_HINTS = re.compile(
    r"^(material|ingredient|name|description|item|product|raw|component|"
    r"بيان|البيان|المادة|الصنف|المنتج|اسم|الوصف)s?$",
    re.I,
)

_HEADER_SCAN = re.compile(
    r"بيان|المادة|material|ingredient|description|الصنف",
    re.I,
)

_SKIP_ROW = re.compile(
    r"رصيد|دفعة|فاتورة|خصم|إجمالي|مجموع|تسوية|بدل\s*تلف|"
    r"balance|payment|invoice|total|opening",
    re.I,
)

_QTY_HINTS = re.compile(r"^(qty|quantity|amount|stock|الكمية|كمية)$", re.I)
_SKU_HINTS = re.compile(r"^(sku|code|id|item_?code|الكود|كود)$", re.I)


def _dedupe_key(raw: str) -> str:
    if has_arabic(raw):
        return normalize_arabic_key(raw)
    return raw.strip().lower()


def _detect_name_column(columns: list[str]) -> str | None:
    for col in columns:
        col_s = str(col).strip()
        if _NAME_HINTS.match(col_s):
            return col
    # Fallback: column with most Arabic/alpha text in name
    for col in columns:
        if has_arabic(str(col)) or _NAME_HINTS.search(str(col)):
            return str(col)
    return columns[0] if columns else None


def _detect_optional(columns: list[str], pattern: re.Pattern[str]) -> str | None:
    for col in columns:
        if pattern.match(str(col).strip()):
            return col
    return None


def _find_excel_header_row(file_obj: BinaryIO) -> int:
    import pandas as pd

    preview = pd.read_excel(file_obj, header=None, nrows=15, dtype=str)
    for idx in range(len(preview)):
        cells = [str(c).strip() for c in preview.iloc[idx] if str(c) != "nan" and str(c).strip()]
        if not cells:
            continue
        joined = " ".join(cells)
        if _HEADER_SCAN.search(joined):
            return idx
    return 0


def _should_skip_row(name: str) -> bool:
    if not name or len(name) < 2:
        return True
    if name.lower() in {"nan", "none", "null", "-"}:
        return True
    if _SKIP_ROW.search(name):
        return True
    if name.isdigit():
        return True
    return False


def parse_inventory_file(
    file_obj: BinaryIO,
    filename: str,
    *,
    name_column: str | None = None,
    max_rows: int = 2000,
    aggregate_duplicates: bool = True,
) -> list[tuple[str, str | None, float | None]]:
    import pandas as pd

    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        header_row = _find_excel_header_row(file_obj)
        file_obj.seek(0)
        df = pd.read_excel(file_obj, header=header_row, dtype=str)
    else:
        df = pd.read_csv(file_obj, dtype=str)

    df = df.dropna(how="all").head(max_rows * 3)
    if df.empty:
        return []

    columns = [str(c) for c in df.columns]
    name_col = name_column or _detect_name_column(columns)
    if name_col is None or name_col not in df.columns:
        raise ValueError("Could not detect a material name column (بيان / material / ingredient).")

    sku_col = _detect_optional(columns, _SKU_HINTS)
    qty_col = _detect_optional(columns, _QTY_HINTS)

    aggregated: dict[str, dict] = defaultdict(
        lambda: {"raw": "", "sku": None, "qty": 0.0, "has_qty": False}
    )

    for _, row in df.iterrows():
        raw = str(row.get(name_col, "")).strip()
        if _should_skip_row(raw):
            continue
        key = _dedupe_key(raw)
        if not key:
            continue

        entry = aggregated[key]
        if not entry["raw"]:
            entry["raw"] = raw
        sku = str(row[sku_col]).strip() if sku_col and pd.notna(row.get(sku_col)) else None
        if sku and not entry["sku"]:
            entry["sku"] = sku
        if qty_col and pd.notna(row.get(qty_col)):
            try:
                q = float(str(row[qty_col]).replace(",", "").strip())
                if aggregate_duplicates:
                    entry["qty"] += q
                else:
                    entry["qty"] = q
                entry["has_qty"] = True
            except ValueError:
                pass

    rows: list[tuple[str, str | None, float | None]] = []
    for entry in aggregated.values():
        qty_out = entry["qty"] if entry["has_qty"] else None
        rows.append((entry["raw"], entry["sku"], qty_out))

    rows.sort(key=lambda r: r[0])
    if len(rows) > max_rows:
        rows = rows[:max_rows]

    if not rows:
        raise ValueError("No valid material rows found in file.")
    return rows


def read_upload_bytes(data: bytes, filename: str) -> list[tuple[str, str | None, float | None]]:
    return parse_inventory_file(io.BytesIO(data), filename)
