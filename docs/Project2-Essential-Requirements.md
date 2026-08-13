# Project 2 — Pharma AI — Essential Requirements

**Project:** Pharma AI — Cited Formulation Library  
**Scope:** MVP essentials only (functional + non-functional)

---

## 1. Essential functional requirements

### 1.1 Knowledge base (core product)

| ID | Requirement | Why essential |
|----|-------------|---------------|
| FR-ING-08 | Detect formula regions and extract structured formulations in the same pass as chunking | Without this there is no formulation library — only generic RAG chunks. |
| FR-ING-09 | Persist structured formulations in SQLite (`data/formulations.db`) | Stable, queryable catalog of unique recipes with line-level data. |
| FR-FORM-01 | Parse common table layouts: percent tables, wt/wt%, column weights, inline weights | Reference books are tables; this is the core extraction problem. |
| FR-FORM-04 | Assign deterministic `formulation_id` for stable references | Stable links from chat, library, and citations across sessions. |
| FR-FORM-07 | Public API: list formulations with filters (`GET /formulations`) | Browse and search the library outside chat. |

### 1.2 Retrieval (find the right recipe)

| ID | Requirement | Why essential |
|----|-------------|---------------|
| FR-RET-05 | Structured-first search with score thresholds (direct / hybrid / fallback) | Fast, accurate path for “give me a shampoo formula” — the main user intent. |
| FR-RET-02 | Metadata filters: `product_types`, `is_formula`, formula-only mode | Reduces irrelevant hits (e.g. baby bath vs baby shampoo). |
| FR-RET-07 | Transparent failure message when no grounded sources found | Prevents silent hallucination; critical in a pharma context. |
| FR-RET-11 | Multilingual retrieval (Arabic queries on English books) | Matches real users and Arabic inventory / form documents. |

### 1.3 Chat and trust (how answers are produced)

| ID | Requirement | Why essential |
|----|-------------|---------------|
| FR-CHAT-02 | Return assistant text grounded only in retrieved sources | Core product promise: answers come from books, not model memory. |
| FR-CHAT-03 | Return `cited_evidence` with document id, pages, and quotes | Every claim must be traceable to source text. |
| FR-CHAT-04 | Server-side validation: quotes must appear in source chunks | Enforces traceability in code, not only in the prompt. |
| FR-CHAT-08 | Route lookup/compare queries without LLM when structured score ≥ threshold | Formulas come from extraction, not generation — better accuracy and lower cost. |
| FR-CHAT-06 | Return `structured_formulation` / `structured_formulations` when applicable | User sees the actual recipe table, not prose only. |
| FR-CHAT-12 | Accept `structured_brief` (product type, banned/preferred ingredients, batch size, cost target) | Real formulation workflow: constraints before search. |

### 1.4 Minimum UI and API (delivery shell)

| ID | Requirement | Why essential |
|----|-------------|---------------|
| FR-UI-01 | Chat page with message thread and composer | Primary user entry point. |
| FR-UI-02 | Evidence panel showing citations from the latest assistant turn | Makes citations visible — trust UX. |
| FR-UI-03 | Structured formula panel (ingredient table + procedure) | Shows extracted recipe as first-class data. |
| FR-API-02 | `POST /api/chat/messages` — proxy to AI service, persist user + assistant messages | Orchestration and audit trail. |
| FR-API-03 | `GET/POST /api/chat/threads` — list and create threads | Conversation continuity for pharmacists. |
| FR-API-04 | `GET /api/chat/threads/{id}` — thread detail with messages and citations JSON | Reload history with evidence intact. |

---

## 2. Essential non-functional requirements

| ID | Requirement | Why essential |
|----|-------------|---------------|
| NFR-ACC-01 | Answers must not invent citations; invalid quotes stripped or flagged | Quality and safety bar for formulation advice. |
| NFR-ACC-03 | Grounding-only system prompt (reference books are authority, not general world knowledge) | Prevents generic “ChatGPT knows cosmetics” behavior. |
| NFR-ACC-04 | Regression tests on golden retrieval queries (no LLM spend) | Proves the library works as the corpus grows. |
| NFR-COST-01 | Minimize LLM calls via intent routing and structured direct answers | Makes MVP affordable at pilot scale. |
| NFR-REL-01 | Graceful degradation when AI service unreachable (user-visible error, retry) | User is not left with a silent failure. |
| NFR-REL-02 | Readiness probe fails if Qdrant empty or SQLite missing formulations | Avoids “empty brain” chat in production. |
| NFR-SEC-01 | Secrets only in `.env` / `.env.local` (never committed) | Baseline for any real deployment. |
| NFR-PERF-03 | Lookup/compare path avoids LLM for sub-second structured responses | Defines acceptable UX for the most common queries. |

---

## 3. Phase 2 (important, not MVP identity)

| Area | Requirement IDs | Note |
|------|-----------------|------|
| Hybrid retrieval | FR-RET-09, FR-RET-03 | Improves recall; structured-first search already works. |
| Streaming chat | FR-CHAT-13 | UX polish for reasoning turns. |
| Formulation tools | FR-TOOL-02, FR-TOOL-07 | Batch calculator and side-by-side compare. |
| Authentication and tenancy | FR-API-11, FR-API-12 | Optional before multi-user production (no admin roles). |
| Security (production) | NFR-SEC-03, NFR-SEC-04, NFR-SEC-06 | Auth, TLS, tenant isolation. |
| Scale and operations | FR-ING-10, NFR-PERF-06, NFR-MAINT-05, NFR-MAINT-06 | Cron ingest, job queue, metrics, CI. |
| More sources | FR-ING-11, FR-ING-12 | OCR for scanned PDFs; XLSX/web ingest. |
| Database scale | FR-FORM-09 | PostgreSQL when multi-tenant filters are needed. |

---

## 4. One-sentence project definition

Pharma AI ingests reference formulation books into a **cited, structured library**, answers pharmacist questions **only from retrieved sources with page-level evidence**, and supports **constrained search** (product type, banned ingredients), with lookup/compare paths that **prefer extracted formulas over LLM generation**.
