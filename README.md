# BILUN

BILUN is a standalone healthcare reimbursement intelligence system. It analyzes, validates, and optimizes hospital claim reimbursements against the Turkish SGK/SUT regulations — the official Health Implementation Communiqué governing public healthcare billing in Turkey.


## Tech Stack

| Layer    | Technology                                                  |
| -------- | ----------------------------------------------------------- |
| Backend  | Python 3, FastAPI, Pydantic v2, DuckDB, pandas/polars       |
| Frontend | TypeScript, Next.js 16, React 19, Tailwind CSS v4, Zustand  |
| AI       | OpenRouter API (OpenAI-compatible), streaming SSE responses  |
| Storage  | DuckDB (embedded OLAP), Parquet catalogs                     |
| Testing  | pytest (backend), Vitest (frontend)                          |

## Quick Start

```bash
# Start everything (backend on :8001, frontend on :3000)
./start.sh all

# Backend only
./start.sh backend

# Frontend only
./start.sh frontend
```

## Project Structure

```
├── src/bilun/
│   ├── api/             # FastAPI app, routes, schemas (15 endpoints)
│   ├── domain/          # Core business logic (40+ modules)
│   │   ├── analytics/   # DRG episode modeling, cost estimation
│   │   ├── billing/     # 21 billing block detectors (BILLING_BLOCK_SPECS)
│   │   ├── optimization/# revenue rule engines
│   │   ├── pricing/     # DRG package pricing lookups
│   │   ├── rules/       # Claim validation (bundling, exclusions)
│   │   ├── claims/      # Synthetic claim-line loader
│   │   ├── materials/   # Specialty materials + drug catalogs
│   │   └── loaders/     # Gazette Parquet/JSON loaders
│   ├── db/              # DuckDB storage layer (builds, patients, alerts)
│   ├── cache/           # Analytics cache build lifecycle
│   ├── chatbot/         # SUT-aware AI assistant (OpenRouter)
│   └── shared/          # Runtime state, exceptions, utilities
├── frontend/            # Next.js SPA (BILUN branding)
├── data/                # 37 gazette catalogs + synthetic demo data
├── scripts/             # Catalog builders, data generators
├── tests/               # Unit + smoke tests
└── raw data/            # Official SGK gazette source documents
```

## Key Features

- **Claim validation** — SUT bundling/exclusion rule engine
- **6 optimization rule engines** — Copay exemptions, surcharge eligibility, copay rates, temporal price validation, DRG unbundling detection, drug discount validation
- **5 billing algorithms** — Lab billing optimizer, drug cost optimizer, copay savings calculator, package vs. itemized recommender, material reimbursability pre-check
- **DRG episode modeling** — Per-patient diagnosis-related group analysis with cost estimation
- **Patient alerts** — Exemption tracking, compliance flags
- **Revenue recovery dashboard** — Cohort-level analytics and financial exposure summaries
- **SUT-aware chatbot** — AI assistant for SUT analytics, drug catalog lookups, and billing workflow guidance
- **Exactness-aware computation** — All billing surfaces track whether inputs are exact claim lines, synthetic demo data, or unavailable; the system refuses to guess recovery amounts

## Environment Variables

| Variable               | Default                       | Description                                                        |
| ---------------------- | ----------------------------- | ------------------------------------------------------------------ |
| `BILUN_CACHE_DB_PATH`  | `.cache/bilun.duckdb`         | DuckDB analytics cache                                             |
| `BILUN_STARTUP_POLICY` | `load-only`                   | `load-only` or `rebuild`                                          |
| `LLM_API_KEY`          | —                             | OpenRouter API key (chat)                                          |
| `EMBEDDING_PROVIDER`   | `auto`                        | SUT clause embeddings: `auto` \| `openai` \| `local`              |
| `EMBEDDING_API_KEY`    | — (falls back to `OPENAI_API_KEY`) | OpenAI key for embeddings (OpenRouter does **not** serve `/embeddings`) |
| `EMBEDDING_MODEL`      | `text-embedding-3-large`      | Embedding model when provider is OpenAI                            |
| `EMBEDDING_DIMS`       | `1024`                        | Embedding dimensionality (OpenAI `text-embedding-3-*`)            |
| `EMBEDDING_BASE_URL`   | `https://api.openai.com/v1`   | OpenAI-compatible embeddings base URL                             |

### SUT clause retrieval (chatbot)

The chatbot can answer free-text SUT questions via the `search_sut_clauses` tool, which retrieves cited, in-force clauses from `data/gazette/sut_clauses.parquet`. Build the embeddings sidecar after extracting clauses:

```bash
# Production quality (needs an OpenAI key):
EMBEDDING_PROVIDER=openai EMBEDDING_API_KEY=sk-... bilun-build-clause-embeddings

# Offline fallback (deterministic, no key/network, lower quality):
python scripts/sut/build_clause_embeddings.py --provider local
```

Run order: `extract_sut_prose.py` → `build_clause_embeddings.py`. If the sidecar is absent, the tool degrades gracefully (returns no clauses).

## Testing

```bash
pytest                  # Unit tests
pytest --live           # Smoke tests against live server
cd frontend && npx vitest run  # Frontend tests
```

## License

Proprietary. Copyright Safa Oksuz. All rights reserved.
