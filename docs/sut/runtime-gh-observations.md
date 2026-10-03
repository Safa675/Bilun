# Measured GH execution metadata

This additive slice observes the actual bounded GH evaluator calls. It does not change the clinical result, create an advisory for a successful `None` result, rerun an evaluator, or establish reimbursement eligibility.

## Evaluated scope

A collector belongs to one actual drug-line evaluation. Explicitly supported protocol versions cover Turner/pediatric continuation, PWS, CKD, mecasermin and pediatric initiation. Only reached comparisons produce predicate receipts. Source-version, phase, report and input gates record the path that actually ran. Source notation and data reconciliation remain route guards rather than invented clinical comparisons. Adult source-only routes and selected unknown protocol versions return unavailable metrics instead of a measured zero.

The binding map lists every authored predicate and exact source locator. A failed atomic predicate is not automatically a clinical failure: an alternative may satisfy the containing OR. A true GH stop-condition comparison is recorded as a failed limited necessary requirement; passing or failing totals never establish eligibility or a billing outcome. Available input counts are distinct validated facts actually read by these instrumented comparisons and gates, rather than a count of fields supplied in the request. Generic legacy report-validator inputs are not retroactively counted merely because its return value is observed. Clinical values never enter the receipts or response.

Source-clause counts require unique active normative source resolution. Mecasermin applies only the three reviewed Word-numbered stable-key overrides; arbitrary prose remains ineligible. No complete-clause mapping is supplied, so fully evaluated source-clause counts remain null even when all reached comparisons pass.

## Transport

The detailed result and canonical per-line evaluation may carry `runtime_coverage`. Existing findings and legacy rows retain the same bounded metadata when present. Cached data without observations remains unmeasured.

V2 adds optional nullable `drug_runtime_coverage`. This slice exports GH summaries at that top level. Existing renal, SMA and antifungal summaries remain attached to their bounded `clinical_restrictions`; the producer does not sum those separately scoped summaries or claim a whole-drug total. Each row contains only `claim_id`, `drug_claim_line_id`, `selected_rule_id`, and the strict bounded `runtime_coverage` summary. A legacy payload without this field serializes as null. A current request with no exported family summaries returns an empty list. Neither state implies a comparison ran. The field does not participate in validity, advisory or financial calculations.

A request-local, single-use sink receives already-computed summaries from the canonical drug evaluation. It is bound to the actual line objects, so a second anonymous request with equal identifiers cannot supply observations. Exports are checked against unique named material positions in the actual request; extra/private payload fields and conflicting summaries fail closed. Internal object identities and execution nonces never leave the request and do not enter receipt digests. No persistent clinical logging is added.

## Integration

The slice is additive over the reviewed GH clinical chain and renal observer dependency. Shared caller and DTO changes must be merged by their exact baseline deltas. Later source-context and family dispatch changes must be retained; do not replace current wrappers with files from an older clinical parent. SMA/antifungal observation8 is a separately reviewed additive dependency, not a new source of GH predicates.

Verification includes unchanged clinical decisions with and without observation, actual named/anonymous/repeated/concurrent requests, successful no-finding lines, mixed line outcomes, old-cache null semantics, strict line identity and hostile payload rejection. Focused and differential results belong to the frozen packet; they do not imply a full-suite pass or whole-SUT runtime coverage.
