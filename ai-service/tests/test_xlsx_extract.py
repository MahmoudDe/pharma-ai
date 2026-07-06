"""Tests for XLSX formula book extraction."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from app.ingestion.extract_xlsx import extract_xlsx


def test_extract_xlsx_sheet(tmp_path):
    path = tmp_path / "formulas.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Shampoo"
    ws.append(["Ingredient", "wt%"])
    ws.append(["Water", "70"])
    ws.append(["SLS", "10"])
    wb.save(path)

    pages = list(extract_xlsx(path))
    assert len(pages) >= 1
    assert "Water" in pages[0].text
    assert "[TABLE]" in pages[0].text
