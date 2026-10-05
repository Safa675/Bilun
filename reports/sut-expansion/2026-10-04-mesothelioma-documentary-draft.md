# Pleural mesothelioma documentary draft — closed release gates

This packet prepares four necessary documentary observations for the existing pemetrexed and raltitrexed malignant pleural mesothelioma routes. It does not admit a new clinical family, establish complete clinical eligibility, decide payment, or extend the source's historical or current date coverage. Both **exact source-date admission** and **independent interpretation release** remain false. Production checks must stay `not_evaluated` until both gates are separately released; complete candidate facts still produce a partial review result with `clinical_eligibility_complete=false`.

## Exact source and drug-parent bounds

The verified base is `499dff4c40298075d9c90d6254baf903266b6611`. The official [SGK consolidated SUT announcement](https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06) is dated 2 October 2026 and identifies the [official consolidation ZIP](https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a). Browsing successfully rendered the announcement; the web tool could not render the ZIP or the 4 October Gazette contents. The locally captured official bytes were inspected directly instead.

The original consolidated DOCX at `/tmp/bilun-official-2026-10-04/sgk-20261002-consolidated.docx` has 1,200,635 bytes and SHA256 `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573`. Its capture records the official ZIP URL and a 4 October 2026 18:10:41.246988 UTC observation (`/tmp/bilun-official-2026-10-04/capture-metadata.json:165`). The same exact DOCX hash and 2 October source observation are pinned in `data/gazette/clinical_sources/source_context_repairs_2026_10.json:2`. This report does not convert the later download observation into a new family admission.

| Drug route | Unique bounded source reference | Corpus identity | Active original DOCX boundary |
| --- | --- | --- | --- |
| Pemetrexed | `4.2.14.C.(2)#db104a38@under:4.2.14.C.m#ceda5531\|4.2.14.C.n#37b794b9` | `C005124` | `m)` parent at body paragraph 5348; pleural child 5350; next `n)` parent 5352 |
| Raltitrexed | `4.2.14.C.(2)#db104a38@under:4.2.14.C.ö#c0b8128e\|4.2.14.C.p#8ad3f65a` | `C005150` | `ö)` parent at body paragraph 5374; pleural child 5376; next `p)` parent 5377 |

Indices above are zero-based `word/document.xml` `body/w:p` indices. They are not stable corpus IDs. The older deployed corpus records paragraphs 5414 and 5440 for the two child identities; the bounded resolver independently returns exactly `C005124` and `C005150` for the respective references despite these positional differences. Both children have normalized active-text SHA256 `db104a380650f7637808fbeb43943f2adaf85b485dc8ac4b97f974be77bd8224`. Direct XML inspection found no struck runs in either child. Their text is identical, so the unsuffixed child hash alone cannot identify the medicine parent.

Repository evidence: `data/gazette/clinical_sources/source_context_repairs_2026_10.json:29` and `:40`; authored routes in `data/gazette/prose_rule_sources/drug_indication/4.2.14.C.yaml:2599` and `:2654`; prior independent limitations in `reports/sut-expansion/2026-10-02-source-context-review.md:8` and `:27`. The captured original transcript exposes the parents/children at `/tmp/bilun-official-2026-10-04/sgk-20261002-consolidated-observer-text.txt:5353` and `:5379`.

## Four supported observations

The two exact drug children support the same conjunction:

