# SUT Clause Retrieval Tool (RAG-as-a-tool) — Implementation Plan

> Status: IMPLEMENTED (2026-06-14) — all phases done; 468 unit tests green.
> Author decision record: embeddings via OpenAI `text-embedding-3-large`; surface as a `search_sut_clauses` tool inside the existing chatbot; in-memory hybrid retrieval (no vector DB).

---

## Task: SUT Clause Retrieval Tool

### Goal

Let the existing BILUN chatbot answer free-text Turkish SUT questions by retrieving the most relevant **non-superseded** SUT clauses from `data/gazette/sut_clauses.parquet` and citing them (`section_id`, `annex_refs`, `source_effective_date`), with **zero new infrastructure** — embeddings precomputed offline, similarity done in-memory, exposed as one new allowlisted chatbot tool.

### Why this shape (vs. a generic RAG stack)

- The chatbot is already **agentic tool-calling** (`src/bilun/chatbot/tools.py`, `src/bilun/chatbot/llm.py`), not RAG. Adding a retrieval *tool* reuses the existing allowlist, JSON-schema validation, circuit breaker, timeout, audit log, SSE streaming, and citation-aware system prompt — instead of building a parallel pipeline.
- Corpus is tiny (`sut_clauses.parquet` ≈ 854 KB, a few thousand clauses). Brute-force cosine over an in-memory float32 matrix is sub-millisecond. **No pgvector / DuckDB-vss / Chroma / Qdrant needed.**
- Clauses are already chunked along legal boundaries (`clause_type` = chapter/section_heading/fıkra/bent) and already carry citation metadata (`scripts/sut/prose/extractor.py:4-27`). The retrieval is the easy part; the metadata is the value.

---

## Subtasks

### Phase 0 — Config & decisions (no code)
- [ ] Confirm OpenAI embeddings access. **Important nuance:** OpenRouter (`https://openrouter.ai/api/v1`) does **not** serve an `/embeddings` route — the existing `LLM_API_KEY`/OpenRouter plumbing is chat-only. Embeddings need OpenAI's `https://api.openai.com/v1/embeddings` with an OpenAI key. Add `EMBEDDING_API_KEY` (fallback `OPENAI_API_KEY`) + `EMBEDDING_MODEL` (default `text-embedding-3-large`) + `EMBEDDING_BASE_URL` (default `https://api.openai.com/v1`) env vars; document in README env table.
- [ ] Decide embedding dimensionality: default 3072 for `text-embedding-3-large`; optionally request `dimensions=1024` to shrink the sidecar (acceptable quality, ~3x smaller). Pick 1024 unless quality eval says otherwise.

### Phase 1 — Offline embedding build (batch, vectorized)
- [ ] New script `scripts/sut/build_clause_embeddings.py`:
  - Read `data/gazette/sut_clauses.parquet` with Polars.
  - Filter the embeddable set: drop `is_heading == True` and `is_superseded_marker == True`; keep `clause_type in {fikra, bent, prose, amendment}`. (Headings carry no answerable prose.)
  - Build embed text = `section_id` + `section_title` + `text_tr` (prefix the section so the vector captures structural context).
  - Batch-call OpenAI embeddings (batches of ~256 inputs) via `httpx`, with retry/backoff. Vectorized numpy stack — no per-row Python loop for math.
  - Write sidecar `data/gazette/sut_clause_embeddings.parquet`: `clause_id`, `embedding` (list[float32]), `embed_model`, `embed_dims`, `built_at`, plus a content hash of `text_tr` for staleness detection.
  - Idempotent: skip clauses whose `clause_id` + content-hash already exist; only embed new/changed clauses.
- [ ] Add `bilun-build-clause-embeddings` entry to `pyproject.toml` `[project.scripts]`.
- [ ] Document run order: `extract_sut_prose.py` → `build_clause_embeddings.py`.

