const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface CorpusStats {
  ready: boolean;
  dependencies: { name: string; ok: boolean; detail: string }[];
  qdrant_points: number;
  bm25_documents?: number;
  formulation_count: number;
  ingredient_count: number;
  source_documents: { doc_id: string; filename: string }[];
  ingest_manifest?: Record<string, IngestManifestDoc>;
  formulation_store?: string;
  ocr_pages_total?: number;
  ocr_documents_count?: number;
}

export interface IngestQualityReport {
  passed: boolean;
  ocr_enabled: boolean;
  ocr: {
    documents_with_ocr: number;
    total_ocr_pages: number;
    documents: IngestManifestDoc[];
  };
  ingest_quality: {
    total_formulas: number;
    share_6plus_ingredients: number;
    share_with_amounts: number;
    share_with_procedure: number;
    share_high_confidence: number;
    share_2_ingredient_only: number;
    median_ingredients: number;
    avg_ingredients: number;
    by_method: Record<string, number>;
    thin_examples: string[];
    failures: string[];
  };
}

export interface IngestManifestDoc {
  doc_id: string;
  filename: string;
  kind: string;
  sha256: string;
  formulations: number;
  chunks: number;
  ocr_pages_count?: number;
  ingested_at?: string;
}

export interface IngestJob {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  force: boolean;
  sqlite_only: boolean;
  pdf_only: boolean;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
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

export async function fetchIngestQuality(): Promise<IngestQualityReport> {
  const response = await fetch(`${BACKEND_URL}/api/corpus/ingest-quality`, {
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
  return body as IngestQualityReport;
}

export async function startIngestJob(options?: {
  force?: boolean;
  sqlite_only?: boolean;
  pdf_only?: boolean;
}): Promise<IngestJob> {
  const response = await fetch(`${BACKEND_URL}/api/corpus/ingest`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(options ?? {}),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
  return (body as { job: IngestJob }).job;
}

export async function fetchIngestJobs(): Promise<IngestJob[]> {
  const response = await fetch(`${BACKEND_URL}/api/corpus/ingest`, {
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
  return (body as { jobs: IngestJob[] }).jobs ?? [];
}
