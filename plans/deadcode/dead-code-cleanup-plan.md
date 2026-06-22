# Plan: Dead Code Cleanup (Backend + Frontend)

**Date:** 2026-06-22  
**Status:** Ready for execution  
**Prerequisite:** Prior audit verified by human review (all high/medium claims confirmed)

---

## Goal

Remove verified dead, broken, and zombie-export code without changing runtime behavior. After completion: targeted pytest + frontend vitest green; no import of deleted modules; `__all__` lists match actual public surface.

## Out of Scope

- `loaders/legacy.py` — live (used by `catalog.py`)
- Offline `scripts/` CLIs — intentional tooling
- `ClaimContextManager`, `expensive_compute.py` — live
- Frontend file-level deletes from `plans/frontend/frontend-deadcode-bug-audit.md` (D1–S3) — separate PR unless bundled explicitly
- B4 EK-2G surcharge engine refactor
- Adding `vulture` to CI (optional follow-up)

---

## Risk summary

| Step | Risk | Mitigation |
|------|------|------------|
| Delete `estimators.py` | **Zero** — broken + zero imports | Delete file only; grep confirms no references |
| Delete `cache/expensive.py` | Zero — facade, no consumers | Delete file only |
| Remove unused symbols | Low — must scrub `__all__` / re-exports | One PR slice per domain; grep after each slice |
| Trim `NotImplementedError` branch | Low | Keep `SUT_REQUIRE_CLAIM_LINES` constant and `if` guard; remove only `raise` branch |
| Remove `chapters` param | **Medium** — ~37 call sites | Dedicated commit; mechanical search-replace |
| ECI rank scaffolding | Low–medium | Remove empty DataFrame plumbing + `read_patient_eci_rank_window`; verify cache build row_counts still valid |

---

## Step 0 — Landmine: delete `estimators.py` (first)

**Why first:** Not merely unused — imports non-existent `runtime_state.py` (`estimators.py:16`). Any accidental import crashes immediately.

**Evidence:**
- Zero `from …estimators` / `import estimators` in repo
- Internal closed loop: `_ensure_enrichment()` → `lookup_lab_price` / `lookup_visit_price` — none called externally
- No `test_estimators*.py`

**Actions:**
- [ ] Delete `src/bilun/domain/estimators.py`
- [ ] Grep repo for `estimators` — expect zero hits (except this plan / archive)

**Verify:** `pytest tests/unit/domain/billing/ -q --tb=no` (smoke; billing unaffected)

---

## Step 1 — Delete `cache/expensive.py` facade

**Evidence:** Re-exports `expensive_compute`; nothing imports `bilun.cache.expensive`. Production uses `expensive_compute` / `build_expensive` directly.

**Actions:**
- [ ] Delete `src/bilun/cache/expensive.py`
- [ ] Grep for `cache.expensive` / `from .expensive` — zero hits

**Verify:** `pytest tests/unit/cache/ -q` if present; else cache builder smoke test

---

## Step 2 — Backend zombie symbols (multi-file export chains)

Each item: remove definition → remove import → remove from `__all__` → update README if mentioned.

### 2a — `_precompute_exemption_map` (3-file chain)

| File | Action |
|------|--------|
| `copay_exemption_rules/ek1a.py` | Delete `_precompute_exemption_map` function |
| `copay_exemptions.py` | Remove import + `__all__` entry |
| `optimization/__init__.py` | Remove import + `__all__` entry |

**Note:** `evaluate_ek1a_exemption` inlines equivalent logic; no call-site behavior change.

### 2b — `_select_patient_rows`

| File | Action |
|------|--------|
| `analytics/shared.py` | Delete function (or delete entire file if only export) |
| `analytics/__init__.py` | Remove import + `__all__` |
| `analytics/README.md` | Remove legacy caller note |

### 2c — `InvalidBuildId`

| File | Action |
|------|--------|
| `shared/exceptions.py` | Delete class; trim module docstring mention |

### 2d — `_LEGACY_DIR`

| File | Action |
|------|--------|
| `domain/constants.py` | Delete `_LEGACY_DIR` definition (~line 24) |

### 2e — `optimization/shared.py` dead helpers

Remove if still unused after grep:
- `_is_blank`
- `_ICD10_CHAPTER_TO_PROCEDURE_PREFIXES`

Scrub `optimization/__init__.py` / `shared.py` exports accordingly.

**Verify:** `pytest tests/unit/domain/optimization/ tests/unit/domain/analytics/ -q`

---

## Step 3 — ECI rank scaffolding

**Evidence:**
- `cache/builder.py:237-238` — `rank_df = pl.DataFrame()` / `rank_storage_df = pl.DataFrame()` always empty
- `read_patient_eci_rank_window` in `db/patient_meta.py:149` — deprecated stub, never called
- Row count `patient_eci_rank` always 0

**Actions:**
- [ ] Delete `read_patient_eci_rank_window` from `patient_meta.py`
- [ ] Remove `rank_df` / `rank_storage_df` variables and `eci_rank_df=` debug arg from `_print_memory_snapshot`
- [ ] Remove `patient_eci_rank` from `row_counts` dict (or document as removed metric in cache schema notes if consumers exist)

