export type AliasSource = "rules" | "corpus" | "llm" | "manual" | "arabic" | "unresolved";

export interface WarehouseMaterialRow {
  id: number;
  raw_name: string;
  sku?: string | null;
  qty?: number | null;
  canonical_name?: string | null;
  alias_source?: AliasSource | null;
  confidence?: number;
  needs_review?: boolean;
}

export interface UploadResponse {
  upload_id: string;
  filename: string;
  row_count: number;
  preview: Array<{ raw_name: string; sku?: string | null; qty?: number | null }>;
}

export interface ResolveResponse {
  upload_id: string;
  resolved: number;
  needs_review: number;
  materials: WarehouseMaterialRow[];
}

export interface DiscoverProductResult {
  formulation_id: string;
  name: string;
  product_types: string[];
  doc_id: string;
  pdf_page: number;
  printed_page?: number | null;
  coverage_pct: number;
  tier: "makeable" | "partial" | "low";
  matched_ingredients: Array<{ raw_name: string; canonical?: string | null; matched: boolean }>;
  missing_ingredients: string[];
  citation_quote: string;
}

export interface DiscoverResponse {
  upload_id: string;
  material_count: number;
  products: DiscoverProductResult[];
}
