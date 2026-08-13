export type ChatRole = "user" | "assistant";

export interface StructuredBrief {
  product_type?: string;
  target_attributes?: string[];
  banned_ingredients?: string[];
  preferred_ingredients?: string[];
  cost_target?: number;
  batch_size?: number;
  markets?: string[];
}

export interface CitedEvidence {
  document_id: string;
  page?: number;
  pdf_page?: number;
  printed_page?: number;
  quote: string;
  confidence?: "low" | "medium" | "high";
  formulation_id?: string;
  quote_verified?: boolean;
}

export interface SuggestedNextAction {
  type: string;
  label: string;
  payload?: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  citedEvidence?: CitedEvidence[];
  suggestedActions?: SuggestedNextAction[];
  structuredFormulation?: StructuredFormulationView | null;
  structuredFormulations?: StructuredFormulationView[];
  route?: QueryRoute;
  llmUsed?: boolean;
  searchConfidence?: number | null;
}

export interface ChatTurnRequest {
  thread_id: string;
  message: string;
  structured_brief?: StructuredBrief;
  history?: Array<{ role: ChatRole; content: string }>;
}

export interface StructuredIngredient {
  raw_name: string;
  normalized_name?: string | null;
  amount?: number | null;
  unit?: string | null;
  phase?: string | null;
}

export interface StructuredFormulationView {
  formulation_id: string;
  name: string;
  product_types: string[];
  doc_id: string;
  pdf_page: number;
  printed_page?: number | null;
  confidence: number;
  ingredients: StructuredIngredient[];
  procedure?: string[];
}

export type QueryRoute =
  | "lookup"
  | "compare"
  | "reasoning"
  | "unknown"
  | "fallback";

export type FallbackStage = "none" | "vector" | "expanded" | "failed";

export interface ChatTurnResponse {
  assistant_message: string;
  cited_evidence?: CitedEvidence[];
  suggested_next_actions?: SuggestedNextAction[];
  structured_formulation?: StructuredFormulationView | null;
  structured_formulations?: StructuredFormulationView[];
  route?: QueryRoute;
  llm_used?: boolean;
  search_confidence?: number | null;
  fallback_stage?: FallbackStage | null;
  rewritten_query?: string | null;
}

export interface ChatThreadSummary {
  id: string;
  title: string;
  updated_at: string | null;
  preview: string | null;
}

export interface ChatThreadMessage {
  id: string;
  role: ChatRole;
  content: string;
  created_at: string;
  cited_evidence?: CitedEvidence[];
  suggested_next_actions?: SuggestedNextAction[];
  structured_formulation?: StructuredFormulationView | null;
  structured_formulations?: StructuredFormulationView[];
}

export interface ChatThreadDetail {
  id: string;
  title: string;
  updated_at: string | null;
  messages: ChatThreadMessage[];
}
