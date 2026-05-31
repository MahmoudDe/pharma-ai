const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Open ingested PDF at a 1-based page (browser PDF viewer fragment). */
export function sourcePdfUrl(documentId: string, page?: number): string {
  const base = `${BACKEND_URL}/api/sources/${encodeURIComponent(documentId)}`;
  if (page != null && page > 0) {
    return `${base}?page=${page}#page=${page}`;
  }
  return base;
}
