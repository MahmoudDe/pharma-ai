from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Sequence

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import get_settings
from app.ingestion.chunk import Chunk


logger = logging.getLogger(__name__)

_CHUNK_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")
_FORMULA_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000003")

_seen_hashes: set[tuple[str, str]] = set()
_seen_formulation_ids: set[str] = set()


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    settings = get_settings()
    logger.info("Connecting to Qdrant at %s", settings.qdrant_url)
    return QdrantClient(url=settings.qdrant_url)


def _ensure_payload_indexes(client: QdrantClient, name: str) -> None:
    for field_name, schema in (
        ("doc_id", qm.PayloadSchemaType.KEYWORD),
        ("is_formula", qm.PayloadSchemaType.BOOL),
        ("chunk_type", qm.PayloadSchemaType.KEYWORD),
        ("product_types", qm.PayloadSchemaType.KEYWORD),
        ("text_hash", qm.PayloadSchemaType.KEYWORD),
        ("formulation_id", qm.PayloadSchemaType.KEYWORD),
        ("formula_name", qm.PayloadSchemaType.KEYWORD),
    ):
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field_name,
                field_schema=schema,
            )
        except Exception as exc:
            logger.debug("Payload index %s may already exist: %s", field_name, exc)


def reset_collection() -> None:
    """Drop and recreate the vector collection (use with run_ingest --force)."""
    settings = get_settings()
    client = get_client()
    name = settings.qdrant_collection
    if name in {c.name for c in client.get_collections().collections}:
        logger.info("Deleting Qdrant collection %s for full re-ingest", name)
        client.delete_collection(name)
    reset_dedup_cache()


def ensure_collection() -> None:
    settings = get_settings()
    client = get_client()
    name = settings.qdrant_collection

    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        info = client.get_collection(name)
        configured_size = info.config.params.vectors.size  # type: ignore[union-attr]
        if configured_size != settings.embed_dim:
            raise RuntimeError(
                f"Collection {name!r} has dim {configured_size} but config expects "
                f"{settings.embed_dim}. Drop the collection and re-ingest."
            )
        _ensure_payload_indexes(client, name)
        return

    logger.info("Creating Qdrant collection %s (dim=%d)", name, settings.embed_dim)
    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(
            size=settings.embed_dim,
            distance=qm.Distance.COSINE,
        ),
    )
    _ensure_payload_indexes(client, name)


def reset_dedup_cache() -> None:
    global _seen_hashes, _seen_formulation_ids
    _seen_hashes = set()
    _seen_formulation_ids = set()


def _point_id(chunk: Chunk) -> str:
    if chunk.formulation_id:
        return str(uuid.uuid5(_FORMULA_NAMESPACE, chunk.formulation_id))
    return str(uuid.uuid5(_CHUNK_NAMESPACE, f"{chunk.doc_id}:{chunk.chunk_index}"))


def upsert_chunks(chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")
    if not chunks:
        return

    settings = get_settings()
    client = get_client()

    points: list[qm.PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        if chunk.formulation_id:
            if chunk.formulation_id in _seen_formulation_ids:
                continue
            _seen_formulation_ids.add(chunk.formulation_id)
        else:
            dedup_key = (chunk.doc_id, chunk.text_hash)
            if dedup_key in _seen_hashes:
                continue
            _seen_hashes.add(dedup_key)

        payload: dict = {
            "doc_id": chunk.doc_id,
            "doc_title": chunk.doc_title,
            "page": chunk.pdf_page,
            "pdf_page": chunk.pdf_page,
            "printed_page": chunk.printed_page,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "is_formula": chunk.is_formula,
            "chunk_type": chunk.chunk_type,
            "section_title": chunk.section_title,
            "product_types": chunk.product_types,
            "text_hash": chunk.text_hash,
            "formulation_id": chunk.formulation_id,
        }
        if chunk.formulation_id:
            payload["formula_name"] = chunk.formula_name
            payload["ingredient_count"] = chunk.ingredient_count
            payload["extraction_confidence"] = chunk.extraction_confidence
            payload["extraction_method"] = chunk.extraction_method

        points.append(
            qm.PointStruct(
                id=_point_id(chunk),
                vector=vector.tolist(),
                payload=payload,
            )
        )

    if not points:
        return
    client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)


def fetch_chunks_by_formulation_ids(
    formulation_ids: list[str],
) -> list[dict]:
    """Retrieve formula chunk payloads by formulation_id (post-ingest)."""
    if not formulation_ids:
        return []
    settings = get_settings()
    client = get_client()
    namespace = _FORMULA_NAMESPACE
    point_ids = [str(uuid.uuid5(namespace, fid)) for fid in formulation_ids]

    try:
        records = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=point_ids,
            with_payload=True,
        )
    except Exception:
        logger.exception("Failed to retrieve formulation points")
        return []

    return [r.payload or {} for r in records if r.payload]


def collection_stats() -> dict[str, int]:
    settings = get_settings()
    client = get_client()
    info = client.get_collection(settings.qdrant_collection)
    return {
        "points_count": int(info.points_count or 0),
        "indexed_vectors_count": int(info.indexed_vectors_count or 0),
    }
