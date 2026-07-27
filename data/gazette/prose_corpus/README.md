# Prose corpus exports (Gate B)

Optional regenerable CSV/JSON exports from `sut_clauses.parquet` — candidate
clauses for human review. **Not** part of the compile/coverage derive pipeline
(Track C4).

- **Not committed** — `*.csv` under this directory are gitignored; regenerate locally when needed.
- **Regenerate** — `export_specialty_prose_corpus.py`, or Gate B writers with `write_corpus=True`
  (`gate_b_generic.write_artifacts`).
- **Human review** — see `docs/gazette/prose-encoding.md`.
- **Review prototypes (XLSX + HTML)** — `python scripts/sut/export_prose_review_bundle.py` → `review/*.review.xlsx` and `*.review.html`.
- **Encode manifests** (which rows became JSON rules) → `data/gazette/prose_manifests/`.
