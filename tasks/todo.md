## Task: Claim Data Integration — Wire Parquets to Billing & Optimizer

### Goal
Connect existing `SUTClaimDataset` claim Parquets to billing and optimization
modules so frontend Unavailable panels become exact in `synthetic_demo` mode.

**Full spec:** [plans/claim-data-integration.md](../plans/claim-data-integration.md)

### Subtasks

#### Phase 0: Foundation — Patient Claim Context
- [x] Add `src/bilun/domain/claims/patient_context.py` with `PatientClaimContext`, `build_patient_claim_context`, `build_cohort_claim_context`
- [x] Pass `sut_claim_dataset` from `assemble_sut_context` into `assemble_billing_context`
- [x] Extend `compute_patient_billing_report` / `compute_all_billing_reports` to accept and use `PatientClaimContext`

#### Phase 1: Cohort Optimization Summary
- [x] Update `optimization/aggregator.py` to aggregate surcharge/copay from claim dataset
- [x] Remove destructive overrides in `_sanitize_optimization_summary`
- [x] Fix `_sanitize_patient_alert_summary` to preserve exact cache summaries

#### Phase 2: Billing — Drug Optimization
- [x] Implement `optimize_drug_from_claims()` in `billing/drug_claims.py`
- [x] Wire into orchestrator; set `exactness_status = exact` when claim lines present

#### Phase 3: Billing — Copay Optimization
- [x] Implement `optimize_copay_from_claims()` in `billing/claim_copay.py`
- [x] Wire into orchestrator

#### Phase 2.5: Billing Aggregator — Cohort Revenue Recovery
- [x] Wire `PatientClaimContext` in `compute_all_billing_reports`
- [x] Verified cohort totals propagate drug/copay/strategy savings

#### Phase 4: Billing Strategy + DRG Unbundling
- [x] Implement `recommend_billing_strategy_from_claims()` in `billing/claim_strategy.py`
- [x] Replace stub in `optimization/unbundling.py` with claim-line-based detection
- [x] Wire DRG unbundling in patient optimization API with claim context

#### Phase 5: Drug Discount Validation
- [x] Implement `validate_drug_discount_tiers()` using cohort drug claim lines

#### Phase 6: Materials Pre-Check
- [x] Implement `precheck_materials_from_claims()` in `billing/claim_materials.py`

#### Phase 7: Lab Integration Fix
- [x] Teach `_optimize_lab_billing` to resolve `L*` codes via `lookup_procedure_code`
- [ ] Export `lab_result_id` / `lab_billing_status` on procedure lines (generator — deferred)

#### Phase 8: Test & Validation Infrastructure
- [x] Update `test_loader.py`, `test_optimization_claim_context.py`, `test_config.py` for v2
- [x] Add `test_claim_integration.py` and `test_cohort_claim_integration.py`
- [x] Update `validate_sut_synthetic_data.py` for v2 workbook and scale checks

#### Phase 9: Cache Rebuild & E2E Verification
- [ ] Rebuild DuckDB cache after deploy (`python -m src.bilun.cache.builder` or project script)
- [ ] Manual UI pass on Compliance Alerts + Revenue Recovery

### Billing UI fixes (2026-05-23)
- [x] Map claim-based copay/strategy fields in frontend (`billingReportFields.ts`)
- [x] Show KPI totals under `partial_exact` (`hasRecoverableBillingTotals`)
- [x] Hide schema placeholder `exactness_status` from missing-input labels
- [x] Clearer chatbot DNS error message in `llm.py`
- [x] Vitest path alias config for `@/` imports

### Out of Scope
- Real hospital claim ingestion (`real_claims` mode)
- Generator lab linkage export (optional follow-up)
- Automated rule engine vs `expected_rule_outputs` assertion harness

### Bug Fix: Material typo handling (2026-05-23)
- [ ] Add `fuzzy_match_name()` to `utils.py` using `difflib` for typo-tolerant matching
- [ ] Update `estimate_material_costs()` to use fuzzy fallback when strict match fails
- [ ] Update `is_consumable_bundled()` to use fuzzy fallback
- [ ] Update `is_material_reimbursable()` to use fuzzy fallback
- [ ] Update `check_bundling_violations()` in bundling_rules.py to use fuzzy fallback
- [ ] Update material pricing endpoint to use fuzzy fallback
- [ ] Verify: "Enejtör" correctly matches "Enjektör" and shows catalog price + bundling flag

### Review
- **Implemented:** Claim context layer, billing drug/copay/strategy/materials from claim lines, cohort optimizer aggregation, DRG unbundling + drug discount validation, lab SUT-code price resolution, API sanitization fixes.
- **Smoke test:** 50 patients → drug 30,504 TRY, copay 10,067 TRY, strategy 1,493,570 TRY cohort savings; optimization summary surcharge/copay/drug exact.
- **Tests:** 14 new/updated integration tests pass; validator passes on v2_50 workbook.
- **Follow-up:** Rebuild cache for live UI; optional generator export for lab↔procedure linkage.
