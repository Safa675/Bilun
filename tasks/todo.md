## Task: Track C — One derive pipeline (slice A)

### Goal
Manifest + coverage are boring, single-shaped derivatives for drug Gate B: one `canonical-v1` schema, thin drug compile path, no corpus CSV in runtime/CI lock. C3+C5 deferred to next PR.

### Decisions (locked)
- [x] Phased: this PR = C1 + C2 + C4-partial; next PR = C3 + C5
- [x] Non-drug (payment / material / specialty / anti-vegf / copay) = Track F exceptions
- [x] Fold uncommitted B1 delete-cut into this PR

### Subtasks

#### C1 — Canonical manifest
- [x] Add JSON schema for `canonical-v1`
- [x] Extend `build_canonical_encoded_shell` (section_clause_total + preserve buckets)
- [x] Re-stamp SUT non-canonical manifests (skip fatura + L1.8 copay)
- [x] Set every `GateBSection.manifest_version` → `canonical-v1`
- [x] Flip compile targets still on `t1-v1` / wave labels
- [x] Test: every SUT manifest validates + version == canonical-v1

#### C2 — Thin compile (drug)
- [x] Collapse drug `gate_b_writer` flavors → one `gate_b_generic`/`shim` path
- [x] Delete dead `gate_b_module` / `from_prose` branch
- [x] Document ≤2 exceptions: `4201_w4`, `4213_tier_b_remap`
- [x] Port phase5 off corpus write; keep `repair_4214c` as documented exception until C3
- [x] Leave payment / material / specialty / anti-vegf as Track F

#### C4 partial — Corpus CSV
- [x] Stop writing corpus CSV from generic/shim (default `write_corpus=False`)
- [x] Drop `prose_corpus/*.csv` from `compile_rules.py --check`
- [x] Delete dead `_L*_CORPUS_PATH` in `rules_catalog.py`
- [x] Update gate_b tests off committed CSV; optional export via `write_corpus=True`

#### Deferred (slice B)
- [ ] C3: coverage one function; delete a0/a1/manifest helpers
- [ ] C5: delete `gate_b_shim` + dead exports

### Out of Scope
- Track D/E, full Track F non-drug port
- Evaluator clinical matching
- `plans/deployment/vps-openhands-smoke-test.md`

### Review
- Branch / PR: `refactor/sut-pipeline-god-plan` → https://github.com/Safa675/Bilun/pull/43
- C1: schema + restamp; exceptions fatura + L1.8
- C2: one writer path; export includes `clause_coordinate`; resolve against full parquet
- C4: CSV optional export only; `--check` no longer fingerprints corpus
- Verified: 123 gate_b + schema tests pass; compile `drug_indication_4206` OK
