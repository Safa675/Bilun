# PR #87 Claim Compliance Correctness Fixes Implementation Plan

> **For the implementer:** Execute this plan on `feat/compliance-k21-k26` with tests first. Do not merge PR #87 until every merge gate at the end is verified.

**Goal:** Make PR #87 safe to merge by removing K21/K26 false positives, bounding cohort evaluation data, and ensuring claim-compliance findings remain discoverable beyond the current cross-surface 5,000-row window.

**Architecture:** Keep the patient/bill `claim_compliance` projection nonfinancial and separate from `recommended_actions`. Correct the two detector inputs at the domain boundary, compact cohort evaluation data before serialization, and use the existing `surface`/pagination API parameters instead of downloading a mixed first page and filtering it in the browser.

**Tech stack:** Python 3.13, dataclasses, Polars, FastAPI, pytest, React 19, Next.js 16, TypeScript, Vitest.

**PR head reviewed:** `96ee910972d0af339b13f00c3e03e8799d90b711`

---

## Why this plan blocks merge

The original PR successfully wires two previously unreachable checks into patient reports, the cohort cache/API, and the compliance UI:

- **K21 / `icu_bundled_leakage_510090`:** a service included in ICU day-rate `510090` was billed separately.
- **K26 / `tablo15_8_missing_diagnosis`:** a claim has no primary diagnosis.

The review reproduced two user-visible false positives:

1. K21 reports a bundled service from a different date merely because it shares the same multi-day claim with a `510090` line.
2. K26 reports “missing diagnosis” when `ClaimHeader.primary_icd10` is blank but the normalized `ClaimDiagnosis` feed contains a valid primary diagnosis.

The review also found that cohort pagination does not bound evaluation records and that the frontend can hide K21/K26 findings behind 5,000 earlier findings from other surfaces.

These are correctness and reachability failures, not stylistic requests.

---

## Locked product decisions

1. **K21 is same-day, not merely same-claim.** A bundled service is a violation only when its `procedure_date` equals the date of a `510090` line in the same claim.
2. **K26 tests diagnosis presence, not diagnosis-source consistency.** A nonblank primary diagnosis from either the header or normalized `ClaimDiagnosis` rows prevents a missing-diagnosis finding.
3. **Conflicting nonblank diagnosis codes are not K26.** They may deserve a future data-consistency rule, but they are not “missing diagnosis.”
4. **Preserve current unknown-input honesty.** Explicit blank header input with no normalized primary diagnosis is an evaluated violation. Omitted/null/NaN header input with no normalized primary diagnosis remains `missing_inputs` unless source-provenance support is deliberately expanded in a separately reviewed change.
5. **Patient/bill reports may retain complete local evaluations.** Cohort cache/API responses must not serialize every evaluated claim identity on every page.
6. **Claim-compliance findings remain nonfinancial.** They must not enter `recommended_actions`, SGK uplift, billed-at-risk, recovery, or audit monetary totals.
7. **Old caches remain honest.** Absence of the new projection must render unavailable/unknown, never a clean zero.
8. **No broad compliance redesign.** Fix only the reviewed K21/K26 reporting path and the minimum pagination/contract work required to make it correct.

---

## Task 1: Enforce same-day semantics for K21

**Objective:** Prevent valid services on other days of a multi-day claim from being reported as bundled into a `510090` ICU day.

**Files:**

- Modify: `src/bilun/domain/prose_rules/icu_bundled_leakage.py`
- Test: `tests/unit/domain/prose_rules/test_icu_bundled_leakage.py`
- Test: `tests/unit/domain/billing/test_claim_compliance.py`

### Step 1: Write the failing detector regression

Add a test with one inpatient claim containing:

- `510090` on `2026-01-01`;
- bundled code `530360` or `530130` on `2026-01-03`.

Expected result: no K21 violation.

Run:

```bash
PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' \
  tests/unit/domain/prose_rules/test_icu_bundled_leakage.py \
  -k different_day -q
```

Expected before the fix: FAIL because the detector emits a violation.

### Step 2: Replace the PR regression that currently codifies the bug

In `tests/unit/domain/billing/test_claim_compliance.py`, split the existing `test_multiple_claims_lines_same_claim_not_same_day_and_once_per_report` coverage into explicit cases:

