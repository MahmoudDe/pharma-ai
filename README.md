# Pharma AI

Three services that together turn cosmetic formulation books into source-cited
chat answers.

**Requirements (functional, non-functional, and planned work):** see **[REQUIREMENTS.md](REQUIREMENTS.md)**.

---

| Service | Port | What it does | Folder |
|---------|------|--------------|--------|
| Next.js frontend | 3000 | Chat UI, Evidence + Suggested-actions panels | [`frontend/`](frontend) |
| Laravel backend  | 8000 | Thin auth/business shell, proxies `/api/chat/messages` to the AI service | [`backend/`](backend) |
| Python AI service (FastAPI) | 9000 | RAG pipeline: PDF -> BGE embeddings -> Qdrant -> LLM (OpenRouter by default; swappable to OpenAI, Groq, DeepSeek, Ollama, ...) | [`ai-service/`](ai-service) |
| Qdrant (Docker) | 6333 | Vector database used by the AI service | spun up via `ai-service/docker-compose.yml` |

The source documents (cosmetic formulation books) live in [`docs/`](docs) and
are ingested by `ai-service` into Qdrant.

## Quick start (one-time)

```bash
# 1. AI service: install Python deps, start Qdrant, ingest the books
cd ai-service
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env       # then edit and set LLM_API_KEY (OpenRouter key from https://openrouter.ai/keys)
docker compose up -d qdrant
.venv/bin/python -m app.ingestion.run_ingest

# 2. Laravel backend
cd ../backend
cp .env.example .env       # then `php artisan key:generate` if needed
composer install
php artisan migrate

# 3. Next.js frontend
cd ../frontend
npm install
cp .env.local.example .env.local
```

## Run all three (dev)

In three terminals from the project root:

```bash
# Terminal 1: AI service
cd ai-service && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload

# Terminal 2: Laravel
cd backend && php artisan serve --port=8000

# Terminal 3: Next.js
cd frontend && npm run dev
```

Then open <http://localhost:3000/chat> and ask, for example, "Give me a basic
sulfate-free shampoo formula".

### Warehouse (what can we make?)

Upload your manufacturer material list (CSV/Excel), resolve ingredient aliases, and
see which formulas from the books you can make:

1. Open <http://localhost:3000/warehouse>
2. Upload a file (see [`docs/examples/warehouse_sample.csv`](docs/examples/warehouse_sample.csv))
3. **Analyze materials** → **Discover products**

Requires ingested `formulations.db` and optional `LLM_API_KEY` for unresolved trade names.

## Data flow on a single chat turn

1. The browser POSTs `{ thread_id, message }` to `http://localhost:8000/api/chat/messages` (Laravel).
2. Laravel's `App\Http\Controllers\Api\ChatController` forwards the JSON to `http://localhost:9000/chat` (FastAPI).
3. FastAPI runs **metadata-filtered** vector search in Qdrant (`product_types`, `is_formula`) and loads matching rows from **SQLite** (`data/formulations.db`).
4. Both are passed to the LLM as SOURCES + STRUCTURED_FORMULATIONS; citations and `formula_lines` are validated server-side.
5. Laravel persists messages in SQLite; the UI shows cited evidence, optional **structured ingredient table**, and chat history in the sidebar.

**Re-ingest after Phase 1 metadata changes:** `cd ai-service && .venv/bin/python -m app.ingestion.run_ingest --force && .venv/bin/python -m app.formulation.run_extract`

## Evaluate RAG without LLM credits

From `ai-service/`:

```bash
.venv/bin/python scripts/eval_retrieval.py          # retrieval only (free)
.venv/bin/python scripts/eval_precision.py          # same, default
.venv/bin/python scripts/eval_precision.py --llm-spot-check 1   # one paid smoke test
```

See [`ai-service/README.md`](ai-service/README.md) for details.

For the deep dive on the AI service, see [`ai-service/README.md`](ai-service/README.md).
