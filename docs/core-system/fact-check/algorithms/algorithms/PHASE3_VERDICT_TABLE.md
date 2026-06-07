# Phase 3 Verdict Table (L2.3, L2.4, L2.5, L2.8)

**Completed:** 2026-06-02  
**Reports:** `L2.3_surcharge_ek2g.md`, `L2.4_copay_rate_ek2c1.md`, `L2.5_temporal_price_audit.md`, `L2.8_cohort_aggregator.md`

| ID | Algorithm | Primary verdict | Secondary | Severity | MEDULA | Registry status | Exactness / NEEDS_CLAIM_LINES | Tests (pass) |
|----|-----------|-----------------|-----------|----------|--------|-----------------|-------------------------------|--------------|
| **L2.3** | Surcharge exposure (EK-2G) | **NEEDS_CLAIM_LINES** | PARTIAL (no runtime EK-2G join; flag semantics = surcharge-eligible, not violation count) | low | ADDITIVE | `surcharge_ek2g` → `needs_claim_lines` ✓ | `missing_exact_inputs` without `ClaimContextManager`; `exact` with claim lines | 7/7 optimization exactness + claim context |
| **L2.4** | Copay rate exposure (EK-2C-1) | **NEEDS_CLAIM_LINES** | PARTIAL (payable/billed ratio only; doc claims gazette % compare) | medium | ADDITIVE | `copay_rate_ek2c1` → `needs_claim_lines` ✓ | Same gating as L2.3 | 7/7 (gap: no dedicated unavailable test) |
| **L2.5** | Temporal price audit (EK-2B/2C) | **COMPLIANT** | PARTIAL vs L4.1 service-date pricing | low | ADDITIVE | `pricing_ek2b`, `pricing_ek2c` → `implemented` ✓ | Not claim-gated (by design) | L4.1 temporal tests; no L2.5 unit test |
| **L2.8** | Cohort aggregator | **COMPLIANT** | Child blocks: NEEDS_CLAIM_LINES | low | ADDITIVE | — (meta) | Gates surcharge/copay/DRG/drug on `claim_dataset`; temporal always on | `test_optimization_exactness`, `test_cohort_claim_integration` |

## Cross-cutting findings

1. **`exactness.py` helpers verified:** `is_exact_output`, `unavailable_surcharge_exposure`, `unavailable_copay_rate_exposure`, `build_exact_*_exposure`, `SURCHARGE_*` / `COPAY_RATE_*` constants — used consistently from `surcharge.py`, `copay_rates.py`, and `aggregator.py`.
2. **Catalog row counts (Gate D):** EK-2G = 213; EK-2C-1 = 465; history tables 7,301 / 2,413 unique codes × 9 amendment dates.
3. **Documentation fix candidate:** `algorithms_reference.md` §2.3 step 3 — states gazette rate validation; L2.4 code does not join `ek2c1_copay_rates.parquet`.
4. **No REGISTRY_DRIFT** for the four units checked against `sut_registry_coverage.parquet`.

## Suggested FIX_BACKLOG lines (Phase 5, non-blocking)

| Priority | ID | Action |
|----------|-----|--------|
| P2 | L2.4 | Join EK-2C-1 parquet; flag `rate_pct` vs `copay_rate_pct` mismatch |
| P2 | L2.3 | Clarify metric naming (`surcharge_eligible` vs `ek2g_prohibited`) |
| S | L2.4 | Fix `algorithms_reference.md` §2.3 wording |
| S | L2.5 | Add unit tests for `_compute_annex_temporal_stats` |
| S | L2.8 | Optional `summary_exactness` rollup for API consumers |
