# Yatak Puanı Motor — Inpatient Bed-Day Billing (Evaluated + Corrected Plan)

**Branch:** TBD (off `main`)
**Goal:** Add a billing motor that computes the hospital bed-day charge (yatak puanı) for inpatient claims: **inclusive bed-days** × EK-2B 510010 price. Follows the blood_uplift pattern (8 touchpoints, verified).

## 3 corrections from the evaluation

| Issue | Plan's original | Corrected (verified) |
|---|---|---|
| **Day counting** | `(discharge - admission).days` = 3 (exclusive, discharge NOT billed) | `(discharge - admission).days + 1` = 4 (inclusive, discharge IS billed) — matches `drg.py:225` convention + Turkish SUT rule |
| **Catalog lookup** | `lookup_procedure_code("510010")` returns scalar 374.97 | Returns dict: `["entry"]["price_try"]` = 222.36 (already puan × katsayı, no multiplication needed) OR `["entry"]["puan"]` × `get_katsayi()` |
| **Touchpoint count** | 7 files | **8 files** — missing `billing_actions.py` (action-collection tuple at lines 139-148) |

## Scope (Phase 1 only)

✅ 510010 Standart yatak for inpatient (yatis) claims
✅ Day counting: **inclusive LOS** = `(discharge_date - admission_date).days + 1`
✅ <24h stay detection → informational flag that 510120 (gündüz yatak) should be used
✅ Skip non-inpatient claims via `infer_care_setting(claim)` != "inpatient"
✅ Skip claims with null admission/discharge dates (MISSING_INPUTS)
❌ ICU day-rate (510090) + packages — Phase 2
❌ Newborn (510070/510081) — Phase 2
❌ Companion (510121) — Phase 2
❌ Surcharge (§1.9.4) — patient-side, not SGK billing

## 8 file changes (following blood_uplift pattern exactly)

### 1. NEW `src/bilun/domain/prose_rules/yatak_puani.py` — core detector
- `detect_yatak_puani_opportunities(claims, procedure_lines) → list[dict]`
- For each inpatient claim with non-null admission+discharge dates:
  - `days = (discharge_date - admission_date).days + 1` (inclusive LOS)
  - `daily_rate = lookup_procedure_code("510010")["entry"]["price_try"]` (222.36 TL/day, already puan×katsayı)
  - `expected_yatak_try = days × daily_rate`
  - Return opportunity dict: claim_id, days, daily_rate, expected_yatak_try, sut_section="2.2.2", rule_id="yatak_puani_510010"
- Flag <24h stays (days == 0 after +1... actually days ≥ 1 always since +1; <24h = admission == discharge date → 1 day billable, but flag for gündüz review)
- Skip non-inpatient via `infer_care_setting(claim) != "inpatient"`

### 2. EDIT `src/bilun/domain/billing/types.py` — result dataclass + constants
- NEW dataclass `YatakPuaniReview`: opportunities, exactness_status, unavailable_reason, required_inputs_missing, rule_source, `confirmed_yatak_try` property
- NEW field `yatak_puani: YatakPuaniReview` on `BillingActionReport` (default_factory)
- NEW constants `YATAK_PUANI_REQUIRED_INPUTS`, `YATAK_PUANI_UNAVAILABLE_REASON`
- NEW cohort fields: `total_yatak_puani: float = 0.0`, `n_yatak_puani_patients: int = 0` on `CohortRecoverySummary`

### 3. EDIT `src/bilun/domain/billing/block_registry.py` — add BillingBlockSpec
- `BillingBlockSpec(attr="yatak_puani", required_inputs=YATAK_PUANI_REQUIRED_INPUTS, unavailable_reason=YATAK_PUANI_UNAVAILABLE_REASON, uplift_field="confirmed_yatak_try", cohort_total_field="total_yatak_puani", cohort_patient_counter_field="n_yatak_puani_patients")`

### 4. NEW `src/bilun/domain/billing/claim_yatak_puani.py` — billing wrapper
- `recommend_yatak_puani_from_claims(ctx) → YatakPuaniReview`
- If no inpatient claims → return MISSING_INPUTS; else loop claims, call detector, return EXACT

### 5. EDIT `src/bilun/domain/billing/patient_report.py` — wire the motor
- Import + `report.yatak_puani = recommend_yatak_puani_from_claims(claim_context)` inside `if claim_context.procedure_lines:` block

### 6. EDIT `src/bilun/domain/billing/cohort_summary.py` — extend hardcoded lists
- Add `total_yatak_puani` rounding to `_finalize_summary_rounding`
- Add `"yatak_puani"` key to `_savings_by_category`

### 7. EDIT `src/bilun/domain/billing/billing_actions.py` — action collection
- Add `("yatak_puani", report.yatak_puani, "expected_yatak_try")` to the hardcoded tuple at lines 139-148

### 8. EDIT `src/bilun/domain/billing/recovery_summary.py` — top-action attribution
- Add `yatak_puani` to `_get_top_action_type` dict + the cached-payload variant

## Key data lookups (verified)
- `lookup_procedure_code("510010")["entry"]["price_try"]` → 222.36 TL/day (already puan × katsayı)
- `lookup_procedure_code("510010")["entry"]["puan"]` → 374.97 (if you want puan × katsayı separately)
- `get_katsayi()` → 0.593 (from `data/gazette/sut_checkup_pricing.json`, static, no temporal versioning)
- `infer_care_setting(claim)` from `prose_rules/claim_utils.py:30-41` → returns "inpatient" for yatis
- `ClaimHeader.admission_date` / `discharge_date` → `date | None` (nullable — must guard)

## NEW `tests/unit/domain/prose_rules/test_yatak_puani.py` + `tests/unit/domain/billing/test_yatak_wiring.py`
- Inpatient claim, 4-day stay (Jul 10→13 inclusive) → expected_yatak_try = 4 × 222.36 = 889.44
- Same-day admission/discharge (1 day inclusive) → 1 × 222.36, flag for gündüz review
- Outpatient claim → no opportunity (skipped)
- Missing admission/discharge dates → MISSING_INPUTS

## Verification
- `pytest tests/unit/domain/prose_rules/test_yatak_puani.py tests/unit/domain/billing/test_yatak_wiring.py -v`
- `pytest tests/unit/ tests/smoke/ -q` — no regression
- `compile_rules.py --check` — byte-identical

## Out of Scope
ICU (510090 + P55200x), newborn (510070/510081), companion (510121), surcharge (§1.9.4) — Phase 2