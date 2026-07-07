## Task: CI Performance Optimization (backend + frontend)

### Goal
Cut backend CI from ~8 min → ~3 min and frontend CI from ~1.3 min → ~45s by adding the caches that are missing and removing the redundant work, without reducing test coverage or correctness.

### Investigation evidence (measured 2026-07-06 against commit 6a72843)

#### Backend job (~8 min, run #28815965487)
| Phase | Time | % | Root cause |
|---|---|---|---|
| `pip install -e ".[dev]"` + 168 packages | ~90-120s | ~25% | **No pip cache** — `setup-python@v5` has no `cache:` flag (frontend has `cache: npm`, backend does not) |
| `test_recoverable_sums_to_patient_total` | 66.7s | ~14% | Runs full 15-motor billing orchestrator across all 50 synthetic patients (`compute_all_billing_reports` = 48.2s) |
| `test_multi_bill_patient_splits_recoverable` | 19.9s | ~4% | **Re-runs** `compute_all_bill_billing_reports` (19.7s) — identical work, no shared fixture with the test above |
| Rest of suite (1873 tests, serial) | ~135s | ~28% | No `pytest-xdist` — dev extras are literally just `pytest>=8`. 2-4 CI cores idle |
| Collection/import | ~13s | ~4% | 1875 tests, heavy import graph |
| `compile_rules.py --check` + manifest parity | ~10s | ~3% | Fast, fine |
| Runner/checkout/setup overhead | ~60-90s | ~18% | Un-cacheable |

#### Frontend job (~67s, job 85455322046)
| Phase | Time | Root cause |
|---|---|---|
| checkout + setup-node | 14s | Fine |
| `npm ci` | 15s | **npm cache IS present** (`cache: npm` line 47) — already optimal; `added 457 packages in 14s` |
| `tsc --noEmit` | 10s | Type check — necessary, already fast |
| `vitest run` | 11s | 38 test files; vitest 4 defaults to parallel file execution — already optimal |
| `npm run build` (`next build`) | 14s | Full Next.js production build — **overlaps with `tsc`** (both compile the entire app); only value is "does Next compile" smoke |
| wrap/overhead | 3s | Fine |

