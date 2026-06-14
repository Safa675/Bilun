# Plan: Fix All Test Failures (23 failed + 22 errors)

## Task: Restore a green Python test suite

### Goal
Make `.venv/bin/python -m pytest` pass with **0 failures and 0 errors** by fixing the 9 root-cause categories behind the current 23 failures and 22 collection/runtime errors.

### Current state

```
23 failed, 412 passed, 22 errors
```

The failures cluster into 9 categories. This plan fixes them in dependency order: import/path fixes first, then data-source/loader drift, then domain-logic/test-coupling issues.

---

### Phase 1 — Fix stale ILAY → BILUN imports and missing fixtures

**Root cause:** Tests still import the old `src.api.*` package and use the old `/api/sut/*` route prefix; the smoke fixture `api_client` is missing.

- [ ] **1.1** `tests/unit/api/test_sut_schema_exactness.py:6`
  - Remove the stale import `from src.api.schemas.patients import PatientOutcomeResponse`.
  - Update `test_patient_outcome_schema_requires_drg_pricing_status()` (line 53) to validate `BilunPatientOutcomeResponse` from `src.bilun.api.schemas`.
  - If that test duplicates `test_sut_patient_outcome_schema_requires_drg_pricing_status()`, delete it instead.

- [ ] **1.2** `tests/unit/api/test_sut_cache_concurrency.py`
  - Remove all `import src.api.routes.sut as sut_mod`.
  - Import the split BILUN modules/functions:
    - `from src.bilun.api.routes.alerts import get_patient_alerts`
    - `from src.bilun.api.routes.optimization import get_optimization_summary, get_patient_optimization, get_revenue_recovery`
    - `from src.bilun.api.routes.billing import get_patient_billing_report`
    - `from src.bilun.api.routes.patients import get_sut_patients, get_sut_patient_outcome`

- [ ] **1.3** `tests/unit/api/test_sut_patient_alerts_api.py`
  - `import src.api.routes.chat as chat_mod` → `import src.bilun.api.routes.chat as chat_mod`
  - `from src import storage as cache_store` → `from src.bilun.db import patient_alerts as cache_store` (functions are re-exported from `src.bilun.db`).

- [ ] **1.4** `tests/smoke/test_sut.py`
  - Replace all `/api/sut/...` paths with `/api/...` (e.g. `/api/sut/validate-claim` → `/api/validate-claim`).

- [ ] **1.5** `tests/conftest.py`
  - Add a module-level `api_client` fixture using the same pattern as `tests/unit/api/test_sut_chat.py`:
    ```python
    from fastapi.testclient import TestClient
    from src.bilun.api import app

    @pytest.fixture
    def api_client():
        with TestClient(app) as client:
            yield client
    ```
  - **Do not** remap `/api/sut/*` paths inside `tests/unit/api/test_sut_chat.py`; those 404 assertions are intentional regression guards for removed routes.

**Verification target:**
```bash
.venv/bin/python -m pytest \
  tests/unit/api/test_sut_schema_exactness.py \
  tests/unit/api/test_sut_cache_concurrency.py \
  tests/unit/api/test_sut_patient_alerts_api.py \
  tests/smoke/test_sut.py
```

---

### Phase 2 — Make billing orchestrator defensive against test stubs

**Root cause:** `MaterialPreCheck` gained fields `prose_bundling_violations` and `specialty_prose_violations`, but several tests monkeypatch `_precheck_materials` with a `SimpleNamespace` that lacks them. The orchestrator reads these fields unconditionally at `src/bilun/domain/billing/orchestrator.py:419-422` and `src/bilun/domain/billing/orchestrator.py:620-626`.

**Decision:** Prefer making production code defensive with `getattr(..., [], [])` rather than spreading dataclass internals across many test stubs. This also hardens the orchestrator against partial reports.

- [ ] **2.1** `src/bilun/domain/billing/orchestrator.py:419-422`
  - Replace direct `len(report.materials.prose_bundling_violations)` accesses with `getattr(report.materials, "prose_bundling_violations", [])`.
  - Do the same for `specialty_prose_violations` and `bundled_separate_billing`.