**Verify:** Grep `eci_rank` — only historical docs remain; run cache builder dry path or unit test if available

---

## Step 4 — Trim dead branch in `patient_report.py`

**Evidence:** `SUT_REQUIRE_CLAIM_LINES = True` hardcoded (`constants.py:364`). `NotImplementedError` branch unreachable.

**Actions:**
- [ ] Keep `if claim_context is None:` + `if SUT_REQUIRE_CLAIM_LINES:` missing-inputs path
- [ ] Remove `raise NotImplementedError(...)` else branch
- [ ] Optionally collapse to single path (no inner `if` on constant) — **only if** tests still assert `SUT_REQUIRE_CLAIM_LINES is True` in `test_honest_gaps.py`

**Do not remove:** `SUT_REQUIRE_CLAIM_LINES` constant (tests + fact_check_audit reference it)

**Verify:** `pytest tests/unit/domain/billing/test_honest_gaps.py tests/unit/domain/billing/test_claim_integration.py -q`

---

## Step 5 — Remove no-op `chapters` parameter (medium effort)

**Evidence:** `compute_patient_billing_report(..., chapters=...)` does `_ = chapters` (`patient_report.py:71`). Param documented as ignored.

**Call sites (~37):** tests (`test_billing_actions.py`, `test_claim_integration.py`, `test_sgk_uplift_synthetic_demos.py`, …), `cohort_runner.py`, `aggregator.py`, `scripts/synthetic/assert_tier_a_post_regen.py`

**Actions:**
- [ ] Remove `chapters` from `compute_patient_billing_report` signature + docstring
- [ ] Mechanical removal of `chapters={"I"}` (and variants) at all call sites
- [ ] Grep `chapters=` under `src/` and `tests/` — zero remaining on billing report calls

**Note:** Tests that passed `chapters=` to exercise missing-inputs behavior are unaffected — that path is driven by `claim_context=None` + `SUT_REQUIRE_CLAIM_LINES`, not `chapters`.

**Verify:** Full billing test suite: `pytest tests/unit/domain/billing/ -q`

---

## Step 6 — Frontend partial dead exports

**Do not delete** `recents.ts` — only `useRecents` is dead; `recordRecent` / `getRecents` are live.

| Symbol | File | Action |
|--------|------|--------|
| `getPriceHistory` | `lib/api/sut.ts` | Delete function + any orphaned types |
| `rollbackCache` | `lib/api/health.ts` | Delete function; update `health.test.ts` (remove test or keep via direct fetch mock only if needed) |
| `canAccessRuleDatabase` | `lib/userRole.ts` | Delete function; update `userRole.test.ts` |
| `useRecents` | `lib/recents.ts` | Delete hook only |
| Config tier helpers | `configTypes.ts` | Delete unused exports (`findRiskTier`, `getScoreColor`, …) |
| Unused config hooks | `configContext.tsx` | Delete hooks with zero importers |
| `TAB_BACKGROUNDS`, `CHART_COLORS`, `BADGE_CLASS` | `constants.ts` | Delete if grep confirms zero usage |
| Cohort URL builders | `cohortFilter.ts` | Delete unused builders |
| `shared.tsx` chart/tier exports | per frontend deadcode audit | Delete unused exports only |

**Verify:** `cd frontend && npm run test -- --run` (or vitest on touched files); `npx tsc --noEmit`

---

## Step 7 — Docstring / comment hygiene (optional, same PR or follow-up)

- [ ] `catalog.py` — trim stale tier 2–3 legacy JSON references if inaccurate
- [ ] `apiClient.ts` — fix pointer to non-existent `lib/api.ts` if still present
- [ ] `analytics/README.md` — post-cleanup accuracy pass

---

## Suggested PR slicing

| PR | Contents | Est. risk |
|----|----------|-----------|
| **PR-A** | Steps 0–1 (`estimators.py`, `expensive.py`) | Trivial |
| **PR-B** | Step 2 (zombie exports) + Step 3 (ECI) | Low |
| **PR-C** | Steps 4–5 (`patient_report` branch + `chapters`) | Medium |
| **PR-D** | Step 6 (frontend symbols) | Low |
| **PR-E** | Step 7 (docs) | Trivial |

Alternatively: one PR if CI time allows — order must still be 0 → 1 → 2 → … internally.

---

## Definition of done

- [ ] All checkboxes above completed
- [ ] `rg estimators` / `rg cache\.expensive` / `rg _precompute_exemption_map` / `rg InvalidBuildId` — no live code hits
- [ ] `pytest tests/unit/ -q` green (or agreed subset + full CI)
- [ ] Frontend vitest + tsc green on touched files
- [ ] `tasks/todo.md` review section updated
- [ ] No behavior change to billing reports, cache payloads, or UI routes

---

## Follow-up (not in this plan)

- Install `vulture` in dev deps + CI gate on `src/bilun` / `frontend/src`
- Execute `plans/frontend/frontend-deadcode-bug-audit.md` file-level deletes (D1–S3, ~466 lines)
- `@deprecated` `SyntheticDemoProvenance`, `SUTOptimizer` default export — remove when importers confirmed gone
