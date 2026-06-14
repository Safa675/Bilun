# Prose corpus exports (Gate B)

Regenerable CSV/JSON exports from `sut_clauses.parquet` — candidate clauses for prose encoding.

- **Regenerable** — re-run `scripts/sut/export_material_bundling_clauses.py`, `export_material_bundling_corpus_batch2.py`, `export_specialty_prose_corpus.py`.
- **Human review** — see `docs/gazette/prose-encoding.md`.
- **Encode manifests** (which rows became JSON rules) → `data/gazette/prose_manifests/`.
- **Audit citation CSVs** (§1.8, §2.2 section dumps) → archived under `tasks/archive/sut-fact-check-2026-06/`; live clause text via Rule Database API.
