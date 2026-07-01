# Repo-wide bug remediation — phased plan

**Created:** 2026-06-30  
**Source:** Repo-wide bug search (pytest + `compile_rules --check` + manifest integrity scan + security review)  
**Current baseline:** 41 failing tests, `compile_rules --check` fails on 20 artifacts, manifest list/trace drift on §4.2.14.C and sibling manifests

---

## How to use this plan

- Phases are **sequential** unless marked parallel-safe.
- Each phase ends with explicit **verification** — do not start the next phase until green.
- Bug IDs (`B-01` … `B-24`) map 1:1 to findings in the audit; every bug appears exactly once.
- Implementation tracking: mirror checkboxes into `tasks/todo.md` when execution starts.

---

## Phase 0 — Baseline & guardrails (½ day)

**Goal:** Freeze the broken state, make drift visible, prevent new regressions while fixing.

| ID | Bug | Action |
|----|-----|--------|
| B-20 | No single source of truth for “is CI green?” | Capture baseline: `pytest -q`, `compile_rules --check`, manifest parity script output → `reports/bug_remediation_baseline.json` |
| — | Accidental partial fixes | Add a one-shot `scripts/sut/audit_manifest_parity.py` that fails if any manifest has `list_ids ⊄ trace_ids` or bucket list sum ≠ trace count |

**Deliverables**

- [ ] `reports/bug_remediation_baseline.json`
- [ ] `scripts/sut/audit_manifest_parity.py` (+ unit test with fixture manifest)

**Verification**

```bash
python scripts/sut/audit_manifest_parity.py   # documents current failures
python -m pytest tests/unit/scripts/test_audit_manifest_parity.py -q
```

**Out of scope:** Fixing anything yet — measurement only.

---

## Phase 1 — Manifest data integrity (P1, blocks honest coverage)

**Goal:** `clause_traces` is authoritative; bucket ID lists are derived, not independently grown.

| ID | Bug | Root cause | Fix |
|----|-----|------------|-----|
| B-06 | §4.2.14.C manifest lists sum to **833** but only **615** traces; 218 stale IDs | `tier_c_manifest_ops` / bucket D updated lists without syncing traces | Add `reconcile_manifest_buckets(manifest_path)` |
| B-06a | Same drift in 4201, 4209_4227, 4213_4216, 4234 manifests | Partial bucket updates | Run reconciler across **all** `L4.2_drug_indication_*` + `L4.33_anti_vegf_*` manifests |
| B-12 | `tier_c_manifest_ops` skips missing manifest files silently | `if not path.is_file(): continue` | Log warning + accumulate `skipped_manifests` in return stats; fail in `--strict` mode |
| B-06b | `clause_trace_complete: true` while lists diverge | No parity check at write time | Set `clause_trace_complete` only when audit passes; otherwise `false` + `parity_errors[]` |

**Implementation sketch**

1. **`scripts/sut/prose/manifest_reconcile.py`**
   - For each trace: set `manifest_status` ∈ `{encoded, tier_c_deferred, emr_blocked, non_actionable}`.
   - Rebuild `encoded_clause_ids`, `tier_c_deferred_clause_ids`, `emr_blocked_clause_ids`, `non_actionable_clause_ids` **from traces only**.
   - Recompute `*_count` fields from list lengths.
   - Drop list IDs not present in traces (stale).
   - For traces missing defer metadata: backfill `defer_reason` / `defer_themes` via `infer_defer_themes` + bucket status templates.

2. **Wire reconciler**
   - Call at end of `update_manifest_bucket()` before write.
   - Call from `encode_tier_c_bucket_{b,c,d}.py` main paths.
   - Add `python scripts/sut/prose/manifest_reconcile.py --all` for one-shot repair.

3. **Harden `tier_c_manifest_ops.py`**
   - Always update trace when list changes (create trace stub if missing, using clause parquet text).
   - Never `continue` on missing manifest without reporting.

**Files**

- `scripts/sut/tier_c_manifest_ops.py`
- `scripts/sut/prose/manifest_reconcile.py` (new)
- `scripts/sut/encode_tier_c_bucket_*.py`
- `data/gazette/prose_manifests/L4.2_drug_indication_*.json`
- `data/gazette/prose_manifests/L4.33_anti_vegf_*.json`

**Verification**

```bash
python scripts/sut/prose/manifest_reconcile.py --all
python scripts/sut/audit_manifest_parity.py   # must exit 0
# §4.2.14.C: encoded+emr+tier_c+non_actionable == 615, each list ⊆ trace ids
```

