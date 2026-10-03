# Source-specific report documentation and puberty input contract

This bounded completion follows the frozen GH28 integration. It introduces two
independent report-content facts and clarifies an existing clinician-assessment
contract. It does not establish complete clinical or reimbursement eligibility.

## Enteral initiation

`enteral_evidence.malnutrition_conditions_documented_in_report` is a nullable,
strict boolean: the initiating specialist report states the malnutrition
conditions. It is independent of `malnutrition_criteria_met` and
`specialist_report_present`; neither supplies the report-content fact.

The exact source is `prose:4.2.8.A#99f29955`, primary October DOCX all-paragraph
index 4448. The explicit content requirement attaches to initiation. The separate
renewal sentence continues to require the existing clinical conditions, report,
author and duration checks; the new content predicate is not imported into
renewal or the exemption path. Unknown phase cannot select this predicate.

## Phosphate initiation and restart

`renal_evidence.prior_phosphate_therapy_documented_in_report` is a nullable,
strict boolean: the report states that the required prior phosphate-lowering
therapy was used for at least three months. It never substitutes for the separate
numeric duration. §4.2.9.B.(1)#00052268 requires both; restart
§4.2.9.B.(4)#e346bde0 explicitly imports initiation criteria.

Both initiation and restart require the new fact. The four clinical groups
remain alternatives, the restart phosphorus boundary is unchanged, and the
continuation branch does not use this initiation report-content fact. No monthly
laboratory or supply conditions are added.

The optional observation is `phosphate.initial.prior_therapy_report`, bound only
to §4.2.9.B.(1)#00052268. Renal evaluator version is
`renal.atomic.v2.2026-10-02`, reflecting the additional predicate, not new temporal
authority. The existing complete phosphate fixture now records 10 comparisons,
14 observed context/clinical facts and the same 6 verified source clauses.
Restart adds its existing phosphorus comparison. Full-clause counts remain null.

## Clinician-recorded puberty contract

`gh_pubertal_status` means a clinician-recorded assessment using
§4.2.6.A-1.(3)#0c2b0e3f: onset is testicular volume at least 4 ml in boys or
T2 thelarche in girls. The API schema, typed frontend contract, EN/TR UI hint and
input-contract artifact state that exact meaning. If the recorded assessment does
not establish use of that definition, leave the status unknown and reconcile it
with the clinician.

No second attestation was added because it would duplicate the existing
source-defined assessment without independently verifying it. This contract
clarification does not retrospectively validate older generic assessments. The
application does not collect raw sensitive puberty measurements, infer the
assessment from age or diagnosis, diagnose puberty, or repurpose
`gh_height_reference_sex`. Existing unknown and growth-stage reconciliation
behavior is unchanged. The source is confirmed in the August DOCX direct-body
paragraph 4247 and October direct-body paragraph 4255.

## Source and privacy boundaries

`reports/sut-expansion/report-documentation-primary-source-verification.json`
records exact primary file and paragraph hashes. Enteral evidence supports the
existing September 5–October 2, 2026 interval; renal remains at its existing
October 2 source snapshot. No service-date policy was expanded here.

Omitted, null or malformed report booleans stay unknown; explicit false means the
stated source requirement is not met. UI fields never infer report content from
clinical qualification, duration or report presence. Public metadata retains
bounded check statuses/missing-field identifiers and optional aggregate runtime
observations; raw evidence, report text and execution receipts remain excluded.
