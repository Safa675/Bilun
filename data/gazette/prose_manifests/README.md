# Prose encode manifests

Canonical JSON manifests for SUT Gate B / gap-closing encode batches
(`manifest_version: canonical-v1`).

- **Schema:** `schemas/canonical_v1.schema.json`
- **Writers:** `gate_b_generic.build_manifest` / `write_artifacts` and
  `manifest_index.build_canonical_encoded_shell` (encoded-only stubs)
- **Exceptions (not canonical-v1 yet):**
  - `fatura_inceleme_prose_manifest.json` — Fatura epic
- **Corpus CSVs** under `data/gazette/prose_corpus/` are optional human exports
  (Track C4); runtime coverage/catalog use parquet + rule JSON + manifests.
