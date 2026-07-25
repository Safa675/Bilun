## Task: Full brittle-test remediation (plan first)

### Goal
Replace hardcoded census locks in unit tests with derived counts, soft floors, and self-consistency invariants so SUT re-extract / encode / synthetic regen no longer mass-break CI. Plan: `plans/refactor/brittle-test-remediation-plan.md`.

### Subtasks
- [x] Investigate brittle patterns (gate_b counts, rule-set lens, synthetic pins, catalog goldens, API/FE copy)
- [x] Write full remediation plan under `plans/refactor/brittle-test-remediation-plan.md`
- [x] **Verify plan with Safa** (approve / adjust scope before any test rewrites)
- [x] Phase 1: Finish gap-closure 0.3 (`==832/282/131` + helpers + `test_rule_sources` leftovers)
- [x] Phase 2: Rest of gate_b suite → invariant helpers
- [x] Phase 3: Rule-set `len() == N` locks (fatura, treatment_pricing, BATCH_*, fact_check)
- [x] Phase 4: Synthetic census + patient/claim ID pins → scenario_tag / soft floors
- [x] Phase 5: Catalog goldens + API/FE copy; mark pipeline Phase 5 done
- [x] Phase 6: Residual grep triage, cross-plan checkboxes, allowed-exact note
- [x] Finish previously deferred: FE TRY HTML asserts + catalog stubs

### Out of Scope
- Changing extractor/evaluator/rule JSON contents
- Regenerating parquet or synthetic cohort
- Non-drug gate_b **code** consolidation
- Frontend i18n catalog expansion

### Review
- Helpers: `brittle_guards.py`, `catalog_stubs.py`, `frontend/src/test/fmtMoney.ts`
- DoD: `==832/282/131` clean; SGK zero hardcoded patient IDs; loader soft floors; catalog prices from stubs; FE money from fixtures
- Verification: 813+ backend remediations; 27 catalog-stub tests; 39 FE vitest
- Cross-plan: gap-closure §0.3 + pipeline Phase 5 marked done
