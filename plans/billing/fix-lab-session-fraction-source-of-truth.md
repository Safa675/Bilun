## Task: Fix lab optimization to use billed claim lines as the source of truth

### Goal
Make the "Laboratuvar optimizasyonu" / session-fraction correction reflect what was actually billed on each claim, using the lab claim lines (`procedure_claim_lines` with `procedure_category == "laboratuvar"`) as the source of truth, and move the "clinical lab result present but not billed" check into an explicit capture-gap comparison.

---

## Current findings (verified in code)

| Problem | Where |
|---------|-------|
| Lab optimizer treats every clinical lab result row as a billed procedure | `src/bilun/domain/billing/lab.py:216` iterates `patient_lab_tests` assuming each entry is one billable line |
| Session-fraction savings use gazette list price, not the amount actually billed | `src/bilun/domain/billing/lab.py:71-97`, `lab.py:245`, `lab.py:155-160` |
| Lab optimizer ignores the actual lab-billed claim lines | `src/bilun/domain/claims/models.py:58-81` defines `ProcedureClaimLine` with `billed_amount_try`, `expected_payable_try`, `lab_result_id`, `lab_billing_status` — none are read by `lab.py` |
| Capture gap does not look at the clinical lab feed at all | `src/bilun/domain/prose_rules/procedure_capture_gap.py:69-76` only consumes `performed_procedure_lines` |
| Per-bill scoping still passes duplicate clinical result rows | `src/bilun/domain/billing/orchestrator.py:434-468` groups `lab_clean.parquet` by visit, preserving duplicates |

**Subsequent decision:** SUT §2.2.2.A(5) applies to surgical "işlemler" with "kesi" (incision), not laboratory "tetkikler". Therefore session-fraction correction was removed from lab optimization entirely; the legacy `lab.py` module was deleted after `claim_lab.py` took over.

This produces phantom flags such as a single billed Kortizol line appearing 4× in the optimization table because the clinical lab feed contains 4 result rows for the same test on the same visit.

---

## Subtasks

### Phase 0 — Spike: inspect one synthetic patient end-to-end
- [ ] Pick `SENTETIK-HASTA-0001-002` (or the patient that demonstrated the bug).
- [ ] Dump:
  - `procedure_claim_lines` rows where `procedure_category == "laboratuvar"` for that claim.
  - `lab_clean.parquet` rows for that patient + `visit_id`.
  - Current `LabOptimization` output (flagged tests, session savings, hemogram savings).
- [ ] Document the exact mismatch: billed line count vs. clinical result row count, billed amount vs. gazette price, and the resulting phantom savings.
- [ ] Assert the correct target: `session_fraction_savings` must be computed from `billed_amount_try` (not gazette list price) and must equal the sum of secondary-line `billed_amount_try × (1 − point_factor)` produced by the existing session-fraction engine. Note: `expected_payable_try` on the claim is a composite of multiple SUT rules, so the session-fraction savings are a component, not necessarily equal to `billed − expected_payable_try`.
- [ ] Confirm with the existing test suite that no test currently asserts the broken behavior as correct.

### Phase 1 — Add a claim-line-based lab optimizer
- [ ] Add `src/bilun/domain/billing/claim_lab.py` with `_optimize_lab_billing_from_claims(claim_context: PatientClaimContext) -> LabOptimization`.
- [ ] Inputs: only the lab claim lines from `claim_context.procedure_lines` filtered by `procedure_category == "laboratuvar"`.
- [x] Group lab claim lines by `episode_id` (visit) for encounter-aware hemogram bundling.
- [x] ~~Reuse `_apply_session_fractions_to_encounter()` logic from `src/bilun/domain/billing/lab.py:128-182`, but with `(procedure_name, procedure_code, billed_amount_try)` tuples instead of gazette prices.~~
- [x] ~~For each secondary lab line where `factor.point_factor < 1.0`, compute savings as `billed_amount_try - (billed_amount_try * factor.point_factor)`.~~
- [x] Session-fraction correction was removed from lab tests after confirming SUT §2.2.2.A(5) does not cover laboratory "tetkikler".
- [x] Preserve hemogram bundling detection, but operate on claim lines: if multiple CBC subtests are billed as separate lines on the same claim, flag the bundle correction using the **sum of their billed amounts** as the overbilling basis.
- [ ] Return the same `LabOptimization` dataclass shape so the frontend requires no change.

### Phase 2 — Merge lab gaps into capture gap
- [ ] Add `src/bilun/domain/prose_rules/lab_capture_gap.py` with `detect_lab_capture_gaps(lab_df_pl, procedure_claim_lines, episode_id)`.
- [ ] Group clinical lab results by `(patient_id, visit_id, sut_code)` and deduplicate (a single test code on a visit = one performed test regardless of result row count).
- [ ] Compare against billed lab claim lines by `(episode_id, procedure_code)`.
- [ ] Emit an opportunity for each clinical lab code that has no matching billed claim line with `billed_amount_try > 0.02 TRY`.
- [ ] Use gazette list price as the recoverable gap estimate (display-only, `included_in_sgk_total=False`).
- [ ] Wire the lab gaps into the existing `procedure_capture_gap` report field so the section remains useful when only lab gaps exist.
- [ ] Update `src/bilun/domain/billing/claim_procedure_capture_gap.py:23-57` exactness logic: report `exact` if either `performed_procedure_lines` or the clinical lab feed is present; mark `unavailable` only when both are missing.