**Success criteria**

- [ ] All drug manifests: `len(union(bucket_lists)) == len(clause_traces)` and lists ⊆ trace IDs
- [ ] §4.2.14.C: encoded **413**, non_actionable **165**, emr **27**, tier_c **10** (matches trace distribution)

---

## Phase 2 — Compiler & committed artifact sync (P0)

**Goal:** `compile_rules.py --check` passes; committed JSON/CSVs/manifests match compiler output.

| ID | Bug | Fix |
|----|-----|-----|
| B-02 | `compile_rules --check` fails on 20 artifacts | Full regen after Phase 1 reconcile |
| B-02a | Corpus CSV drift (4206, 4209_4227, 4215, 4224, 4235_4237, 4238) | Re-run affected gate_b export stages inside compile pipeline |
| B-02b | `drug_indication_prose.json` drift | Full `drug_indication_prose` target compile from YAML + patches |

**Steps**

1. [ ] Run Phase 1 reconciler first (manifests are compile inputs for some stages).
2. [ ] `python scripts/sut/compile_rules.py` (no `--check`).
3. [ ] `python scripts/sut/prose/coverage.py` or `build_sut_coverage.py` — rebuild `sut_clause_coverage.parquet`.
4. [ ] `python scripts/sut/compile_rules.py --check` → exit 0.
5. [ ] Commit all changed artifacts under `data/gazette/`.

**Verification**

```bash
python scripts/sut/compile_rules.py --check
python -m pytest tests/unit/scripts/test_rule_sources.py::test_yaml_sources_match_runtime_rule_json -q
```

**Success criteria**

- [ ] Zero changed files on `--check`
- [ ] `drug_indication_prose.json` has **919** rules; YAML loader parity identical

---

## Phase 3 — Test suite realignment (P0 / P3)

**Goal:** All 41 failing tests pass with **honest** assertions (not weakened to greenwash).

### 3A — Rule source parity tests (6 failures)

| ID | Bug | Old constant | New constant / approach |
|----|-----|--------------|------------------------|
| B-13 | `test_drug_yaml_all_paths_cover_full_corpus` expects **824** rules | **919** |
| B-13a | Wave 1 expects **93** | **94** (includes `4.2.1.C-2.bucket_b.C003650`) |
| B-13b | Wave 2/3/4 counts stale | Derive from `DRUG_INDICATION_YAML_WAVE*_SECTIONS` + live JSON, not magic numbers |
| B-14 | `test_yaml_file_count_matches_runtime_sections` — 168 files vs 179 sections | Document exception: `tier_c_bucket_a.yaml` / `tier_c_bucket_b.yaml` are multi-section bundles → change test to count **section groups** not file count, OR split bucket YAMLs per section (prefer test fix) |

**Files:** `tests/unit/scripts/test_rule_sources.py`, `tests/unit/scripts/test_all_rule_family_yaml_sources.py`

### 3B — Gate B / manifest tests (~28 failures)

| ID | Bug | Fix |
|----|-----|-----|
| B-15 | §4.2.10 `tier_c_deferred_count == 111` | Update to **65**; add assertions for `emr_blocked_count == 37`, `non_actionable_count == 7` |
| B-15a | §4.2.14.C `tier_c_deferred_count >= 20` | Update to `>= 10` post-bucket C/D |
| B-15b | Per-section `encoded_clause_count` / gate_b source counts across 4201, 4206, 4209, 4213, 4215, 4216, 4227, 4235, 4238 | Refresh from reconciled manifests; prefer **derived** assertions (`== len(encoded_clause_ids)`) over literals |
| B-15c | `test_audit_gap_parity_zero_untraced` failures | Should pass after Phase 1+2; if not, fix gate_b export to respect reconciled traces |

**Files:** `tests/unit/scripts/test_drug_indication_*_gate_b.py`, `tests/unit/domain/prose_rules/test_drug_indication_*.py`, `tests/unit/scripts/test_drug_indication_manifest.py`

### 3C — Coverage & catalog tests (4 failures)

| ID | Bug | Fix |
|----|-----|-----|
| B-07 | Tier-C inventory `>= 1200` rows, actual **936** | Update floors to post-bucket reality: `>= 900` inventory, `bucket C >= 250` (or derive from `extract_tier_c_rules()` snapshot file) |
| B-09 | `encode_tier_c_deferred_count >= 40`, actual **10** | Fix metric first (Phase 4), then assert repo-wide defer `>= 700` OR §4.2.14.C defer `>= 10` with separate keys |
| B-16 | `prose_engine_status == "partial"` in old test | Already **implemented** — update test to `== "implemented"` |
| B-17 | `test_drug_indication_manifest_on_disk` | Align with reconciled manifest schema (`emr_blocked_count`, `non_actionable_count`) |

