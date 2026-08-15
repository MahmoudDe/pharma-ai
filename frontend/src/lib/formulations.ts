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

export interface FormulationCompareReport {
  left_id: string;
  right_id: string;
  left_name: string;
  right_name: string;
  left_cost_per_kg: number | null;
  right_cost_per_kg: number | null;
  cost_delta_per_kg: number | null;
  left_compliance: string;
  right_compliance: string;
  markets: string[];
  only_in_left: string[];
  only_in_right: string[];
  ingredient_deltas: Array<{
    key: string;
    raw_name: string;
    left_amount: number | null;
    left_unit: string | null;
    right_amount: number | null;
    right_unit: string | null;
  }>;
  role_summaries: Array<{
    role: string;
    left_count: number;
    right_count: number;
    left_examples: string[];
    right_examples: string[];
  }>;
  summary_lines: string[];
}

export interface FormulationCost {
  formulation_id: string;
  cost_per_kg: number | null;
  currency: string;
  covered_percent: number;
  missing_ingredients: string[];
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
  precision_score?: number | null;
  kbs_status?: "verified" | "review" | "low_precision" | null;
  estimated_cost_per_kg?: number | null;
  cost_coverage_percent?: number | null;
}

export interface KbsFinding {
  rule_id: string;
  family: string;
  severity: "info" | "warning" | "error";
  message: string;
  ingredient?: string | null;
}

export interface KbsReport {
  formulation_id: string;
  formulation_name: string;
  precision_score: number;
  status: "verified" | "review" | "low_precision";
  compliance_status: "pass" | "warn" | "fail" | "skipped";
  extraction_method: string;
  findings: KbsFinding[];
  validated_at: string;
}

export async function fetchKbsReport(formulationId: string): Promise<KbsReport | null> {
  const response = await fetch(`${BACKEND_URL}/api/kbs/report/${formulationId}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
  return body as KbsReport;
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

export async function fetchReviewQueue(limit = 50): Promise<FormulationSummary[]> {
  const response = await fetch(
    `${BACKEND_URL}/api/formulations/review?limit=${limit}`,
    { headers: { Accept: "application/json" } },
  );
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

export async function patchFormulation(
  formulationId: string,
  patch: { name?: string; confidence?: number },
): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/api/formulations/${formulationId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
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
  includeLlmNote = false,
): Promise<SubstitutionSuggestion[]> {
  const name = ingredient.trim();
  if (!name) {
    return [];
  }

  const hasConstraints = Boolean(
    constraints &&
      (constraints.product_type ||
        (constraints.banned_ingredients?.length ?? 0) > 0 ||
        (constraints.preferred_ingredients?.length ?? 0) > 0 ||
        (constraints.markets?.length ?? 0) > 0 ||
        constraints.cost_target != null ||
        constraints.batch_size != null),
  );

  const payload: Record<string, unknown> = {
    ingredient: name,
    include_llm_note: includeLlmNote,
  };
  if (hasConstraints && constraints) {
    payload.constraints = {
      ...(constraints.product_type ? { product_type: constraints.product_type } : {}),
      ...(constraints.banned_ingredients?.length
        ? { banned_ingredients: constraints.banned_ingredients.filter(Boolean) }
        : {}),
      ...(constraints.preferred_ingredients?.length
        ? { preferred_ingredients: constraints.preferred_ingredients.filter(Boolean) }
        : {}),
      ...(constraints.markets?.length
        ? { markets: constraints.markets.filter(Boolean) }
        : {}),
      ...(constraints.cost_target != null ? { cost_target: constraints.cost_target } : {}),
      ...(constraints.batch_size != null ? { batch_size: constraints.batch_size } : {}),
      ...(constraints.target_attributes?.length
        ? { target_attributes: constraints.target_attributes.filter(Boolean) }
        : {}),
    };
  }

  const response = await fetch(
    `${BACKEND_URL}/api/formulations/${formulationId}/substitutions`,
    {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail =
      typeof body === "object" && body && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : null;
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : detail
          ? `Request failed (${response.status}): ${detail}`
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

export async function fetchFormulationCost(formulationId: string): Promise<FormulationCost> {
  const response = await fetch(`${BACKEND_URL}/api/formulations/${formulationId}/cost`, {
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
  return body as FormulationCost;
}

export async function fetchCompareFormulations(
  leftId: string,
  rightId: string,
  markets?: string[],
): Promise<FormulationCompareReport> {
  const response = await fetch(`${BACKEND_URL}/api/formulations/compare`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      left_id: leftId,
      right_id: rightId,
      markets: markets?.length ? markets : undefined,
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body === "object" && body && "message" in body
        ? String((body as { message: unknown }).message)
        : `Request failed (${response.status})`,
    );
  }
  return body as FormulationCompareReport;
}