### Phase 3 — Replace the old lab optimizer call sites
- [ ] In `src/bilun/domain/billing/orchestrator.py:338-343`, call the new claim-line-based optimizer when `claim_context` is present.
- [ ] In `src/bilun/domain/billing/orchestrator.py:489-555` (`compute_all_bill_billing_reports`), remove the clinical lab feed grouping and pass the per-bill `claim_context` directly to the new optimizer.
- [ ] In `src/bilun/domain/billing/orchestrator.py:558-679` (`compute_all_billing_reports`), compute patient-level lab optimization by summing per-bill claim-line lab results instead of falling back to the clinical lab feed. If no claim dataset is available, return an empty lab section and mark `required_inputs_missing` honestly.
- [x] Remove the old `lab.py` path entirely; lab optimization now requires claim lines.

### Phase 4 — Frontend label / exactness updates
- [ ] Update `frontend/src/messages/tr/billing.ts` and `en/billing.ts` so the lab section title/description reflects claim-line sourcing (e.g., "Fatura lab satırlarına göre" / "Based on billed lab lines").
- [ ] When per-bill, label says "this bill's lab billing"; when patient aggregate, label says "sum across all bills".
- [ ] Add an exactness/required-inputs note when claim lines are missing so the lab section is not silently empty.

### Phase 5 — Tests
- [ ] Add `tests/unit/domain/billing/test_claim_lab_optimizer.py`:
  - One billed lab per visit → no flag.
  - Two distinct billed labs per visit → secondary flagged with factor and savings based on `billed_amount_try`.
  - CBC subtests billed separately on one claim → hemogram bundling savings equal sum of billed subtest amounts minus one CBC gazette price.
- [ ] Add `tests/unit/domain/prose_rules/test_lab_capture_gap.py`:
  - Clinical lab exists, claim line missing → gap flagged.
  - Clinical lab has 4 result rows but 1 billed claim line → no gap.
  - Clinical lab exists and billed line exists with amount > 0 → no gap.
- [ ] Add regression test `tests/unit/domain/billing/test_lab_optimizer_sentetik_0001_002.py`:
  - Load claim `F-SENTETIK-HASTA-0001-002`.
  - Assert lab optimizer emits **≤ 3** `session_fraction_overbilling` flags (one per lab claim line, no phantom duplicates).
  - Assert `session_fraction_savings` is derived from `billed_amount_try` and equals the session-fraction engine output for the 3 billed lab lines (HLA primary, Kortizol and İdrar secondary at 30%).
- [ ] Update `tests/unit/domain/billing/test_lab_session_fractions.py` to test the new claim-line path or rename it as the deprecated patient-level path test.
- [ ] Run full suite: `pytest -q`.

### Phase 6 — Cache rebuild and spot check
- [ ] Run `scripts/bilun/build_cache.py --activate`.
- [ ] Spot-check the same patient from Phase 0:
  - Lab optimization row count equals the number of lab claim lines on that bill.
  - Session-fraction savings derive from actual billed amounts.
  - No 4× phantom rows.
- [ ] Verify capture gap does not misflag the 4-result-row case.

---

## Phase 0 Review (completed 2026-06-15)

Patient: `SENTETIK-HASTA-0001`, claim: `F-SENTETIK-HASTA-0001-002`, episode: `B-SENTETIK-HASTA-0001-002`.

### Claim-line truth
3 lab claim lines on the bill:

| SUT code | Name | Billed TRY | Expected payable TRY | Variance |
|---|---:|---:|---:|---:|
| L112180 | Kortizol | 12.84 | 6.42 | 6.42 |
| L120000 | İdrar bütünlük | 7.89 | 4.74 | 3.15 |
| L103430 | HLA-DRB1 | 888.97 | 711.18 | 177.79 |
| **Total** | | **909.70** | **722.34** | **187.36** |

### Clinical lab feed
`lab_clean.parquet` for the same visit contains **12 rows**: 4 result rows per SUT code (`L112180`, `L120000`, `L103430`).

### Current optimizer output (broken)
The existing `src/bilun/domain/billing/lab.py` receives the 12 clinical result rows as if they were 12 billed procedures and produces:

- `session_fraction_savings`: **1,873.05 TRY** (10× the real variance)
- `flagged_tests`: **11 rows** (4 Kortizol + 4 İdrar + 3 HLA)
- Each flag uses the **gazette list price** (e.g., ₺38.91 for Kortizol, ₺808.16 for HLA), not the billed amount.

### Correct target
After the claim-line switch (before session-fraction removal):

