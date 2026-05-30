## Task: Patient invoices table recovery columns

### Goal
All cohort patients show Recoverable, Priority, Actions, and Top action in PatientInvoiceTable — not only top-10 from revenue recovery.

### Subtasks
- [x] Add `patient_summaries` to `CohortRecoverySummary` (all patients, sorted by recoverable)
- [x] Populate in billing orchestrator; keep `top_patients` as first 10
- [x] API fallback: hydrate `patient_summaries` from `patient_billing_report_rows` for old caches
- [x] Update frontend types + `PatientInvoiceTable` to merge `patient_summaries`
- [x] Unit test + verify frontend tsc

### Out of Scope
- Changing billing algorithm outputs
- New dedicated bulk billing API endpoint (reuse revenue-recovery payload)

### Review
- Root cause: table joined only `revenue_recovery.top_patients` (hard cap 10); page 1 patients outside top 10 showed `—`.
- Fix: full `patient_summaries` on cohort summary + API hydration from `patient_billing_report_rows` for existing builds.
- No cache rebuild required for hydration path; rebuild still recommended to persist field in `cohort_recovery_summary`.
