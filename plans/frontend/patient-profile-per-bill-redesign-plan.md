# Patient Profile Redesign — Per-Bill Optimization + Original Invoice

> Status: IN PROGRESS — Phase 10 automated verify complete (2026-06-14); manual smoke pending server restart.
>
> **Phase 0 findings (verified):** `build_bill_claim_context(patient_id, claim_id, dataset)` added to `src/bilun/domain/claims/patient_context.py`. Per-bill billing reports are correct and **additive** — `action_count` and `total_recoverable_try` summed across bills equal the patient aggregate (validated on SENTETIK-HASTA-0001…0005: e.g. 0003 → 6967.01 on one bill, 0 on the rest; sum = patient total). **Lab IS attributable per bill**: the clinical lab feed carries `basvuru_id` which `cache/loaders.py:_normalize_lab` renames to `visit_id` (= `episode_id`), and `compute_patient_billing_report` already accepts `patient_lab_visit_ids`; filtering lab tests to the selected claim's `episode_id` scopes labs to the bill. **Decision: per-bill lab, no patient-level fallback needed.** Phase 8's lab caveat is therefore dropped.
> Supersedes the deferred item in `plans/frontend/patient-claim-invoice-selector-plan.md` ("Claim-scoped billing report", listed there as Out of Scope).
> Decisions locked with Safa: **backend per-bill scoping**, layout = **patient financial summary (all bills) → bill picker → selected bill's original invoice + that bill's optimization**, **full-fidelity original invoice**, **segmented bill picker**.

---

## Task: Make the patient profile bill-aware

### Goal
On `/patient/[id]`: show a patient-level **financial summary across all bills** at the top; let the user pick a **single bill** (claim) from a segmented picker; and below it show that **one bill's original invoice (as submitted)** alongside **that bill's own optimization suggestions** — instead of today's behavior where every optimization section is silently summed across all of the patient's bills.

### The core problem (verified in code)
- A "bill" = a **claim** (`claim_id`, derived from `fatura_id`); patients can have several. `episode_id` (`basvuru_id`) is the admission/visit. See `src/bilun/domain/claims/models.py:24-42` and `scripts/synthetic/exporters.py:187-199`.
- The bill picker today is a `<select>` (`ClaimSelector`) that **only** toggles a raw line-items panel. The billing/optimization sections come from patient-level aggregates (`/api/billing-report/{patient_id}`, `/api/patient/{id}/optimization`) and are **not** filtered by selection — this is the "sum of all bills" complaint. See `frontend/src/app/patient/[id]/page.tsx:75-80, 385-414` and `frontend/src/components/patient/ClaimSelector.tsx:72-75`.
- The billing report is served from a **precomputed cache** (`patient_billing_report_rows`, keyed by build + patient), `src/bilun/api/routes/billing.py:105-169`. Optimization is computed **live** from a `PatientClaimContext`, `src/bilun/api/routes/optimization.py:105-215`.
- `PatientClaimContext` is a flat per-patient bundle (`src/bilun/domain/claims/patient_context.py:21-76`) — trivially scopable to a single `claim_id`. The orchestrator already iterates per claim internally (`claim_strategy.py:266-272`), so a single-claim context yields a correct per-bill report.
- The "original bill" is barely shown: only per-opportunity `actual_billed → expected` rows + the raw `ClaimDetailPanel` when a claim is selected (`frontend/src/components/patient/ClaimDetailPanel.tsx:54-65, 164-182`). No faithful invoice view; no patient financial-summary card wired on this route (`ClaimSummaryPanel` exists but is only used on the home tab).

