from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from app.ingestion.extract import PageRecord, _normalize, doc_id_from_path
from app.ingestion.xlsx_utils import read_xlsx_sheets, sheet_to_table_text


logger = logging.getLogger(__name__)

_MAX_SECTION_CHARS = 12000


def extract_xlsx(path: Path) -> Iterator[PageRecord]:
    doc_id = doc_id_from_path(path)
    doc_title = path.stem
    sheets = read_xlsx_sheets(path)
    logger.info("[%s] %d XLSX sheet(s)", path.name, len(sheets))

    page_index = 0
    for sheet_name, rows in sheets:
        text = _normalize(sheet_to_table_text(sheet_name, rows))
        if len(text) < 40:
            continue
        if len(text) > _MAX_SECTION_CHARS:
            chunk_size = _MAX_SECTION_CHARS
            for start in range(0, len(text), chunk_size):
                chunk = text[start : start + chunk_size]
                if len(chunk) < 40:
                    continue
                page_index += 1
                yield PageRecord(
                    doc_id=doc_id,
                    doc_title=doc_title,
                    pdf_page=page_index,
                    printed_page=None,
                    text=chunk,
                )
            continue
        page_index += 1
        yield PageRecord(
            doc_id=doc_id,
            doc_title=doc_title,
            pdf_page=page_index,
            printed_page=None,
            text=text,
        )


def discover_xlsx(docs_dir: Path) -> list[Path]:
    files = sorted(
        p
        for p in docs_dir.glob("*.xlsx")
        if p.is_file() and not p.name.startswith("~$")
    )
    logger.info("Found %d XLSX file(s) in %s", len(files), docs_dir)
    return files