1. The diagnosed malignancy is **pleural mesothelioma**. The source does not equate the entire C45 family with pleural disease. Explicit nonpleural disease, an unknown site, and C45 alone stay unresolved for this documentary route. An explicit pleural fact must not override contradictory nonpleural evidence.
2. **Three specialist physicians** prepare the health board report. Count concerns distinct specialist physicians who prepare the applicable report, not three different specialties, the length of a specialty list, or unrelated physicians elsewhere in the record. Generic report presence supplies no count evidence.
3. The **treatment protocol is shown in that health board report**. A free-standing protocol elsewhere in the chart or a generic report flag does not establish this relationship.
4. The prescription is made by a **specialist physician** on the basis of the report. A generic physician label or report presence does not establish specialist status. The draft's explicit specialist-prescriber fact checks the specialist status only; the separate prescription-to-report relationship remains unresolved among the remaining clinical criteria. It must be independently interpreted before any future release, rather than inferred from two present records. The child specifies no named specialty list, report duration, dose, line of therapy, or facility level. Oncology, chest medicine, or the colorectal facility alternatives must not be copied into this child.

The original wording contains the short phrases “üç uzman hekim”, “tedavi protokolünü gösterir” and “uzman hekimlerce reçete edilir”. These are separate facts; one true report flag cannot satisfy their conjunction. The source-only packet explicitly retained each as unimplemented (`source_context_repairs_2026_10.json:37` and `:48`).

