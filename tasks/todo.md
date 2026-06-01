## Task: Billing algorithm bugfixes (billing_bugfixes.md)

### Goal
Fix lab per-visit duplicate grouping, copay/drug double-counting on claim path, propagate visit_id through lab pipeline, relabel recoverable total in UI.

### Subtasks
- [x] Phase 1: Add basvuru_id to lab export, visit_id in loader + orchestrator
- [x] Phase 2: Per-visit hemogram bundling and duplicate detection in lab.py
- [x] Phase 3: Copay total visit-only; drug_claims excludes exempt copay; orchestrator sums rx separately
- [x] Phase 4: Relabel "Rule-calculated opportunity" in billing i18n + tests
- [x] Phase 5: Unit tests, rebuild cache (alt db path), spot-check 0039

### Out of Scope
- EK-1A exemption logic changes
- Visit ID on drugs/procedures/materials

### Review
- 19 billing unit tests pass (`tests/unit/domain/billing/`)
- Synthetic data regenerated; `lab_clean.parquet` includes `basvuru_id`
- Cache rebuilt to `.cache/bilun_build_test.duckdb` (live `.cache/bilun.duckdb` locked by uvicorn on :8001)
- Run `scripts/bilun/build_cache.py --activate` after stopping API to activate on main cache