**Files:** `tests/unit/scripts/test_sut_coverage.py`, `tests/unit/domain/sut/test_rules_catalog.py`

**Verification**

```bash
python -m pytest tests/ -q   # 0 failures
```

**Success criteria**

- [ ] Full pytest green
- [ ] No assertion weakened without a comment explaining honest semantic change

---

## Phase 4 — Drug indication metrics & observability (P2)

**Goal:** UI/catalog/API stats reflect **repo-wide** drug engine state, not §4.2.14.C header only.

| ID | Bug | Fix |
|----|-----|-----|
| B-09 | `encode_tier_c_deferred_count` reads only 4214C manifest (**10**) | Aggregate across all `L4.2_drug_indication_*` manifests in `_drug_indication_manifest_stats()` |
| B-09a | `rules_catalog.py` key typo `encode_tier_C_deferred_count` vs `encode_tier_c_deferred_count` | Normalize to snake_case `encode_tier_c_deferred_count` everywhere |
| B-09b | `emr_blocked_count` / `non_actionable_count` also 4214C-only | Add repo-wide totals + per-subsection breakdown (reuse `_drug_indication_subsection_coverage`) |
| B-11 | A0 inventory uses only 4214C manifest | Extend `drug_indication_a0_inventory.py` to union all drug manifests OR read from `sut_clause_coverage.parquet` as primary |

**Files**

- `src/bilun/domain/prose_rules/drug_indication.py` (`_drug_indication_manifest_stats`, `drug_indication_coverage_scope`)
- `src/bilun/domain/sut/rules_catalog.py`
- `scripts/sut/prose/drug_indication_a0_inventory.py`
- `tests/unit/scripts/test_drug_indication_a0_inventory.py`

**Verification**

```bash
python -m pytest tests/unit/domain/sut/test_rules_catalog.py tests/unit/scripts/test_drug_indication_a0_inventory.py -q
python -c "from src.bilun.domain.sut import rules_catalog as rc; rc.reset_cache(); d=rc.coverage_summary()['partial_engines']['drug_indication_prose']; print(d['encode_tier_c_deferred_count'], d['emr_blocked_rows'])"
# expect defer ~728 coverage rows, emr_blocked ~356
```

**Success criteria**

- [ ] `encode_tier_c_deferred_count` matches sum of manifest `tier_c_deferred_count` across drug manifests
- [ ] A0 summary `total_clauses` reflects full §4.2 drug motor (~2300+), not 4214C-only

---

## Phase 5 — Runtime enforcement semantics (P2)

**Goal:** Bucket B rules behave consistently when EMR fields are absent.

| ID | Bug | Fix |
|----|-----|-----|
| B-10 | Missing `prior_therapies` → `severity: error` | Mirror biomarker path: empty/None → `needs_prior_therapy_verification`, `severity: review` |
| B-10a | Missing `biomarkers` already → `review` | Keep as reference behavior |
| B-10b | Populated but wrong prior therapy → keep `error` | No change |

**Files**

- `src/bilun/domain/prose_rules/drug_indication.py` (`_evaluate_prior_therapy_constraints`)
- `tests/unit/domain/prose_rules/test_drug_indication_bucket_b.py` (new or extend tier_b tests)

**Verification**

```bash
python -m pytest tests/unit/domain/prose_rules/ -k "prior_therapy or biomarker or bucket_b" -q
```

**Success criteria**

- [ ] `prior_therapies is None` → review, not error
- [ ] `prior_therapies=()` → review (needs verification), not error
- [ ] Wrong prior drug present → error unchanged

---

## Phase 6 — API security & operability (P1)

**Goal:** Production deployments cannot accidentally expose unauthenticated or half-ready API.

| ID | Bug | Fix |
|----|-----|-----|
| B-03 | Auth fails open when `BILUN_AUTH_*` unset | Default **fail-closed**; allow fail-open only with `BILUN_AUTH_OPTIONAL=1` |
| B-04 | `/health` returns 200 without active build | `status_code = 200` only if `db_ok and active_build`; else 503 |
| B-05 | Startup swallows cache build failure | On build/load failure: set module-level `_startup_ready = False`; health returns 503; optional `BILUN_STARTUP_POLICY=strict` → `sys.exit(1)` |
| B-18 | Shared DuckDB reader cursor across concurrent requests | Audit `get_cache_reader()` usage; document read-only safety OR use per-request connections for write-adjacent paths |