- [ ] **2.2** `src/bilun/domain/billing/orchestrator.py:620-626`
  - Apply the same defensive reads when summing `total_material_flags`.

**Affected tests (should pass after fix):**
- `tests/unit/domain/billing/test_billing_bugfixes.py::test_orchestrator_recoverable_total_counts_rx_once_with_visit_copay`
- `tests/unit/domain/billing/test_honest_gaps.py::test_orchestrator_total_includes_only_exact_blocks`
- `tests/unit/domain/billing/test_orchestrator_grand_total.py::test_grand_total_sums_patient_recoverable_not_heuristic_blocks`
- `tests/unit/domain/test_billing_strategy_exactness.py::test_billing_report_totals_exclude_gated_strategy`

**Verification target:**
```bash
.venv/bin/python -m pytest \
  tests/unit/domain/billing/test_billing_bugfixes.py \
  tests/unit/domain/billing/test_honest_gaps.py \
  tests/unit/domain/billing/test_orchestrator_grand_total.py \
  tests/unit/domain/test_billing_strategy_exactness.py
```

---

### Phase 3 — Fix claims config env-var messages and loader mode handling

**Root cause:** `resolve_sut_data_source` now uses `BILUN_*` env var names in error messages and validates synthetic paths more strictly. The loader cache drops the `mode` parameter.

- [ ] **3.1** `tests/unit/domain/claims/test_config.py:94,135`
  - Update test assertions to match the new `BILUN_DATA_MODE`, `BILUN_CLAIMS_DIR`, `BILUN_CLEAN_DIR` wording in production error messages.
  - No source change needed unless backward-compatible error strings are desired.

- [ ] **3.2** `tests/unit/domain/claims/test_config.py:159`
  - Update expected claim count from `138` to `134` (current committed fixture has 134 rows).

- [ ] **3.3** `tests/unit/domain/claims/test_config.py:177`
  - Fix `test_loader_can_read_configured_real_claims_dir`: the cached loader call loses `mode`, so real-claims directories are re-validated as synthetic.
  - Fix `src/bilun/domain/claims/loader.py:205-208` so `_load_sut_claim_dataset_cached` accepts and preserves `mode` in the cache key and passes it to `read_claim_tables(resolved_directory, mode=mode)`.

- [ ] **3.4** `tests/unit/domain/claims/test_loader.py:25-28`
  - Update expected parquet row counts to current fixture dimensions:
    - procedures: `753`
    - materials: `151`
    - drugs: `336`
    - expected outputs: `579`

**Verification target:**
```bash
.venv/bin/python -m pytest \
  tests/unit/domain/claims/test_config.py \
  tests/unit/domain/claims/test_loader.py
```

---

### Phase 4 — Fix `validate_claim` unit tests for prose side effects

**Root cause:** `validate_claim` unconditionally calls `check_material_bundling_prose` and `check_specialty_materials_prose` at `src/bilun/domain/rule_engine.py:160-222`. The unit tests only monkeypatch the old rule-engine helpers, so prose adds extra violations/risk.

- [ ] **4.1** Decide approach:
  - **Option A (recommended):** Update the tests to monkeypatch `check_material_bundling_prose` and `check_specialty_materials_prose` to return empty lists, keeping the production behavior intact.
  - **Option B:** Make prose calls conditional on non-empty material list + a feature flag, but this weakens the rule engine.

- [ ] **4.2** Implement chosen approach for:
  - `tests/unit/domain/test_rule_engine_validate_claim.py:42` — `test_validate_claim_bundling_violation`
  - `tests/unit/domain/test_rule_engine_validate_claim.py:75` — `test_validate_claim_exclusion_makes_invalid`

**Verification target:**
```bash
.venv/bin/python -m pytest tests/unit/domain/test_rule_engine_validate_claim.py
```

---

### Phase 5 — Fix billing strategy recommendation kind