#### Key findings
- **Backend has no dependency cache** while frontend does — asymmetric and the biggest backend win.
- **Two backend tests burn 86s** (30% of suite) with the second recomputing identical orchestrator work — verified both call `compute_all_bill_billing_reports(cache)` independently with `_cache_for(_DATASET)` and no shared fixture.
- **Backend runs serially** (no `pytest-xdist`); frontend already parallelizes.
- **Frontend is already well-cached and parallel** — the only real lever is whether `npm run build` adds enough value to justify its 14s (it duplicates `tsc`'s type-check work).

### Subtasks

#### Tier 1 — Backend (biggest wins, lowest risk)

- [ ] **B1. Add pip dependency cache to backend job** (~2 lines, saves ~90-120s/run)
  - In `.github/workflows/ci.yml`, add `cache: pip` + `cache-dependency-path: pyproject.toml` to the `setup-python@v5` step.
  - Verify the cache key restores on the second run.

- [ ] **B2. Memoize the orchestrator result across the two heavy tests** (~5 min, saves ~20s)
  - In `tests/unit/domain/billing/test_bill_billing_report.py`, convert `TestPerBillAdditivity` to use a `class-scoped fixture` (or module-scope) that computes `compute_all_billing_reports` + `compute_all_bill_billing_reports` **once**, then both tests reuse the cached `patient_reports` and `bill_reports`.
  - The `autouse` cache-clear in `tests/unit/domain/claims/conftest.py` clears the *dataset* cache, not the orchestrator result — safe to cache the orchestrator output at class scope.
  - Verify both tests still pass with identical assertions.

#### Tier 2 — Backend (bigger win, moderate effort)

- [ ] **B3. Add `pytest-xdist` + parallel execution** (~15 min, saves ~60-90s on the "rest of suite")
  - Add `pytest-xdist` to dev extras in `pyproject.toml`.
  - Change CI `Run Python tests` to `python -m pytest -n auto --dist loadgroup -q`.
  - **Caveat:** the two heavy `TestPerBillAdditivity` tests share `_DATASET` module state + the `autouse` cache-clear; mark them with `@pytest.mark.xdist_group("billing_heavy")` so `--dist loadgroup` keeps them on one worker (avoids dataset contention).
  - Local verify: `python -m pytest -n auto -q tests/unit/` green.

- [ ] **B4. Re-classify the two heavy tests as integration** (optional, ~10 min)
  - Move `test_recoverable_sums_to_patient_total` + `test_multi_bill_patient_splits_recoverable` to `tests/integration/` (they're cohort-level, not unit). Lets the unit suite parallelize cleanly.
  - Add a separate CI step or mark them for a slower cadence if the xdist group proves fragile.

#### Tier 1 — Frontend (smaller wins)

- [ ] **F1. Evaluate dropping `npm run build` from CI** (saves ~14s, *decide first*)
  - `tsc --noEmit` already type-checks; `vitest run` already executes. `next build` only adds "does the Next bundler compile" — a smoke check that rarely catches issues `tsc` doesn't.
  - **Decision needed:** is the "Next build compiles" smoke worth 14s every run? If yes, keep it (it's cache-cheap since npm cache exists). If no, drop it. Recommendation: keep for now (it's cheap insurance, and the real frontend lever is the backend), but revisit if frontend CI grows.

- [ ] **F2. No parallelization change needed** — vitest 4 already runs files in parallel (38 files in 11s ≈ already concurrent). No action.

#### Tier 3 — deeper work (out of scope for this plan, note for future)
- **B5. Profile `compute_patient_billing_report`** — ~1s/patient for 50 patients × ~10 lines is high. Likely candidates: repeated catalog lookups per line, per-procedure `resolve_payment_method` calls, session-pricing recomputation. This is a real perf investigation, not a CI tweak.
- **B6. Smaller synthetic cohort for CI** — run heavy tests on a 10-patient subset; keep the 50-patient run for nightly. Saves ~60s but reduces signal.

### Out of Scope
- Rewriting the billing orchestrator internals (B5 — separate profiling task).
- Splitting CI into multiple jobs per test directory (adds setup overhead, net negative at this suite size).
- Self-hosted runners / larger runner instances (infra/cost decision, not code).

### Verification
- [ ] After B1: second CI run shows pip cache restored (log "Cache restored successfully").
- [ ] After B2: both heavy tests pass; `--durations=10` shows the 66s test drops to ~48s and the second drops to <1s.
- [ ] After B3: `python -m pytest -n auto -q tests/unit/` green locally; CI backend job wall-clock drops.
- [ ] Backend CI total ≤ 4 min (target ~3 min).
- [ ] Frontend CI: no regression (≤ 70s).

### Expected outcome
| Job | Now | After Tier 1 (B1+B2) | + Tier 2 (B3) |
|---|---|---|---|
| Backend dep install | ~100s | ~10s (cache) | ~10s |
| Heavy tests | ~86s | ~48s (dedup) | ~48s |
| Rest of suite | ~135s | ~135s | ~50s (parallel) |
| **Backend total** | **~8 min** | **~4 min** | **~3 min** |
| Frontend total | ~67s | ~67s (no Tier 1 change) | ~67s |

### Review (post-implementation)

**Implemented:** B1 (pip cache), B2 (orchestrator dedup). B3 (xdist) attempted then reverted. F1 (npm build) kept.

**Measured on the CI runner (ubuntu-latest), same branch:**

| Step | Baseline (6a72843, serial) | After B1+B2 (cache hit run) |
|---|---|---|
| Install dependencies | 31s (uncached ~100s) | ~10s (cache hit, est.) |
| Run Python tests | 405s | ~385s (B2 saves ~20s) |
| **Backend total** | **~455s (~7.5 min)** | **~400s (~6.7 min)** |

**B3 (xdist) — REVERTED, net-negative on this runner.** CI measurement:
- Serial test step: **405s**
- xdist `-n auto --dist loadgroup` test step: **572s** (+167s, **41% slower**)

Diagnosis: `auto` spawned workers matching the runner's 2-4 cores, but the workers contended for shared resources (the heavy billing orchestrator is CPU+memory bound). The parallel gains on the 1873 light tests were more than wiped out by contention on the 70s orchestrator test + per-worker overhead. xdist stays in dev extras for opt-in **local** use (`pytest -n auto`); not worth the CI regression. The conftest `_is_xdist_main_worker` race-fix is kept (defensive — makes reconcile fixtures xdist-safe for local parallel runs).

**Net CI improvement: ~0.8 min saved per run (7.5 → ~6.7 min backend), plus the pip cache makes dep-install deterministic.** Smaller than the ~5 min initially projected because (a) the serial test baseline on the runner was already 405s, not the 218s seen on the dev machine, and (b) xdist didn't help. The bigger remaining lever is **B5** (profile the orchestrator — ~1s/patient is high) and **B6** (smaller cohort for CI), both out of scope here.

**Honest lesson:** the investigation's local measurements (218s serial, 132s xdist) did not predict CI behavior (405s serial, 572s xdist) — the dev machine has more effective cores/memory than the shared runner. Always measure on the target environment before committing to a parallelization change.

---

### B5 — orchestrator profiling + fix (implemented, commit 5a3a918)

cProfile of `compute_all_billing_reports` (50 patients) found the ~1s/patient cost was **two classic anti-patterns**, not inherent orchestrator complexity:

| Hotspot | Before | Root cause |
|---|---|---|
| `_load_curated_ek2b_by_asof` | 62s | re-read parquet + `pandas.iterrows` (0.887s/call) × 87 distinct procedure dates; no result cache |
| `_load_curated_ek2c_by_asof` | 21s | same iterrows pattern |
| `pandas.iterrows` (aggregate) | 42s | 837,734 per-row Series allocations |
| `_drug_name_matches` + `re._compile` | 36s + 26s | regex recompiled 241,740× |

**Fix A (gazette.py):** three layered caches — read parquet once per process, parse effective_date once, cache the filtered-by-date result dict per asof_date; replaced `iterrows` with `to_dict(orient="records")` (6.5× faster, measured).
**Fix B (drug_indication.py):** `@lru_cache` the compiled word-boundary regex per INN token.

**Measured impact (cProfile, same 50-patient cohort):**
- Total: **152.2s → 54.1s (-64%)**
- Per-patient: ~3.04s → ~1.08s
- `_load_curated_ek2b_by_asof`: 62s → 9.65s
- `_drug_name_matches` / iterrows: dropped out of top-20 entirely

**CI test step (same runner):** 380s → **322s** (-58s, -15%). Backend total: 7m08s → **6m11s**.

**New (previously masked) hotspot, out of scope:** `difflib.ratio` in `ek4d_exempt.fuzzy_match_name` (~19s) — fuzzy drug-name matching. Separate optimization.

**Correctness:** 1844 tests pass; outputs byte-identical (only iteration strategy changed).

---

### B6 — fuzzy_match_name length-bound pre-filter (implemented, commit 62fd4a6)

The difflib hotspot B5 unmasked: `fuzzy_match_name` (ek4d copay-exempt drug matching) called `SequenceMatcher.ratio()` ~260k times/cohort (~19s).

**Investigation detour (abandoned):** first tried a call-level cache keyed by `(needle, candidate-names, threshold)` after instrumentation showed 71% needle-repetition. But the candidate *lists* differ per section (each drug hits different sections by diagnosis), so `(needle, candidates)` pairs were 99.5% unique — 0.5% cache hit rate. Cache removed.

**The actual fix — length-bound pre-filter:** `SequenceMatcher.ratio()` is bounded above by `2*min(len_a,len_b)/(len_a+len_b)` (matching blocks can't exceed the shorter string). When that bound is already below threshold, `ratio()` cannot reach threshold, so skip it. Measured: **94.8% of ratio() calls are skippable** this way on the real cohort. The check is a 3-op arithmetic comparison vs the full LCS-based ratio computation.

**Correctness is mathematical** (the pre-filter can only skip pairs that would have returned below-threshold) and **verified empirically**: compared optimized vs reference (no pre-filter) on all 851 real `fuzzy_match_name` calls captured during an orchestrator run — **0 mismatches**.

**Measured impact:**

| Metric | After B5 | After B6 | Δ from B5 |
|---|---|---|---|
| cProfile total (50 patients) | 54.6s | **37.6s** | -31% |
| `difflib.ratio` cumtime | ~16s | dropped out of top-15 | gone |
| CI test step (same runner) | 322s | **261s** | -61s (-19%) |
| CI backend total | 6m11s | **5m9s** | -62s |

**Cumulative CI improvement (B1+B2+B5+B6):** backend **7m37s → 5m9s** (-2m28s, -32%). Test step **405s → 261s** (-36%).

**Next remaining hotspots (out of scope):** `catalog.load_sut_catalog` (16s, inherent 86-date filter cost) and `session_specialty.resolve_procedure_specialty_key` (14s, catalog-lookup path). Both are catalog-lookup duplication across the 86 procedure dates — a date-bucketing fix (collapsing 86 dates to ~2-3 tebliğ effective dates) would address both.