### Phase 2 — Retrieval engine (domain layer, in-memory)
- [ ] New module `src/bilun/domain/sut/clause_retrieval.py`:
  - Module-level cached load of `sut_clauses.parquet` (metadata) joined with `sut_clause_embeddings.parquet` (vectors) into a single Polars frame + a numpy `(N, dims)` float32 matrix (L2-normalized once at load). Mirror the graceful-degradation + `reset_cache()` pattern in `rules_catalog.py:62-132`.
  - `embed_query(text)` — single embeddings call (cached by query hash within process).
  - **Hybrid scoring** (legal text needs keyword + structure, not pure semantic):
    1. Hard metadata filters: exclude `is_superseded_marker`; if query contains an explicit ref (`§3.1.2`, `EK-2/C`, a `P######`/`L######` code) filter to matching `section_id` / `annex_refs` / `procedure_codes` first.
    2. Lexical score: token overlap / simple BM25-ish over `text_tr` (Turkish-lowercased).
    3. Vector score: cosine (query · normalized matrix), vectorized.
    4. Final = weighted sum (start 0.5 vector / 0.3 lexical / 0.2 structural), then a recency tiebreak on `source_effective_date` (newer wins).
  - `search_clauses(query, *, top_k=5, annex=None, section_prefix=None) -> list[dict]` returning narrow citation payloads (reuse `_clause_payload` shape from `rules_catalog.py:206-225`: `clause_id`, `section_id`, `section_title`, `text_tr`, `annex_refs`, `source_effective_date`, `score`).
  - Bound payload: cap `text_tr` length and `top_k` so it fits the chatbot's 8 KB `RESPONSE_SIZE_CAP` (`tools.py:187`).

### Phase 3 — Wire as a chatbot tool
- [ ] In `src/bilun/chatbot/tools.py`:
  - Add a `search_sut_clauses` schema to `TOOL_SCHEMAS` (params: `query` required string; optional `annex`, `section_prefix`).
  - Add to `_TOOL_FUNCTION_MAP` and the `_exec()` namespace, calling `clause_retrieval.search_clauses(...)`.
  - Reuse existing validation/timeout/circuit-breaker — no new safety code.
- [ ] Update the system prompt (`src/bilun/chatbot/prompts.py`) so the model: (a) calls `search_sut_clauses` for regulatory questions, (b) answers **only** from returned clause text, (c) cites `§section_id`, `annex_refs`, and `source_effective_date` (e.g. "§3.1.2(2), EK-2/C, 17.01.2026"), (d) says "ilgili SUT maddesi bulunamadı" when retrieval is empty rather than guessing.

### Phase 4 — Optional thin endpoint (deferred)
- [ ] Not in scope for v1 (decision: tool-only). If a clean demo surface is later wanted, a thin `POST /api/sut-ask` can wrap `clause_retrieval.search_clauses` — left as a follow-up.

### Phase 5 — Evaluation (non-negotiable for a regulatory assistant)
- [ ] Build a gold set `tests/data/sut_retrieval_gold.jsonl`: 20–30 Turkish questions → expected `clause_id`(s) / `section_id`(s). Source from `raw data/Interviews/` real questions where possible.
- [ ] `tests/domain/sut/test_clause_retrieval.py`:
  - Retrieval metric: recall@5 over the gold set (target ≥ 0.8 to ship).
  - Supersession guard: assert no clause with `is_superseded_marker == True` is ever returned.
  - Ref-filter test: a query naming `EK-2/C` returns only `EK-2/C`-tagged clauses.
  - Graceful degradation: missing embeddings parquet → tool returns empty, no crash (mirror `rules_catalog` behavior).
- [ ] Manual smoke: run a known SUT question through the chatbot end-to-end and verify citations match the source clause.

---

## Out of Scope

- Any vector database (pgvector, DuckDB-vss, Chroma, Qdrant) — explicitly rejected for this corpus size.
- Re-ingesting PDFs/DOCX for the main SUT corpus — `sut_clauses.parquet` already exists and is the source.
- Indexing other documents (MEDULA guide, SGK circulars, appeal decisions) — possible later, same pipeline, not v1.
- A standalone `/api/sut-ask` endpoint (Phase 4 deferred).
- Fine-tuning or swapping the chat model.
- Frontend changes — the existing chat UI already renders tool-grounded answers.

