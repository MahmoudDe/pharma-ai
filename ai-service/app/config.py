import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_service_host: str = "0.0.0.0"
    ai_service_port: int = 9000

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "pharma_chunks"

    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384

    # LLM provider — defaults to OpenRouter (https://openrouter.ai) which is OpenAI-API
    # compatible and proxies to 100+ models. To use OpenAI directly, set
    # LLM_BASE_URL=https://api.openai.com/v1 and LLM_MODEL=gpt-4o-mini.
    # To use Ollama locally, set LLM_BASE_URL=http://localhost:11434/v1.
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"

    # OpenRouter model for eval generation + LLM-as-judge (defaults to llm_model)
    eval_model: str = ""

    docs_dir: str = Field(default=str(PROJECT_ROOT.parent / "docs"))
    chunk_char_size: int = 3200
    chunk_char_overlap: int = 400

    hf_home: str = Field(default=str(PROJECT_ROOT / "data" / "hf-cache"))

    app_env: str = "development"
    debug_retrieval: bool = False

    # Routing thresholds (structured search 0–100)
    structured_direct_threshold: float = 80.0
    structured_hybrid_threshold: float = 50.0
    use_llm_on_hybrid: bool = False
    use_llm_on_vector_fallback: bool = False
    enable_query_expansion: bool = True
    min_vector_score: float = 0.30

    # BM25 + dense hybrid (RRF)
    enable_bm25_hybrid: bool = True
    bm25_fetch_k: int = 40
    hybrid_rrf_k: int = 60

    # Cross-encoder reranking (Phase 3)
    enable_cross_encoder_rerank: bool = True
    cross_encoder_model: str = "BAAI/bge-reranker-base"
    rerank_top_n: int = 40
    rerank_ce_weight: float = 0.72
    rerank_vector_weight: float = 0.18
    rerank_heuristic_weight: float = 0.10

    # Warehouse inventory
    warehouse_max_rows: int = 2000
    warehouse_max_upload_bytes: int = 5_242_880
    warehouse_fuzzy_threshold: int = 82
    warehouse_llm_batch_size: int = 25
    warehouse_review_threshold: float = 0.7
    warehouse_makeable_coverage: float = 95.0

    # Formulation store: sqlite (default) or postgres
    formulation_store: str = "sqlite"
    database_url: str = ""

    # Conversation context (Phase A)
    chat_history_max_messages: int = 10
    enable_conversation_rewrite: bool = True

    # OCR for scanned PDF pages
    ocr_enabled: bool = True
    ocr_lang: str = "eng"
    ocr_min_text_chars: int = 40

    # Ingest job queue (file-based under data/ingest_jobs)
    ingest_jobs_dir: str = Field(default=str(PROJECT_ROOT / "data" / "ingest_jobs"))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    hf_home_path = Path(settings.hf_home)
    if not hf_home_path.is_absolute():
        hf_home_path = (PROJECT_ROOT / hf_home_path).resolve()
    hf_home_path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(hf_home_path))

    # Resolve a relative docs_dir against the project root, not the process
    # CWD — the API server and the CLI run from different directories, and a
    # relative DOCS_DIR (e.g. "../docs") would otherwise point somewhere that
    # only exists for one of them, silently failing UI-triggered ingests.
    docs_path = Path(settings.docs_dir)
    if not docs_path.is_absolute():
        settings.docs_dir = str((PROJECT_ROOT / docs_path).resolve())
    return settings
