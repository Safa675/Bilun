# Prose encode manifests

Canonical JSON manifests for SUT Gate B / gap-closing encode batches
(`manifest_version: canonical-v1`).

- **Schema:** `schemas/canonical_v1.schema.json`
- **Restamp:** `python -m scripts.sut.prose.restamp_canonical_manifests`
- **Writers:** `gate_b_generic.build_manifest` (drug Gate B) and
  `manifest_index.build_canonical_encoded_shell` (encoded-only stubs)
- **Exceptions (not canonical-v1 yet):**
  - `fatura_inceleme_prose_manifest.json` — Fatura epic
  - `L1.8_copay_exemption_encoded_manifest.json` — Track F compositor shape
- **Corpus CSVs** under `data/gazette/prose_corpus/` are optional human exports
  (Track C4); runtime coverage/catalog use parquet + rule JSON + manifests.
