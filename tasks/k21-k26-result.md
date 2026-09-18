# PR87 claim-compliance correctness fixes — final evidence

Date: 2026-09-18
Branch: `feat/compliance-k21-k26`
Plan/base commit: `58f3308a477efda747e9dde031fe29a9e6c07846` (`docs(plan): define PR87 compliance correctness fixes`)

## Implemented behavior

- **K21 / `icu_bundled_leakage_510090`:** bundled-service findings now require the service `procedure_date` to equal a `510090` date on the same eligible inpatient claim. Different-day services on the same multi-day claim no longer produce a K21 finding; same-day positives, code normalization, keyword fallback, P55200x exclusion, identity, and dedup behavior remain covered.
- **K26 / `tablo15_8_missing_diagnosis`:** diagnosis presence is reconciled from a nonblank `ClaimHeader.primary_icd10` or a linked normalized primary `ClaimDiagnosis` row. A nonblank legacy/direct header wins even when `primary_icd10_available=False`. Explicit blank header input with no normalized primary is an evaluated violation; omitted/null/NaN provenance with no normalized primary remains `missing_inputs`.
- **Cohort evaluation payload:** cache data stores exact per-patient status counts plus at most 20 non-evaluated details. Successful evaluated claim identities are not persisted or serialized without bound. API responses expose exact filtered counts, exact non-evaluated totals, bounded details, and `details_truncated`.
- **Rolling-deploy compatibility:** compact API responses also carry `evaluations: []`. This keeps the pre-change frontend from crashing during backend-first deployment without reintroducing successful evaluation identities.
- **Reachability/pagination:** active compliance surfaces are fetched independently with server-side `surface`, `patient_id`, `limit`, and `offset`; the table has reachable previous/next controls. KPIs and badges use server summaries rather than current-page row counts.
- **Large cohort transport:** `getComplianceIndex()` uses GET for normal requests and switches to a JSON POST when the encoded query exceeds 6,000 characters. Measured representative query sizes were about 1,593 bytes (50 IDs), 2,043 (100), 5,043 (250), 10,043 (500), and 20,043 (1,000).
- **Nonfinancial contract:** claim-compliance `billed_try` is nullable in TypeScript and renders as `—`; the projection remains outside recommended actions and legacy monetary totals.
- **Old cache behavior:** missing projection data remains unavailable/unknown rather than a clean zero. Legacy caches containing `evaluations` are still read and compacted by the new API path.

## Independent-review follow-ups

Two review findings were fixed before the final gate:

1. **P2 stale aggregate summary after cohort changes.** The dashboard could briefly pair a new surface request with the previous cohort's aggregate KPIs/badges. Aggregate results are now keyed to the cohort request and stale summaries are hidden while the new request is pending. Regression: `selectCurrentComplianceIndex()` rejects a mismatched request key.
2. **P1 rolling-deploy compatibility.** An already-open old frontend calls `claim_compliance.evaluations.filter(...)`; dropping the field entirely would crash while the backend is restarted before the frontend. API summaries now return a bounded compatibility field `evaluations: []`.

The final fresh `codex review --uncommitted` returned **0 findings**, `overall_correctness: "patch is correct"`, confidence **0.91**. Its read-only sandbox could not rerun pytest because no writable temporary directory was available; the writable-workspace runs below are the execution evidence.

## Verification on the final tree

Backend:

- Focused: `PYTHONPATH=. .venv/bin/python -m pytest -o addopts='' tests/unit/domain/prose_rules/test_icu_bundled_leakage.py tests/unit/domain/billing/test_claim_compliance.py tests/unit/domain/billing/test_cohort_compliance.py tests/unit/api/test_claim_compliance_pipeline.py tests/unit/domain/test_loaders.py -q` → **84 passed**, 1 warning.
- Full: `PYTHONPATH=. .venv/bin/python -m pytest -o addopts='' tests/unit -q` → **2631 passed**, 3 warnings, 190.84s.
- Ruff on all changed backend/test files via `/home/safa/miniforge3/bin/ruff check ...` → **passed**.

Frontend (run from `frontend/`):

- Focused: `npx --no-install vitest run src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/lib/workspaceViews.test.ts src/lib/api/sut.complianceIndex.test.ts` → **3 files, 22 tests passed**.
- Full: `npx --no-install vitest run` → **51 files, 266 tests passed**.
- `npx --no-install tsc --noEmit` → **passed**.
- ESLint on every changed frontend source/test/message file → **passed**.

Hygiene:

- `git diff --check` → **passed** before this evidence-only documentation update and is rerun at final handoff.
- Test runs produced no unexpected catalog/generated-data drift; final status is limited to the scoped source/tests/tracking files plus the new compliance API test.
- No production cache rebuild, deploy, service operation, merge, push, commit, or other-worktree edit was performed.

## Merge-gate result

All correctness gates in `plans/billing/2026-09-18-pr87-claim-compliance-fixes-plan.md` are covered by the implementation, tests, static checks, full backend/frontend suites, and the final independent review. Production cache rebuild/deploy remains intentionally out of scope for this implementation pass.
