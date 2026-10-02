# Thiotepa source-target correction and September 5 relocation

This is a separate, review-only overlay on the October temporal base. It does not change the first temporal packet's October 10 dates.

## Verified authority

The official August 29 amendment (Resmi Gazete 33355) adds thiotepa 4.2.14.C(3)(zzz) in Article 8(d), repeals 4.2.61 in Article 13 and provides commencement in Article 24(a). The official October consolidation explicitly annotates both addition and repeal as effective **2026-09-05**. This date is distinct from the October 10 ff/gg/aaaa group; it is not inferred from October publication or a blanket date.

- August DOCX: https://sgd.sgk.gov.tr/Download/DownloadFile?f=873126b6-2250-4c64-b0a4-fe910055fe11.docx&d=658f4ba1-b0e8-4dfb-8504-fa0b09e353e0
- August SHA256: `ffd269486c0fb75a65321c0ebafb898bc74193125a49a916842bcc457c6ea491`
- October consolidated ZIP: https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a
- ZIP SHA256: `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61`
- Consolidated DOCX SHA256: `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573`

Paragraph indexes are zero-based all-`w:p` XML indexes. Paragraphs 6125–6127 contain the new thiotepa provision. Paragraph 7536 supplies the repeal annotation, and 7538 explicitly names Thiotepa as the former section's medicine. Paragraph 7539 mentions carmustine only as a contraindication condition for thiotepa use. These are source evidence, not a claim that the raw struck text is an unambiguous complete historical consolidated version.

## Runtime boundary

The successor is selected from September 5 for `thiotepa`, `tiyotepa` and `tiotepa`. It remains manual-review-required: combination treatment, qualifying transplant/solid-tumor and progenitor-cell context, and board composition are incomplete. Elementary report-presence, exact six-month duration and stated specialist checks cannot certify eligibility or nonpayment.

Before September 5, the generic tiotepa rule is not used as proof of historical applicability. The result records `historical_source_unverified`. No lower bound is invented and the distinct old off-label/provider/contraindication requirements are not silently erased or treated as satisfied. Missing/invalid dates remain unresolved.

The exact old ID `4.2.61.onco.carmustine_offlabel_bmt_conditioning_coverage` is suppressed by a separately source-pinned correction record. This medicine-target error exists on both sides of repeal; no date makes a thiotepa provision a carmustine provision. Both existing medicine aliases, `karmustin` and `carmustine`, receive the same guarded review; the old defective rule's one-name list is not used to delimit the family. Only that exact ID is removed. A different rule on the same section is not automatically suppressed.

## Preserve real carmustine scope

The current source separately contains carmustine in 4.2.14.C(3)(ğğ), paragraphs 5664–5666: brain-tumor criteria and Hodgkin/non-Hodgkin lymphoma transplant-conditioning criteria. Thus removal of the wrong thiotepa-derived ID must not fabricate a carmustine lymphoma denial based only on the remaining encoded C71 route.

The existing `4.2.14.C.carmustine_brain_tumor_board` rule is preserved unchanged. This overlay does not claim it encodes all current clinical conditions. When an independently matching retained route exists, evaluation proceeds normally. Otherwise a case that would have relied on the mis-targeted ID gets explicit `source_target_mismatch` review with the excluded ID and repeal date, never a manufactured `indication_mismatch` or automatic payment clearance. The unencoded genuine carmustine lymphoma conditions remain open for separate source-complete work.

## Verification

Seventy-eight focused regression cases cover September 4/5/6, all three thiotepa aliases, absent dates, exact duration, exact-ID-only suppression, both pass/fail states of the unaffected C71 route, and public projection of the source correction. The 28 initial cases failed against the unchanged October base before implementation. Full backend fixture/CI limitations remain as documented in the first packet.
