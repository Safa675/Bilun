# Source-authority transport verification

Transport work is implemented in `bilun-sut-date-authority`. The frozen original was read for comparisons/dependency copying and was not edited.

## Scope

- Strict bounded optional provenance is carried through nested clinical restrictions and top-level mecasermin canonical results, cache normalization, frozen public projection, HTTP/V2, recommended actions and cohort rows.
- Detailed mecasermin propagation in `evaluation.py` is copy-only; no predicate, ordering or financial behavior was changed.
- UI distinguishes source observation, legal effective date, admission window and official review time. Blocked-source metadata displays its next action. Legacy absence and non-mecasermin GH produce no new guarantee.
- The source model and resolver remain parent-owned. Source-authority metadata is validated before allowlist selection, so extra/raw/patient fields invalidate the object rather than becoming trusted after stripping.

## Verified gates

- Combined backend transport/security/canonical/action/cohort/API/V2/GH-observation selection: **251 passed, 3 warnings** in 7.12 seconds on the final settled source tree. This includes all 52 source-authority transport tests, including six strict-Literal regression variants.
- Focused source-authority plus existing action/cohort suites: **78 passed, 1 warning** before the final non-mecasermin regression was added.
- Frontend clinical details + claim validator + input form + V2 contract: **40 passed** in four files.
- TypeScript `tsc --noEmit`: passed.
- Changed frontend-file ESLint: passed.
- Changed backend-file Ruff: passed.
- Python compileall over changed initial transport modules: passed.
- The tests exercise canonical dataclass serialization and DuckDB JSON cache storage, admitted/missing/stale metadata, direct strict model schemas, hostile cache/public reinjection, actual V2 HTTP serialization, real mecasermin leaf-to-HTTP on October 2/3/4 and missing date, and unchanged non-mecasermin GH observations.

## Verification recovery and limits

The parent-owned source schema now rejects Pydantic Literal coercion of `schema_version=True`, `schema_version=1.0`, and `clinical_eligibility_complete=0`. The six corresponding nested/top-level regression cases pass. The stronger historical-coherence validator also required correcting the synthetic continuity fixture so its admission does not begin before observation; the real source assertions were retained unchanged.

Temporary-filesystem exhaustion initially blocked test collection and exec sandbox startup. The parent removed only its independently identified disposable test directory, restoring capacity. The final tests ran with a workspace `TMPDIR` and `NODE_COMPILE_CACHE`. One intermediate frontend attempt used the wrong working directory for an existing fixture-relative test; the final correct-cwd 40-test run passed. One intermediate backend run intersected the parent's source-catalog/schema updates; the final settled-tree 251-test run passed. These recovered attempts are not outstanding code failures.

Only three known disposable edit scripts created by this worker were removed from `/tmp`; no other worker test artifacts were deleted. A copied (not linked) `frontend/node_modules` and `.tmp-verification` were used only for verification and are not source deliverables. Full-suite and production-build verification remain parent-owned. No remaining transport-specific blocker.

## Source deliverables changed by this worker

- `src/bilun/domain/billing/drug_clinical_evidence.py`
- `src/bilun/domain/billing/drug_indication_findings.py`
- `src/bilun/domain/billing/billing_actions.py`
- `src/bilun/domain/billing/cohort_compliance.py`
- `src/bilun/domain/claim_validation_v2.py`
- `src/bilun/domain/validation_contract.py`
- `src/bilun/domain/prose_rules/_drug_indication/evaluation.py`
- `src/bilun/api/schemas.py`
- `src/bilun/api/public_responses.py`
- `src/bilun/api/public_contracts.json`
- `frontend/src/lib/api/clinicalEvidence.ts`
- `frontend/src/lib/api/sut.ts`
- `frontend/src/components/tabs/sut/sections/ClinicalRestrictionDetails.tsx`
- `frontend/src/components/tabs/sut/sections/ClinicalRestrictionDetails.test.tsx`
- `frontend/src/components/tabs/sut/sections/ClaimValidatorSection.tsx`
- `frontend/src/messages/en/sections.ts`
- `frontend/src/messages/tr/sections.ts`
- `tests/unit/domain/test_source_authority_transport.py`
- `docs/sut/source-authority-transport.md`
- `tasks/todo.md` (worker subtask appended; parent plan retained)
- This verification report.

## Focused rerun commands

From the repository root, use `../bilun-py313/bin/python -m pytest` with:

`tests/unit/domain/test_source_authority_transport.py tests/unit/domain/test_clinical_public_security.py tests/unit/domain/billing/test_drug_indication_findings.py tests/unit/domain/billing/test_billing_actions.py tests/unit/domain/billing/test_cohort_compliance.py tests/unit/api/test_patient_billing_drug_indication_api.py tests/unit/api/test_validation_contract_v2.py tests/unit/domain/prose_rules/test_gh_runtime_callers.py tests/unit/domain/prose_rules/test_gh_runtime_observations.py tests/unit/domain/prose_rules/test_gh_extended_runtime_observations.py -q --disable-warnings`

From `frontend/`, use `./node_modules/.bin/vitest run` with:

`src/components/tabs/sut/sections/ClinicalRestrictionDetails.test.tsx src/components/tabs/sut/sections/ClaimValidatorSection.test.tsx src/components/tabs/sut/sections/ClaimValidatorSection.inputs.test.tsx src/lib/api/sut.validationContract.test.ts`

If `/tmp` remains full, point `TMPDIR` and `NODE_COMPILE_CACHE` to the writable verification directory after runner startup is restored.