The [official CDC/NCHS ICD-10 tabular list, 2025](https://www.cdc.gov/nchs/nvss/manuals/2025/2e-vol1-2025.html) separately confirms the classification distinction: C45.0 identifies pleural site, C45.1 peritoneum, C45.2 pericardium, C45.7 other sites, and C45.9 unspecified site. This classification source supplies no Turkish reimbursement authority, service-date admission or patient diagnosis. In the candidate only, an observed C45.1, C45.2 or C45.7 alongside an explicit pleural fact blocks that conflicting scope as unknown. C45.0, C45 and unspecified codes never supply a missing pleural fact. Absent code context adds no inferred diagnosis; the helper's other necessary observations remain incomplete clinical evidence.

## Count interpretation and candidate cases

The child says three specialists without a minimum qualifier. General SUT `1.10.2.(1)#5bc0db34` (`C000475`, active original body paragraph 739) separately describes three specialists from the relevant branch and, where that composition is unavailable, an alternative board of **at least three** specialists selected with the relevant specialist. The general clause is active and unstruck; see the captured original transcript at `/tmp/bilun-official-2026-10-04/sgk-20261002-consolidated-observer-text.txt:744`. This broader context prevents treating a fourth specialist as an established prohibition while also requiring independent interpretation before automatically accepting every larger board.

The closed draft therefore uses the conservative candidate comparison below. It is a documentary candidate, not an admitted clinical or payment result.

| Candidate evidence | Candidate observation | Runtime with closed gates |
| --- | --- | --- |
| Report present, missing one or more of the four facts | `unknown`; report alone cannot clear scope | `not_evaluated`, review |
| Nonpleural C45 or unknown site | `unknown`; preserve unresolved scope | `not_evaluated`, review |
| Explicit pleural site; 2 distinct specialist report preparers | Count requirement not met | `not_evaluated`, review |
| Explicit pleural site; 3 distinct specialist report preparers | Count observation met | `not_evaluated`, review |
| Explicit pleural site; more than 3 specialist report preparers | `unknown`; count interpretation unresolved | `not_evaluated`, review |
| Protocol explicitly absent from the board report | Protocol requirement not met | `not_evaluated`, review |
| Generic physician or unknown specialist status | Specialist status unresolved | `not_evaluated`, review |
| Explicitly non-specialist prescriber | Specialist-prescribing requirement not met | `not_evaluated`, review |
| All four candidate observations met | Partial documentary candidate only | `not_evaluated`, review; `clinical_eligibility_complete=false` |

Candidate tests may prove the fact comparisons in an isolated helper. Runtime tests must separately prove that the helper's hypothetical passes/failures are not promoted to authoritative checks while the two release gates are closed. Candidate failures are not reimbursement denials. Generic existing specialty strings must not manufacture authenticated specialist status or specialist count.

## Date admission and independent interpretation limits

`source_context_repairs_2026_10.json:4` explicitly leaves the legal effective interval unestablished; the prior report repeats the historical limitation at `2026-10-02-source-context-review.md:27`. A nearby 2015 annotation after the pemetrexed block is not sufficient evidence for the complete history of both drug-specific children or every general report dependency. The corpus's `source_effective_date=2026-08-29` describes its consolidated source snapshot; it must not become an invented clause-specific commencement date.

The repository's existing official review receipt names exactly 12 families (`data/gazette/source_authority/review_receipt_2026_10_03.json:7`). It does not name this new mesothelioma documentary family. The existing 12-family renewal PR #150 therefore supplies no automatic admission for it. Runtime source authority already requires the exact family/version/date binding and rejects a reviewed-continuity window if its receipt omitted that family (`src/bilun/domain/prose_rules/_drug_indication/source_authority.py:255` and `:267`). It preserves review when a family, service date or admitted window is unavailable (`:311`). This draft does not modify `clinical_versions.json`, a receipt, binding evidence, or the corpus.

The 4 October capture's [Gazette regular issue](https://www.resmigazete.gov.tr/eskiler/2026/10/20261004.htm) transcript contains no SUT amendment title, while its [Gazette homepage](https://www.resmigazete.gov.tr/) capture advertises the last supplement as 6 September. Those bounded observations were read from the existing official capture (`/tmp/bilun-official-2026-10-04/rg-20261004-daily-contents-observer-text.txt:7` and `/tmp/bilun-official-2026-10-04/rg-homepage-20261004-observer-text.txt:7`); they do not guarantee later publication absence or admit this family. The [official 2 October amendment announcement](https://www.sgk.gov.tr/duyuru/detay/02102026-Tarihli-ve-33388-Sayili-Resm-Gazetede-Yayimlanan-Sosyal-Guvenlik-Kurumu-Saglik-Uygulama-Tebliginde-Degisiklik-Yapilmasina-Dair-Teblig-2026-10-02-02-48-55) was also successfully browsed. Its captured amendment text changes `ff`, `gg` and adds `aaaa` in section 4.2.14.C; it does not independently establish the history or admission of the `m`/`ö` mesothelioma children.

Before future authoritative execution, a separate owner must admit exact documentary family/version/source/date evidence, including actual service-date coverage and applicable general report context. A separate independent interpretation release must approve the meaning of the necessary observations and preserve the unresolved boundaries. Neither gate follows from a fresh download, a generic source-review receipt, passing software tests, or candidate facts alone. Missing dates, uncovered history and later dates remain review; today is never substituted for the actual service date.

## Compatibility and verification scope

Pemetrexed's NSCLC child (active original paragraph 5349) and raltitrexed's colorectal child (5375) remain separate routes. The colorectal child explicitly has its own oncology-member and prescribing/facility alternatives; neither those facts nor the NSCLC duration/branched prescribers transfer into mesothelioma. The current authored mesothelioma rows retain `source_clinical_scope_incomplete=true` and `verification_status=ai_generated_pending_review` (`4.2.14.C.yaml:2611` and `:2666`).

Required focused cases are: strict typed input and invalid values; report-only; missing/contradictory/nonpleural site; 2 versus 3 specialists and greater-than-3 uncertainty; missing protocol and protocol/report relationship; generic versus explicit specialist prescribing; all-clear still partial/review; both closed release gates and exact date absence; parent-bound source identity; API/UI evidence parity; and unchanged NSCLC/colorectal behavior. Full CI, exact-head verification and independent code review are separate implementation evidence. This source report records no software-suite pass.

Read-only verification for this report reproduced both unique bounded resolver identities, compared the active original DOCX text and hashes with the pinned records, inspected strikethrough state and general board context, and checked the existing family admission contract. No source/corpus catalogue was edited. The temporary original captures aid review but are not a new deployed runtime dependency. The unresolved source-date and independent interpretation releases are deliberate blockers to activating clinical authority, not blockers to the authorized closed draft.