- same claim + same date → finding;
- same claim + different date → no finding;
- other claim → no leak between claims;
- reordered inputs → stable output;
- duplicate line → stable deduplication.

Do not retain a test that expects a different-day service to be a violation.

### Step 3: Implement the minimal detector correction

Within each eligible inpatient claim:

1. collect the set of `procedure_date` values carried by normalized `510090` lines;
2. inspect candidate bundled-service lines only when `line.procedure_date` is in that set;
3. preserve code normalization, keyword fallback, `P552001-P552009` exclusion, line identity, and existing deduplication;
4. update the violation detail to say the service occurred on the same date, not merely the same claim.

Do not move this date join into the UI or cache layer; correctness belongs in the domain detector.

### Step 4: Verify positive and negative behavior

Run:

```bash
PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' \
  tests/unit/domain/prose_rules/test_icu_bundled_leakage.py \
  tests/unit/domain/billing/test_claim_compliance.py -q
```

Expected: all tests pass, including same-day positives and different-day negatives.

---

## Task 2: Resolve K26 diagnosis presence from both normalized sources

**Objective:** Do not report a missing diagnosis when either the header or a linked normalized primary diagnosis row contains a valid ICD-10 code.

**Files:**

- Modify: `src/bilun/domain/billing/claim_compliance.py`
- Modify only if needed for provenance: `src/bilun/domain/claims/models.py`
- Modify only if needed for ingestion provenance: `src/bilun/domain/claims/parsing/row_parsers.py`
- Test: `tests/unit/domain/billing/test_claim_compliance.py`
- Test: `tests/unit/api/test_claim_compliance_pipeline.py`

### Step 1: Add failing tests for source reconciliation

Add tests covering at least:

| Header value | `primary_icd10_available` | Normalized primary diagnosis | Expected K26 result |
|---|---:|---|---|
| blank | true | `J96.0` | evaluated, no finding |
| omitted/null | false | `J96.0` | evaluated, no finding |
| `J96.0` | false (legacy/direct constructor) | none | evaluated, no finding |
| blank | true | none | evaluated, finding |
| omitted/null | false | none | `missing_inputs`, no finding |
| `J96.0` | true/false | conflicting nonblank primary row | evaluated, no missing-diagnosis finding |
| blank | true | secondary-only diagnosis row | preserve the explicitly defined primary-diagnosis behavior |

The first case must reproduce the reviewed failure before implementation.

### Step 2: Build a claim-scoped primary-diagnosis index

Inside the report-owned projection, index `ctx.diagnoses` by `claim_id`, considering only rows that:

- belong to the report patient and a context claim;
- are primary according to the typed diagnosis contract;
- carry a nonblank `icd10_code`.

The existing patient/claim scope guards must remain active.

### Step 3: Resolve effective diagnosis presence deterministically

For each claim:

1. treat a nonblank `ClaimHeader.primary_icd10` as present even if a legacy/direct constructor left `primary_icd10_available=False`;
2. otherwise, treat any valid normalized primary diagnosis for the claim as present;
3. when neither source is nonblank, preserve the explicit-blank versus unavailable distinction described in the locked decisions;
4. pass an effective claim representation to the existing missing-diagnosis detector or adapt its interface narrowly—do not duplicate the rule in the frontend.

If multiple nonblank primary rows exist, K26 only needs a deterministic presence decision. Do not introduce diagnosis-conflict adjudication into this PR.

### Step 4: Verify patient, bill, and API paths

Run:

```bash
PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' \
  tests/unit/domain/billing/test_claim_compliance.py \
  tests/unit/api/test_claim_compliance_pipeline.py -q
```

Expected: all source-reconciliation cases pass and no patient/claim scope leakage occurs.

---

## Task 3: Compact cohort evaluation data before serialization

**Objective:** Preserve honest coverage counts without attaching every evaluated patient/claim identity to every paginated response.

**Files:**

- Modify: `src/bilun/domain/billing/cohort_compliance.py`
- Modify if response assembly requires it: `src/bilun/api/routes/compliance.py`
- Test: `tests/unit/domain/billing/test_cohort_compliance.py`
- Test: `tests/unit/api/test_claim_compliance_pipeline.py`
- Modify types: `frontend/src/lib/domains/sut.ts`
- Modify rendering: `frontend/src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx`
- Test: `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`

