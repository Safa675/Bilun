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

### Review
_To be updated at each checkpoint._
