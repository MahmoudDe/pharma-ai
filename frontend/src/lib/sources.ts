const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/**
 * Normalize titles or legacy labels to the same slug used by ingestion (`doc_id_from_path`).
 * Already-slug ids pass through unchanged.
 */
export function toSourceDocId(documentId: string): string {
  const trimmed = documentId.trim();
  if (!trimmed) return trimmed;
  if (/^[a-z0-9]+(?:_[a-z0-9]+)*$/i.test(trimmed)) {
    return trimmed.toLowerCase();
  }
  return trimmed
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** Open ingested PDF at a 1-based page (browser PDF viewer fragment). */
export function sourcePdfUrl(documentId: string, page?: number): string {
  const docId = toSourceDocId(documentId);
  const base = `${BACKEND_URL}/api/sources/${encodeURIComponent(docId)}`;
  if (page != null && page > 0) {
    return `${base}?page=${page}#page=${page}`;
  }
  return base;
}
