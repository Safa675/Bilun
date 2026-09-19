# Rule Engine Surfacing — Phase B Migration Scope Proposal

Date: 2026-09-19
Status: **accepted by Chief for bounded Phase 5 implementation**
Accepted checkpoint: `5122d63472fcc8eb7182e7d45d3daf14c24c7a67`
Audited source revision: `4c9c9d92595959dc12382a3130c6b400fd56c52c`

This document locks the accepted first-wave scope. Acceptance authorizes only the bounded checkpoints listed below; it does not authorize pricing changes, deployment, cache rebuild, push, merge, or migration beyond the selected slice.

## Decision

The first Wave A vertical slice should contain exactly three existing **Tablo 15 line-integrity detectors**:

| Canonical runtime detector | Stable emitted rule ID | Canonical line identity | Severity today |
| --- | --- | --- | --- |
| `src.bilun.domain.prose_rules.common_billing_errors.detect_unreported_lab_result` | `tablo15_10_unreported_lab_result` | `procedure_line_id` | warning |
| `src.bilun.domain.prose_rules.common_billing_errors.detect_missing_drug_barcode` | `tablo15_20_missing_drug_barcode` | `drug_claim_line_id` | error |
| `src.bilun.domain.prose_rules.common_billing_errors.detect_material_identity_errors` | `tablo15_5_material_identity_error` | `material_line_id` | error |

All three satisfy the accepted Wave A filters directly from the matrix: each is `hidden_runtime`, `unpriced_compliance`, excluded from totals, has no money fields, requires only data already present in the canonical claim context, and emits a real rule ID rather than a synthetic `kind:<callable>` identity. The accepted matrix records those facts at `2026-09-18-rule-surfacing-matrix.json:4861-4899`, `:5024-5062`, and `:5472-5510`.

The slice is deliberately three detectors rather than one because it proves the generic architecture across all three line namespaces already used by the claim model—procedure, drug, and material—without introducing a broad prose-rule family. Their current detector outputs already carry `claim_id` plus the corresponding real line identifier in `common_billing_errors.py:407-457`, `:588-648`, and `:759-809`. Their current canonical analyzer calls are in `engine.py:322-325`, `:349-353`, and `:367-372`.

The accepted audit reports 50 runtime rows matching the first two Wave A filters. Applying the remaining objective gates removes synthetic callable identities and every analyzer row already covered by a verified independent adapter/rerun relationship. The accepted audit records 12 rerun relationships covering 1,291 semantic IDs/kinds and explicitly separates that debt from product-surface duplication (`2026-09-18-rule-surfacing-audit.md:145-165`).

## Explicit exclusions

The first slice must not include any of the following:

- **Verified independently re-run visible equivalents.** Exclude bundling; material bundling, specialty materials, material preauthorization, and material MIAT; ICU bundled leakage (K21); missing diagnosis (K26); DRG package adequacy; gazette repricing; material pairing; procedure pairing; and drug indication. The K21/K26 relationship is explicitly tagged `hard_coded_two_rule_projection_rerun` in the accepted audit (`2026-09-18-rule-surfacing-audit.md:150-161`). These relationships are architecture debt to collapse, not additional Wave A findings to duplicate.
- **Synthetic identities.** Exclude `check_exclusion_violations_for_context`, `check_material_miat_for_context`, `detect_diagnosis_procedure_mismatch_for_context`, `detect_los_procedure_density_anomaly_for_context`, `detect_missing_laterality_imaging_for_context`, `detect_missing_laterality_surgery_for_context`, `detect_never_principal_diagnosis_for_context`, `detect_procedure_time_overlap_for_context`, `detect_sct_temporal_window_violations_for_context`, `detect_traffic_accident_billing`, and `detect_unnecessary_additional_diagnosis_for_context` until each has an approved stable emitted identity. Their accepted audit identity is only `kind:<callable>` or equivalent synthetic kind (`2026-09-18-rule-surfacing-audit.md:29-69`).
- **Financial or revenue outputs.** Anything with financial money semantics, a money field, or total inclusion stays on its existing monetary path. Phase 5's accepted constraints require existing financial semantics to remain unchanged (`2026-09-18-rule-engine-surfacing-audit-plan.md:337-343`).
- **Aggregate-only outputs.** Do not manufacture row findings for aggregate-only engines; the accepted plan reserves those for a later explicit decision (`2026-09-18-rule-engine-surfacing-audit-plan.md:383-387`).
- **Registry/artifact-only rows.** Catalog presence is metadata, not runtime execution, so these are outside Wave A by definition (`2026-09-18-rule-surfacing-audit.md:183-188`).
- **Broad prose engines in the first slice.** Defer dental 2.4.1, drug combination, fatura inceleme, gap-closing misc/treatment, payment-method traceability, and treatment pricing. They have multiple emitted IDs and source/cardinality decisions that are unnecessary to prove the first generic vertical.