**Files**

- `src/bilun/api/__init__.py` (`SessionGateMiddleware`, `health_check`)
- `src/bilun/api/startup.py`
- `src/bilun/api/auth.py` (optional env docs)
- `tests/unit/api/test_auth.py` (fail-closed default)
- New: `tests/unit/api/test_health.py`

**Verification**

```bash
python -m pytest tests/unit/api/ -q
# Manual: unset BILUN_AUTH_* → POST /api/... → 401
# Manual: empty cache DB → GET /health → 503
```

**Success criteria**

- [ ] Unconfigured auth → 401 on protected routes (unless `BILUN_AUTH_OPTIONAL=1`)
- [ ] `/health` 503 when `active_build is None`
- [ ] Startup failure surfaces in health payload (`"cache_ready": false`)

---

## Phase 7 — Regression test hygiene (P2)

**Goal:** Tests actually guard product surfaces.

| ID | Bug | Fix |
|----|-----|-----|
| B-08 | Phase 8 surface test scans **0 files** (`apps/sut_web` deleted) | Retarget `ACTIVE_SURFACE_ROOTS` to `frontend/src/...` |
| B-08a | Missing `src/bilun/api/routes/*` SUT surfaces | Add `frontend/src/components/tabs/sut/`, `frontend/src/app/patient/[id]/billing/page.tsx`, relevant `src/bilun/api/routes/` |

**Files**

- `tests/unit/domain/test_phase8_surface_regressions.py`

**Verification**

```bash
python -m pytest tests/unit/domain/test_phase8_surface_regressions.py -q
# Confirm files_scanned > 50 in a debug assertion or log
```

**Success criteria**

- [ ] Test scans ≥ 50 production `.ts/.tsx` files
- [ ] Still passes (no banned wording in current frontend)

---

## Phase 8 — Pipeline hardening & deduplication (P2 tech debt)

**Goal:** Prevent manifest drift from recurring; one parsing path.

| ID | Bug | Fix |
|----|-----|-----|
| B-19 | Duplicate manifest parsing (a0 vs a1 vs coverage vs tier_c_manifest_ops) | Extract `scripts/sut/prose/manifest_index.py` — load all drug manifests, indexed by `clause_id` |
| B-19a | `close_algorithmic_gaps.py` can re-defer encoded clauses | Already partially fixed — add test that clauses in `gate_b_sources` are never re-added to `tier_c_deferred` |
| B-21 | `encode_tier_c_bucket_d.py` ignores inventory path (`from_inv` unused) | Either wire inventory filter or remove dead code; document candidate-only sourcing |
| B-22 | CI does not run manifest parity audit | Add `python scripts/sut/audit_manifest_parity.py` to `.github/workflows/ci.yml` after compile check |

**Files**

- `scripts/sut/prose/manifest_index.py` (new)
- `scripts/sut/close_algorithmic_gaps.py`
- `scripts/sut/encode_tier_c_bucket_d.py`
- `.github/workflows/ci.yml`
- `tests/unit/scripts/test_close_algorithmic_gaps.py`

**Verification**

```bash
python scripts/sut/audit_manifest_parity.py
python -m pytest tests/unit/scripts/test_close_algorithmic_gaps.py -q
```

---

## Phase 9 — Frontend CI verification (environment gap)

**Goal:** Confirm frontend job green (not runnable in agent env — `npx` missing).

| ID | Bug | Fix |
|----|-----|-----|
| B-23 | Frontend typecheck/tests not verified locally | Run in dev/CI: `cd frontend && npm ci && npx tsc --noEmit && npx vitest run && npm run build` |
| B-23a | Any failures from Phase 7 path changes | Fix frontend wording if phase8 test now catches violations |

**Verification**

```bash
cd frontend && npm ci && npx tsc --noEmit && npx vitest run && npm run build
```

---

## Phase 10 — Final integration & sign-off

**Goal:** Staff-engineer approval bar from AGENTS.md.

**Checklist**

- [ ] `python -m pytest tests/ -q` — 0 failures
- [ ] `python scripts/sut/compile_rules.py --check` — exit 0
- [ ] `python scripts/sut/audit_manifest_parity.py` — exit 0
- [ ] `sut_clause_coverage.parquet`: true unencoded gaps **0**
- [ ] `drug_indication_prose.json`: **919** rules
- [ ] Frontend CI job green
- [ ] Update `tasks/todo.md` review section with before/after metrics
- [ ] `graphify update .` after code changes