---

## Definition of Done

1. `build_clause_embeddings.py` produces `sut_clause_embeddings.parquet` and is idempotent on re-run.
2. `search_sut_clauses` is an allowlisted chatbot tool returning cited, non-superseded clauses within the 8 KB cap and 5 s timeout.
3. The chatbot answers a Turkish SUT question grounded in retrieved clauses with correct `§section_id` / annex / effective-date citations, and refuses when nothing is retrieved.
4. Retrieval eval recall@5 ≥ 0.8 on the gold set; supersession guard test passes.
5. `pytest -q` green; new env vars documented in README.

---

## Key file references (verified)

- Clause source + schema: `data/gazette/sut_clauses.parquet`, schema in `scripts/sut/prose/extractor.py:4-27`
- Path constants: `src/bilun/domain/constants.py:26-29`
- Existing clause loader pattern to mirror: `src/bilun/domain/sut/rules_catalog.py:62-132, 206-225`
- Tool registry to extend: `src/bilun/chatbot/tools.py:25-185, 299-425`
- LLM client / env plumbing: `src/bilun/chatbot/llm.py:33-45`
- Chatbot tool loop cap: `src/bilun/chatbot/tools.py:187-189`

---

## Review (2026-06-14)

### What shipped
- `src/bilun/domain/sut/embeddings.py` — pluggable providers: `OpenAIEmbeddingProvider` (default `text-embedding-3-large`, dims via `dimensions=`) + `LocalHashEmbeddingProvider` (deterministic, offline). `resolve_provider()` keys off the stored `embed_model` so the query always embeds in the corpus's space; `default_build_provider()` is env-driven (`auto`/`openai`/`local`).
- `scripts/sut/build_clause_embeddings.py` — idempotent offline build (content-hash reuse). Entry point `bilun-build-clause-embeddings`. Built `data/gazette/sut_clause_embeddings.parquet` (6162 clauses; headings + 282 superseded excluded).
- `src/bilun/domain/sut/clause_retrieval.py` — cached in-memory hybrid search: hard metadata filters (`§section`, `EK-x/y`, `P######`) + idf-weighted lexical + cosine vector, with graceful degradation when the sidecar is absent. No vector DB.
- `src/bilun/chatbot/tools.py` — `search_sut_clauses` added to the allowlist/schema/executor; reuses validation, 5 s timeout, circuit breaker, 8 KB cap.
- `src/bilun/chatbot/prompts.py` — added retrieval/citation guidance (answer only from returned clauses; cite §/EK/effective-date; refuse when empty).
- Tests: `tests/unit/domain/sut/test_clause_retrieval.py` (+ `tests/data/sut_retrieval_gold.jsonl`, 15 Q) and tool-routing tests in `tests/unit/chatbot/test_tools.py`.

### Results
- recall@5 = 0.87 on the gold set with the **local-hash** provider (≥ 0.8 bar; OpenAI expected higher).
- Supersession guard: returned clause IDs are disjoint from the 282 superseded clauses across multiple queries.
- End-to-end tool call: 5 EK-2/C-filtered cited clauses, 3.3 KB payload (< 8 KB cap), within the 5 s timeout.
- Full suite: **468 passed**.

### Notable
- Fixed a latent bug: `ToolCallResult.content` had no default, so the validation-failure and circuit-breaker branches in `execute_tool_call` would have raised `TypeError`. Added `content: str = ""`.
- The committed embeddings sidecar is the **local-hash** build (works in CI offline). For production quality, rerun `bilun-build-clause-embeddings` with an OpenAI key — `embed_model` in the parquet makes the swap automatic and self-consistent.

### Deferred (unchanged from plan)
- `POST /api/sut-ask` standalone endpoint; indexing MEDULA guide / circulars / appeal decisions.
