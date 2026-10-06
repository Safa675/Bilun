# MDS/GH prerequisite follow-up to PR161

The immutable integration base is `93002f03077ae9b7f6e7b677a98eed3fb17a1870` (PR161, full hosted CI506 attempt3 successful). This packet implements source-backed missing documentary facts for the two families. Neither family's source-date admission nor independent clinical release changes; `clinical_eligibility_complete=false` remains mandatory.

## Source-backed MDS correction

The operative `4.2.9.A-2#17efb08b` requires prescribing based on the hematology specialist report. The seven strike-aware paragraphs and their corpus bindings are pinned in [the existing source proof](../../data/gazette/clinical_sources/mds_candidate_2026_10.json). Separate observations of report presence, report author and prescriber specialty do not establish that relationship.

`MdsEvidence.prescription_based_on_same_hematology_report` now records the explicit relationship. Its strict boolean parser preserves native true/false and treats missing or invalid facts as unknown. The candidate requires this fact for the existing alfa/beta initiation and continuation scopes. Generic report flags, matching dates, specialties or caller-supplied identifiers never supply it. The existing typed transport and bounded public field projection use the dataclass fields, so shared models, adapters and routes need no changes. The actual controlled form carries the same field in Turkish and English.

With all other necessary evidence complete, true passes this candidate check, false fails it and unknown remains unknown. Passing candidate checks still establishes neither complete eligibility nor payment clearance. Existing source/date, indication, substance and phase guards remain ahead of predicates. MDS's existing known-failure-with-missing-facts behavior is preserved; missing evidence remains visible alongside the known failed check.

## GH source and documentary boundaries

The renewed source review identified a factual representation gap in the bounded `4.2.6.A-2(2)-(4)` scope: distinct record IDs and a row count do not establish that two actual test procedures were documented. `two_distinct_stimulation_procedures_documented` records that explicit clinical-document fact. It does not require different methods or days. Missing or invalid observations remain unknown; the documented non-PRL/non-GH pituitary deficiency exception still permits one appropriate test without a pair observation. An unconfirmed exception remains relevant when a documented pair is absent.

Differential tests also establish that a generic report flag cannot replace the individual ITT peak's report documentation; the one-test exception does not remove childhood diagnosis/treatment/closure-stop prerequisites; the numeric cutoff applies only to ITT; and missing non-ITT interpretation remains unknown. Documented clinician interpretation is a patient fact the application can carry. Complete, compatible extra test records do not create a blocker merely through their count. Missing or contradictory extra records remain visible for review. When a known failed check coexists with missing relevant evidence, GH's existing conservative overall unknown behavior and the individual failed check are preserved.

The application labels the result as a diagnosis/stimulation subset. It separately displays an unverified report/prescription review checklist grounded in the existing operative (5), general A(1)/A(2) and report-formality cross-reference. This display does not attest board composition, report identity or validity, prescribing relationship, dose, treatment scheme or supply. It preserves the adult internal-medicine prescribing alternative and native year/month units.

An absent inadequate-response document is not evidence of a confirmed adequate response. This packet does not invent a clinical reconciliation rule from that flag or unify the two families' overall verdict policies.

## What remains unresolved

| Boundary | Result of this packet | Remaining requirement |
| --- | --- | --- |
| MDS report-to-prescription relationship | Explicit necessary fact, candidate check and application transport implemented | Real documentary evidence for the specific claim; broader report validity requires review |
| MDS diagnosis/start thresholds | Existing explicit indication and three numeric prerequisites preserved | No unsupported biopsy, diagnosis algorithm or unit conversion added |
| MDS restart, report validity and dispensing period | Existing unknown restart and native calendar-month limit preserved | No inferred restart protocol, test age, 30-day month or report expiry |
| GH diagnosis/test prerequisites | Explicit two-procedure documentary observation; one-test exception and diagnostic-only scope preserved | Actual clinician adequacy/independence evidence; unresolved ITT preference/contraindication and contradictory extra tests require clinical review |
| Missing versus known-false overall policy | Both documented contracts preserved with visible individual evidence | Any policy unification requires independent release review |
| Source-date admission and clinical release | Both hard release constants remain false; no catalog/receipt change | Separate exact family/date admission and independent interpretation release |

The source owner's renewed acceptance input was supplied by the parent and read locally at its verified hash. It remains AI-generated and pending human review. The publication-denied source note and its evidence packet are not copied into this PR. The source owner's GH pytest setup attempt ran zero test bodies and is not a successful test run. No new expert release decision, historical gap fill or October6 admission window is claimed.

## Validation and ownership

Focused runs passed: the unchanged MDS packet's 439 source/parser/candidate/private-helper tests; the final GH packet's 430 strict-input/candidate/private-helper/documentary tests; 64 real authenticated application API tests; 65 GH editor/application form tests; and 19 bounded result/checklist display tests. Final TypeScript, Ruff, whitespace checks, generated-artifact comparison (134 byte-identical artifacts) and manifest parity (23 manifests, zero issues) passed. These are separate focused runs, not a local full-suite result. The earlier 15 GH, 59 API and 49 frontend runs belong to the initial snapshot and are not added to these counts.

Independent read-only code and source reviews found no P1/P2 issue in the initial 15 code/report paths at `a7d95c85`. The seven operative MDS paragraphs match the preserved DOCX proof; the corrected GH test fixture uses the actual drug-specific report field. Independent raw-paragraph reviews also support the subsequent GH factual representation and separate checklist. Final-head code review remains a separate gate after the acceptance addendum.

Source proof/context, source-authority catalog/receipts, corpus and committed coverage parquets are preserved. Canonical coverage evidence currently matches 159 of 163 dependencies. The two MDS and two GH code dependency hashes require refresh; their exact four-line hash delta is prepared outside this PR pending parent single-writer coordination. No shared metadata was changed without that coordination. Exact-head review and hosted CI for the follow-up remain separate publication gates. No main, VPS, deployment or PR159/160/161 head mutation is performed by this packet.
