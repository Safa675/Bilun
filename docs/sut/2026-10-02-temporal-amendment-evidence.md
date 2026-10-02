# SGK SUT temporal source review

This report records the first reviewed temporal base. The subsequent narrow thiotepa source-target correction is documented in [the follow-up report](2026-10-02-thiotepa-source-correction.md); its source-only successor supersedes the initial quarantine after exact-ID safeguards were implemented.

Review date: 2026-10-02 UTC

## Findings and disposition

The October 2 amendment and SGK consolidated source support **2026-10-10** as the effective date for the replacement trastuzumab emtansine provision, replacement pertuzumab provision, and new satralizumab provision. Satralizumab also enters the inpatient-only EK-4/G list under the same commencement provision. Do not substitute October 9 by manually counting business days: the consolidated SGK annotations expressly say October 10.

The August 29 primary amendment resolves thiotepa's legal relocation: Article 8(d) adds section 4.2.14.C(3)(zzz), Article 13 repeals section 4.2.61, and the consolidated source expressly dates both changes to **2026-09-05**. Legal-source uncertainty is resolved; complete automated clinical eligibility is not.

**Recommendation:** a narrowly scoped, source-only partial thiotepa route is supportable after the safeguards below are implemented and independently checked. Until then, leave it quarantined. Do not activate a complete reimbursement/compliance rule. The existing section 4.2.61 encoding mistakenly targets carmustine, so adding a thiotepa successor alone does not prevent the repealed rule from continuing to run for carmustine.

## Primary sources and hashes

### October amendment

- Publication: Resmi Gazete 2026-10-02, number 33388.
- Official SGK announcement: https://corum.sgk.gov.tr/duyuru/detay/02102026-Tarihli-ve-33388-Sayili-Resm-Gazetede-Yayimlanan-Sosyal-Guvenlik-Kurumu-Saglik-Uygulama-Tebliginde-Degisiklik-Yapilmasina-Dair-Teblig-2026-10-02-02-48-55
- Official DOCX, independently downloaded during this review: https://corum.sgk.gov.tr/Download/DownloadFile?f=006c75f8-7b03-4780-b946-a15c7831bea8.docx&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a
- SHA256: `a717ac7e9e932449461c353fcb3d3845ed834d104f35a75505c53185bbcfccbb`
- Bytes: 35,919. Identical hash to the supplied amendment DOCX.
- Existing catalog uses the same download identifier on kars.sgk.gov.tr. The independently retrieved corum.sgk.gov.tr file matches the catalog hash.

### October consolidated SUT

- Official announcement, retrieved successfully through a read-only HTTP request: https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06
- Official ZIP link extracted from that announcement: https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a
- Supplied ZIP SHA256, independently recomputed: `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61`
- Consolidated DOCX SHA256: `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573`
- The DOCX hash matches the corresponding member of the supplied ZIP.
- Paragraph locators below are zero-based indexes over all `w:p` elements in `word/document.xml`, including table paragraphs. They are not python-docx `Document.paragraphs` indexes.

### August amendment

- Publication: Resmi Gazete 2026-08-29, number 33355. SGK announcement date August 31 is distinct from legal publication date.
- Official announcement: https://sgd.sgk.gov.tr/duyuru/detay/29082026-Tarihli-ve-33355-Sayili-Resm-Gazetede-Yayimlanan-Sosyal-Guvenlik-Kurumu-Saglik-Uygulama-Tebliginde-Degisiklik-Yapilmasina-Dair-Teblig-2026-08-31-03-04-56
- Official DOCX, directly downloaded during this review: https://sgd.sgk.gov.tr/Download/DownloadFile?f=873126b6-2250-4c64-b0a4-fe910055fe11.docx&d=658f4ba1-b0e8-4dfb-8504-fa0b09e353e0
- SHA256: `ffd269486c0fb75a65321c0ebafb898bc74193125a49a916842bcc457c6ea491`
- Bytes: 77,751.

## Article and date mapping

| Provision | Legal amendment | Effective date and basis |
|---|---|---|
| 4.2.14.C(3)(ff), trastuzumab emtansine | October Article 2(a) | 2026-10-10; October Article 8(b) says five business days after publication; consolidated paragraph 5644 explicitly supplies the date |
| 4.2.14.C(3)(gg), pertuzumab | October Article 2(b) | 2026-10-10; same commencement provision; consolidated paragraph 5651 |
| 4.2.14.C(3)(aaaa), satralizumab | October Article 2(c) | 2026-10-10; same commencement provision; consolidated paragraph 6128 |
| EK-4/G entry 92, satralizumab | October Article 7 | Same effective date as Article 2 under October Article 8(b) |
| 4.2.14.C(3)(zzz), thiotepa addition | August Article 8(d) | 2026-09-05; August Article 24(a) says five business days after publication; consolidated paragraph 6125 explicitly supplies the date |
| 4.2.61 repeal | August Article 13 | 2026-09-05; same August commencement provision; consolidated paragraph 7536 explicitly supplies the date |