### Step 1: Lock a compact response contract with failing tests

The cohort `claim_compliance` block must provide:

- exact counts for `evaluated`, `missing_inputs`, and `unavailable`;
- exact total number of non-evaluated records;
- a bounded detail list for non-evaluated records;
- an explicit truncation indicator when more details exist;
- no unbounded list of successful evaluated claim identities.

The existing regression in `test_claim_compliance_pipeline.py` that expects every two-row page to contain all evaluation rows must be replaced. A request with a small findings limit must return correct counts but only bounded evaluation details.

### Step 2: Use a scalable cache representation

Recommended representation:

- aggregate evaluation counts per patient and rule/status;
- retain only bounded non-evaluated details needed by the UI;
- preserve full evaluations only inside each patient/bill report.

The implementation may choose an equivalent structure, but it must satisfy these invariants:

1. serialized cohort evaluation data does not grow with every successful claim evaluation;
2. arbitrary supported patient filters still produce correct aggregate counts;
3. API response detail size is bounded independently of total cohort claims;
4. old-cache `claim_compliance: null` behavior remains unchanged.

### Step 3: Update frontend types and rendering

Replace the assumption that cohort responses always contain `evaluations: ClaimComplianceEvaluation[]` with the compact contract. Continue to show:

- evaluated count;
- missing-input count;
- unavailable count;
- at most the bounded non-evaluated details;
- honest “more details omitted”/truncated messaging.

Patient/bill report rendering may continue using complete local `ClaimCompliance.evaluations`.

### Step 4: Add scale regressions

Add a cohort with many claims/patients and assert:

- counts remain exact;
- serialized detail length remains at or below the declared cap;
- clean evaluated claim IDs are not all present in the response;
- patient filtering recalculates counts correctly;
- no monetary fields or totals change.

---

## Task 4: Give claim-compliance its own server-side pagination path

**Objective:** Ensure K21/K26 findings cannot disappear because 5,000 earlier findings from materials, lab, drug, or payment-method surfaces consumed the mixed page.

**Files:**

- Modify: `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx`
- Modify if needed: `frontend/src/lib/api/sut.ts`
- Modify if pagination UI is shared: `frontend/src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx`
- Test: `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`
- Test backend behavior if changed: `tests/unit/api/test_claim_compliance_pipeline.py`

### Step 1: Add the failing >5,000 mixed-surface regression

Construct/mock an index where more than 5,000 non-claim findings precede K21/K26 rows.

Expected behavior:

- the claim-compliance tab queries `surface=claim_compliance`;
- its first page contains claim-compliance rows;
- total and `has_more` refer to that surface;
- badges/counts do not derive from the length of a truncated mixed `rows` array.

### Step 2: Use the existing API parameters

`getComplianceIndex()` already accepts:

- `surface`;
- `patientId`;
- `limit`;
- `offset`.

Fetch the active index surface independently and paginate it. Do not fetch a single mixed `limit=5000` page and then filter it client-side.

Use server-provided summaries (`n_findings`, `n_patients_with_findings`, and `by_surface`) for counts rather than treating loaded row count as the total. When a cohort filter is active, pass the supported patient filter to the server and verify URL/request-size assumptions with a representative cohort.

### Step 3: Add reachable pagination controls

The UI must provide a way to reach subsequent pages when `pagination.has_more` is true. A warning that results are partial is insufficient if users cannot navigate to the omitted findings.

At minimum, verify:

- next/previous page behavior;
- active surface retained in the query;
- active cohort filter retained;
- loading/error/old-cache states remain honest;
- badge and KPI values remain total counts, not current-page counts.

---

## Task 5: Correct the nullable frontend monetary contract

**Objective:** Make the TypeScript contract match the backend’s deliberate `null` monetary value for nonfinancial claim-compliance findings.

**Files:**

- Modify: `frontend/src/lib/domains/sut.ts`
- Test relevant formatting/rendering in: `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`

Change:

```ts
billed_try: number;
```

to:

```ts
billed_try: number | null;
```

for `ComplianceIndexSurfaceSummary`, or narrow the type equivalently without lying about runtime data.

