# Bounded clinical source authority in public results

`source_authority` is optional provenance for a named set of necessary clinical/report checks. It never establishes complete clinical eligibility, payment entitlement, or whole-SUT currentness. `clinical_eligibility_complete` remains `false`, and interpretation remains `ai_generated_pending_review` even for an admitted source.

## Placement and compatibility

- Capped clinical families carry the evidence inside each `clinical_restrictions` entry.
- A reached mecasermin clinical result carries it at the top level of the detailed result, canonical finding/evaluation and existing legacy observation. V2 preserves that top-level evidence on the corresponding review advisory.
- Recommended actions and the surfaced cohort index retain the same bounded top-level or nested provenance, without changing classifications or monetary values.
- Source admission does not turn a V2 historical observation into a proven Compliance finding. Existing advisory/disposition rules are unchanged.
- An earlier generic report gate may return before the mecasermin clinical leaf runs. That observation has no fabricated source-authority evidence.
- Non-mecasermin GH results do not receive this source-date guarantee. Existing runtime observations retain their separate scope and values.
- Older canonical/cache payloads without the optional field remain without an assertion of currentness. Permissive response models may serialize the optional field as `null`.

## Dates and UI wording

The UI separately labels the actual service date, recorded legal effective date (when known), source-observation date, source-admission start and checked-through date, and timestamp of the official-source review. A source-observation date is not displayed as a legal effective date or automatically converted into a continuous admission period. The source version defines its explicit bounded admission period; the UI never extends it using the current clock.

`admitted` displays “Source admitted for these limited checks” with the named clinical/report-only scope. `review_required` displays a review notice and the supplied bounded `next_action`. A checked-through date, when available, remains visible so an operator can see the last admitted boundary. Neither state creates a payment or full-law guarantee.

## Trust boundaries

`ClinicalSourceAuthorityEvidence` is the shared strict response model. Canonical construction, cache normalization and frozen public response projection validate the original provenance object before exposing it. Unknown fields, raw/patient objects, wrong types, overlong values, or contradictory admission evidence invalidate the entire provenance object; selecting only the familiar fields first would incorrectly make malformed evidence appear trusted. The strict HTTP/V2 models reject invalid direct model inputs.

Public metadata includes only the bounded status/reason, family/version/review identifiers, dates, source hash, action text and fixed limited-scope flags. No source document body, raw clinical measurement, private notes or payment amount is added. Nested clinical evidence retains its check/reference truncation disclosures across cache round trips.

## Focused checks

Backend transport coverage is in `tests/unit/domain/test_source_authority_transport.py`: admitted/missing/stale states, legacy absence, malformed provenance, canonical/cache/public model parity, actual V2 HTTP serialization, and the real mecasermin leaf-to-HTTP path. The adjacent clinical-public security and existing drug-indication/V2 suites cover compatibility. UI tests in `ClinicalRestrictionDetails.test.tsx` exercise bilingual limited-scope wording, distinct dates, blocked-source actions and hidden arbitrary fields.