- Lab optimizer should emit **≤ 3** flags (one per lab claim line).
- `session_fraction_savings` should be derived from `billed_amount_try` via the SUT session-fraction engine.
- For the 3 lab lines, the session-fraction engine assigns HLA (L103430) as primary (100%) and Kortizol (L112180) / İdrar (L120000) as secondary (30%).
- Expected output with session fraction:
  - Flags: 2 (Kortizol and İdrar; HLA is primary, so no flag).
  - `session_fraction_savings`: `(12.84 + 7.89) × 0.70 = 14.51 TRY`.

### Final target (session fraction removed)
After legal review, SUT §2.2.2.A(5) does not apply to laboratory tests. The final implementation:

- Lab optimizer emits **0** session-fraction flags.
- `session_fraction_savings`: **0.00 TRY**.
- Only hemogram bundling remains active.

### Existing tests
No existing test asserts the 12-row/11-flag behavior. `tests/unit/domain/billing/test_lab_session_fractions.py` tests simple distinct-name scenarios; `tests/unit/domain/billing/test_billing_bugfixes.py` tests duplicate suppression and hemogram bundling by visit. These will be updated or preserved as deprecated-path tests in Phase 5.

---

## Out of Scope

- Changing how non-lab capture gap works (`performed_procedure_lines` for EMR/OR procedures stays as-is).
- Re-architecting the claim data model or ingestion pipeline.
- Adding new SUT session-fraction rules; only fix the input/pricing source for existing rules.
- Altering the frontend table component structure beyond labels and scope notes.
- Real (non-synthetic) hospital data ingestion.

---

## Verification / Definition of Done

- [ ] `SENTETIK-HASTA-0001-002` lab optimization shows one row per lab claim line, not per clinical result row.
- [ ] Session-fraction "tasarruf" equals the SUT-expected fraction of `billed_amount_try`, not the gazette list price.
- [ ] Hemogram bundling uses billed subtest amounts as the overbilling basis.
- [x] Capture gap section is available and accurate when only lab gaps exist (not hidden because EMR/OR log is missing).
- [x] Lab capture gap flags only clinical lab codes with no matching billed line; duplicate clinical result rows do not create duplicate gap flags.
- [x] Patient aggregate lab optimization equals the sum of per-bill claim-line lab optimizations; no silent fallback to clinical lab feed.
- [x] All new and existing tests pass (`pytest -q` green).
- [x] Cache rebuild succeeds and per-bill reports differ from patient aggregate where expected.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Some existing tests assert old gazette-price savings | Phase 5 explicitly updates tests; old behavior is considered buggy, not contractual |
| Patient-level aggregate must sum per-bill results | Refactor `compute_all_billing_reports` to reuse per-bill lab computation or iterate claims |
| Lab claim lines may be missing in production data | Required-inputs / exactness framework marks reports as partial; lab section shows unavailable reason |
| Capture gap exactness logic changes | Update exactness status to consider lab feed presence, not only performed_procedure_lines |
| Clinical lab-to-claim matching by code/date may be ambiguous | Match by `(episode_id, procedure_code)`; document that time-of-day is out of scope |

---

## Implementation review (completed 2026-06-15)

- Phase 0 confirmed the bug: `SENTETIK-HASTA-0001-002` had 3 lab claim lines but 12 clinical lab result rows; the old optimizer produced 11 phantom flags and ₺1,873.05 in gazette-price savings.
- Phase 1 added `src/bilun/domain/billing/claim_lab.py` with `_optimize_lab_billing_from_claims()`, using `billed_amount_try` as the savings basis.
- Phase 2 added `src/bilun/domain/prose_rules/lab_capture_gap.py` and merged lab gaps into the existing capture-gap report field; the section is no longer unavailable when only lab data exists.
- Phase 3 replaced optimizer call sites in `src/bilun/domain/billing/orchestrator.py`; patient aggregate now sums per-bill claim-line lab results.
- Phase 4 updated EN/TR i18n labels for the lab section and capture gap to reflect claim-line sourcing and lab-feed input.
- Phase 5 added 11 new tests; the `SENTETIK-HASTA-0001-002` regression initially asserted ≤3 flags and ₺14.51 session savings, then was updated to **0** flags and **₺0** session savings after session-fraction removal.
- Phase 6 rebuilt the cache (`c515aafb-606f-4a30-b06f-3a9913677e2b`) and verified the per-bill report shows 0 flags / ₺0.
- **Cleanup:** deleted legacy `src/bilun/domain/billing/lab.py`, removed its imports/exports, removed unused `patient_lab_tests/date/visit_ids` parameters from `compute_patient_billing_report()`, and updated tests/docs.

### Verification results
- `pytest -q`: **507 passed** after deleting `lab.py` and the legacy lab session-fraction tests (was 511; net -4 tests)
- `scripts/bilun/build_cache.py --activate`: succeeded
- Spot check: per-bill lab flags dropped from 11 → **0**; session savings from ₺1,873.05 → **₺0.00**

## Related plans

- `plans/frontend/patient-profile-per-bill-redesign-plan.md` — per-bill scoping context
- `plans/billing/billing_bugfixes.md` — previous lab grouping fixes (visit_id plumbing)
