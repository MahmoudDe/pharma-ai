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

    # Cross-encoder reranking (Phase 3)
    enable_cross_encoder_rerank: bool = True
    cross_encoder_model: str = "BAAI/bge-reranker-base"
    rerank_top_n: int = 40
    rerank_ce_weight: float = 0.72
    rerank_vector_weight: float = 0.18
    rerank_heuristic_weight: float = 0.10


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    hf_home_path = Path(settings.hf_home)
    if not hf_home_path.is_absolute():
        hf_home_path = (PROJECT_ROOT / hf_home_path).resolve()
    hf_home_path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(hf_home_path))
    return settings
