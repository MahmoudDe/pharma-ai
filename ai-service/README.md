# Pharma AI Service

Python FastAPI service that powers the thin end-to-end RAG pipeline for the project:

```
Next.js (3000) -> Laravel proxy (8000) -> FastAPI (this, 9000) -> Qdrant (6333) + LLM
```

The LLM step uses any OpenAI-API-compatible provider. **Default: OpenRouter**
(unified gateway to OpenAI, Anthropic, DeepSeek, Llama, Gemini, ...). Switching
providers is a 2-line env change — see "LLM provider" below.

The service exposes:

- `GET /health` -> liveness probe.
- `GET /health/live` -> process up (k8s liveness).
- `GET /health/ready` -> Qdrant + SQLite + BM25 readiness.
- `POST /chat`  -> hybrid retrieval (Qdrant + structured SQLite) + LLM grounded answer.
- `GET /formulations` / `POST /formulations/search` -> structured formula JSON API.
- `GET /debug/retrieve` -> retrieval-only debug (dev).

Architecture: **vector RAG** (semantic chunks in Qdrant) + **structured formulations** (SQLite `data/formulations.db`), built from a **single PDF pass**. Chat uses **intent routing** so lookup/compare queries can skip the LLM.

## Stack

- FastAPI + uvicorn (server)
- PyMuPDF (`pymupdf`) for PDF extraction
- `sentence-transformers` with `BAAI/bge-small-en-v1.5` for 384-d embeddings (CPU)
- Qdrant for vector storage (Docker container, cosine distance)
- OpenRouter -> `openai/gpt-4o-mini` for grounded reasoning (JSON-mode)
via the OpenAI Python SDK (any compatible provider works)

## One-time setup

```bash
cd ai-service

# 1. Python env
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
# includes python-multipart (required for /warehouse/upload file uploads)

# 2. Config
cp .env.example .env
# Edit .env and set LLM_API_KEY=sk-or-v1-...   (from https://openrouter.ai/keys)
# or point at any other OpenAI-compatible provider (see "LLM provider" below)

# 3. Start Qdrant (uses ./data/qdrant as the volume)
docker compose up -d qdrant

# 4. Unified ingest: PDFs + DOCX -> SQLite formulations + Qdrant + BM25 (~1-2 minutes)
.venv/bin/python -m app.ingestion.run_ingest
# Existing Qdrant data without BM25 file: .venv/bin/python scripts/rebuild_bm25.py

# 5. (Optional) spaCy model for ingredient normalization
.venv/bin/python -m spacy download en_core_web_sm
```

The unified ingest CLI writes `data/ingested.json` and `data/formulations.db` in one pass.
Reruns skip unchanged PDFs/DOCX by SHA-256. Use `--force` after schema or segmentation changes.
Use `--pdf-only` to skip Word documents.

**Migration note:** Re-ingest assigns deterministic `formulation_id` values. Old random IDs in chat history may no longer resolve.

`python -m app.formulation.run_extract` is deprecated; it delegates to the same unified ingest.

## Run the dev server

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

Quick smoke check from another terminal:

```bash
curl -s http://localhost:9000/health
curl -s -X POST http://localhost:9000/chat \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"t1","message":"basic sulfate-free shampoo formula"}'

# Streaming (SSE) — tokens during LLM reasoning
curl -N -X POST http://localhost:9000/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"t1","message":"Why use CAPB instead of SLS in baby shampoo?"}'
```

## Evaluate RAG without LLM credits

Retrieval checks use **local BGE embeddings + Qdrant only** — no `LLM_API_KEY` required.

```bash
cd ai-service
.venv/bin/python scripts/eval_product.py      # ingest + retrieval + routing (product promises)
.venv/bin/python scripts/eval_ingest.py         # parser/ingestion completeness only
.venv/bin/python scripts/eval_retrieval.py      # 8 golden queries
.venv/bin/python scripts/eval_rerank.py         # compare heuristic vs CE rerank (slow first run)
```

`eval_product.py` checks what the app promises: complete structured formulas for lookup
queries, golden retrieval relevance, and no-LLM routing. Re-ingest after parser changes:

```bash
.venv/bin/python -m app.ingestion.run_ingest --force
```

