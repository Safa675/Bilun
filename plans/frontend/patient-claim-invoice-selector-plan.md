# Plan: Add Invoice/Claim Selector to Patient Billing Page

## Task: Let users choose a specific invoice on the patient page

### Goal
Add a claim/invoice selector to `/patient/[id]` so a billing officer can pick a specific invoice (`F-...`) or episode (`B-...`) and see its details, instead of only seeing the aggregated per-patient view.

### Current state

- Patient page (`frontend/src/app/patient/[id]/page.tsx`) loads three patient-level endpoints:
  - `getSutPatientOutcome(patientId)`
  - `getPatientOptimization(patientId)`
  - `getPatientBillingReport(patientId)`
- There is no API to list a patient’s claims or view a single claim’s lines.
- The backend domain already has `SUTClaimDataset.claims_by_patient` and `*_lines_by_patient` in `src/bilun/domain/claims/loader.py`.

### Design decisions (to confirm with Safa)

1. **Selector scope:** show one row per claim/invoice (`F-...`) grouped by episode/visit (`B-...`).
2. **Selecting an invoice shows:** claim metadata + raw claim lines (procedures, materials, drugs) + exactness status. It does **not** yet show a full claim-scoped billing report (that requires per-claim re-run of the billing algorithms).
3. **Default view:** keep the existing patient-level aggregated billing report; the selector is an additional panel above or beside it.
4. **Data source:** read from `SUTClaimDataset` (same as `build_patient_claim_context`), not from the DuckDB cache, so it works in `synthetic_demo` mode without an analytics build.

### Subtasks

#### Phase 1 — Backend: patient claim list endpoint
- [ ] Add `GET /api/patients/{patient_id}/claims` in `src/bilun/api/routes/patients.py`.
- [ ] Response schema: list of claims with `claim_id`, `episode_id`, `claim_type`, `admission_date`, `discharge_date`, `claim_start_date`, `claim_end_date`, `primary_icd10`, `expected_total_billed_try`, `expected_total_payable_try`, `scenario_tag`, `line_counts` (procedures/materials/drugs).
- [ ] Load `SUTClaimDataset` via `load_sut_claim_dataset()` and filter by `patient_id`.
- [ ] Handle `real_claims` / `synthetic_demo` modes via existing config.
- [ ] Register route and re-export handler in `src/bilun/api/routes/__init__.py`.
- [ ] Add API test in `tests/unit/api/test_patient_claims_api.py`.

#### Phase 2 — Backend: single claim detail endpoint
- [ ] Add `GET /api/patients/{patient_id}/claims/{claim_id}` in `src/bilun/api/routes/patients.py`.
- [ ] Response schema: claim header + procedure lines + material lines + drug lines + diagnoses.
- [ ] 404 if claim does not belong to patient.
- [ ] Add API test.

#### Phase 3 — Frontend API client
- [ ] Add `getPatientClaims(patientId)` and `getPatientClaimDetail(patientId, claimId)` to `frontend/src/lib/api/sut.ts`.
- [ ] Add types in `frontend/src/lib/domains/sut.ts` (or existing domain types file):
  - `PatientClaimSummary`
  - `PatientClaimDetail`
  - `ClaimLine*` helpers.

#### Phase 4 — Frontend ClaimSelector component
- [ ] Create `frontend/src/components/patient/ClaimSelector.tsx`:
  - Dropdown or list of claims sorted by date.
  - Shows claim type badge, date range, total billed, ICD10.
  - "All claims" option to restore aggregated view.

#### Phase 5 — Frontend claim detail panel
- [ ] Create `frontend/src/components/patient/ClaimDetailPanel.tsx`:
  - Claim header metadata.
  - Tabs for procedures / materials / drugs / diagnoses.
  - Simple data table reusing existing `DataTable` primitive.

#### Phase 6 — Wire into patient page
- [ ] Update `frontend/src/app/patient/[id]/page.tsx`:
  - Load claims list alongside outcome/optimization/billing.
  - Add `selectedClaimId` state.
  - Render `ClaimSelector` + `ClaimDetailPanel` when a claim is selected.
  - Keep existing aggregated billing report below or as the default view.

#### Phase 7 — i18n
- [ ] Add EN+TR keys to `frontend/src/messages/en/patient.ts` and `frontend/src/messages/tr/patient.ts` (or appropriate files):
  - claim selector label, claim types (`yatis`, `poliklinik`, `acil`), line type labels, "all claims".

#### Phase 8 — Verify
- [ ] Backend tests pass.
- [ ] Frontend type-check (`npx tsc --noEmit`) — note: Node toolchain not available in this environment, so run locally.
- [ ] Manual smoke: open patient page, select a claim, verify detail panel renders.

### Out of Scope

- Claim-scoped billing report (re-running optimizer/billing algorithms on a single claim).
- Editing or creating claims from the UI.
- Adding claim selection to other pages (e.g., SUTPatients list).

### Definition of Done

- `/patient/[id]` shows a claim/invoice selector.
- Selecting a claim renders its raw lines (procedures, materials, drugs, diagnoses).
- Selecting "All claims" keeps the existing aggregated patient billing view.
- New endpoints have unit tests.
- i18n covers EN and TR.
