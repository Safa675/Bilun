# K21 + K26 implementation evidence

## Reviewer follow-up — 2026-09-17

Only the two blockers and cheap old-cache badge fix were changed in this pass.
- Full schema inference at `src/bilun/domain/billing/cohort_compliance.py:189` handles late money and other late non-null fields. Regression at `tests/unit/domain/billing/test_cohort_compliance.py:115` builds 101 null-money findings before a legacy 123.45 TRY row, checks build and slice, unchanged legacy row/surface/aggregate, and all eight new-row money fields null. Before the fix it failed with Polars ComputeError (the first reported late field was `sut_section_id`); afterward it passed.
- Scoped presentation selector at `frontend/src/lib/workspaceViews.ts:58` is shared by rendered findings and tab count. KPI at `frontend/src/components/patient/views/ComplianceViewSection.tsx:66` and badge at `frontend/src/components/patient/views/PatientWorkspaceViews.tsx:56` now include only the scoped projection findings. Rendered tests assert patient count 4, claim count 3, legacy-only count 1; foreign-patient exclusion, unchanged legacy actions, 123.45 billed risk, 23 uplift and unchanged report payload.
- Dashboard badge guard at `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx:172` omits the count key when the old cache lacks the projection. Regression checks the actual strip props have no claim-compliance key, no rendered badge, preserved legacy count 1, and new-cache count 2.

### Commands and actual outcomes
All commands used this worktree (frontend commands from `frontend/`); the existing Python environment was used only as a runtime.
- Red regression: `PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' tests/unit/domain/billing/test_cohort_compliance.py -q` — 1 failed (new ordering regression), 6 passed before fix.
- Green regression: `PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' tests/unit/domain/billing/test_cohort_compliance.py::test_late_legacy_money_after_more_than_100_null_findings -q` — 1 passed (also rerun successfully).
- Focused backend: `PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' tests/unit/domain/billing/test_cohort_compliance.py tests/unit/domain/billing/test_claim_compliance.py tests/unit/api/test_claim_compliance_pipeline.py -q` — **46 passed**, 14.81s; one Starlette TestClient deprecation warning.
- Frontend baseline: `npx --no-install vitest run src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx` — 10 passed.
- Final frontend: `npx --no-install vitest run src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/lib/workspaceViews.test.ts` — **18 passed**, 6.34s.
- `npx --no-install tsc --noEmit` — passed on final code/tests (earlier `npx tsc --noEmit` also passed).
- `npx --no-install eslint src/components/patient/views/ComplianceViewSection.tsx src/components/patient/views/PatientWorkspaceViews.tsx src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/lib/workspaceViews.ts` — one error only: existing `react-hooks/set-state-in-effect` at `PatientWorkspaceViews.tsx:77`.
- Baseline proof: `git show HEAD:frontend/src/components/patient/views/PatientWorkspaceViews.tsx | npx --no-install eslint --stdin --stdin-filename src/components/patient/views/PatientWorkspaceViews.tsx` — same error at HEAD line 75. Navigation effect left untouched, not suppressed.
- `npx --no-install eslint src/components/patient/views/ComplianceViewSection.tsx src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/lib/workspaceViews.ts` — passed.
- `/opt/Bilun/.venv/bin/python -m ruff check src/bilun/domain/billing/cohort_compliance.py tests/unit/domain/billing/test_cohort_compliance.py` — passed.
- Mistaken `npx vitest run tests/unit/domain/billing` — no test files, exit 1; Python tests were then run with pytest as recorded above.
- `git diff --check` — passed; final status showed no catalog/generated-data drift relative to session-start paths. Additional modified files this pass: `PatientWorkspaceViews.tsx` and `test_cohort_compliance.py`; remaining edits are within existing scoped files/tracking.

Pagination and its >5000 warning remain unchanged. No commit, push, service operation, cache rebuild, or other-worktree edits. No browser/full-suite claim. Full requested changed-file ESLint is not green solely due to the empirically confirmed HEAD navigation-effect error above.