Verify claim-compliance renders `—` and is never added to monetary totals.

---

## Task 6: Regression verification and evidence

**Objective:** Prove correctness across domain, API, frontend, and existing financial behavior before requesting merge.

### Focused backend tests

```bash
PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' \
  tests/unit/domain/prose_rules/test_icu_bundled_leakage.py \
  tests/unit/domain/billing/test_claim_compliance.py \
  tests/unit/domain/billing/test_cohort_compliance.py \
  tests/unit/api/test_claim_compliance_pipeline.py \
  tests/unit/domain/test_loaders.py -q
```

### Backend lint

```bash
/opt/Bilun/.venv/bin/python -m ruff check \
  src/bilun/domain/prose_rules/icu_bundled_leakage.py \
  src/bilun/domain/billing/claim_compliance.py \
  src/bilun/domain/billing/cohort_compliance.py \
  src/bilun/api/routes/compliance.py \
  tests/unit/domain/prose_rules/test_icu_bundled_leakage.py \
  tests/unit/domain/billing/test_claim_compliance.py \
  tests/unit/domain/billing/test_cohort_compliance.py \
  tests/unit/api/test_claim_compliance_pipeline.py
```

### Focused frontend tests

Run from `frontend/`:

```bash
npx --no-install vitest run \
  src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx \
  src/lib/workspaceViews.test.ts
npx --no-install tsc --noEmit
```

Run ESLint on every changed frontend file. The pre-existing `react-hooks/set-state-in-effect` finding in `PatientWorkspaceViews.tsx` is baseline debt, not permission to introduce new lint failures.

### Full regression suites

```bash
PYTHONPATH=. /opt/Bilun/.venv/bin/python -m pytest -o addopts='' tests/unit -q
cd frontend
npx --no-install vitest run
```

If the full suite cannot complete, report the measured stopping point and blocker; do not substitute focused tests for a claimed full pass.

### Final hygiene

```bash
git diff --check origin/main...HEAD
git status --short --branch
```

Update `tasks/k21-k26-result.md` with commands actually run and their real outcomes. Do not record planned commands as passed.

---

## Required merge gates

PR #87 may be recommended for merge only when all are true:

- [ ] Different-day K21 reproduction emits no finding.
- [ ] Same-day K21 positive still emits exactly the expected finding(s).
- [ ] A valid normalized primary diagnosis prevents K26 even when the header is blank/omitted.
- [ ] A valid legacy/direct header diagnosis prevents K26 even when the availability flag defaults false.
- [ ] Explicit blank diagnosis with no normalized primary diagnosis emits K26.
- [ ] Unknown diagnosis provenance remains `missing_inputs`, not a clean pass.
- [ ] Cohort responses expose exact evaluation counts with bounded details.
- [ ] Successful evaluated claim identities are not serialized without bound.
- [ ] Claim-compliance findings remain reachable beyond 5,000 earlier findings on other surfaces.
- [ ] Claim-compliance pagination can reach every page.
- [ ] Nonfinancial findings do not change any legacy monetary total.
- [ ] Old-cache behavior remains unavailable/unknown rather than zero/clean.
- [ ] Focused backend tests, Ruff, frontend tests, TypeScript, and changed-file ESLint pass relative to baseline.
- [ ] Full backend and frontend test suites pass, or any inability to run them is explicitly reviewed before merge.
- [ ] A fresh independent review finds no remaining correctness blocker.

---

## Recommended implementation commits

Keep the plan commit separate. Add implementation in reviewable commits such as:

1. `fix(compliance): enforce same-day K21 findings`
2. `fix(compliance): reconcile K26 diagnosis sources`
3. `fix(compliance): bound cohort evaluation payloads`
4. `fix(frontend): paginate claim-compliance findings`
5. `test(compliance): close PR87 regression matrix`

Do not amend or force-push the existing PR commits. The PR can be squash-merged after all gates pass.

---

## Non-goals

- Adding more SUT detectors.
- Converting claim-compliance findings into monetary opportunities.
- Redesigning every compliance subtab.
- Resolving conflicting diagnosis codes beyond determining that a diagnosis exists.
- Changing unrelated workspace navigation or existing lint debt.
- Rebuilding or deploying production caches before the corrected code is reviewed and merged.