## Canonical single-evaluation data flow

The implementation checkpoint must replace the K21/K26 projection pattern with this flow:

`PatientClaimContext → canonical compliance evaluation → RuleFinding/RuleEvaluation batch → pure patient projection → cached JSON → cohort index/API → patient and cohort Compliance UX`.

The current debt is concrete: `analyze_claim` already evaluates ICU bundled leakage and missing diagnosis in `engine.py:244-255` and `:302-305`, while `project_claim_compliance` imports those same detector functions and calls them again in `claim_compliance.py:12-16` and `:127-131`. Patient report assembly calls that projector directly at `patient_report.py:81-83`.

The first implementation checkpoint should therefore create a generic canonical evaluator in a new `src/bilun/domain/billing/rule_findings.py` module. That evaluator owns evaluation-status logic and executes the approved surfaceable detector functions once per claim-context evaluation. `analyze_claim` consumes the evaluator's legacy violation projection for the detectors moved into it, while `compute_patient_billing_report` consumes the same evaluator result directly for product surfacing. The detector calls for K21/K26 and the selected three Tablo 15 detectors must exist in only that canonical evaluation stage after migration.

`project_claim_compliance` becomes a **pure projection** over a precomputed finding/evaluation batch. It must not call `analyze_claim`, `detect_icu_bundled_leakage`, `detect_missing_diagnosis`, any selected Tablo 15 detector, or any other detector. The cohort projector must likewise consume serialized findings and must not reconstruct or re-evaluate them.

This preserves the accepted architectural constraint that canonical runtime output is evaluated once and then reused (`2026-09-18-rule-engine-surfacing-audit-plan.md:337-343`) without turning `RULE_REGISTRY` into a dispatcher.

## Initial `RuleFinding` contract

Create a typed `RuleFinding` domain record in `src/bilun/domain/billing/rule_findings.py` with these fields:

- `finding_id: str` — generated exactly once by the domain projection.
- `patient_id: str`, `claim_id: str`.
- `line_kind: "procedure" | "drug" | "material" | "claim"` and `line_id: str | None`.
- `rule_id: str`, `kind: str`, `finding_type: "compliance"`.
- `severity: str`, `detail: str`.
- `sut_section_id: str | None`, `regulatory_source: object | None`, and `source_engine: str`.
- `surface: "claim_compliance"`, `money_semantics: "unpriced_compliance"`.
- Nullable money fields: `amount_try`, `billed_try`, `payable_try`, `savings_try`, `recoverable_uplift_try`, `compliance_savings_try`, `risk_amount_try`, and `audit_exposure_try`; all are `null` for this slice.
- `evaluation_status: "evaluated" | "missing_inputs" | "unavailable"`, `required_inputs: list[str]`, and `missing_inputs: list[str]`.

Positive findings always have `evaluation_status="evaluated"`. Non-finding evaluation state remains represented by the companion `RuleEvaluation`/existing `claim_compliance.evaluations` stream so a missing input is never converted into a clean pass.

### Deterministic identity rules

For backward compatibility, the canonical `finding_id` uses the already-shipped claim-compliance identity format:

`claim_compliance:<urlquoted rule_id>:<urlquoted patient_id>:<urlquoted claim_id>:<urlquoted line_id-or-empty>`.

The current projector already uses that encoding at `claim_compliance.py:132-150`. For K21 this preserves the existing procedure-line identity; for claim-level K26 the final component remains empty. For the selected slice:

- `tablo15_10_unreported_lab_result`: `line_kind="procedure"`, `line_id=procedure_line_id`.
- `tablo15_20_missing_drug_barcode`: `line_kind="drug"`, `line_id=drug_claim_line_id`.
- `tablo15_5_material_identity_error`: `line_kind="material"`, `line_id=material_line_id`.

`action_id` remains serialized as a compatibility alias equal to `finding_id`; new code uses `finding_id` as the canonical key. Findings are de-duplicated by `finding_id` and serialized in deterministic `finding_id` order. Patient/cohort surfaces must copy the same identity rather than rebuilding it.

Severity and detail are copied from the detector output. Source mapping prefers existing structured `clause_ref`/source metadata when present, with `sut_section_id` retained for backward compatibility. No presentation registry may change execution; registry metadata is optional enrichment only.

## Exact implementation map after Chief acceptance

### Checkpoint 1 — contract and domain plumbing