`scripts/eval_precision.py` runs the same retrieval checks by default. LLM validation
is opt-in and **bills your OpenRouter account**:

```bash
# Free (default)
.venv/bin/python scripts/eval_precision.py

# One paid smoke test
.venv/bin/python scripts/eval_precision.py --llm-spot-check 1

# Full golden set (intentional spend)
.venv/bin/python scripts/eval_precision.py --with-llm
```

Optional stricter expectations live in `scripts/golden_retrieval.json` and
`scripts/golden_product.json`.

### Routing eval (minimal LLM spend)

```bash
.venv/bin/python scripts/eval_routing.py
```

Asserts lookup/compare routes avoid the LLM; reasoning intent is classification-only unless `--with-reasoning-llm`.

### OpenRouter book eval (generate 50 questions + LLM judge)

Uses `LLM_API_KEY` / OpenRouter for **question generation** and **LLM-as-judge** scoring (retrieval still local).

```bash
# Generate 50 hard stress-test questions from ingested book passages
.venv/bin/python scripts/generate_book_questions.py --hard --force

# Run pipeline + OpenRouter judge on all questions (bills OpenRouter; ~3–5 min without CE rerank)
ENABLE_CROSS_ENCODER_RERANK=false .venv/bin/python scripts/eval_openrouter.py \
  --questions scripts/generated_hard_questions.json \
  --output scripts/hard_eval_results.json

# Smoke test (first 3 questions)
.venv/bin/python scripts/eval_openrouter.py --limit 3
```

Optional `EVAL_MODEL` in `.env` overrides the judge/generator model (defaults to `LLM_MODEL`).

### Debug retrieval (dev)

When `APP_ENV` is not `production`, or `DEBUG_RETRIEVAL=true`:

```bash
curl -s 'http://localhost:9000/debug/retrieve?q=baby%20shampoo%20formula&top_k=5&formula_only=true&product_type=baby'
```

## Structured formulations

```bash
# List extracted formulas
curl -s 'http://localhost:9000/formulations?product_type=shampoo&limit=5'

# Search by ingredient
curl -s -X POST http://localhost:9000/formulations/search \
  -H 'Content-Type: application/json' \
  -d '{"product_type":"shampoo","ingredient":"water","limit":5}'
```

Ingest flags: `--docs <path>`, `--force` (rebuild SQLite + Qdrant).

## Chat routing

| Intent | Example | LLM |
|--------|---------|-----|
| lookup | anti-dandruff shampoo formula | Usually no (structured score ≥ 80) |
| compare | compare baby shampoos | Usually no |
| reasoning | why use CAPB instead of SLS? | Yes |
| unknown | best shampoo formula | Structured-first, then vector → expansion → transparent failure |

Env knobs: `STRUCTURED_DIRECT_THRESHOLD` (80), `STRUCTURED_HYBRID_THRESHOLD` (50), `ENABLE_QUERY_EXPANSION`, `USE_LLM_ON_HYBRID`, `USE_LLM_ON_VECTOR_FALLBACK`, `ENABLE_BM25_HYBRID`, `ENABLE_CROSS_ENCODER_RERANK`, `RERANK_CE_WEIGHT`.

## Project layout

```
app/
  main.py                FastAPI entrypoint, mounts routers
  config.py              Settings via pydantic-settings (.env)
  schemas.py             Pydantic models matching the frontend contract
  api/
    health.py            GET /health
    chat.py              POST /chat -> reasoning.pipeline.run_chat_pipeline
  ingestion/
    extract.py           PyMuPDF -> per-page text records
    chunk.py             Char-based sliding-window chunker
    embed.py             BGE singleton (HF_HOME pinned into ./data/hf-cache)
    index.py             Qdrant collection + upsert helpers (deterministic UUIDs)
    run_ingest.py        Unified CLI: segment -> SQLite + Qdrant + manifest
    segments.py          FormulaArtifact + segment_page (one pass)
    unified.py           process_pages: formulations + chunks together
  retrieval/
    search.py            embed_query + Qdrant + BM25 RRF + cross-encoder rerank
    rerank.py            BGE cross-encoder reranker
    bm25_index.py        sparse BM25 index (persisted JSON)
  reasoning/
    prompt.py            Grounding-only system prompt + SOURCES formatter
    llm.py               Provider-agnostic LLM client (uses the OpenAI SDK against any
                         OpenAI-API-compatible endpoint set by LLM_BASE_URL)
    router.py            intent -> structured search -> fallbacks -> optional LLM
    pipeline.py          delegates to router
    query_expand.py      cheap LLM synonym expansion (fallback only)
    templates.py         lookup/compare responses without LLM
data/
  qdrant/                Qdrant persistent volume (gitignored)
  hf-cache/              HuggingFace model cache (gitignored)
  ingested.json          Per-document SHA + chunk count manifest
docker-compose.yml       Qdrant service
Dockerfile               Optional containerised FastAPI (Python 3.12-slim)
```

