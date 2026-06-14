# Plan: Fix 4 Pre-existing Test Failures

## Task: Fix stale ILAY→BILUN imports + material bundling golden mismatch

### Goal
Make the 4 pre-existing failing tests green by updating stale `src.api.*`/`src.storage` imports to the current `src.bilun.*` package structure, and resolving the `C001637` material-bundling golden rule mismatch.

### Current State

Running `.venv/bin/python -m pytest` currently shows **23 failed, 22 errors** overall. This plan scopes to the 4 failure clusters explicitly called out in `tasks/todo.md` as pre-existing:

| Test file | Failure mode | Root cause (preliminary) |
|-----------|--------------|--------------------------|
| `tests/unit/api/test_sut_schema_exactness.py` | `ModuleNotFoundError: No module named 'src.api'` | Imports `src.api.schemas.patients.PatientOutcomeResponse`; current model is `BilunPatientOutcomeResponse` in `src.bilun.api.schemas`. |
| `tests/unit/api/test_sut_cache_concurrency.py` | `ModuleNotFoundError: No module named 'src.api'` | Imports `src.api.routes.sut`; functions moved to `src.bilun.api.routes.{alerts,optimization,billing,patients}`. |
| `tests/unit/api/test_sut_patient_alerts_api.py` | `ModuleNotFoundError: No module named 'src.api'` | Imports `src.api.routes.chat` (now `src.bilun.api.routes.chat`) and `from src import storage` (now `src.bilun.db.patient_alerts`). |
| `tests/unit/domain/prose_rules/test_material_bundling_golden.py::test_gate_b_golden_expected_rule[C001637]` | `AssertionError: '3.1.2.(2).not_in_ek3c' == '3.1.1.(17).barcode_sut_mismatch'` | Golden expects `barcode_sut_mismatch`, but engine returns `not_in_ek3c` first. |

### Subtasks

#### Phase 1 — Remap stale imports in `test_sut_schema_exactness.py`
- [ ] Replace `from src.api.schemas.patients import PatientOutcomeResponse` with `from src.bilun.api.schemas import BilunPatientOutcomeResponse`.
- [ ] Update `test_patient_outcome_schema_requires_drg_pricing_status()` to validate `BilunPatientOutcomeResponse` (or remove if redundant with existing `SutPatientOutcomeResponse` tests).
- [ ] Run the file and confirm collection + all tests pass.

#### Phase 2 — Remap stale imports in `test_sut_cache_concurrency.py`
- [ ] Remove `import src.api.routes.sut as sut_mod` pattern; import the specific new modules:
  - `from src.bilun.api.routes.alerts import get_patient_alerts`
  - `from src.bilun.api.routes.optimization import get_optimization_summary, get_patient_optimization, get_revenue_recovery`
  - `from src.bilun.api.routes.billing import get_patient_billing_report`
  - `from src.bilun.api.routes.patients import get_sut_patients, get_sut_patient_outcome`
- [ ] Update each test function to call the remapped functions.
- [ ] Run the file and confirm all 9 tests pass.

#### Phase 3 — Remap stale imports in `test_sut_patient_alerts_api.py`
- [ ] Replace `import src.api.routes.chat as chat_mod` with `import src.bilun.api.routes.chat as chat_mod`.
- [ ] Replace `from src import storage as cache_store` with `from src.bilun.db.patient_alerts import ensure_patient_alert_summary, ensure_patient_alert_tables as cache_store` (or equivalent explicit import).
- [ ] Verify `_fetch_db_context` is still exposed by `src.bilun.api.routes.chat`.
- [ ] Run the file and confirm all 10 tests pass.

#### Phase 4 — Resolve `C001637` material bundling golden mismatch
- [ ] Confirm the two candidate rules in `data/gazette/prose_rules/material_bundling_prose.json`:
  - `3.1.1.(17).barcode_sut_mismatch` (golden expectation, keyword-match on name).
  - `3.1.2.(2).not_in_ek3c` (actual result, generic "not in EK-3/C" rule).
- [ ] **Decision required from Safa**:
  - **Option A (update golden expectation):** Change `expected_rule_id` in `data/gazette/prose_rules/golden/material_bundling_gate_b.json` to `3.1.2.(2).not_in_ek3c`, because the synthetic material `LOST1` is not in EK-3/C and that rule fires first.
  - **Option B (change rule precedence):** Update `check_material_bundling_prose()` so `barcode_sut_mismatch` wins when the material name matches, even if the material is also absent from EK-3/C.
- [ ] Implement chosen option.
- [ ] Run `test_material_bundling_golden.py` and confirm all cases pass.

#### Phase 5 — Verification
- [ ] Run the scoped 4 test targets together and confirm green:
  ```bash
  .venv/bin/python -m pytest \
    tests/unit/api/test_sut_schema_exactness.py \
    tests/unit/api/test_sut_cache_concurrency.py \
    tests/unit/api/test_sut_patient_alerts_api.py \
    tests/unit/domain/prose_rules/test_material_bundling_golden.py
  ```
- [ ] Update `tasks/todo.md`: mark the Rule Database task's CI item complete and note the 4 failures are fixed.

### Out of Scope
- Fixing the **other** 19 failures and 22 errors discovered in the full suite (those are separate regressions or unrelated stale tests, not the 4 explicitly identified pre-existing failures).
- Adding CI/GitHub Actions workflow (covered separately; CI should only be enabled after the full suite is green).
- Refactoring the test file structure or renaming tests beyond import/path fixes.

### Risks / Open Questions
1. **Domain decision on C001637:** Cannot proceed with Phase 4 until Safa chooses Option A or B.
2. **Full-suite rediscovery:** Running the complete test suite reveals additional failures. After these 4 are fixed, a follow-up plan is needed to address the remaining 19 failures and 22 errors before CI can be turned on.
3. **Chat route compatibility:** `src.bilun.api.routes.chat._fetch_db_context` signature may have changed; verify during Phase 3.
