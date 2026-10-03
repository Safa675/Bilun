# SMA and antifungal necessary clinical restrictions

Base main: 04878812b87a82392e64671e8edce46c48cfaebe. This packet layers on the separately reviewed SMA heading-scoped source correction. All AI-authored rules and clinical outcomes are pending independent review.

## Executable scope
- SMA: explicitly documented negative history for shared hypoxic ischemic encephalopathy and hypoxic-birth neurological sequelae; nusinersen-only procedure-interfering brain/spinal history, CSF shunt/catheter, bacterial meningitis and viral encephalitis. Documented lumbar-puncture suitability is required only for nusinersen type 2/3. Missing diagnoses never stand in for negative history.
- Anidulafungin: adult, treatment intent, invasive candidiasis, ANC >=500/mm3 and actual laboratory result present.
- Micafungin: treatment for invasive/esophageal candidiasis; separate allogeneic HSCT/ALL neutropenic or post-neutropenic day 0-7 branch; autologous HSCT with mucositis during neutropenia. The >=10-day “other patients” no-pay branch is evaluated only after every allowed prophylaxis branch is known false.
- Posaconazole: high-risk prophylaxis alternatives, with inability to use oral formulations restricted to the parenteral branch. Separate source-defined treatment/salvage branches preserve disease, formulation, drug and refractory/intolerant conjunctions.
- Itraconazole solution: HIV/immunodeficiency plus fluconazole-resistant esophageal candidiasis treatment. Prophylaxis population can be checked, but the source literally states cells/ml and no conversion to cells/mm3 is invented.

## Input and date contract
Optional nested SmaEvidence, AntifungalEvidence and RenalEvidence dataclasses share strict API/dict/row parsing. Exact booleans preserve false versus unknown, real numeric values must be finite/nonnegative, enum values are family-specific, dates are civil dates. No raw value is converted to an asserted absence. `applies_on` explicitly scopes a clinician assessment to the service date; `assessment_date` cannot be future. There is no invented maximum age for an assessment. Drug service date is never replaced with today's date.

SMA source replacement is effective 2025-05-06; micafungin replacement effective 2018-04-01. These implementations are verified through 2026-10-02. Other source intervals lack a verified original lower bound, so they are supported only at the verified source snapshot; any historical/future request remains review-only. The snapshot date is not represented as a legal effective date.

## Explicit limits
These are necessary restrictions, never complete payment eligibility. Cleared checks always retain clinical_eligibility_complete=false and a review of remaining SUT clinical criteria. Unknown clinical evidence or source dates never triggers a false exclusion. A source-qualified antifungal prophylaxis branch is not rejected by the legacy infection-only ICD route. No monetary uplift/payable amount is emitted.

The renal dataclass and transport are additive scaffolding for a separately implemented renal group; this packet does not claim renal clinical coverage. It includes the source-only correction of the cinacalcet row previously mislabeled as albumin/bisphosphonate; generic prior_therapy matching is removed where it does not represent a source agent or outcome.

## Source and verification
Captured official current clauses with stable content hashes are committed at data/gazette/clinical_sources/sma_antifungal_2026_10.json. Both disease/drug headings and repeated SMA paragraph context were verified. Synthetic tests cover independent positive, negative and missing values, exact inclusivity (ANC500; day7), pre-effective and future boundaries, invalid dates, strict transport, unknown enum/unit handling, full-corpus medicine isolation and old-ICD false-denial regression.

106 focused/public/adapter tests passed before final transport-overflow regression. Source/scripts Ruff passed. Full Python3.13 tests/ attempted and stopped during collection because this partial checkout lacks raw data; exact single collection blocker is test_extract_sut_prose.py. Earlier six compiler manifest differences reproduced identically on pristine main. Broader domain/API tests are separately running; neither full suite nor compiler is represented as passing.

## Review focus
Check the tri-state OR/AND behavior, correct drug and intent scope, applicability versus observed dates, unit limitations, required-input transport, public finding projection, and all paths that might turn a partial clinical clear into payment compliance. No merge, deploy or production/VPS action is authorized.

## Independent-review corrections and integrated renal group

Four independently reproduced issues were corrected: SMA markers now explicitly exclude gene therapy; multiple antifungal families fail closed; micafungin's other-patient no-pay requires the exact source prophylaxis indication; and bounded clinical checks/source references plus the actual failing-rule identity survive canonical finding/evaluation, legacy, patient/recommended-action, cohort, public DTO and DuckDB JSON projections. Strict v2 advisories retain the same evidence while remaining unpriced review-only. Private/arbitrary keys are dropped. Input dates follow the strict A API contract (invalid non-null dates rejected), while raw-dict invalid dates remain unknown.

The separately reviewed renal module and 70-case test group are integrated: phosphate initiation/restart/stop, cinacalcet dialysis versus primary-hyperparathyroidism branches, and renal oral amino-acid/ketoanalogue initiation/restart/response checkpoints. Its three marker rows add no ICD or payment route. A separate six-month albumin fact prevents later values replacing the historical six-month response. Every cleared necessary gate still requires remaining clinical review.

Final expanded source/clinical/transport/canonical/cohort focused selection passes 327 tests; six independent end-to-end/scope regressions also pass, and the two new micafungin unknown/other-indication cases pass. Source/scripts Ruff passes. Full local tests/ still require the original raw-data DOCX for collection. Broader local domain/API completed with 3476 passes and 106 failures before targeted fixes; pristine attribution was killed near 90% and is not claimed complete. Newly hydrated exact baseline curated data should remove missing-catalog failures, but that full rerun remains an integration gate.

The generated corpus was normalized to compiler rule order without any rule-semantic differences. Five manifests update only rules_in_json counts (global 933→936, renal55→58). All other compiler differences remain the same six known baseline/materialization deltas; they are not presented as a successful compiler gate. Surfacing artifacts were regenerated, and the authored C* inventory is updated by the approved PR124 repair. This revised packet supersedes the earlier D25 clinical review snapshot.
