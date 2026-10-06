# MDS/GH prerequisite follow-up to PR161

The immutable integration base is `93002f03077ae9b7f6e7b677a98eed3fb17a1870` (PR161, full hosted CI506 attempt3 successful). This packet implements one source-backed missing documentary relation. Neither family's source-date admission nor independent clinical release changes; `clinical_eligibility_complete=false` remains mandatory.

## Source-backed MDS correction

The operative `4.2.9.A-2#17efb08b` requires prescribing based on the hematology specialist report. The seven strike-aware paragraphs and their corpus bindings are pinned in [the existing source proof](../../data/gazette/clinical_sources/mds_candidate_2026_10.json). Separate observations of report presence, report author and prescriber specialty do not establish that relationship.

`MdsEvidence.prescription_based_on_same_hematology_report` now records the explicit relationship. Its strict boolean parser preserves native true/false and treats missing or invalid facts as unknown. The candidate requires this fact for the existing alfa/beta initiation and continuation scopes. Generic report flags, matching dates, specialties or caller-supplied identifiers never supply it. The existing typed transport and bounded public field projection use the dataclass fields, so shared models, adapters and routes need no changes. The actual controlled form carries the same field in Turkish and English.

With all other necessary evidence complete, true passes this candidate check, false fails it and unknown remains unknown. Passing candidate checks still establishes neither complete eligibility nor payment clearance. Existing source/date, indication, substance and phase guards remain ahead of predicates. MDS's existing known-failure-with-missing-facts behavior is preserved; missing evidence remains visible alongside the known failed check.

## GH source and documentary boundaries

No definite missing necessary condition was established in the implemented bounded `4.2.6.A-2(2)-(4)` scope. GH runtime/model code is unchanged. New differential tests establish that a generic report flag cannot replace the individual ITT peak's report documentation; the one-test exception does not remove childhood diagnosis/treatment/closure-stop prerequisites; the numeric cutoff applies only to ITT; and missing non-ITT interpretation remains unknown. When a known failed check coexists with missing relevant evidence, GH's existing conservative overall unknown behavior and the individual failed check are preserved.

An absent inadequate-response document is not evidence of a confirmed adequate response. This packet does not invent a clinical reconciliation rule from that flag or unify the two families' overall verdict policies.

## What remains unresolved

| Boundary | Result of this packet | Remaining requirement |
| --- | --- | --- |
| MDS report-to-prescription relationship | Explicit necessary fact, candidate check and application transport implemented | Real documentary evidence for the specific claim; broader report validity requires review |
| MDS diagnosis/start thresholds | Existing explicit indication and three numeric prerequisites preserved | No unsupported biopsy, diagnosis algorithm or unit conversion added |
| MDS restart, report validity and dispensing period | Existing unknown restart and native calendar-month limit preserved | No inferred restart protocol, test age, 30-day month or report expiry |
| GH diagnosis/test prerequisites | Existing source-backed paths preserved and documentary differentials added | Non-ITT adequacy, ITT preference/contraindication and contradictory extra tests remain clinical review |
| Missing versus known-false overall policy | Both documented contracts preserved with visible individual evidence | Any policy unification requires independent release review |
| Source-date admission and clinical release | Both hard release constants remain false; no catalog/receipt change | Separate exact family/date admission and independent interpretation release |

The prior independent three-family source review and October6 local source observations were read from the source owner's isolated worktree. A fresh source-owner decision-list exchange could not be completed through the unavailable worker-message connector; no claim of a new expert release decision is made. No historical gaps or October6 admission windows are filled.

## Validation and ownership

Focused owner runs passed: 439 MDS source/parser/candidate/private-helper tests, 15 GH documentary differential tests, 59 real authenticated application API tests and 49 frontend tests. TypeScript, Ruff, whitespace checks, generated-artifact comparison (134 byte-identical artifacts) and manifest parity (23 manifests, zero issues) passed. These are separate focused runs, not a local full-suite result.

Independent read-only code and source reviews found no P1/P2 issue in the 15 code/report paths. The seven operative MDS paragraphs match the preserved DOCX proof; the corrected GH test fixture uses the actual drug-specific report field. This working-tree review does not establish final published-head closure.

Source proof/context, source-authority catalog/receipts, corpus and committed coverage parquets are preserved. Canonical coverage evidence still matches 161 of 163 dependencies. Only the two changed MDS code dependency hashes need refresh; their exact delta is prepared outside this PR pending parent single-writer coordination. No shared metadata was changed without that coordination. Exact-head review and hosted CI for the follow-up remain separate publication gates. Main, VPS, deployment and PR159/160/161 heads are unchanged.