Other October changes demonstrate why publication date must not be applied globally: Article 1 has an explicit consolidated effective date of 2026-11-02 (paragraph 1096); Article 4(b) takes effect on publication with effect from 2026-09-05; Article 5 uses a separate five-calendar-day commencement formula; Article 6 has row-specific annex dates and marker-dependent rules. This review does not derive a numerical date for Article 5 or validate every Article 6 product row.

## Clinical deltas from October 10

### Trastuzumab emtansine

The replacement adds adjuvant monotherapy for qualifying HER2-positive early breast cancer after at least four neoadjuvant taxane and anti-HER2 cycles, with postoperative invasive residual disease over 1 cm in the breast or invasive residual disease in a lymph node. Maximum adjuvant treatment is 14 cycles.

The metastatic salvage branch requires prior trastuzumab and one line of taxane treatment, subsequent progression, the specified HER2 test result, and single-agent treatment until progression. Further single-agent or combination use after progression is excluded. The former categorical exclusion after any prior pertuzumab use is absent from the replacement. Both branches require the specified medical-oncology board report and medical-oncology prescription.

Unresolved implementation inputs include treatment setting and stage, prior regimen and cycle count, pathology and residual-disease measurement/site, monotherapy, treatment cycle count, progression, and board composition.

### Pertuzumab

The replacement adds qualifying neoadjuvant early breast cancer use with trastuzumab and chemotherapy, maximum four cycles. The text specifies locally advanced/inflammatory disease and T3-4 and/or node positivity.

The metastatic first-line branch retains ECOG 0-1, no previous systemic chemotherapy or trastuzumab for metastatic disease, the specified HER2 test result, and pertuzumab plus trastuzumab plus docetaxel until progression. It omits the predecessor's visceral-metastasis condition. The prior blanket exclusion after adjuvant/neoadjuvant trastuzumab is replaced by the stated 12-month relapse/progression condition. The source excludes recurrence/progression during treatment or within the first 12 months after completion, and permits the described combination after more than 12 months. Do not invent a day-count convention for the exact anniversary boundary without a defined clinical-date representation.

Progression precludes continuing/restarting pertuzumab as monotherapy or combination treatment. The docetaxel-toxicity exception permits continued trastuzumab plus pertuzumab. Medical-oncology board and prescribing requirements remain.

For both ff and gg, generic HER2 positivity alone does not verify the legal test criterion: the source requires IHC 3+ or positive FISH/SISH/CISH. Assay/method verification must remain explicitly incomplete.

### Satralizumab

The new provision requires high-activity, relapsing NMOSD, age at least 12 years and body weight at least 40 kg. Initiation conditions are conjunctive: AQP4 antibody positivity, EDSS no greater than 6.5, and at least one attack during treatment despite appropriate monotherapy dose/duration with at least two of the listed immunosuppressants (azathioprine, mycophenolate mofetil, cyclophosphamide, rituximab).

It permits initiation as monotherapy or with immunosuppressive treatment. A tertiary-care board report with three neurologists is required, valid for at most six months, with neurologist prescribing. After six months of treatment, EDSS at least 8 requires discontinuation; EDSS must appear in every board report. October Article 7 additionally places satralizumab in EK-4/G's inpatient-only list. Report-duration or antibody checks alone cannot establish reimbursement eligibility.

## Thiotepa clinical and encoding review

### Source differences

Former section 4.2.61 required patient-specific Ministry of Health off-label approval, the specified tertiary official/public provider context, a six-month board report containing pediatric hematology-oncology or adult hematology, and prescribing by those specialists. For Hodgkin/non-Hodgkin lymphoma transplant-conditioning use, subject to the source's CNS-lymphoma exception wording, the report had to document carmustine contraindication. Approval date and duration had to be reported.

New zzz describes thiotepa **combined with other chemotherapy products**, in adult/pediatric hematology patients' conditioning before allogeneic or autologous hematopoietic progenitor-cell transplantation, or for adult/pediatric solid tumors when high-dose chemotherapy with hematopoietic progenitor-cell support is appropriate. It requires a six-month board report including at least one pediatric hematology-oncology or adult hematology specialist, and prescription by the specified specialists.

The new provision does not repeat the former off-label-approval, tertiary official-provider, carmustine-contraindication, or approval-date/duration wording. They must not be carried forward as if part of zzz. This comparison does not prove that every independently applicable general SUT or other regulatory requirement has disappeared.

### Existing rule defects

Inspected the original and recovered temporal workspaces. In both, `data/gazette/prose_rule_sources/drug_indication/4.2.61.yaml` and the generated corpus encode the old provision as:

- Rule ID `4.2.61.onco.carmustine_offlabel_bmt_conditioning_coverage`
- Drug names: `karmustin`
- ICD-10 codes C81-C85, six-month report, hematology specialties
- Source reference `4.2.61.(1)#fbf73d45`

This is a drug-targeting error: the section heading is Thiotepa; carmustine occurs in a contraindication condition. A successor matched only against thiotepa aliases will not intercept this old carmustine rule.

A separate generic rule, `4.2.14.C.tiotepa_fikra2_heme`, targets only `tiotepa`, uses broad cancer/myeloproliferative ICD ranges, and permits medical oncology or hematology. It is not a faithful encoding of the specific new zzz branches, six-month report, and specialist/board requirements.

### Narrow safe disposition

A partial-source thiotepa route is supportable only if all of the following hold:

1. Correct provenance to August 29, Article 8(d), with the August DOCX URL/hash above. Preserve the October consolidation as corroborating evidence rather than calling it the initiating amendment.
2. Select the successor only for service dates on or after 2026-09-05. Unknown/invalid dates require review. Historical lower bounds remain unverified.
3. Keep the result explicitly partial/manual-review-required even when elementary report checks pass. Do not emit definitive compliant/eligible/reimbursable status.
4. Leave combination regimen, qualifying transplant or solid-tumor context, high-dose chemotherapy suitability and progenitor-cell support, exact board composition, specialist qualification, and report duration as explicit unresolved inputs wherever not faithfully implemented.
5. Date-suppress or quarantine the repealed section 4.2.61 rule by its exact section/rule identity, including its erroneous carmustine match, from the repeal date. Do not rely exclusively on drug-name successor matching. Do not silently relabel or broadly rewrite historical carmustine behavior as part of this narrow change.
6. Ensure the generic tiotepa rule cannot produce an affirmative current determination that bypasses the successor review route. Test all three aliases: `thiotepa`, `tiyotepa`, and `tiotepa`.
7. Test September 4/5 boundary behavior, missing/invalid service date, thiotepa aliases, and carmustine against the repealed section. Preserve unrelated carmustine rules.

If these interaction safeguards are outside the current implementation scope, keep thiotepa quarantined and report the legal relocation as verified. Legal-source verification alone is insufficient to activate the existing encoded rule.

## Historical predecessor boundaries

October consolidated paragraphs 5645-5646 and 5652-5653 retain the struck ff/gg predecessor texts. They match the supplied August extracted evidence. Their safe successor boundary is exclusive 2026-10-10, so the predecessor source is appropriate for the October 9 service-date scenario.

The ff annotation cites initial effectiveness on 2016-08-30. The gg introduction cites 2016-10-15, but the full predecessor includes a docetaxel-toxicity amendment effective 2020-06-24. It would be incorrect to backdate that entire combined gg text to 2016. Original historical acts were not comprehensively reviewed; historical lower bounds remain explicitly unverified.

Satralizumab has no predecessor in the inspected evidence: its only main-DOCX occurrence is the newly added provision. This does not establish that all possible prior reimbursement mechanisms were unavailable.

## Text hash verification

All supplied catalog paragraph text was independently compared with the consolidated DOCX. SHA256 values below use the newline-joined, stripped paragraph texts represented in the catalog:

- ff successor: `8ab002c60a7b1f2237f8ca4ea357860371b7341e8188d8b197cf4693a012e48a`
- gg successor: `ff744c1ed929ed7ce9295526e7689c43da3f73bf7df723858ee017ee626b4b24`
- zzz thiotepa: `cd575654a4f7799ef6e73ddeb151b1c195b9d90512d5afe9497f6a25304f7435`
- aaaa satralizumab: `3d18fa0551375e910ce2ef7de20e4d54f48d8607a601ac5f339d5472ff339677`
- ff predecessor, paragraphs 5645-5646: `070528de04342e442e995c78aed856ab70b5811e7fcf8289249d9c5736662fee`
- gg predecessor, paragraphs 5652-5653: `69bd69b0445082b603c3e0dd9ccc852082b3148465d458fdaaa71d69602d6bfd`

The catalog includes HER2-assay and satralizumab EK-4/G unresolved inputs. Thiotepa remains excluded from loaded rules; its quarantined record uses the verified August provenance. Clinical/rule-interaction safeguards remain the activation concern.

## Verification limits

This was read-only implementation research. The source DOCX was downloaded and rendered, and this requested report was written; no implementation files, merges, or deployments were changed. Both October amendment pages and the relevant August amendment pages 2 and 10 were visually inspected. Consolidated evidence was checked structurally, including struck predecessor runs and explicit commencement annotations. Public web retrieval confirmed official SGK announcements and their attachment links; direct Gazette pages were unavailable through the web tool. No conclusion relies on third-party summaries.