### Known constraint to design around (lab attribution)
The lab optimizer consumes a **clinical lab feed** (`lab_df_pl`) keyed by patient, not by `claim_id` (`src/bilun/domain/billing/orchestrator.py:463-485`, `lab.py:185-206`). Lab-billed rows otherwise live as procedure lines with `procedure_category == "laboratuvar"`. **Phase 0 must determine** whether lab savings can be attributed to a specific bill (via the lab procedure lines' `claim_id`) or must remain a patient-level section. Default if not cleanly attributable: keep **lab at patient level in the top summary**, and clearly label it as "across all bills" in the per-bill view (honors the exactness rules — never present an all-bills number as a single-bill number).

---

## Subtasks

### Phase 0 — Spike: bill-scoped context + lab attribution (decide before building)
- [ ] Add `build_bill_claim_context(patient_id, claim_id, dataset)` in `src/bilun/domain/claims/patient_context.py` that returns a `PatientClaimContext` filtered to one `claim_id` (claims, procedure/material/drug lines, diagnoses, performed lines, medula events). Reuse `build_patient_claim_context` then filter by `claim_id`.
- [ ] Run `compute_patient_billing_report` on a single-bill context for a multi-claim patient; confirm every section's totals reflect just that bill.
- [ ] Determine lab attribution: can `lab_df_pl` rows be tied to a `claim_id` (join via lab procedure lines / episode / date)? Record the answer. Pick: (a) per-bill lab, or (b) patient-level lab labeled accordingly.
- [ ] Write findings into this plan's Review section before Phase 1.

### Phase 1 — Backend: per-bill billing report
- [ ] Orchestrator entry that accepts a bill-scoped context (reuse `compute_patient_billing_report`; if lab stays patient-level, pass a flag to skip/relabel the lab block).
- [ ] **Cache build**: in `src/bilun/cache/builder.py`, precompute one billing report per `(patient_id, claim_id)` and store in a new payload-rows table `patient_bill_billing_report_rows` (key: build_id, patient_id, claim_id). Parallelize per patient (AGENTS.md §9). Schema mirrors existing billing rows (`src/bilun/db/schema.py`).
- [ ] New endpoint `GET /api/billing-report/{patient_id}/bills/{claim_id}` in `billing.py`, mirroring the existing cache-read pattern (`billing.py:116-160`); 404 when the claim isn't the patient's.
- [ ] Reuse `BillingReportResponse` (add optional `claim_id` echo + `scope: "bill" | "patient"`).
- [ ] Tests: `tests/unit/api/test_patient_bill_billing_api.py` (per-bill totals < patient totals; sum of per-bill ≈ patient aggregate where sections are claim-attributable).

### Phase 2 — Backend: per-bill optimization
- [ ] New endpoint `GET /api/patient/{patient_id}/bills/{claim_id}/optimization` in `optimization.py`, reusing the live-compute path (`optimization.py:147-201`) but with the bill-scoped context from Phase 0.
- [ ] Reuse `PatientOptimizationResponse` (+ `claim_id`, `scope`).
- [ ] Tests: bill-scoped surcharge/copay-rate/DRG-unbundling reflect only the selected claim.

### Phase 3 — Backend: enrich the claims list for the picker
- [x] Extend `PatientClaimSummary` (`src/bilun/api/schemas.py:551-567`) with `recoverable_try` and `priority` per bill (computed in cache build alongside Phase 1, cheap rollup of each per-bill report's `total_recoverable_try` / `priority`).
- [x] Populate in `GET /api/patients/{patient_id}/claims` (`patients.py:222-242`).
- [x] Tests: list returns per-bill recoverable + priority; absent build degrades gracefully (nulls).

### Phase 4 — Frontend: API client + types
- [x] Add `getBillBillingReport(patientId, claimId)` and `getBillOptimization(patientId, claimId)` to `frontend/src/lib/api/sut.ts` (alongside `:278-306`).
- [x] Extend `PatientClaimSummary` type with `recoverable_try`, `priority` (`frontend/src/lib/domains/sut.ts`).

### Phase 5 — Frontend: PatientFinancialSummary (top, all bills)
- [x] New `frontend/src/components/patient/PatientFinancialSummary.tsx`: total billed, total expected payable, total recoverable, claim/bill count, overall priority — composed from `outcome.sut_claim_totals` (`sut.ts:110-119`) + patient-level `billing-report` aggregate (`total_recoverable_try` / `sgk_uplift_try` / `priority`). No new endpoint needed.
- [x] Render as the first block under the header (before the picker). Keep the clinical/rule snapshot (`PatientOptimizationSnapshot`) but demote it under the summary.

### Phase 6 — Frontend: segmented BillPicker
- [x] Replace `ClaimSelector` dropdown with `frontend/src/components/patient/BillPicker.tsx`: one card/segment per bill showing date, `expected_total_billed_try`, claim type, and a **badge when `recoverable_try > 0`** (and priority color).
- [x] **Default-select a bill** (highest `recoverable_try`, tiebreak most recent) instead of "All bills"; keep an explicit "All bills (summary)" segment that maps to the existing patient-level report for users who want the aggregate.
- [x] Lift `selectedClaimId` to drive the per-bill data fetches (still local `useState` in `page.tsx:75-80` is fine; no Zustand needed).

### Phase 6 Review
- Created `frontend/src/components/patient/BillPicker.tsx` with segmented card UI, priority dot, recoverable badge, and `defaultSelectedClaimId` helper.
- Wired `BillPicker` into `frontend/src/app/patient/[id]/page.tsx`, replacing `ClaimSelector`.
- Default selection on load picks the bill with highest `recoverable_try` (tiebreak most recent).
- Added EN/TR i18n keys under `patient.billPicker`.
- Verified `npm run lint` (no new errors) and `npm run build` succeed.
- Fixed a pre-existing test regression in `tests/unit/db/test_patient_alert_row_columns.py` caused by missing exactness-status columns in the fixture row; full suite now `500 passed`.

### Phase 7 — Frontend: OriginalBillView (full-fidelity invoice)
- [x] New `frontend/src/components/patient/OriginalBillView.tsx` built from `getPatientClaimDetail` (`patients.py:245-346`): grouped sections for procedures, labs (`procedure_category == "laboratuvar"`), materials, drugs — each line showing **billed amount** and **SUT-expected payable** side by side, with per-group and grand totals (claim header `expected_total_billed_try` / `expected_total_payable_try`).
- [x] This is the "as submitted" bill; the per-bill optimization sections render directly under it as the "how it should have been billed".
- [x] Reuse existing `DataTable` primitive; keep `ClaimDetailPanel` logic or fold it into this view.

### Phase 8 — Frontend: wire per-bill optimization into the page
- [x] When a specific bill is selected: fetch `getBillBillingReport` + `getBillOptimization` and feed the existing billing/optimization section components (`SutBillingReportSections.tsx`) with the **bill-scoped** payload (same response shape, so components are reused as-is).
- [x] When "All bills (summary)" is selected: use the existing patient-level endpoints (current behavior).
- [x] Remove the misleading "the billing report above stays patient-level" hint (`ClaimSelector.tsx:72-75`); the report now matches the selected bill.
- [x] Lab is per-bill (Phase 0): no patient-level lab fallback in the per-bill block.

### Phase 9 — i18n
- [x] EN + TR keys for: financial summary labels, bill picker (date/amount/recoverable badge/"all bills"), original invoice group headers (procedures/labs/materials/drugs), "billed" vs "SUT-expected", per-bill scope notes. Files: `frontend/src/messages/{en,tr}/patient.ts` + `billing.ts`.
- [x] `BillingSummary` shows bill-scoped title/description when `scope === "bill"`.
- [x] Removed obsolete `claimSelector.selectedHint`; bill picker uses `patient.billPicker.*` keys.

### Phase 10 — Verify
- [x] Backend: `pytest -q` green (500 passed, 2026-06-14).
- [x] Frontend: `npx tsc --noEmit && npx vitest run` green (120 passed); fixed stale test fixtures (i18n label drift, `OptionalOverrideSection`, `hasRecoverableBillingTotals` mock).
- [ ] Manual smoke: open a **multi-bill** patient → top summary shows all-bills totals → pick a bill → original invoice + that bill's optimization (numbers differ from the all-bills total and from other bills) → "All bills" segment restores the aggregate. **Blocked on local:** dev uvicorn on `:8001` is a stale build (per-bill routes 404); restart after cache rebuild.
- [x] Exactness check: unit tests cover per-bill scoping; live API smoke pending server restart.

---

## Out of Scope
- Editing/creating claims or invoices from the UI.
- Re-architecting the chatbot/runtime context (the existing `page_context` continues to work; optional follow-up: pass `selected_claim_id`).
- Bill selection on other pages (home Patients tab, optimizer list).
- New optimization algorithms — this only re-scopes existing ones to one bill.
- Real (non-synthetic) claim ingestion.

## Definition of Done
1. `/patient/[id]` renders: (1) all-bills financial summary, (2) segmented bill picker with recoverable badges, (3) selected bill's full original invoice, (4) that bill's optimization sections — with numbers that are genuinely per-bill.
2. Selecting different bills changes the optimization numbers; "All bills" restores the aggregate.
3. New per-bill endpoints exist, are cached/served consistently, and have tests; `pytest -q` green.
4. Frontend type-check + vitest green.
5. Lab attribution handled honestly per the Phase 0 decision (never an all-bills number mislabeled as one bill).

---

## Key file references (verified)
- Page: `frontend/src/app/patient/[id]/page.tsx:75-80, 311-460`
- Bill picker (current): `frontend/src/components/patient/ClaimSelector.tsx`
- Billing sections (reused per-bill): `frontend/src/components/patient/SutBillingReportSections.tsx`
- Claim detail (original invoice source): `frontend/src/components/patient/ClaimDetailPanel.tsx`; `src/bilun/api/routes/patients.py:245-346`
- Claim model / scoping: `src/bilun/domain/claims/models.py:24-42`; `src/bilun/domain/claims/patient_context.py:21-76`
- Billing serve (cache pattern to mirror): `src/bilun/api/routes/billing.py:105-169`
- Optimization (live compute to reuse): `src/bilun/api/routes/optimization.py:105-215`
- Lab attribution constraint: `src/bilun/domain/billing/orchestrator.py:463-485`; `src/bilun/domain/billing/lab.py:185-206`
- Claims list schema to extend: `src/bilun/api/schemas.py:551-567`
- Patient totals (summary source): `frontend/src/lib/domains/sut.ts:110-119`
