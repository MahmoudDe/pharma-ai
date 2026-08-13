from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["low", "medium", "high"]
QueryRoute = Literal["lookup", "compare", "reasoning", "unknown", "fallback"]
FallbackStage = Literal["none", "vector", "expanded", "failed"]


class StructuredBrief(BaseModel):
    product_type: Optional[str] = None
    target_attributes: Optional[list[str]] = None
    banned_ingredients: Optional[list[str]] = None
    preferred_ingredients: Optional[list[str]] = None
    cost_target: Optional[float] = None
    batch_size: Optional[float] = None
    markets: Optional[list[str]] = None


class CitedEvidence(BaseModel):
    document_id: str
    page: Optional[int] = None
    pdf_page: Optional[int] = None
    printed_page: Optional[int] = None
    quote: str
    confidence: Optional[Confidence] = None
    formulation_id: Optional[str] = None
    quote_verified: Optional[bool] = None


class SuggestedNextAction(BaseModel):
    type: str
    label: str
    payload: Optional[dict[str, Any]] = None


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatTurnRequest(BaseModel):
    thread_id: str
    message: str
    structured_brief: Optional[StructuredBrief] = None
    history: Optional[list[ChatHistoryMessage]] = None


class StructuredFormulationView(BaseModel):
    formulation_id: str
    name: str
    product_types: list[str] = Field(default_factory=list)
    doc_id: str
    pdf_page: int
    printed_page: Optional[int] = None
    confidence: float = 0.0
    kbs_status: Optional[str] = None
    precision_score: Optional[float] = None
    kbs_warnings: list[str] = Field(default_factory=list)
    ingredients: list[dict[str, Any]] = Field(default_factory=list)
    procedure: list[str] = Field(default_factory=list)


class ChatTurnResponse(BaseModel):
    assistant_message: str
    cited_evidence: list[CitedEvidence] = Field(default_factory=list)
    suggested_next_actions: list[SuggestedNextAction] = Field(default_factory=list)
    structured_formulation: Optional[StructuredFormulationView] = None
    structured_formulations: list[StructuredFormulationView] = Field(default_factory=list)
    route: QueryRoute = "unknown"
    llm_used: bool = False
    search_confidence: Optional[float] = None
    fallback_stage: Optional[FallbackStage] = None
    rewritten_query: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "0.1.0"


class DependencyHealth(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class ReadinessResponse(BaseModel):
    status: str
    service: str
    ready: bool
    dependencies: list[DependencyHealth] = Field(default_factory=list)
