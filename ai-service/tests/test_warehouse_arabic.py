from __future__ import annotations

from pathlib import Path

from app.warehouse.arabic_aliases import resolve_arabic_alias
from app.warehouse.parse_upload import read_upload_bytes


def test_arabic_xlsx_parses_bayan_column():
    path = Path(__file__).resolve().parents[2] / "docs" / "حساب السيد اسماعيل أبو نبوت المحترم.xlsx"
    if not path.is_file():
        return
    rows = read_upload_bytes(path.read_bytes(), path.name)
    assert len(rows) >= 30
    names = {r[0] for r in rows}
    assert any("تكسابون" in n for n in names)
    assert not any("رصيد مدور" in n for n in names)
    assert not any("دفعة" == n for n in names)


def test_arabic_alias_texapon():
    hit = resolve_arabic_alias("تكسابون")
    assert hit is not None
    assert "sulfate" in hit[0] or "laureth" in hit[0]


def test_arabic_alias_glycerin():
    hit = resolve_arabic_alias("غليسيرين")
    assert hit is not None
    assert hit[0] == "glycerin"
