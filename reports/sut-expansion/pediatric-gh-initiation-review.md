# Pediatric GH initiation and SGA necessary checks

Scope: §4.2.6.A-1(1), current somatropin/somatrogon heading effective 17 May 2024. Standard velocity and bone-age conditions are selected only with an explicit recorded initiation pathway. Somatropin-only neurosecretory and SGA paths do not gain somatrogon or generic-hormone aliases. All negative necessary-condition screens remain manual clinical review.

## Source proof
`data/gazette/source_evidence/pediatric_gh_initiation.json` pins both original DOCX SHA256 values and 20 contiguous paragraphs (including superseded/struck content) with every run and strike state. August paragraph indices4235–4254 have exact text counterparts in the October document. Current heading and explicit effective annotation govern this bounded version; no older enactment date is inferred.

- Standard annual growth: recorded source band0–2: strictly<10cm;2,1–4: strictly<7cm;4,1–prepuberty: strictly<5cm. Printed bands are explicitly reported classifications, never generated from numeric age. Source classification correctness remains a clinical responsibility; no new decimal-years/months interpretation is invented.
- Puberty: recorded pediatric endocrine specialist assessment of monitoring and growth using other findings, without a fabricated numeric growth threshold. Explicit puberty assessment determines the branch, never sex or chronological age.
- Bone age: disregarded before age4 or in puberty; from4 before puberty, chronological age minus bone age must be at least2years. Decimal conversion from numeric text preserves8.2−6.2 equality. Puberty requires open epiphyses.
- SGA case1: gestational-age birth weight OR length SDS strictly<−2; age>=4; last-year growth velocity SDS strictly<0. One known positive birth-size branch suffices without inventing the other. No raw birth-weight/length conversion.
- SGA case2: explicit SGA birth confirmation, current height SDS strictly<−2.5 AND parental-adjusted height SDS strictly<−1. It never inherits case1 age/catch-up conditions. Selecting either source case does not assert full statutory eligibility.
- Organic/surgical and neurosecretory paths remain explicit manual review before report and standard measurement checks; their specific laboratory/genetic/diagnostic predicates are outside this slice.

## Implementation
`pediatric_gh_initiation.py` exposes `evaluate_pediatric_gh_initiation_preconditions` and `evaluate_pediatric_gh_initiation_checks`. Routing requires `gh_initiation_pathway` before considering report-duration/specialty hints. Three existing initiation rules receive protocol/pathway metadata; continuation rules are unchanged. Signed SDS fields share one strict finite parser; booleans, strings, NaN and infinity do not become measurements. API rejects invalid typed values, row parsing retains them as unknown with errors. Shared adapter dictionaries already transport all explicit GH fields.

Actual failed-condition discriminator: `violation_kind=growth_hormone_initiation_criterion_not_met`, `growth_hormone_failed_criteria`. No independent predicate IDs or runtime receipts are claimed. Review-only identifiers: `gh_initiation_clinical_assessment`, `gh_growth_stage_reconciliation`; public UI/projection is a reviewed follow-on dependency.

## Verification
- 1,021 focused drug/GH/source tests pass, including106 new initiation tests.
- Changed-file Ruff passes.
- Target compiler regeneration then check:128 artifacts byte-identical.
- Broader prose run:1,925 passed/22 failed initially. Two changed GH golden expectations were fixed and pass in the final focused run. All20 remaining failed node IDs reproduce unchanged in the prior mecasermin worktree (20 failed/70 passed comparison), before this slice. This is not a full-suite green claim.
- Source snapshots are source evidence, not standalone executable/full-clause coverage counts. Parent labels a/b are structural; puberty's biological definition and specialist clinical sufficiency remain partial scope.

## Integration
Apply additive diffs over all six prior GH packets. Preserve temporal service-date adapter and other clinical families, plus their source@within-heading resolution. Regenerate the combined4206 manifest with all merged rules; the standalone47 encoded source links are not a runtime or full-clause count. Do not overwrite later shared models/evaluation/routing wholesale. Independent review is required before root publication; merge/deploy remain outside authorization.

## Independent-review revision2
Clear conflicts between supplied age and source band now return `gh_growth_stage_reconciliation` before any threshold. The guard rejects first-band age>=2.1, second-band age<2 or>=4.1 and third-band age<4. It deliberately does not classify the transition intervals2–2.1 or4–4.1, assign a band, or choose between decimal-years/month notation. Nine regression cases include the reviewed age1.5/band2_1_4/growth8 scenario and both ambiguous regions.
