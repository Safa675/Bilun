## Task: Remove hardcoded SUT date paths

### Goal
Resolve default SUT input paths dynamically from `raw data/` so scripts keep working when new tebliğ folders are added.

### Subtasks
- [x] Add shared helper to detect latest consolidated SUT folder and main docx.
- [x] Update `extract_sut_prose.py` to auto-resolve latest docx when `--docx` is omitted.
- [x] Update `convert_xlsx_to_parquet.py` to auto-resolve latest SUT folder when `--input-dir` is omitted.
- [x] Verify both scripts resolve to current `2026.05.23` source locally.

### Out of Scope
Changing extraction logic, coverage logic, or re-running the full ETL pipeline.

## Task: Repo-wide bug remediation (phased)

### Goal
Fix all 24 bugs from the 2026-06-30 repo-wide audit: CI green, manifest integrity, honest metrics, security hardening, and regression test hygiene.

**Full plan:** `plans/testing/repo-wide-bug-remediation-phases.md`

### Subtasks

#### Phase 0 — Baseline ✅
- [x] Capture baseline metrics → `reports/bug_remediation_baseline.json`
- [x] Add `scripts/sut/audit_manifest_parity.py` + unit test

#### Phase 1 — Manifest integrity ✅
- [x] Implement `scripts/sut/prose/manifest_reconcile.py`
- [x] Wire reconciler into `tier_c_manifest_ops.py` + compile pipeline
- [x] `audit_manifest_parity.py --drug-only` exits 0

#### Phase 2 — Compiler sync ✅
- [x] `compile_rules.py --check` passes
- [x] Rebuild `sut_clause_coverage.parquet`

#### Phase 3 — Test realignment ✅
- [x] YAML parity tests (919 rules, derived wave counts)
- [x] Gate B / manifest tests aligned to reconciled manifests
- [x] Tier-C inventory + EMR catalog thresholds updated
- [x] **1692 passed**, 0 failed

#### Phase 4 — Metrics ✅
- [x] `_drug_indication_manifest_stats()` aggregates all drug manifests
- [x] `encode_tier_c_deferred_count` repo-wide (~757)
- [x] `rules_catalog.py` snake_case key
- [x] A0 inventory unions all drug manifests (+ anti-VEGF dict traces)

#### Phase 5 — Prior-therapy semantics ✅
- [x] Absent `prior_therapies` → `needs_prior_therapy_verification` + `review`
- [x] Wrong prior therapy → `prior_therapy_mismatch` + `error`
- [x] Unit tests added

#### Phase 6 — Security (B-03–B-05, B-18) ✅
- [x] Fail-closed auth default + `BILUN_AUTH_OPTIONAL=1` opt-in
- [x] `/health` 503 without `active_build` + `cache_ready` payload
- [x] Startup `_startup_ready` + strict policy exit
- [x] DuckDB reader concurrency documentation
- [x] `tests/unit/api/test_health.py` + auth test updates

#### Phase 7 — Phase 8 test paths ✅
- [x] Retarget `ACTIVE_SURFACE_ROOTS` to `frontend/` + `src/bilun/api/routes/`
- [x] Confirm `files_scanned >= 50` (102 files)
#### Phase 8 — Pipeline hardening + CI parity step ✅
- [x] `scripts/sut/prose/manifest_index.py` + wired into a0/a1/coverage/tier_c/reconcile
- [x] `test_close_algorithmic_gaps.py` — gate_b encoded never re-deferred
- [x] `encode_tier_c_bucket_d.py` — candidate-only sourcing documented
- [x] CI: `audit_manifest_parity.py --drug-only` after compile check
- [x] `write_reconciled_manifest` + test session reconcile fixtures

#### Phase 9 — Frontend CI ✅ (workflow present; local npm unavailable)
- [x] `.github/workflows/ci.yml` frontend job: `tsc`, `vitest`, `build`

#### Phase 10 — Final sign-off ✅
- [x] **1705 passed**, 0 failed
- [x] `compile_rules.py --check` PASS
- [x] `audit_manifest_parity.py --drug-only` PASS
- [x] 919 drug rules, 0 true algorithmic gaps
- [x] `reports/bug_remediation_signoff.json`
- [x] `graphify update .`

### Review

**Phases 0–5 completed 2026-06-30**

| Check | Before | After |
|-------|--------|-------|
| pytest | 41 failed | **1692 passed, 0 failed** |
| `compile_rules --check` | FAIL | **PASS** |
| Manifest parity | 20+ issues | **0** |
| `encode_tier_c_deferred_count` | 10 (4214C only) | **~757 repo-wide** |

Signoff: `reports/bug_remediation_phases_0_5_signoff.json`

**Phases 6–7 completed 2026-07-01**

| Check | Result |
|-------|--------|
| `pytest tests/unit/api/` | **127 passed** (incl. new health + auth) |
| Phase 8 surface regression | **102 files scanned**, 0 banned-word violations |
| Auth default | Fail-closed (401); `BILUN_AUTH_OPTIONAL=1` for dev/pytest |
| `/health` | 503 unless `db_ok` + `active_build` + `cache_ready` |
| Full pytest | **1698 passed**, 0 failed |

**Phases 8–10 completed 2026-07-01**

| Check | Result |
|-------|--------|
| `manifest_index.py` | 23 manifests, 2244 clause IDs indexed |
| CI manifest parity step | Added to `.github/workflows/ci.yml` |
| `close_algorithmic_gaps` tests | 3 tests (1 skipped when no gaps) |
| Full pytest | **1705 passed**, 0 failed |
| `compile_rules --check` | **PASS** |
| `audit_manifest_parity --drug-only` | **0 issues** |
| Drug rules / true gaps | **919** / **0** |
| Frontend CI (local) | npm not installed — GitHub Actions job configured |
| Signoff | `reports/bug_remediation_signoff.json` |
