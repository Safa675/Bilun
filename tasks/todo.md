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
- [x] Capture baseline metrics → `reports/archive/bug_remediation_baseline.json`
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

Signoff: `reports/archive/bug_remediation_phases_0_5_signoff.json`

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

---

## Task: Rule-Encoding Gap Closure & Unified Claim Engine

### Goal
Eliminate the 2,183 "implemented/partial but not encoded" clauses via honest reclassification + real encoding + a unified claim engine. Drop `has_algorithmic_gap` from 1,896 → <150.

**Full plan:** `plans/refactor/rule-encoding-gap-closure-roadmap.md`
**Branch:** `rule-encoding-gap-closure`

### Verified baseline (post-`ec33851`, captured 2026-07-05)
4,710 in-force rows · implemented=1,585 · partial=2,422 · non_algorithmic=703 · encoded=1,978 · **gaps=1,896 (40.3%)** · unencoded(impl|partial)=2,183

### Subtasks

#### Phase 0 — Hygiene (~2 days)
- [ ] 0.1 Reconcile 61 orphan `gate_b_sources` (32 drug rules, struck clauses) via `amendment_refs` + `_apply_source_patches`
- [ ] 0.2 Delete dead `data/gazette/prose_rules/schemas/base_rule_set.schema.json`
- [ ] 0.3 Soften brittle `==` count locks in `test_rule_sources.py:79-80,86,113,129` + `test_drug_indication_gate_b.py:18,20` + `==131/282/832` tests → `>=` floors
- [ ] 0.4 Extract `is_implemented_but_unencoded(row)` helper into `coverage.py` (next to `:118`); replace masks in 5 scripts
- [ ] **Checkpoint 0:** `pytest tests/unit/scripts/test_{rule_sources,sut_coverage}.py` green; `build_sut_coverage.py` reproduces 1,896 gaps / 1,978 encoded ±0; orphan count == 0

#### Phase 1 — Honest reclassification (~1 week)
- [ ] 1.1 Reclassify 821 structural (amendment/section_heading) → `non_algorithmic` via `_has_actionable_signal` (`coverage.py:79-93`)
- [ ] 1.2 Reclassify ~66 pure annex-lookup clauses (text is essentially `(EK-x)`)
- [ ] 1.3 Reclassify ~250 price-oracle/code-only decision-rule clauses via explicit `RECLASSIFY_AS_NON_ALGORITHMIC` set
- [ ] **Checkpoint 1:** `non_algorithmic` up ~1,100–1,200; `algorithmic_gaps` drops materially

#### Phase 2 — Unified claim engine (3–4 weeks, HIGHEST RISK)
- [ ] 2.1 `check_bundling_violations_for_context` + `check_exclusion_violations_for_context` + 50-claim parity test (**HARD GO/NO-GO GATE**)
- [ ] 2.2 Canonical dict→`PatientClaimContext` adapter (`src/bilun/domain/claims/adapter.py`)
- [ ] 2.3 New `analyze_claim(ctx)` core in `src/bilun/domain/billing/engine.py`
- [ ] 2.4 `validate_claim(dict)` → thin adapter; preserve `ClaimValidationResult` contract; double-counting audit
- [ ] 2.5 Caller migration (no-op if 2.4 preserves contract); chatbot monkeypatch path intact
- [ ] 2.6 `compute_patient_billing_report` → facade over `analyze_claim`
- [ ] **Checkpoint 2 (HARD GATE):** parity + chatbot round-trip + `/validate-claim` byte-identical + cohort totals identical

#### Phase 3 — New prose evaluators (~1 week, gated on Phase 2)
- [ ] 3.1 Wire `dental_2_4_1` (evaluator exists)
- [ ] 3.2 Wire + encode `drg_package_adequacy` (28 clauses)
- [ ] 3.3 Wire `procedure_pairing`
- [ ] 3.4 `material_preauth_ek3c1` → JSON rules + encode 2
- [ ] 3.5 `material_miat_ek3c2` → JSON rules + encode 3
- [ ] 3.6 Add `// CODE-ONLY BY DESIGN` markers to skipped motors
- [ ] **Checkpoint 3:** evaluator unit tests; encoded count +~40

#### Phase 4 — Encode decision-rule clauses (~2 weeks)
- [ ] 4.1 `material_bundling_prose` (44 real, ~2 batches)
- [ ] 4.2 `specialty_materials_prose` (~190 real, ~4 batches)
- [ ] 4.3 `copay_rate_general` (34 real, paired refactor)
- [ ] 4.4 `drg_unbundling` (4 clauses, decision at entry)
- [ ] **Per-batch workflow:** subagent owns `*_patches.py` + own manifest; orchestrator sequential `compile_rules` + `coverage.py` wiring
- [ ] **Checkpoint 4:** monotonic encoded↑/gap↓; `algorithmic_gaps` in low hundreds

#### Phase 5 — Drug Tier-C re-triage (~1.5 weeks)
- [ ] 5.1 Build ~860-clause triage worklist
- [ ] 5.2 Per-section PROMOTE/KEEP-DEFERRED/EMR-BLOCKED triage
- [ ] 5.3 Encode PROMOTE set via drug parametric shape
- [ ] 5.4 Update 23 drug manifests via `reconcile_drug_manifests`
- [ ] **Checkpoint 5:** section `manifest_coverage_pct` ≥95%; `drug_indication_prose` gaps <100

#### Phase 6 — Final verification (~3 days)
- [ ] 6.1 Full fresh pipeline + cache rebuild
- [ ] 6.2 Gap reconciliation (<150 target)
- [ ] 6.3 Dashboard audit
- [ ] 6.4 Full test suite green
- [ ] 6.5 Update `tasks/lessons.md`
- [ ] **Checkpoint 6:** staff-engineer review

### Out of Scope
No gap-policy change (A retained). No new rule categories. No frontend rewrite. No DB schema changes. `payment_method`/`copay_rate_general`/`surcharge_general`/`lab_billing` stay code-only. No cohort regen unless 6.1 surfaces a latent bug.

### Review
_To be updated at each checkpoint._