Create/update:

- **Create** `src/bilun/domain/billing/rule_findings.py`: typed `RuleFinding`, evaluation record/batch, deterministic identity builder, generic normalization, and canonical one-pass compliance evaluator.
- **Update** `src/bilun/domain/billing/engine.py`: route K21/K26 plus the three selected Tablo 15 detector calls through the canonical evaluator and keep `analyze_claim`'s legacy flat return behavior backward-compatible.
- **Update** `src/bilun/domain/billing/claim_compliance.py`: remove detector imports/calls and make it a pure projection of precomputed findings/evaluations.
- **Update** `src/bilun/domain/billing/patient_report.py`: evaluate the canonical compliance batch once and pass it to the pure projector.
- **Update** `src/bilun/domain/billing/types.py`: type the existing `ClaimCompliance` container around the generic serialized contract as needed.
- **Do not change detector semantics** in `src/bilun/domain/prose_rules/common_billing_errors.py`; its selected outputs already expose the required stable IDs and line identities.

Primary tests:

- `tests/unit/domain/prose_rules/test_common_billing_errors.py`
- `tests/unit/domain/prose_rules/test_common_billing_errors_phase2.py`
- `tests/unit/domain/prose_rules/test_clause_provenance.py`
- `tests/unit/domain/billing/test_claim_compliance.py`
- `tests/unit/api/test_claim_compliance_pipeline.py`

The existing detector tests already cover the selected rule IDs (`test_common_billing_errors.py:347-373`, `test_common_billing_errors_phase2.py:278-311`, and `:403-439`).

### Checkpoint 2 — backend projection, cache, and API

Update:

- `src/bilun/domain/billing/cohort_compliance.py`: remove `_CLAIM_COMPLIANCE_RULES`, stop filtering to K21/K26, copy canonical `finding_id`, and aggregate generic evaluation statuses without rebuilding identities.
- `src/bilun/api/schemas.py`: add explicit generic finding/evaluation response typing only if useful; current `BillingReportResponse` and cache envelope are already additive/permissive (`schemas.py:82-92`, `:383-451`).

Verify/reuse without SQL schema migration:

- `src/bilun/cache/builder.py`: existing report and cohort index serialization writes complete JSON payloads (`builder.py:249-292`).
- `src/bilun/db/schema.py`: patient reports and cohort compliance are payload JSON, so no new DuckDB column/table is required for this additive contract (`schema.py:245-252`, `:274-280`).
- `src/bilun/api/routes/compliance.py`: existing GET/POST endpoint can serve the additive payload; missing old-cache artifacts already return unavailable/null rather than zero (`compliance.py:97-128`, `:131-155`).

Primary tests:

- `tests/unit/domain/billing/test_cohort_compliance.py`
- `tests/unit/api/test_claim_compliance_pipeline.py`
- `tests/unit/api/test_compliance_index_api.py`
- `tests/unit/scripts/test_rule_surfacing_inventory.py`

### Checkpoint 3 — patient and cohort Compliance UX

Update:

- `frontend/src/lib/domains/sut.ts`: replace the two-ID `ClaimComplianceRule` union with the generic serialized finding/evaluation contract; add `finding_id`, `line_kind`, and `line_id`.
- `frontend/src/lib/workspaceViews.ts`: consume the generic `claim_compliance.findings` identity.
- `frontend/src/components/patient/views/ComplianceViewSection.tsx`: render selected generic findings on the existing patient Compliance surface.
- `frontend/src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx`: key/deep-link rows by canonical `finding_id` with `action_id` fallback for old payloads.
- `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx`: keep the existing `claim_compliance` cohort surface and counts; no new navigation surface is required.

Primary tests:

- `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`
- `frontend/src/lib/api/sut.complianceIndex.test.ts`
- `frontend/src/lib/workspaceViews.test.ts`

The existing top-level `claim_compliance` report field and `surface="claim_compliance"` are retained. The first slice therefore requires **new typed fields inside an existing additive JSON field, not a new API route or database schema**.

### Checkpoint 4 — CI regression gate

Only after checkpoints 1–3 are green:

1. replace the audit test that captures the current two-rule allowlist with a generic-surfacing assertion;
2. regenerate/check the surfacing inventory so the selected hidden rows become visible and the K21/K26 hard-coded rerun debt disappears;
3. run the financial, identity, old-cache, execution-count, backend, frontend, and inventory gates below.

## Hard invariants and verification commands