## Knobs

All tunable in `.env`:


| Env var              | Default                        | Purpose                                                                     |
| -------------------- | ------------------------------ | --------------------------------------------------------------------------- |
| `QDRANT_URL`         | `http://localhost:6333`        | Qdrant endpoint                                                             |
| `QDRANT_COLLECTION`  | `pharma_chunks`                | Collection name                                                             |
| `EMBED_MODEL`        | `BAAI/bge-small-en-v1.5`       | Embedding model                                                             |
| `EMBED_DIM`          | `384`                          | Must match the model                                                        |
| `LLM_BASE_URL`       | `https://openrouter.ai/api/v1` | OpenAI-API-compatible LLM endpoint                                          |
| `LLM_API_KEY`        | (empty)                        | Required for `/chat`                                                        |
| `LLM_MODEL`          | `openai/gpt-4o-mini`           | Model id (provider-qualified for OpenRouter)                                |
| `DOCS_DIR`           | `../docs`                      | PDF source directory                                                        |
| `CHUNK_CHAR_SIZE`    | `3200`                         | ~800 tokens at 4 chars/token                                                |
| `CHUNK_CHAR_OVERLAP` | `400`                          | ~100 tokens of overlap                                                      |
| `HF_HOME`            | `./data/hf-cache`              | Keeps weights inside the workspace                                          |
| `APP_ENV`            | `development`                  | Set to `production` to hide `/debug/retrieve` unless `DEBUG_RETRIEVAL=true` |
| `DEBUG_RETRIEVAL`    | `false`                        | Enable `/debug/retrieve` in production                                      |


## LLM provider

The service uses the OpenAI Python SDK against whatever endpoint `LLM_BASE_URL`
points at. To swap providers, set three env vars and restart — no code changes:


| Provider                 | `LLM_BASE_URL`                   | `LLM_MODEL` example          | `LLM_API_KEY`                                                                              |
| ------------------------ | -------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------ |
| OpenRouter (default)     | `https://openrouter.ai/api/v1`   | `openai/gpt-4o-mini`         | `sk-or-v1-...` from [https://openrouter.ai/keys](https://openrouter.ai/keys)               |
| OpenAI direct            | `https://api.openai.com/v1`      | `gpt-4o-mini`                | `sk-...` from [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Anthropic via OpenRouter | `https://openrouter.ai/api/v1`   | `anthropic/claude-haiku-4.5` | `sk-or-v1-...`                                                                             |
| DeepSeek via OpenRouter  | `https://openrouter.ai/api/v1`   | `deepseek/deepseek-chat`     | `sk-or-v1-...`                                                                             |
| Llama 3.1 70B via Groq   | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile`    | `gsk_...`                                                                                  |
| Ollama (local, free)     | `http://localhost:11434/v1`      | `llama3.1:8b`                | `ollama` (any non-empty string)                                                            |


OpenRouter is the recommended default because it lets you switch between all
the hosted models with one env var change.

## Planned later

See [../REQUIREMENTS.md](../REQUIREMENTS.md) for the full list. Highlights still open:

- PostgreSQL formula store + SQL pre-filters (banned ingredients, cost).
- Conversation-aware retrieval; `structured_brief` wired into search.
- Batch calculator, substitution, cost estimator, regulatory checks.
- Auth on the Laravel proxy; per-user thread isolation.
- OCR for scanned PDFs.

Done in this service: hybrid BM25+vector (RRF), cross-encoder rerank, structured SQLite formulations, intent routing.

