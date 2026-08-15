from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.sources.pdf_map import list_source_documents, resolve_pdf_path


router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources() -> dict:
    return {"documents": list_source_documents()}


@router.get("/{doc_id}")
def get_source_pdf(doc_id: str) -> FileResponse:
    path = resolve_pdf_path(doc_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail=f"PDF not found for doc_id={doc_id!r}.")
    return FileResponse(
        path=Path(path),
        media_type="application/pdf",
        filename=path.name,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )
