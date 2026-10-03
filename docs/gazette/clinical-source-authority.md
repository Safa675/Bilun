# Bounded clinical source authority

The former October 2 cap was an intentional assurance boundary, not a legal sunset. The reviewed catalog now separates a clause-specific legal lower bound, observed source snapshots, and explicitly admitted forward-continuity dates. Passing source admission permits only the named necessary clinical/report checks. It never establishes complete clinical eligibility, product-list availability, pricing, or payment.

## Current admission

`data/gazette/source_authority/clinical_versions.json` preserves all previously admitted dates and adds October 3, 2026 for 12 bounded clinical families. The official source review was completed at 07:04 UTC that day. Current continuity is admitted through October 3 only. October 4 and later remain source-version review until new evidence is reviewed and admitted. A calendar change never extends authority.

Known historical lower bounds remain unchanged: SMA May 6, 2025; micafungin April 1, 2018; pediatric enteral September 5, 2026; ravulizumab July 7, 2026; the bounded SC immunoglobulin/HBV branches November 9, 2024. These do not assert first enactment of every nearby criterion.

Other antifungals, renal, follow-up, HCV and denosumab retain unknown historical legal starts. Their October 2 observation plus reviewed October 3 continuity does not establish October 1 or any earlier date. Mecasermin retains its separate August 29 and October 2 observation points; August 30 through October 1 remains unverified. The new continuity window does not fill that gap.

Non-mecasermin GH keeps its existing, distinct legacy behavior: the verified May 17, 2024 heading lower bound with no reviewed upper bound. This packet does not tighten those paths or give them the new reviewed-window guarantee.

## Positive official currentness evidence

The source review used the directly observed [October 3 Gazette daily contents, issue 33389](https://www.resmigazete.gov.tr/eskiler/2026/10/20261003.htm), the [Gazette homepage and latest-supplement pointer](https://www.resmigazete.gov.tr/), and the live [SGK GSS announcement listing](https://www.sgk.gov.tr/birimler/duyurular/GENEL-SAGLIK-SIGORTASI-GENEL-MUDURLUGU-2026-01-28-02-00-42). The regular issue contained no new SUT Tebliği amendment; the homepage advertised September 6 as the latest supplement at observation. This is positive observed-source evidence, not an inference from missing search results, and is not a guarantee against later publication that day.

The [October 3 İlaç Geri Ödeme Yönetmeliği amendment](https://www.resmigazete.gov.tr/eskiler/2026/10/20261003-3.htm) was read in full. Its articles change reference/equivalent groups, price-band and market-share mechanisms, Medula/data terminology, committee representation and submission requirements. Article 8 makes it effective on publication. It does not directly amend the named disease-specific clinical/report clauses. Pricing, grouping, market-share handling, product/list availability and downstream whole-reimbursement interpretation are explicitly outside this clinical-only admission. The separate [October 2 Pricing Commission decision](https://www.resmigazete.gov.tr/eskiler/2026/10/20261002-7.pdf) is an additional unreviewed pricing dependency.

The October 2 SUT amendment and consolidation are separately pinned. Consolidated annotations identify October 10 for the named article 2 drug successors and November 2 for organ-transplant article 1. Article 4(b) has September 5 retroactive applicability. Existing announced-future selection remains intact; publication, extraction `is_in_force`, workbook filename, or observation date must not replace the specific effective date.

## Deployed evidence and failure behavior

Runtime depends only on repository-local reviewed artifacts: the catalog, strict receipt, positive official-observation captures, exact clause/context bindings, the existing mecasermin historical-evidence file, and the deployed clause corpus. It does not read a QA `/tmp` or shared-folder DOCX. All new runtime files must ship with the code.

The original primary documents were verified offline. October consolidated DOCX SHA256 is `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573`; amendment DOCX is `a717ac7e9e932449461c353fcb3d3845ed834d104f35a75505c53185bbcfccbb`; August DOCX is `e6697a42cb24e20335c0a59ef9f9b7554d95a2db9a0280a90617564df9538821`. Primary-page captures are explicitly labeled observer transcriptions from successful live accessibility results, not original HTML/download bytes.

Each claim rechecks deployed evidence hashes and resolves content-pinned clauses against the installed corpus. Parent/context anchors remain part of the binding, including repeated ravulizumab/satralizumab text. Missing files, corrupt proof, moved/wrong-context or changed source, malformed/ambiguous authority, unknown history and uncovered service dates all fail closed before clinical predicates. The bounded status and actionable `next_action` survive canonical/cache/API/UI transport. They are display-only provenance, never editable clinical facts.

The exact published-parent clause corpus is also pinned: SHA256 `9639c4578223ff46a40499270af5043d229ab2a1a1c3783114b43b64787384ac` (789,732 bytes), independently confirmed equal to the frozen parent and pristine main, not the research-only October reconstruction. Its bytes are rehashed before each admission and the parsed frame is cached by those exact bytes, so a warmed corpus cache cannot hide deletion, modification, same-section parent relocation or an approved renewal. Deliberately, even an unrelated corpus change requires reviewing and updating this compatibility pin; bot ingestion alone does not grant clinical authority.

## Reproducible verification

From the deployed repository root:

```sh
python scripts/sut/verify_clinical_source_authority.py --check --json-output /tmp/source-authority-assets.json
python -m pytest -q tests/unit/domain/prose_rules/test_clinical_source_authority.py tests/unit/domain/test_mecasermin_request_integration.py
python scripts/sut/compile_rules.py --check
python scripts/sut/audit_manifest_parity.py --drug-only
```

The first command enumerates the complete repository-local asset closure and verifies source identity. Run it again on the exact published parent plus selected delta, without access to research-only files. Preserve that report in the review packet. Full backend/frontend gates and existing temporal, runtime-observation, source/coverage and surfacing audits are still required; this narrow verifier does not replace them.

## Refresh procedure

1. Read the live official SGK SUT listing, Gazette daily issue and advertised supplements on the target review day. Capture exact links, issue/date, observation timestamps and readable text/bytes. A stale cached listing, unavailable official page or no search hits cannot establish currentness.
2. Read every relevant new publication, including non-SUT regulations that may affect dependencies. Review named clinical/report clauses separately from pricing, lists, groups and general reimbursement. Record excluded dependencies. If a source or scope is unclear, leave admission blocked.
3. Verify official downloaded document bytes against their SHA256. Re-extract selected clauses using the existing extraction workflow into a separate review workspace. Compare normalized full text, structural identity, parent context and explicit effective annotations against the pinned binding snapshots. Do not use opaque positional IDs as source identity or import an unreviewed bot catalog.
4. Prepare a new immutable `SourceReviewReceipt` with positive observations for all required source categories and exactly the families reviewed. Pin the capture files. The catalog review timestamp/day must match that receipt. Updating only a date or the `positive_currentness_evidence` flag will fail validation.
5. Append a nonoverlapping admitted continuity window only for verified unchanged scope. Unknown historical starts remain null; do not interpolate between old snapshots. If wording/scope changed, stop extending the existing family and close it at the actual effective boundary. This catalog permits one compiled source version per family; a changed clinical criterion requires a separately reviewed evaluator/version-selection migration before admission. Adding duplicate family records is rejected. Preserve the existing separate announced-future amendment selection. Do not broaden this catalog to pricing or global eligibility.
6. Run the strict verifier, boundary and API tests, old-admitted-date clinical/observation parity, source integrity mutations, artifact compiler/coverage gates and relevant frontend checks. Verify asset closure on the exact release materialization. Review the diff and freeze evidence before publication.
7. If any step fails, retain prior covered dates, surface source review for new dates and make the missing official source/version actionable. Never substitute today's date for a missing service date or claim that the existing bounded window covers future law.

This procedure is manual/source-reviewed. No external monitor, bot PR128, automation, merge, deployment or VPS behavior is changed.
