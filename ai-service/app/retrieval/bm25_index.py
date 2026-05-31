"""Sparse BM25 index persisted alongside Qdrant for hybrid retrieval."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from rank_bm25 import BM25Okapi

from app.config import PROJECT_ROOT
from app.ingestion.chunk import Chunk


logger = logging.getLogger(__name__)

INDEX_PATH = PROJECT_ROOT / "data" / "bm25_index.json"
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?|[%]")


@dataclass(slots=True)
class Bm25Record:
    point_id: str
    doc_id: str
    doc_title: str
    pdf_page: int
    printed_page: int | None
    chunk_index: int
    text: str
    is_formula: bool = False
    chunk_type: str = "prose"
    section_title: str | None = None
    product_types: list[str] | None = None
    text_hash: str = ""
    formulation_id: str | None = None
    ingredient_count: int = 0
    extraction_confidence: float = 0.0


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _point_id_for_chunk(chunk: Chunk) -> str:
    from app.ingestion.index import _point_id

    return _point_id(chunk)


class Bm25Index:
    def __init__(self) -> None:
        self.records: list[Bm25Record] = []
        self._bm25: BM25Okapi | None = None
        self._corpus_tokens: list[list[str]] = []

    def clear(self) -> None:
        self.records = []
        self._bm25 = None
        self._corpus_tokens = []

    def add_chunks(self, chunks: Sequence[Chunk]) -> int:
        added = 0
        seen: set[str] = set(r.point_id for r in self.records)
        for chunk in chunks:
            pid = _point_id_for_chunk(chunk)
            if pid in seen:
                continue
            seen.add(pid)
            self.records.append(
                Bm25Record(
                    point_id=pid,
                    doc_id=chunk.doc_id,
                    doc_title=chunk.doc_title,
                    pdf_page=chunk.pdf_page,
                    printed_page=chunk.printed_page,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    is_formula=chunk.is_formula,
                    chunk_type=chunk.chunk_type,
                    section_title=chunk.section_title,
                    product_types=chunk.product_types or None,
                    text_hash=chunk.text_hash,
                    formulation_id=chunk.formulation_id,
                    ingredient_count=chunk.ingredient_count,
                    extraction_confidence=chunk.extraction_confidence,
                )
            )
            added += 1
        if added:
            self._rebuild()
        return added

    def _rebuild(self) -> None:
        self._corpus_tokens = [_tokenize(r.text) for r in self.records]
        self._bm25 = BM25Okapi(self._corpus_tokens) if self._corpus_tokens else None

    def search(self, query: str, *, top_k: int = 40) -> list[tuple[Bm25Record, float]]:
        if not query.strip() or not self._bm25 or not self.records:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            zip(self.records, scores),
            key=lambda item: item[1],
            reverse=True,
        )
        return [(rec, float(score)) for rec, score in ranked[:top_k]]

    def save(self) -> None:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "records": [asdict(r) for r in self.records],
        }
        INDEX_PATH.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("Saved BM25 index (%d documents)", len(self.records))

    @classmethod
    def load(cls) -> Bm25Index:
        index = cls()
        if not INDEX_PATH.exists():
            return index
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            raw = data.get("records") or []
            index.records = [Bm25Record(**item) for item in raw]
            index._rebuild()
            logger.info("Loaded BM25 index (%d documents)", len(index.records))
        except Exception:
            logger.exception("Failed to load BM25 index from %s", INDEX_PATH)
        return index


@lru_cache(maxsize=1)
def get_bm25_index() -> Bm25Index:
    return Bm25Index.load()


def clear_bm25_index() -> None:
    get_bm25_index.cache_clear()
    index = Bm25Index()
    index.save()
    if INDEX_PATH.exists():
        INDEX_PATH.unlink(missing_ok=True)


def append_chunks_to_bm25(chunks: Sequence[Chunk]) -> int:
    index = get_bm25_index()
    added = index.add_chunks(chunks)
    if added:
        index.save()
        get_bm25_index.cache_clear()
    return added
