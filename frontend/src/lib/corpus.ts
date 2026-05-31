const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface CorpusStats {
  ready: boolean;
  dependencies: { name: string; ok: boolean; detail: string }[];
  qdrant_points: number;
  bm25_documents?: number;
  formulation_count: number;
  ingredient_count: number;
  source_documents: { doc_id: string; filename: string }[];
}

export async function fetchCorpusStats(): Promise<CorpusStats> {
  const response = await fetch(`${BACKEND_URL}/api/corpus/stats`, {
    headers: { Accept: "application/json" },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
  return body as CorpusStats;
}