**Root cause:** `tests/unit/domain/test_billing_strategy_exactness.py:59` expects `recommendation_kind == "mandatory_compliance"`, but `src/bilun/domain/billing/claim_strategy.py:311-321` returns `"optional_override"` for DRG-overridable procedures.

- [ ] **5.1** Inspect the synthetic fixture for `F-SENTETIK-HASTA-0003-011` to determine its actual `claim_kind` before changing anything.
  - If `claim_kind == DRG_OVERRIDABLE` → update test expectation to `optional_override`.
  - If `claim_kind == DRG_MANDATORY` → fix `claim_strategy.py` classification.
  - Do not default to updating the test without checking the fixture.

**Verification target:**
```bash
.venv/bin/python -m pytest tests/unit/domain/test_billing_strategy_exactness.py
```

---

### Phase 6 — Fix patient recovery summary payload mapping

**Root cause:** `patient_recovery_summary_from_payload` reads `billing_strategy.uplift_savings_try` while the test uses `billing_strategy.total_savings`; it also emits extra keys `sgk_uplift_try` and `compliance_adjustment_try` not expected by the test.

- [ ] **6.1** Align schema in `src/bilun/domain/billing/orchestrator.py:755-787` with the test payload, **or** update `tests/unit/domain/test_patient_recovery_summaries.py:26` to match the new contract.
  - **Default recommendation:** update the test to use `uplift_savings_try` and include the new keys, preserving the production contract.

**Verification target:**
```bash
.venv/bin/python -m pytest tests/unit/domain/test_patient_recovery_summaries.py
```

---

### Phase 7 — Resolve material bundling golden `C001637` mismatch

**Root cause:** Golden expects `3.1.1.(17).barcode_sut_mismatch`, but the engine returns `3.1.2.(2).not_in_ek3c` because the synthetic material `LOST1` is absent from EK-3/C and the barcode rule requires an explicit `barcode_sut_mismatch: true` flag that the test does not pass.

- [ ] **7.1** Decide:
  - **Option A (recommended):** Update `data/gazette/prose_rules/golden/material_bundling_gate_b.json` so `C001637` expects `3.1.2.(2).not_in_ek3c`.
  - **Option B:** Change `src/bilun/domain/prose_rules/material_bundling.py` so the barcode rule fires on name match alone.

**Verification target:**
```bash
.venv/bin/python -m pytest tests/unit/domain/prose_rules/test_material_bundling_golden.py
```

---

### Phase 8 — Full-suite verification and regression guard

- [ ] **8.1** Run the entire Python test suite:
  ```bash
  .venv/bin/python -m pytest
  ```
- [ ] **8.2** Confirm `0 failed, 0 errors`.
- [ ] **8.3** Mark the task complete in `tasks/todo.md` and archive the narrower "4 failures" plan.
- [ ] **8.4** (Optional) Register the `unit`, `smoke`, and `live` markers in `pyproject.toml` under `[tool.pytest.ini_options]` to silence marker warnings.
- [ ] **8.5** (Optional but recommended) Add the GitHub Actions CI workflow now that the suite is green.

---

### Out of Scope

- Frontend `tsc`/`vitest`/`next build` failures (separate Node toolchain work).
- Adding CI workflow itself is listed as a follow-up in Phase 8.4, not part of this plan.
- Re-architecting the test suite beyond the minimal fixes required to go green.

---

### Risks / Open Questions

1. **Domain decisions needed:** Phases 3.1, 5.1, and 7.1 require Safa to confirm whether to update tests or source behavior.
2. **Smoke test value:** After `/api/sut/*` → `/api/*` remapping, verify the endpoints still behave as expected; smoke tests may expose deeper drift or require DuckDB cache bootstrap in `TESTING` mode.
3. **Loader cache:** Changing `_load_sut_claim_dataset_cached` signature requires care to avoid breaking production caching.
4. **404 regression guards:** `tests/unit/api/test_sut_chat.py` intentionally asserts `/api/sut/*` returns 404. These must not be "fixed" to `/api/*`.