1. **Financial totals are byte/value-equivalent.** The three selected rules remain `unpriced_compliance`, every money field stays `null`, and no selected finding enters totals. Add a canonical sorted-JSON financial snapshot assertion so the pre/post financial slice is byte-identical as well as numerically equal. Existing financial-regression coverage lives in `test_claim_compliance_pipeline.py:424` and `test_claim_compliance.py:349`.

   `/home/safa/Documents/Bilun/.venv/bin/python -m pytest -o addopts='' -q tests/unit/api/test_claim_compliance_pipeline.py::test_stable_projection_and_unchanged_legacy_finances tests/unit/domain/billing/test_claim_compliance.py::test_legacy_financial_report_unchanged_disabling_only_new_projection`

2. **No duplicate detector execution.** Add spies for K21, K26, and all three selected detectors at the canonical evaluator boundary. For one report scope each detector executes exactly once; the pure projection and cohort index execute zero detectors.

   `/home/safa/Documents/Bilun/.venv/bin/python -m pytest -o addopts='' -q tests/unit/domain/billing/test_claim_compliance.py tests/unit/api/test_claim_compliance_pipeline.py`

3. **One stable identity is reused across patient/cohort surfaces.** The exact domain-generated `finding_id` must be equal in patient report JSON, bill report JSON, cached cohort row, API response, and frontend row; reordering/duplicate source rows must not change or multiply it.

   `/home/safa/Documents/Bilun/.venv/bin/python -m pytest -o addopts='' -q tests/unit/api/test_claim_compliance_pipeline.py::test_normal_ingestion_reports_cache_and_http_scopes tests/unit/api/test_claim_compliance_pipeline.py::test_duplicate_context_lines_do_not_duplicate_cached_findings`

4. **Old cache stays unavailable.** Missing legacy `cohort_compliance_index` or missing generic projection yields `artifacts_available=false`/null counts, never invented zero.

   `/home/safa/Documents/Bilun/.venv/bin/python -m pytest -o addopts='' -q tests/unit/api/test_compliance_index_api.py::test_missing_cache_is_unavailable_not_zeros tests/unit/domain/billing/test_cohort_compliance.py::test_unavailable_payload_has_null_counts_not_zeros`

5. **No one-off rule-ID allowlist.** There must be no K21/K26/selected-ID list controlling generic projection. Detector execution remains structurally wired in the domain engine; projection accepts typed findings generically.

   `! rg -n '_CLAIM_COMPLIANCE_RULES|ICU_RULE_ID|DIAGNOSIS_RULE_ID' src/bilun/domain/billing/claim_compliance.py src/bilun/domain/billing/cohort_compliance.py`

   `/home/safa/Documents/Bilun/.venv/bin/python -m pytest -o addopts='' -q tests/unit/scripts/test_rule_surfacing_inventory.py && python3 scripts/audits/build_rule_surfacing_inventory.py --check`

6. **Frontend preserves null money, deep links, pagination, and old-cache honesty.**

   `cd frontend && npx vitest run src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/lib/api/sut.complianceIndex.test.ts src/lib/workspaceViews.test.ts && npx tsc --noEmit`

7. **Final repository hygiene.**

   `git diff --check`

No cache rebuild is part of this Phase B checkpoint. When the implementation reaches cached cohort artifacts, rebuild verification must use only the active build ID, as required by the accepted rollout plan.

## Deferred Wave A candidates

After the hard exclusions, defer these focused exact-ID/kind detectors until the generic contract above is proven and each line/claim identity is explicitly checked: admission billing window, blood component ISBT128, conditional EK-2D add-on, dental GA uplift, donor prep as exam, drug quantity error, duplicate exam 10-day, duplicate tests, exam/admission date mismatch, green-area bundled extras, inpatient-on-outpatient, material preauthorization missing, material type missing, normal-polyclinic wrong method, radiation-oncology violations, transplant package scope, vakabaşı wrong method, and yatak/ICU overlap.

Also defer the seven broad multi-ID prose engines listed above. Their deferral is about first-slice scope and identity/source cardinality, not a conclusion that they should remain hidden permanently.

## Chief review decision

Chief independently verified the selected rows against the accepted matrix and detector source, confirmed they are not present in the 12 analyzer→adapter rerun relationships, and accepted:

1. the three-detector Tablo 15 slice;
2. the canonical one-evaluation architecture;
3. the `RuleFinding` identity/serialization contract;
4. the additive `claim_compliance` transport choice; and
5. the deferred/excluded candidate sets.

The three new Tablo 15 findings plus the K21/K26 rerun-removal refactor are authorized for Checkpoint 1 only. Later backend/cache/API, frontend, and CI checkpoints remain separately review-gated. Phase 5 implementation is otherwise unstarted at this acceptance checkpoint.
