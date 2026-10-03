# Pediatric enteral reports and ravulizumab continuation

## Delivered scope

This extends the reviewed clinical-evidence framework with two necessary-predicate groups. Neither group certifies complete reimbursement eligibility. Complete, failed, unknown and unverified-date states are distinct; all-clear necessary predicates still require review of remaining SUT conditions.

- C004150 / `4.2.8.A#99f29955`: pediatric malnutrition report maximum <=6 months; from the verified September 5 amendment, neurological disease permits <=12 months. Initiation and renewal have distinct report-author specialty sets. The author is not inferred from the prescriber. An explicitly present specialist report is not falsely rejected because a board-report flag is absent. Exempt pathway (1)(b) remains separately review-required rather than receiving malnutrition-only restrictions. The legacy generic-name thickener/dysphagia supplemental row does not create an unverified board-report denial for a malnutrition record.
- C005814 / ravulizumab `4.2.14.C(3)(yyy)(2)(b)`: NMOSD stopping predicate requires both at least six explicit completed treatment months and EDSS >=8; EDSS must be on each report. Numeric duration is an explicitly supplied fact, with no invented day-to-month conversion. The associated <=6-month report maximum no longer rejects shorter reports as if exactly six were mandatory. PNH/aHUS cases are not subjected to this NMOSD predicate. The stopping rule is no longer an affirmative ICD indication route.

The source interval is verified from September 5 for enteral and July 7 for ravulizumab, through the October 2 authoritative snapshot. That review window is not a legal expiration date. Missing, earlier unverified or later not-yet-verified service dates remain review-only; no wall-clock date is substituted.

## Primary evidence

The October SGK consolidated DOCX was independently inspected, with SHA256 `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573`.

- [Official consolidated ZIP](https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a), SHA256 `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61`.
- [August 29 amendment](https://sgd.sgk.gov.tr/Download/DownloadFile?f=873126b6-2250-4c64-b0a4-fe910055fe11.docx&d=658f4ba1-b0e8-4dfb-8504-fa0b09e353e0), SHA256 `ffd269486c0fb75a65321c0ebafb898bc74193125a49a916842bcc457c6ea491`. Article 6(a) adds the neurological one-year phrase, with the consolidated paragraph explicitly annotating September 5.
- [Official June 29 announcement](https://rtb.sgk.gov.tr/duyuru/detay/29062026-Tarihli-ve-33295-Sayili-Resm-Gazetede-Yayimlanan-Sosyal-Guvenlik-Kurumu-Saglik-Uygulama-Tebliginde-Degisiklik-Yapilmasina-Dair-Teblig-2026-06-29-04-48-43). The consolidated ravulizumab yyy annotation explicitly gives July 7. The independent June amendment DOCX was not redownloaded for this packet; commencement evidence is the official consolidated annotation.

All source paragraph texts, normalized SHA256 values, source context and dates are pinned in `data/gazette/clinical_sources/enteral_ravulizumab_2026_10.json`. Indexes count all XML w:p elements. Enteral continuation is paragraph 4448; ravulizumab stop is 6123, between yyy 6106 and zzz 6126.

## Source-identity safeguards

The October satralizumab stop sentence at 6134 is byte-identical to the ravulizumab sentence. The old content-key resolver intentionally returns every equal-text row, so a bare hash would link both medicines. New explicit `@between:start-key|end-key` citations require two unique active content anchors, correct ordering and exactly one child inside the open interval. This selects baseline August C005814 and October C005832 without selecting satralizumab C005843. Missing, duplicated, reversed, inactive or malformed anchors fail closed.

The enteral continuation is classified as prose by extraction even though it contains operative report conditions. A `prose:coordinate#hash` citation replaces wrong numeric C004140. It requires exactly one active prose row with matching content; headings, chapters, amendments, missing and duplicated references are rejected. Ordinary encode-eligible rules are not relaxed. The API rule-source consumer uses the shared validator/resolver and remains fail-closed.

The authored C* inventory falls from the reviewed preceding D count 213 to 212 solely because C004140 is replaced. The prior D changes removed C007082/C007088 from the original 215. No new positional cite is added. Generated rule identities are retained, and deterministic surfacing output is regenerated and checked.

## Remaining boundaries

- The enteral (1)(b) exempt route, all other nutrition product distinctions, report content and prescription quantity conditions are not completed by this report-duration/author group. Malnutrition qualification is an explicit clinician fact here, not calculated from raw anthropometrics.
- Ravulizumab initiation eligibility, prior immunosuppressant adequacy, board composition, vaccination/prophylaxis, and PNH/aHUS eligibility remain outside the stopping predicate. A clear EDSS stopping check is never payment clearance.
- Full tests needing absent local raw/annex assets remain for the complete hosted environment. Final local focused results, compiler, parity and surfacing evidence are provided with the review packet.

## Independent-review revision2

Independent review reproduced a pediatric-applicability bug: unknown pediatric status could combine with a failing pediatric report-author predicate to emit a restriction. The revised evaluator establishes pediatric applicability before any pediatric-only author/duration check. Exact full-corpus regressions include unknown pediatric status with the other author and12 months, and13-month invalid-duration variants; all remain explicit review with no pediatric predicate claimed evaluated.

The analogous adult NMOSD boundary is also explicit. Unknown adult status with EDSS8 at6 months cannot claim an adult stopping result. Known adult=false reports only the source's adult-eligibility restriction, with stop_required=null and no EDSS/report predicate evaluated. The runtime source list now additionally identifies the exact heading-bounded adult NMOSD paragraph, whose source text was already in the pinned evidence. Existing field/reason identifiers are reused, so the paired UI contract is unchanged.