**Deliverable:** `reports/bug_remediation_signoff.json` with all metrics.

---

## Complete bug index

| ID | Severity | Phase | Summary |
|----|----------|-------|---------|
| B-01 | P0 | 3 | 41 failing pytest tests |
| B-02 | P0 | 2 | `compile_rules --check` — 20 artifact drift |
| B-02a | P0 | 2 | Corpus CSV drift (6 files) |
| B-02b | P0 | 2 | `drug_indication_prose.json` drift |
| B-03 | P1 | 6 | Auth fails open without env vars |
| B-04 | P1 | 6 | `/health` 200 without active build |
| B-05 | P1 | 6 | Startup swallows cache failure |
| B-06 | P1 | 1 | Manifest bucket lists ≠ traces (4214C: 833 vs 615) |
| B-06a | P1 | 1 | Same drift in sibling manifests |
| B-06b | P1 | 1 | `clause_trace_complete` true while inconsistent |
| B-07 | P2 | 3 | Tier-C inventory test floor stale (1200 vs 936) |
| B-08 | P2 | 7 | Phase 8 test scans 0 files |
| B-08a | P2 | 7 | Wrong surface roots (`apps/sut_web`) |
| B-09 | P2 | 4 | `encode_tier_c_deferred_count` 4214C-only |
| B-09a | P2 | 4 | `encode_tier_C` vs `encode_tier_c` key inconsistency |
| B-09b | P2 | 4 | EMR/non-actionable counts 4214C-only |
| B-10 | P2 | 5 | Prior-therapy absent → error not review |
| B-10a | P2 | 5 | (reference) biomarker absent → review ✓ |
| B-10b | P2 | 5 | Wrong prior therapy should stay error |
| B-11 | P2 | 4 | A0 inventory 4214C-scoped only |
| B-12 | P2 | 1 | `tier_c_manifest_ops` silent skip |
| B-13 | P3 | 3 | Rule count constant 824 → 919 |
| B-13a | P3 | 3 | Wave 1 count 93 → 94 |
| B-13b | P3 | 3 | Wave 2/3/4 magic counts |
| B-14 | P3 | 3 | YAML file count vs section groups |
| B-15 | P3 | 3 | §4.2.10 tier_c 111 → 65 |
| B-15a | P3 | 3 | §4.2.14.C tier_c floor 20 → 10 |
| B-15b | P3 | 3 | Per-section gate_b literal counts |
| B-15c | P3 | 3 | Gate B untraced parity |
| B-16 | P3 | 3 | `prose_engine_status` partial → implemented |
| B-17 | P3 | 3 | Manifest on disk schema assertions |
| B-18 | P2 | 6 | Shared DuckDB reader concurrency |
| B-19 | P2 | 8 | Duplicate manifest parsing paths |
| B-19a | P2 | 8 | `close_algorithmic_gaps` re-defer risk |
| B-20 | — | 0 | Baseline capture |
| B-21 | P2 | 8 | `bucket_d` dead inventory branch |
| B-22 | P2 | 8 | CI missing manifest parity step |
| B-23 | P2 | 9 | Frontend CI not verified in audit env |
| B-23a | P2 | 9 | Frontend wording if phase 7 activates |

---

## Estimated effort

| Phase | Effort | Parallel? |
|-------|--------|-----------|
| 0 Baseline | 2–4 h | — |
| 1 Manifest integrity | 1–2 days | — |
| 2 Compiler sync | 4–8 h | after 1 |
| 3 Tests | 1–2 days | after 2 |
| 4 Metrics | 4–8 h | after 1 |
| 5 Prior-therapy | 2–4 h | after 3 |
| 6 Security | 4–8 h | parallel with 3–5 |
| 7 Phase 8 test | 1–2 h | anytime |
| 8 Pipeline hardening | 1 day | after 1–2 |
| 9 Frontend CI | 2–4 h | parallel |
| 10 Sign-off | 2–4 h | last |

**Total:** ~5–8 engineering days for one developer; Phases 6+7+9 can overlap with 3–5.

---

## Explicit non-goals

- EMR runtime ingest for Bucket C clauses (enforcement when clinical fields arrive)
- Splitting `tier_c_bucket_*.yaml` into per-section files (test adaptation preferred)
- Force-push or git history rewrite
- Fixing unrelated git working-tree changes outside this bug set