## Outcome
Coverage: **2/2 selected detectors connected**, not coverage of all rules. Existing diff remains on `feat/compliance-k21-k26` for Chief. No commit/push/deploy/live-cache work.

## Ownership and provenance
`patient_report.py` owns one narrow `claim_compliance` projection; the validator engine remains separate. Existing detector functions and their legal semantics are unchanged. The projection never enters financial action collection or report totals.

Normal `SUTClaimDataset.from_rows` parsing/context tests cover ICU/bundled positives, no-leak and P55200x negatives, multiple claims/lines, stable identity/dedup and wrapped-real detector calls once per patient/bill report scope. K26 availability distinguishes explicit blank/whitespace strings from omitted/null/NaN inputs; legacy constructors default to unknown. Unknown care setting and missing procedure context are not evaluated passes; invalid dates are rejected by ingestion. K21 retains its existing same-claim (not date-matching) semantics.

Temporary DuckDB writers/readers and isolated FastAPI TestClient verify patient/bill reports, compliance index, filtering/pagination, patient scope, null money and legacy financial invariants. Frontend rendered tests verify both findings, native group filtering, patient/claim drill-through and missing/old-cache honesty.

## Verification
- Chief independently reported **71 backend tests**, **9 frontend tests**, typecheck and changed-file lint passing before the final compact-summary change. Exact Chief commands were not supplied.
- `/opt/Bilun/.venv/bin/python -m ruff check tests/unit/api/test_claim_compliance_pipeline.py`: passed after removing unused `copy.deepcopy`.
- `PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' tests/unit/api/test_claim_compliance_pipeline.py -q`: **4 passed**, one TestClient deprecation warning (prior finish).
- Final frontend cwd: `frontend/`.
- `npx --no-install vitest run src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx -t compact`: **1 passed, 9 skipped**.
- `npx --no-install vitest run src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`: **10 passed**, 3.47s.
- `npx --no-install eslint src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx`: passed.
- Final regression uses 120 evaluations: 80 evaluated, 20 missing-input, 20 unavailable; correct summary, closed details with only 20 entries, unknown empty state distinct from evaluated empty state, findings/links/null money retained.

## Files in scoped diff
Backend:
- `src/bilun/domain/claims/models.py`
- `src/bilun/domain/claims/parsing/row_parsers.py`
- `src/bilun/domain/billing/types.py`
- `src/bilun/domain/billing/patient_report.py`
- `src/bilun/domain/billing/claim_compliance.py`
- `src/bilun/domain/billing/cohort_compliance.py`
- `tests/unit/domain/billing/test_claim_compliance.py`
- `tests/unit/api/test_claim_compliance_pipeline.py`

Frontend:
- `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx`
- `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`
- `frontend/src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx`
- `frontend/src/lib/domains/sut.ts`
- `frontend/src/lib/recommendedActions.ts`
- `frontend/src/lib/workspaceSubtabs.ts`
- `frontend/src/lib/workspaceViews.ts`
- `frontend/src/messages/en/optimizer.ts`
- `frontend/src/messages/tr/optimizer.ts`

Tracking: `tasks/todo.md`, `tasks/lessons.md`, `tasks/k21-k26-result.md`.

## Limitations
No browser test, production startup, full cache rebuild or whole-suite claim. Typecheck was reported passing before the last UI change; only the requested Vitest file and two-file ESLint were rerun in the final finish. Chief reports three unrelated existing broad frontend lint set-state-in-effect errors in unchanged CopayExemptionCompliance/CopayRateCompliance/SurchargeCompliance; not modified. Existing first-5,000 finding pagination is explicitly labeled partial. Evaluation details intentionally show only the first 20 non-evaluated entries. Prior diff/status inspection found no catalog/generated-data changes; no broad final rescan was run per the narrow finish instruction.
