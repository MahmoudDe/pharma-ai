import type { StructuredBrief, StructuredFormulationView } from "@/types/chat";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface SubstitutionSuggestion {
  substitute: string;
  confidence: number;
  reason: string;
  source: string;
  citations: { document_id: string; quote: string; pdf_page?: number }[];
}

export interface ComplianceFinding {
  ingredient: string;
  normalized_name: string;
  market: string;
  status: string;
  max_percent: number | null;
  source_ref: string;
  message: string;
}

export interface ComplianceReport {
  status: "pass" | "warn" | "fail";
  markets: string[];
  findings: ComplianceFinding[];
}

export interface IngestJob {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  force: boolean;
  created_at: string;
  finished_at?: string | null;
  error?: string | null;
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

export interface FormulationSummary {
  formulation_id: string;
  name: string;
  product_types: string[];
  doc_id: string;
  pdf_page: number;
  printed_page?: number | null;
  ingredient_count: number;
  confidence: number;
}

export async function fetchFormulationSummaries(params?: {
  product_type?: string;
  ingredient?: string;
  limit?: number;
}): Promise<FormulationSummary[]> {
  const qs = new URLSearchParams();
  if (params?.product_type) qs.set("product_type", params.product_type);
  if (params?.ingredient) qs.set("ingredient", params.ingredient);
  if (params?.limit) qs.set("limit", String(params.limit));

  const response = await fetch(`${BACKEND_URL}/api/formulations?${qs}`, {
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
  return (body as { formulations: FormulationSummary[] }).formulations ?? [];
}

export async function fetchFormulationDetail(
  formulationId: string,
): Promise<StructuredFormulationView> {
  const response = await fetch(`${BACKEND_URL}/api/formulations/${formulationId}`, {
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
  const record = body as {
    id: string;
    name: string;
    product_types: string[];
    doc_id: string;
    pdf_page: number;
    printed_page?: number | null;
    confidence: number;
    ingredients: StructuredFormulationView["ingredients"];
    procedure?: string[];
  };
  return {
    formulation_id: record.id,
    name: record.name,
    product_types: record.product_types,
    doc_id: record.doc_id,
    pdf_page: record.pdf_page,
    printed_page: record.printed_page,
    confidence: record.confidence,
    ingredients: record.ingredients,
    procedure: record.procedure,
  };
}

export async function fetchSubstitutions(
  formulationId: string,
  ingredient: string,
  constraints?: StructuredBrief,
): Promise<SubstitutionSuggestion[]> {
  const response = await fetch(
    `${BACKEND_URL}/api/formulations/${formulationId}/substitutions`,
    {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ ingredient, constraints }),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
  return (body as { suggestions: SubstitutionSuggestion[] }).suggestions ?? [];
}

export async function fetchComplianceReport(
  formulationId: string,
  markets: string[],
): Promise<ComplianceReport> {
  const response = await fetch(
    `${BACKEND_URL}/api/formulations/${formulationId}/compliance`,
    {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ markets }),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
  return body as ComplianceReport;
}
