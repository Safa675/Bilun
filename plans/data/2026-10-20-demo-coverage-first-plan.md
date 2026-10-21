# Demo coverage-first plan: the bills after S8 (revision 2, work-package schedule)

Date: 2026-10-20 (revision 1), 2026-10-21 (revision 2)
Status: **plan only.** No code, data or gate was touched; every number marked ✓ or called "skeleton" was measured in memory (a scratch harness that edits copies of the 9 claims tables, rebuilds the dataset through the real loader and calls `compute_patient_billing_report`; nothing was written to the repo); the rest is file:line evidence from read-only research passes, marked "research" where a probe gave the figure. Branch `claude/clever-roentgen-5cbbda`; revision 1 is commit `97c3b825` (base `main` 4def9577); revision 2 is built on `main` be4b9ec7 (the all-diagnoses fix #333 is in; merge commit `6e552ef0`).
Ask (Safa, 2026-10-20): "growing 8 patients to 50 adds nothing by itself". The demo data should trigger engine rules that no current patient triggers, and some patients should carry several bills (the legacy 50 had them).
Answers (Safa, 2026-10-21, relayed by the orchestrator session): follow-up bills on **all** patients; build all of it; add the chronic-report column; no second basamak-3 facility; engine issues #335, #336, #337 filed, data production first (recorded in §10).
Revision 2 changes (against revision 1): the answers are recorded (§10); follow-up bills on S1–S8 get story cards F1–F8 (§5.5) and three stories of revision 1 are re-hosted on them (§5.2); the chronic-report slice is specified (§7.4); the plan is turned into a **strictly sequential schedule WP2–WP19** of session-sized work packages (§6); matrix, targets and costs are refreshed for the enlarged scope. **WP1 (slices G0 + G12 and story S9) was built by the session `demo-wp1-g0-g12-s9` (commit `bbd4b5fc`, CI-image gate green, push and PR pending when this was written); this plan takes it as given and does not re-plan it.** Revision 2.1 (same day, after WP1): WP1's deviations are folded in (S9 facts: anaesthesia `550220` and a silent clean twin; the count pins move to WP2 as step G0b; story ids fixed in §5.1a; WP1 as delivered in §6.1 rule 6).
Companion files: `reports/synthetic-data/2026-10-20-demo-coverage-matrix.csv` (the 20 blocks and 25 Wave A groups), `reports/synthetic-data/2026-10-20-demo-coverage-wavea-rules.csv` (all 528 Wave A rule ids: group, class, evaluated/matched on which of the 8 patients, cause, candidate bill, which work package lit it in the skeleton).
Existing design this plan builds on: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`, `plans/data/2026-10-15-showcase-stories-draft.md`, `data/synthetic/pathways/README.md`, `data/synthetic/faults/README.md`, `reports/synthetic-data/2026-10-17-pathways-judgment-list.md`.

Contents: 1 Where the demo stands · 2 Coverage matrix (blocks, Wave A groups, levers, specialty breadth) · 3 Capability map for the finished engine work · 4 Multi-bill patterns · 5 Bill list and cards (new patients S9–S21, follow-ups F1–F8, conditional X1–X7) · 6 Execution schedule WP2–WP19 · 7 Generator slices, data-model gaps, the chronic-report slice, the pin classes · 8 Engine issues · 9 Measurement · 10 Decisions and open points · Appendix A never-evaluated Wave A rules by cause · Appendix B per-patient skeleton numbers · Appendix C method, limits and what is unverified.

## Kısaca (Türkçe)

1. **Ne değişti:** 21 Ekim cevaplarınız plana işlendi (§10). Plan artık yalnız yeni hastalar değil, **S1–S8'in kendilerine de takip faturaları** ekliyor: sonuç **16 hasta, 42 fatura** (bugün 8 hasta, 8 fatura). Hasta sayısı hedef değil; her fatura adı konmuş bir blok, bir Wave A kuralı ya da bir çok-fatura örüntüsü için var.
2. **Bugün** (`main` be4b9ec7'de yeniden ölçüldü, 4def9577'ye göre değişmedi): 20 rapor bloğundan 9'u çıktı veriyor; Wave A'da 528 kuraldan 273'ü değerlendiriliyor, yalnız 14'ü eşleşiyor, mali satır yok. Katılım payı düzeltmesi uygulama yolunda 11, betikte 7 (#333'ün etkisi).
3. **Hedef** (WP19 sonu, iskelet ölçümü): 15 blok, 292 değerlendirilen kural, 25 eşleşen, satırı olan 35 (12'si radyoterapi, durumu "unavailable"), 10 yeni bulgu türü. İlk Wave A mali satırı WP5'te (YBÜ→servis devrinde 510010).
4. **Takvim:** WP1 (G0 + G12 + S9) yapıldı (commit `bbd4b5fc`, CI-imajı kapısı yeşil; push/PR bekliyor). WP2–WP19 **kesinlikle ardışık**; her biri bir oturum ve bir PR, bir sonrakine sizin push/PR/merge onayınızla geçilir. Toplam 62,75 iş günü (WP1 dahil 66,25; klinik inceleme ayrı). Koşullu kuyruk (≈ 20,75 gün) sizin sözünüze kadar başlamaz.
5. **En riskli adım WP4** (çok-encounter jeneratörü). Kabul ölçütü: mevcut 12 tablo ve kayıt bayt bayt aynı çıkar, S1–S8 kanıtları değişmez. Ondan önce yalnız tek-faturalı, blok yakan hikâyeler gelir (S9, S11, S12).
6. **Yeniden konumlama:** önceki sürümün S13, S16, S19 hikâyeleri yeni hasta olmaktan çıktı; kuralları S2, S4, S5, S6, S7, S8'in takip faturalarına taşındı (19 yerine 16 hasta). Her faturada en fazla bir hata; bazı faturalar hatasız (ör. S2'nin raporlu kontrolü).
7. **Kronik rapor sütunu** WP8'de eklenir (2,75 gün) ve yalnız S2 taşır. S2 "kısmi muaf"tan "muaf"a geçer, ilk parasal muafiyet satırı WP9'da görünür (≈ 17 TL); S3–S6 kısmi kalır ve arayüz "EK-1A eşleşti, rapor yok" der (5 ekranda yeni metin, EN/TR).
8. **Karanlık kalacaklar, adlarıyla:** `drg_uplift`, `care_setting_review`, YBÜ +%100 (ikinci basamak-3 tesis yok); `drg_package_adequacy`; `blood_uplift` (#336 sonrası); `material_uplift` (EI-10 doğrulamasına bağlı). Veriyle tavan 15/20 blok.
9. **Motor:** #335, #336, #337 açık; veri bunları beklemiyor. Bugün hiçbir şey göstermeyecek "uyuyan" faturalar var (F1 b3, X6, X7). Yeni motor sorunu **EI-25**: muaf hastada §1.8.2 ilaç katılım satırı düşüyor, oysa EK-1/A yalnız §1.8.1'i muaf tutar.
10. **Açık soru yok;** iki küçük varsayılan §10.3'te.

## In one paragraph

Wave A and the 20 report blocks are mostly dark for the 8 showcase patients not because the patients are too few but because each patient is one clean-or-faulty bill of one kind. The plan therefore adds *bills*, not patients: each is a clinically coherent step in a patient's timeline (a precursor visit, a readmission, a control, a second device) or the start of a new patient, and lights something no current bill lights (a silent block, a Wave A rule, a cross-bill rule that no single bill can trigger). After Safa's answers of 2026-10-21 it covers all patients: 8 new patients (S9–S21) and follow-up bills on the 8 showcase patients (F1–F8), 42 bills in all, in nineteen strictly sequential work packages. Most of the effort sits in the generator (one recipe = one patient = one claim today), so the schedule prices the generator slices separately from the bills, pays each slice once, and puts the riskiest change (multi-encounter, WP4) early, with byte-identical committed data as its acceptance test. The six dark blocks that data alone can light are lit by WP7 (9 → 15 blocks with output); the rest of the schedule adds Wave A rules, finding kinds and the multi-bill patterns, and migrates the pins of the existing patients one patient at a time.

## Reading guide

| Term | Meaning in this plan |
|---|---|
| **block** | one of the 20 report blocks (`BILLING_BLOCK_SPECS`) |
| **block with output** | the block's primary list is non-empty on at least one patient (primary lists in §9.2). Baseline 9 of 20 |
| **Wave A rule** | one of 528 rule ids in 25 groups (`wavea_full_evidence.py`: 18 focused detector groups = 32 ids, 7 broad prose families = 496 ids) |
| **evaluated** | at least one evaluation of the rule id has `evaluation_status == "evaluated"` (the rule looked and may have found nothing). Baseline 273 |
| **matched** | at least one evaluated row has `decision == "matched"` (the rule applies to a claim). Baseline 14 |
| **rule with a row** | the id appears in the reviews, advisories or financial rows of the Wave A evidence (a focused detector can also end as a `claim_compliance` finding without such a row). Baseline 14 (8 review + 6 advisory + 0 financial) |
| **finding kind** (K) | a new row kind inside an already lit block or in `claim_compliance`: an action `surface:kind`, a drug status, an audit-exposure kind, a MIAT violation |
| **N** (value of a bill) | newly triggered items = new blocks (B) + new matched or row-bearing Wave A ids (M) + new finding kinds that are not already counted (K). E (newly evaluated Wave A ids) is reported next to it, not added |
| **skeleton** | a scratch bill with the codes, claim types, department, dates and lines a planned bill would have, built only to be measured. Skeleton numbers are not generator output; the clinical content is not complete |
| **data-fixable / model / engine / facility** | what must change for a silent row to fire (definitions at the top of §2) |
| **WP** | work package: one session, one PR on `main`, strictly after the previous one and after Safa's merge word (§6) |
| **S / F / X labels** | `S9…S21` new-patient bills; `F1…F8` follow-up bills on the patients of S1…S8 (`F4 b2` is the second bill of S4's patient; `b1` is always the existing admission); `X1…X7` conditional extensions. Plan labels are names in this document, not generator story ids (§5.1) |
| **bill-scoped** | a context or proof built over one claim (`build_bill_claim_context`) instead of all claims of the patient |
| **dormant bill** | a bill whose data is plausible today but whose rule cannot be derived yet (engine-first, #337); built now without a fault record, its expected hit documented |

## 1. Where the demo stands (re-measured on `main` 4def9577, unchanged on be4b9ec7)

Both scripts of the orchestrator ran here in about 5.5 s each (`python ~/.cache/bilun-tools/demo_coverage_blocks.py <out.json>` and `python ~/.cache/bilun-tools/demo_coverage_inputs.py`, from the worktree root). **Every number of the brief reproduced** (20 blocks, 9 with output, 528 Wave A rule ids in 25 groups, 273 evaluated, 255 never evaluated, 8 review rules, 6 advisory rules, 0 financial, 1,106 missing-input evaluations over 107 names). Where this plan adds a number it says how it was measured. Re-run on 2026-10-21 after merging `main` be4b9ec7 (the all-diagnoses fix #333): blocks, Wave A figures and the per-patient table below are unchanged (the JSON output is byte-identical); only the copay count of the app path moved (§1.2).

### 1.1 Per patient (baseline)

| Patient | Blocks with output | Wave A rules evaluated | matched | review rules | advisory rules |
|---|---|---|---|---|---|
| 0001 (S1) | 6 | 256 | 7 | 4 | 3 |
| 0002 (S2) | 6 | 191 | 9 | 6 | 3 |
| 0003 (S3) | 7 | 264 | 9 | 6 | 3 |
| 0004 (S4) | 6 | 191 | 9 | 6 | 3 |
| 0005 (S5) | 6 | 254 | 7 | 4 | 3 |
| 0006 (S6) | 6 | 192 | 10 | 7 | 3 |
| 0007 (S7) | 4 | 231 | 4 | 4 | 0 |
| 0008 (S8) | 4 | 250 | 7 | 4 | 3 |

(Distinct rule ids per patient; the Wave A hand-over of 2026-10-20 counts evaluations, so 0005 reads 258 there. "Evaluated" is the weak word: of the 1,833 evaluated rows on the 8 patients, 1,771 are `not_matched` and 62 are `matched`, so this plan counts blocks and matched rules as the real targets and keeps "evaluated" as a secondary number.)

### 1.2 Three readings of the brief that did not reproduce exactly (item 2 and 3 updated 2026-10-21)

1. **"9 blocks with output" is a count of two different sets.** Script 1 prints "with >=1 opportunity on some patient: 5" (it reads only `opportunities`/`recommendations`). Script 2 prints nine keys, but one of them is `medula_rejection_playbook` with only a `required_inputs_missing` list (no real output), and it hides `billing_strategy` on purpose. The set that this plan counts (primary list non-empty, §9.2) is: `billing_strategy`, `copay`, `claim_submission_checklist`, `drug_indication`, `yatak_puani`, `refakatci`, `anestezi_puani`, `procedure_capture_gap`, `materials`. It is also nine, so the number agrees, but **do not compare the scripts' sets by count**: after S10 lights the playbook, script 2 would show no change for that block. §9.4 describes the measurement script (G12, built in WP1) with the §9.2 map.
2. The copay block shows **7** rate corrections with the two scripts and **11** on the app's path since #333 (P1 1, P2 2, P3 2, P4 2, P5 2, P6 2; it was 8 before: the new ones are the "EK-1/A ICD match without chronic health report" row on S4, S5 and S6 through their secondary codes): the scripts, like `engine_proof.py`, call `compute_patient_billing_report(pid, claim_context=ctx)` without the patient's `copay_exemption` and without the lab feed (`lab_df_pl`). A story aimed at the copay exemption or at the lab capture-gap must be measured through the cache/API path, not through the two scripts.
3. "The exemption check now reads all diagnoses" was **not in `main`** on 2026-10-20 (commit `3218922d` on another branch). It is in `main` since #333 (`be4b9ec7`): `collect_patient_diagnoses` (`src/bilun/domain/optimization/shared.py:58-105`) unions the diagnoses of every episode, principal codes first. Consequence: S4, S5 and S6 now match EK-1/A through a secondary code (G30.1 and I10; I10 and M81.09; I10) and show the partial state; the catalog still has no entry for G20, S72.00, J18.9, K80.2, K35.9, K42.9 and F05.1 (§7.4).

### 1.3 The fact that shapes the plan

The loader, the model and the engine already carry several bills per patient (`build_patient_claim_context`, `slice_for_claim`, `ctx.history`, per-bill reports; precedent `tests/unit/domain/billing/test_bill_billing_report.py:44-70`). **The blockers are in the generator**: `scripts/synthetic/cohort/` and the pathway/fault schemas assume "one recipe = one patient = one claim = one of eight stories". §7 lists what must change and prices it. Most of the effort of any work package is generator work, not story writing, and the answers of 2026-10-21 (follow-up bills on the eight existing patients) add the pins of those patients to it (§7.5).

## 2. Coverage matrix

How to read it. **Class** says what can fix a silent row:

| Class | Meaning |
|---|---|
| **DATA** | the tables already hold every column the engine reads; a story supplies the values (generator slices from §7 may still be needed to author it) |
| **MODEL** | a new column, or plumbing between an existing column and its reader, is needed first |
| **ENGINE** | the block or rule cannot fire for this demo even with ideal data (engine, corpus or vocabulary change) |
| **FACILITY** | needs a third-tier (basamak 3) facility header; the demo has one private basamak-2 hospital |

"✓" marks a trigger run in memory in this session (by me or by one of the read-only research passes; see Status). File:line evidence is from read-only research passes of the same day. Prices are the 2026-07-07 lists. Story ids refer to §5.

### 2.1 The 20 report blocks

| # | Block | Fires today | What it needs | Class | Evidence | Story |
|---|---|---|---|---|---|---|
| 1 | `billing_strategy` | all 8 (S1 package gap 4,122.06; S5, S8 package rows at 0 TL; 2–34 rows elsewhere) | a bill whose package/itemized choice the SUT decides | — (active) | `claim_strategy.py`; tier-3 "optional override" rows need FACILITY | S20 adds the day-case variant (no new row kind) |
| 2 | `copay` | S1–S7: generic §1.8.2 20 % drug row; EK-1/A "partial exempt" on S2–S6 (S4–S6 since #333); §1.8.3 material rate on S5; S7 acil exemption review. 7 corrections by script, 11 on the app path | money needs `copay_rate_applicable` True and billed > payable on a line, plus an exempt ground: status (yeşil kart, gazi, vatani hizmet), occupational context, acil, koruyucu. All columns exist but the generator hard-codes them (`compose.py:164-168`). **EK-1/A with a chronic report has no carrier yet (decided 2026-10-21: a nullable profile column, slice G13)** | DATA (status, occupational, acil) / **MODEL** (EK-1/A report) | `claim_copay.py:232-247`, `copay_line_waivers.py:174-211`; `optimization/copay_exemption_rules/ek1a.py:80`; `has_chronic_health_report` is passed by no caller (`src/bilun/cache/sut_context.py:508-516`, `aggregator.py:353-359`, `api/routes/optimization.py:147-151`); one default in `build_copay_exemption_input` serves all three (§7.4); ✓ with the report True: 20.0 waived on a 100/80 exam, without: `partial_exempt`, 0 TL | F2 b2 (WP9, after G13 in WP8) |
| 3 | `claim_submission_checklist` | S1–S6, S8: 19 items, **6 of 51 emit-able ids** (ORTAK-17/21/27/29, ORTOPEDİ-6, readiness `0704`) | new ids: poliklinik claim → ORTAK-5; drug flag False → readiness `0612`; TPN line → ORTAK-24; `acil` + "Acil Tip" + burn codes → ACIL-1; department names need Turkish letters | DATA | `fatura_inceleme_checklist.py:114-297`, `claim_readiness.py:117-170`; ✓ the planned stories add exactly **2 ids (6 → 8 of 51)**: ORTAK-5 (F4 b2, the first outpatient bill; later outpatient bills repeat it) and `0612` (S18) | F4, S18 |
| 4 | `drug_indication` | 19 evaluations on 6 patients; 1 violation (S6, amantadine without G20) | other statuses from the drug flags that exist on `DrugClaimLine` (1 of 19 lines sets them today); report duration needs the `DrugFlags` extension | DATA (+ G9) | ✓ `report_duration_mismatch` (F5 b5), `prescriber_specialty_mismatch` (S17), `missing_board_report` (S18) | F5 b5, S17, S18 |
| 5 | `yatak_puani` | 7 yatis claims (S2 +667.08; the rest are 0 TL rows) | a one-date stay (day bed 510120) needs `nights` 0 in the pathway grammar | DATA / generator (G3) | ✓ one-date stay, nothing billed: 44.45 action `yatak_puani_day_bed`; `yatak_puani.py:394-526` | F7 b2 |
| 6 | `refakatci` | 7 (S4 +370.50) | — | — (active) | `refakatci.py:161-166` | — |
| 7 | `anestezi_puani` | S3 (+928.09) | — | — (active) | — | — |
| 8 | `procedure_capture_gap` | S7 (+1,138.22) | EMR/PACS log; the lab feed (`lab_df_pl`) is a second path no script measures | — (active) | `lab_bill_merge.py` | — |
| 9 | `materials` | S5 (UTS violation 6,465.27 at risk; cement info) | MIAT interval needs two bills with the same EK-3/C-2 code; the composer reads EK-3/F-1 only; pre-auth needs a flagged line | DATA / generator (G7b, G5a) | ✓ MIAT: OP1000 crutch twice, 168 days < 365 → action `material_miat_interval`; ✓ `material_pre_auth` action; `miat_interval.py:51` reads `ctx.history` | F6 b2–b3 (MIAT), F2 b5 (pre-auth; conditional) |
| 10 | `lab` | none | two CBC lines (L107020 + L103120, or two L107020) on one date of one claim; `L103120` is not in `data/synthetic/reference/lab_reference.csv`, so the pathway check refuses it | DATA (G7a) | ✓ L107020 + L103120 same day: 5.88 TL `hemogram_unbundling`; `claim_lab.py:59-119` | S10 b1 |
| 11 | `session_uplift` | none | two operations on one date, the second billed below the strict rate; itemized pair at 0.25 (on the ladder) → 151.60 | DATA | ✓ S3 base + 615995 at 25 %: 151.60; at the correct 50 % the clean twin is silent (built in WP1: the review row appears only between the 30 % and 50 % readings, e.g. at 40 %); `session_uplift.py:109-118,385-397` | S9 |
| 12 | `blood_uplift` | none | a package line + a blood code (705371…) billed below 0.36 × `expected_payable_try`. **Closed while payable == billed** (loader default, composer, plausibility rule) | **ENGINE** (EI-2: price the ceiling from the EK-2/B list) | ✓ fires only with payable ≠ billed: 2,213.11 / 2,320.58; `blood_uplift.py:73-74`, `session_pricing.py:728-737` | F5 b3 (today shows the full-price audit instead; the uplift after #336) |
| 13 | `icu_puani` | none | an inpatient claim with ≥ 1 line 510090 or P552001-3/6-8; a row only if the ICU lines are billed **below** the expectation (a missing day-rate unit while packages are billed, or a price shortfall) | DATA / generator (G4a) | ✓ ICU stay, package at 50 %: row; clean ICU stay: 0 TL row; `icu_puani.py:277-368` | S11 |
| 14 | `yenidogan_yatak` | none | `Z38.x` or `P00-P96` diagnosis, or a department named yenidoğan/neonatal; ≥ 1 procedure line; a Kuvöz/Kot day not billed | DATA / generator (G4b) | ✓ Z38.0 + P07.3, 6 dates, Kuvöz on 3: 1,322.94; clean Kuvöz ×6: 0; `yenidogan_yatak.py:129-198,275-327` | S12 |
| 15 | `material_uplift` | none | one of 16 trigger codes billed without its paired EK-3 material. **12 pilot heuristics, `sut_derived_unverified`**; ceiling uses KDV 20 % while the demo bills ex-VAT, so the clean twin is not silent (549.17); the composer reads EK-3/F-1 only, so only 612480/612510 + AP1390 can be authored | DATA (one pair) / **verification** (EI-10) | `material_pairing_uplift.json` provenance note; `material_uplift.py:118-132` | X1 (conditional) |
| 16 | `procedure_addon_uplift` | none | colonoscopy 701450 (or the 5 other endoscopy triggers) billed, add-on 701460 absent that date; `sut_derived_unverified`; the engine cannot tell whether a polyp existed (EI-11) | DATA | ✓ 701450 alone: 263.92 + Wave A `GENEL CERRAHİ-2.kolonoskopi_ozefagogastroskopi_bundling` matched; the clean twin must bill the add-on at 30 % or 50 % (at 100 % it shows an audit exposure of 439.86) | S10 b2 |
| 17 | `drg_uplift` | none | package billed + billed itemized lines + `package_candidate` False + a DRG_OVERRIDABLE code at a basamak-3 facility; the builder forbids the shape | **ENGINE + FACILITY** | `claim_drg_uplift.py:67-146`; unit tests patch the resolver | — |
| 18 | `drg_package_adequacy` | none | billed package 609270 + billed 600150 (+600160). The **rule corpus is clinically incoherent** (609270 = biliary-fistula package, 609300 = islet-cell transplant, 600150/600160 = cheek tumour excisions) | **ENGINE** (EI-9) | `drg_package_adequacy_prose.json`; ✓ the shape fires with placeholders | — |
| 19 | `care_setting_review` | none | `gunubirlik` claim (or same-day yatis) at a **basamak-3** facility with a package and itemized alternatives; silent at the demo facility, and practically unreachable at catalog prices (EI-22) | **FACILITY** + generator | ✓ test claim fires at `egitim_arastirma`, silent at `2_3_basamak_ozel`; `care_setting_review.py:140-217` | — |
| 20 | `medula_rejection_playbook` | none (status `not_applicable`) | rows in `medula_rejection_events` (table exists, 0 rows) with a `sonuc_kodu` among the 11 playbook entries; the date must lie inside the claim's range (a real post-discharge rejection is refused by the loader, EI-18) | DATA / generator (G8) | ✓ event `0901` on the second CBC line of the ER bill: 1 playbook entry (and the `lab` row); `claim_medula_rejection.py:23-54`, `validation/links.py:134-140` | S10 b1 |

Reading of the table: **11 dark blocks = 6 DATA (lab, session, icu, yenidogan, addon, playbook) + 1 DATA with a verification gate (material_uplift) + 1 ENGINE-first (blood) + 3 not reachable by data (drg_uplift, drg_package_adequacy, care_setting_review)**. With the demo facility, data alone can take the cohort from 9 to at most 16 blocks with output (17 after the blood fix, #336); the schedule reaches 15 at WP7 and stays there (the 16th is `material_uplift`, X1, gated by EI-10).

### 2.2 The 25 Wave A groups (528 rule ids)

Wave A is 18 *focused detector* groups (32 rule ids, each wrapping a legacy detector) plus 7 *broad prose* families (496 rule ids). The classification below reads each rule's 8 evaluations (one per patient) and the builder that feeds its family; the per-rule table is in the companion CSV and every never-evaluated id is listed by cause in Appendix A.

| # | Group | Rules | Hit today | Checked, no hit | Needs a planted hit | Data-fixable | Input never produced | Engine unavailable |
|---|---|---|---|---|---|---|---|---|
| 1 | `treatment_pricing_2_4` | 202 | 0 | 128 | 0 | 6 | 5 | 63 |
| 2 | `fatura_inceleme_prose` | 91 | 7 | 83 | 0 | 0 | 1 | 0 |
| 3 | `drug_combination_4_2` | 53 | 0 | 6 | 0 | 0 | 0 | 47 |
| 4 | `gap_closing_misc` | 46 | 1 | 5 | 0 | 0 | 33 | 7 |
| 5 | `gap_closing_treatment_2` | 43 | 1 | 17 | 0 | 0 | 21 | 4 |
| 6 | `payment_method_2_2` | 42 | 5 | 18 | 0 | 4 | 4 | 11 |
| 7 | `dental_2_4_1` | 19 | 0 | 2 | 0 | 2 | 15 | 0 |
| 8–25 | 18 focused detector groups | 32 | 0 | 0 | 29 | 0 | 0 | 3 |
| | **Total** | **528** | **14** | **259** | **29** | **12** | **79** | **135** |

Column meanings. *Hit today* = matched on at least one patient. *Checked, no hit* = evaluated on at least one patient but never matched. *Needs a planted hit* = the focused detector ran on every patient and found nothing, and the projection **certifies a positive only** (`unavailable: detector_negative_not_certified`, `focused_rule_projection.py:759`), so the rule is evaluated only when a claim plants a hit. *Data-fixable* = the only blockers are lines or a claim type the builder can read. *Input never produced* = the rule's condition key is produced by no context builder. *Engine unavailable* = the evaluator marks it unavailable whatever the data.

**What this says.** Of the 255 never-evaluated rules, **214 (84 %) cannot be moved by any demo patient** (135 engine, 79 input never produced). Only 41 can: 29 focused detectors that need a planted hit and 12 broad rules that need a line or a claim type. And of the 29 focused ids, a planted hit makes only **11 evaluated**; 17 stay `unavailable` even on a perfect hit (their spec carries a `predicate_limitation`: 2 EK-2/D add-ons, 2 dental, 12 radiotherapy, 1 transplant) but still produce a review or financial row; 1 (`tablo15_4_normal_poliklinik_wrong_method`) is a dead stub (`common_billing_errors.py:487-508` returns `[]`). Wave A is therefore the **secondary** target; the dark blocks and the cross-bill rules are the primary one.

| Group | What a demo can still do | What blocks the rest (engine / model) |
|---|---|---|
| `treatment_pricing_2_4` | physiotherapy same-day combinations flip from missing to *unavailable* only (proxies force `unavailable`, `treatment_pricing_evaluations.py:36-53`); no new match | 63 engine reasons: 14 `unsupported_predicate_shape`, 12 `treatment_board_report_not_established`, 14 facility-vocabulary mismatches, 4 `cross_claim_history_unavailable`, …; the dialysis rules key on codes that do not exist (`P5010046/47/50`); ESWT keys `P915010` (does not exist) |
| `fatura_inceleme_prose` | new matches follow new claim kinds and branches (§2.4: 72 of 91 rules were reachable by a skeleton claim; 40 of the 66 not matched today are keyed on a billed code) | one rule needs `drug_category` (no attribute on `DrugClaimLine`); 4 rules have no condition and match any claim of their branch (EI-24) |
| `drug_combination_4_2` | the 6 wireable rules can match a *named drug combination* (two DOACs, cinacalcet + etelcalcetide, …) | 47 rules use blocked keys (`ecog_score`, `drug_class_any`, `pdl1_*`, …: `drug_combination_evaluations.py:69-126`) |
| `gap_closing_misc`, `gap_closing_treatment_2` | nothing | 54 rules read keys no builder produces (`drug_overseas_sourced`, `patient_proxy_service_fraud`, `extra_fee_charged`, `early_discharge`, `patient_died_before_drg_procedure`, …) |
| `payment_method_2_2` | a **poliklinik or günübirlik claim evaluates 12 more rules and matches ORTAK-20** (measured); 2 more need `visit_type` or a contract marker | 11 engine (7 because `acil` is an unrecognised claim type, 54 evaluations); the same-day / multi-specialty / visit-sequence inputs are **never derived even with several bills** (EI-12) |
| `dental_2_4_1` | needs dental material lines + board flags | 15 rules need `patient_age`, `years_since_last_prosthesis`, `patient_category_any`, … (not on the claim model) |
| 18 focused groups | each rule fires only when a planted hit exists (table below) | 3 non-emitting by design (`tablo15_9_admission_billing_window`, `tablo15_22_exam_admission_date_mismatch`, `radiation_oncology.same_day_collapse.hyperthermia`); the dead `tablo15_4` |

**The 18 focused groups, one by one** (positive triggers read in code by a dedicated research pass and lit end-to-end in memory on copies of the 9 tables; ✓ = ran). "Status on a hit" is what the projection gives a perfect positive.

| Group (ids) | Positive trigger | Status on a hit; row | Class | Story |
|---|---|---|---|---|
| `detect_yatak_icu_overlap` (1) | an ICU claim (510090 or P55200x, with admission and discharge) and a 510010 line, billed, dated on its discharge day, on the same or a later claim of the patient ✓ | evaluated; financial review (ORTAK-29 beside) | DATA, multi-bill (single-claim variant exists) | S14 |
| `detect_duplicate_exam_10day` (1) | two **outpatient** claims (not `yatis`, not `acil`), exam line category `muayene`, same non-empty branch code, 0–10 days apart; the finding lands on the later bill ✓ (SUT analogue C000573) | evaluated; unpriced finding | DATA, multi-bill | F4 b3 |
| `detect_duplicate_tests` (1) | the same code, category in {laboratuvar, radioloji, radyoloji, patoloji, test}, on two different claims ≤ 7 days apart; any claim type (`acil` then `yatis` works) ✓ | evaluated; review | DATA, multi-bill | S10 |
| `detect_blood_component_isbt128_violations` (1) | a blood line (705371/705430/705440/705372/705373/705441-3) with an empty or malformed barcode (`=` or `A` + 13–16 alphanumerics) ✓ (SUT §4.6: C007926, C007927) | evaluated; unpriced finding | DATA (needs the barcode flag, G5a) | S18 b2 (F5 b3 carries valid barcodes) |
| `detect_drug_quantity_error` (1) | a drug line with quantity ≤ 0 (finding) or > 999 (review; a local heuristic) ✓ | evaluated | DATA (fault op, G6) | F2 b3 |
| `detect_green_area_bundled_extras` (1) | code `520021` plus any other line on the claim, any claim type ✓ | evaluated; one review per extra line | DATA | F8 b2 |
| `detect_vakabasi_wrong_method` (1) | an exam line with `is_package_included` True on an outpatient claim ✓ | evaluated; finding | DATA (flag, G5a) | F2 b4 |
| `detect_material_preauth_missing` (1) | a material line with `requires_pre_auth` True (the model has no approval field) ✓ | evaluated; review | DATA (flag, G5a) | F2 b5 (conditional) |
| `detect_material_type_missing` (1) | a material line with blank `material_type` ✓ | evaluated; finding | DATA (fault op, G6) | X2 |
| `detect_inpatient_on_outpatient` (1) | a line categorised `ameliyat/cerrahi/anestezi/yatis/gunubirlik` on an outpatient claim ✓ | evaluated; finding | **vocabulary artifact**: the composer never writes those labels; false positive on day-case `ameliyat` (EI-17) | skip |
| `detect_donor_prep_as_exam` (1) | an exam line on a claim whose `occupational_context` is `donor…` ✓ | evaluated; review | needs a transplant donor patient | X2 |
| `detect_transplant_package_scope_violations` (1) | `P609080` plus a separate `islem` line ✓ (P609080 alone is ≈ 29× the largest demo bill) | **unavailable** by spec; financial row per extra line | needs a transplant pathway | X2 |
| `detect_conditional_addon_ek2d_opportunities` (2) | `P703365` without a D-4 primary, or `P614981` without a D-5 primary ✓ (SUT C001389, C001413) | **unavailable** by spec; review | DATA, neurosurgery host | F3 b4 (neuromonitoring); X2 (neuronavigation) |
| `detect_dental_ga_uplift_violations` (2) | a dental code + a `550xxx` line (double-billed), or dental lines with a `dental_ga*` category (missing uplift) ✓ | **unavailable** by spec; claim-level financial row | needs dental pathways; **legal basis of the +30 % not found in the SUT corpus (EI-21)** | skip until verified |
| `detect_radiation_oncology_violations` (12 emitting ids; 13th non-emitting) | RT family codes 800070–800590 repeated beyond the course/day limits; one 14-line claim lights all 12 ✓ | **unavailable** by spec; one financial row per participant line | DATA, rows only; evaluated would need course and session identity (model gap, EI-19) | S21 |
| `detect_normal_poliklinik_wrong_method` (1) | none: the detector returns `[]` (payment-method compliance owns the verdict) | cannot fire | **ENGINE (dead rule, EI-13)** | none |
| `detect_admission_billing_window`, `detect_exam_admission_date_mismatch` (2) | none: non-emitting | cannot fire | **ENGINE (EI-13)** | none |

### 2.3 Cheap levers measured in memory

Each row is one edit of the 8-patient tables (or one added claim), rebuilt through the real loader and measured with the §9 metrics. Baseline: 9 blocks, 273 evaluated, 14 matched.

| Lever | Δ blocks | Δ evaluated | Δ matched | Verdict |
|---|---|---|---|---|
| add any `poliklinik` or `gunubirlik` claim (one exam line) | 0 | +12 (`payment_method_2_2`) | +1 (`ORTAK-20.ayaktan_ek2a_yatis_ek2b`) | worth it once, with F4 (WP6) |
| two outpatient bills, same branch, 5 days apart | 0 | +13 | +2 (ORTAK-20, `tablo15_2_duplicate_exam_10day`) | F4 |
| a ward claim + an ICU claim, 510010 on the ICU discharge day | +1 (`icu_puani`) | +1 | +1 (`yatak_icu_overlap_510010`, the first Wave A **financial** row) | S11 + S14 |
| `provider_type` `Ozel` → `sozlesmeli` on all 8 | 0 | **−1** (+5 gained, 6 lost: the string also carries ownership) | 0 | **do not** (EI-3) |
| `facility_tier` basamak 3 / training hospital on all 8 | 0 | −1 to −5 | 0 to +2 (training-hospital advisories) | not a lever (no new block) |
| `acil`, `koruyucu`, `meslek_hastaligi` claim | 0 | 0 | 0 | the engine does not recognise them (EI-1) |
| a department written with Turkish letters (`Göğüs Hastalıkları`, `İç Hastalıkları`) | 0 | 0 | +1 on existing patients; exposes the checklist and `.lower()` casing issues (EI-15) | free, apply in every new story |
| label lines with one of the 113 rule-vocabulary categories | 0 | 0 beyond the outpatient baseline | at most 1–2 per label; **15 labels hit any rule** | needs a `service_category` column (EI-5), not a demo edit |
| a drug line moves from absent to present | 0 | 0 evaluated (53 rules go missing → *unavailable*) | 0 | no gain |

### 2.4 The specialty-breadth lever (Fatura İnceleme prose)

The 91 Fatura İnceleme rules key on the claim's department (a branch keyword) plus billed codes or a category. A skeleton sweep (one scratch claim per rule, built from the rule's own condition, in a department whose name carries the branch keyword with Turkish letters) reached **72 of 91 rules**; 66 of those are not matched on the 8 patients today. By what the rule keys on:

| Rule key | Newly reachable | Authorable by the composer? |
|---|---|---|
| a billed code (`procedure_code_any`) | 40 | yes (EK-2/B or EK-2/C numeric codes; lab and imaging codes need the lab/imaging kinds, §7) |
| a service category (`procedure_category_any`) | 17 | **no** until a vocabulary column exists (EI-5) |
| nothing but the branch (4 rules with an empty condition) or the setting (1) | 5 | any claim of that department matches (EI-24); free but meaningless |
| other (annex membership, setting + category) | 4 | partly |

Seven coherent branch patients built as skeletons (Göğüs TB work-up, ERCP, hand fracture, delivery with tubal ligation, urology, eye, cardiology) added **+17 matched** Fatura İnceleme rules with 0 new blocks; 13 are keyed on billed codes, 3 on branch or setting alone, and 1 fired only because the skeleton wrote a service category the composer cannot write (so 16 count). Two cautions: a rule keyed on a code alone matches even when the clinical context differs from its denial text (the eye-laser rule names trichiasis; a retinopathy patient would match it), and every branch patient needs its own clinician pass. This lever is **optional and low value per patient** (§5.6, X3); it is the only way to move the "matched" count by more than a handful once the blocks are lit.

## 3. Capability map: the finished engine work

Thirteen pieces of engine work are finished and none is visible in the demo. Each row says which story shows it, what the user will see, and what stands in the way. "Silent by design" means the engine's job there is to *not* flag (an exclusion), so the story is a precision demo, not a finding.

| # | Finished engine work | Story | What the user sees | Class / blocker |
|---|---|---|---|---|
| 1 | ICU days 510090 and EK-2/C ICU packages (P552001-3, P552006-8) | S11, S14 | an `icu_puani` row when the package days are billed below the expectation (package at 50 %: row; clean stay: a 0 TL row); the 510010 billed on the transfer day as a Wave A financial row and ORTAK-29 | DATA + G4a. The +100 % ilave oran needs a basamak-3 header (FACILITY; decided 2026-10-21: no second facility, it stays dark); the tier-overbilling detector #242 is not surfaced in the report (EI-4) |
| 2 | Newborn bed 510070 / 510081 with `Z38` / `P00-P96` | S12, S15 | `yenidogan_yatak` row (Kuvöz billed on 3 of 6 days: 1,322.94); the standard-bed block loses the newborn-owned days | DATA + G4b. Rooming-in ("Kot not billable beside the mother") is unreachable (EI-14) |
| 3 | Stays under 24 h priced at the day bed 510120 | F7 b2 | a one-date stay with nothing billed for the bed: action `yatak_puani_day_bed`, 44.45 | DATA + G3 (one-date stay) |
| 4 | ER critical bed 530000 | F2 b3 | **silent by design**: 530000 on day 0 removes that bed day from the expectation; the unbilled ward days after it still show 667.08 and the detail names 530000 | DATA; no block of its own |
| 5 | Special rooms 510100 (sterile) / 510110 (radioiodine) | X5 (conditional) | silent by design (days paid by the room are removed); partly billed room: 444.72 | DATA + G4c; heavy clinician need; low value |
| 6 | Hemodialysis 704210 / 704230 | S17 | the monthly `P704230` bill is informational; a one-date stay with `P704210` shows no day bed (through the package window; the control without it shows 44.45). The day-bed *exclusion* for the itemized codes cannot be shown without triggering EI-7 | DATA + G1, G3. **An itemized 704230 is mis-signalled by the engine (EI-7): do not use it as a fault** |
| 7 | Day case (`gunubirlik`) with an EK-2/C procedure | S20 | clean `P603840`: informational; itemized `603840`: `compliance_violation` + uplift 5,255.17 (the S1 fault in a day-case claim) | DATA + G1. `care_setting_review` stays dark (FACILITY, EI-22); Wave A 2.2.2.(4)/(5) are evaluated but cannot match a plain `gunubirlik` claim (EI-20) |
| 8 | 510010-beside-newborn audit detector | S15 | audit exposure row `yatak_newborn_overlap_double_billing` (222.36 for one day), across the NICU bill and the ward bill | DATA + G2, G4b |
| 9 | EK-1/A exemption with a chronic health report | F2 b2 (WP9; model slice G13 in WP8) | S2 moves from "partial exempt" to "exempt" and its control bill shows the visit copay waived (about 17 TL on 85.73 at 20 %; 20.0 on a 100/80 test exam); S3–S6 keep the partial state, now with explicit wording | **MODEL** (decided 2026-10-21: G13, nullable column + wiring + wording) + poliklinik grammar (G1) + payable ≠ billed (G5b); the all-diagnoses fix is in `main` since #333 |
| 10 | Surcharge EK-2/G | X4 (conditional) | the surcharge alert counts a line on the EK-2/G list that does not carry the flag | G5b (flags + payable ≠ billed, paid in WP9); patient alert, not one of the 20 blocks |
| 11 | Drug indication with health-board reports | F5 b5, S17, S18 | `report_duration_mismatch`, `prescriber_specialty_mismatch`, `missing_board_report` (plus `eligible` on the clean lines) | DATA + G9 (`report_duration_months` is not settable from a pathway). Drug prices stay 0 / "fiyat yok" |
| 12 | Blood products | F5 b3, S18 b2 | full-price blood inside a package: audit exposure `blood_component_partial_bill` (5,712.20 for two units); missing barcode: ISBT finding | DATA + G5a. **The uplift side (`blood_uplift`) is ENGINE-first (EI-2)** |
| 13 | Sessions: dialysis and physiotherapy | S17 (dialysis); physio: none | dialysis: see 6. Physiotherapy: no new matched rule is reachable (proxies force `unavailable`, EI-8; corpus codes do not exist), so **no story** | physio is ENGINE-bound |

## 4. Multi-bill patterns

Safa's list, one row each (2026-10-21: follow-up bills on all patients). "Today" says what the engine does with the pattern now; "dormant" means the data is plausible today but the rule input is never derived (EI-12, issue #337): the bill is built now (data first) without a fault record, and its expected hit is documented in its card.

| Pattern | Where | Engine status today | Rules that fire (measured ✓) |
|---|---|---|---|
| **Outpatient follow-up after admission** | F2 b2 (22 days after discharge), F3 b3 (12 days), F4 b2 (10 days), F6 b2 (15 days), F5 b4 (3 days after the readmission), F1 b3 (6 days, inside the 10-day package period: dormant) | the post-discharge control inside the package period (SUT 2.2.2.B-3.(1) = C000714: outpatient exams and routine tests within 10 days after discharge from a diagnosis-based package are included in the package payment) has **no implemented rule**; each such bill adds the outpatient baseline only | ORTAK-5 (checklist), ORTAK-20 and 12 payment-method evaluations (once, on the first outpatient claim) ✓ |
| **Readmission** | F2 b3 (36 days after discharge, via the ER), F5 b3 (8 days), F8 b3 (11 days), F3 b4 (26 days, planned second operation), S18 b1 → b2 (admission to admission 4 weeks) | no readmission rule is implemented (the corpus rule of C000714 also names a repeat admission, but its condition keys are never derived, EI-12) | none from the pattern; each bill carries its own fault or none (quantity, blood, ERCP codes, neuromonitoring, ISBT) |
| **Same-day multi-specialty outpatient** | dormant X7 (on S4) | `same_day_multi_specialty_outpatient` (C000576) is a rule condition that **no builder derives** (EI-12) | none today (expected 0, to be confirmed when built) |
| **Same-day outpatient visit, then admission** | dormant X6 (on S18) | `same_day_outpatient_visit` (C000575) never derived (EI-12) | none today |
| **Prior therapy** | not buildable | `requires_prior_drug_use_condition` (C003457) needs `medula_record_of_prior_drug`, a column that does not exist (model gap) and a derivation that does not exist | none |
| **Prior prosthesis or device** | MIAT on F6 b2 → b3 (walker `OP1106`, 42 days apart, MIAT 1 year) works today; the dental form is blocked | `years_since_last_prosthesis` (C000761, 4 years) is never produced and the pathway window (2026-02..09) cannot hold a bill years earlier | MIAT ✓ (42 days < 365) |
| **Bills that together trigger a rule no single bill does** | S10 (duplicate test), F4 b3 (duplicate exam), S14 (ICU overlap), S15 (newborn double billing), F6 b3 (MIAT); F7 b2 repeats a test of S7's own ER bill (a structural hit, not a fault) | the first, second, third and fifth were lit with two or more bills; S15's detector also fires inside one bill, and its cross-bill form was read in code (`ctx.history`) but not lit separately | `tablo15_12_duplicate_test` ✓, `tablo15_2_duplicate_exam_10day` ✓, `yatak_icu_overlap_510010` ✓ (financial), `yatak_newborn_overlap_double_billing` ✓, `material_miat_interval` ✓ |
| Stem-cell add-on after an allogeneic transplant (60 / 90 days, `sct_temporal_window.py`) | not proposed | a real cross-claim rule, but a hematology transplant timeline (heavy clinical review) and its report surfacing was not verified | unverified |

## 5. Bill list and cards (revision 2, continuing after S8)

### 5.1 How to read the list

- A **story** is one planted-fault bill (or a clean bill) with its own pathway. **Patients** group bills: the 8 showcase patients (S1–S8) keep their existing bill as `b1` and gain follow-up bills; new patients start at S9. Labels used below: `S9…S21` = the new-patient stories of revision 1 that stay (S13, S16, S19 are retired, see 5.2); `F1…F8` = follow-up bills on the patients of S1…S8 (`F4 b2` = the second bill of S4's patient; `b1` is always the existing admission); `X1…X7` = conditional extensions (revision 1 called X1–X5 S22–S26; X6 and X7 are the two dormant bills of revision 1). Plan labels are names in this document; the generator's story ids are fixed in §5.1a.
- **One planted fault per bill** (the recipe grammar and the answer key assume it); a bill may also be clean. Cross-bill hits (duplicate test, ICU overlap) are *structural consequences* of bills that are each clinically right and are declared as expected hits, not as faults. A fault the engine cannot derive yet (post-discharge control, readmission, same-day visits; issue #337) is a **dormant** bill: built now (Safa, 2026-10-21: data first), no fault record until the engine rule exists, expected finding documented in its card.
- Every bill keeps `payable == billed` (except the one waiver bill, WP9), prices on the 2026-07-07 EK-2/B and EK-2/C lists, drug prices at 0 ("fiyat yok"), the demo facility (`2_3_basamak_ozel`, `Ozel`), department names with Turkish letters, ICD codes from the SKRS table, dates inside the code-set window 2026-02-01 to 2026-09-30, and a `basis`/`source` per pathway entry. Follow-up bills of a patient use the same age and sex (the plausibility check `patient.age_arithmetic` ties them to the first bill) and, where possible, diagnoses already on the patient's list so that the union list read by `test_all_diagnoses_by_patient.py:157-166` stays unchanged.
- **N** = newly triggered items (B blocks + M Wave A ids matched or with a row + K finding kinds), **E** = newly evaluated Wave A ids, **N per day** = N over the story's own days plus the slice days it is first to need in the order of §6. ✓ = measured on a skeleton (cumulative, in the work-package order, §6.4); (research) = a read-only probe of 2026-10-20/21. Skeleton numbers are not generator output.

### 5.1a Story ids (the generator's `S<n>`)

One id per bill (per pathway): WP1 keeps one fault per story (`fault.duplicate_story`, the fixture `fault(story)`, the JS `faultFor(story)`) and one story per pathway (`Pins.story`). A patient's bills are grouped by the registry key `scenarios` (patient and claim ids), never by sharing an id. S1–S8 keep their ids and roles; their follow-up bills are scenarios. The numbers carry no meaning beyond being unique; the package that builds a bill records label → id in its PR and in the recipe file.

| Plan label | Generator story id | Built in |
|---|---|---|
| S9 | S9 | WP1 (built) |
| S11 (ICU bill), S14 (ward bill) of patient 10 | S11, S14 | WP2, WP5 |
| S12 (NICU bill), S15 (ward bill) of patient 11 | S12, S15 | WP3, WP18 |
| S10 b1 (ER), S10 b2 (admission) | S10, S22 | WP7 |
| S20 | S20 | WP10 |
| S17 b1, b2 | S17, S23 | WP12 |
| S18 b1, b2 | S18, S24 | WP13 |
| S21 | S21 | WP19 |
| F1 b2, b3 | S30, S31 | WP18 |
| F2 b2, b3, b4, b5 | S32, S33, S34, S35 | WP9, WP11, tail |
| F3 b2, b3, b4 | S36, S37, S38 | WP16 |
| F4 b2, b3 | S39, S40 | WP6 |
| F5 b2, b3, b4, b5 | S41, S42, S43, S44 | WP15 |
| F6 b2, b3 | S45, S46 | WP14 |
| F7 b2, b3 | S47, S48 | WP10 |
| F8 b2, b3, b4 | S49, S50, S51 | WP17 |
| X1…X7 | S60 and up, assigned when built | tail |

### 5.2 What the answers of 2026-10-21 changed in the story set

Safa asked for follow-up bills on **all** patients. Three stories of revision 1 described a patient whom the cohort already has, so their rules are re-hosted on the existing patient; the rules, faults and clause ids stay, three new patients disappear (19 → 16 patients) and the bill count rises (34 → 42; 43 with the conditional home-BPAP bill):

| Retired (rev 1) | What it was to light | New host | Why this host |
|---|---|---|---|
| S13 diabetes + hypertension, 3 outpatient bills | duplicate exam (C000573), `ORTAK-20` and the 12 outpatient evaluations, checklist `ORTAK-5`; the EK-1/A waiver (b4) | F4 b2–b3 (duplicate exam, outpatient baseline) and F2 b2 (waiver) | S4 and S2 already have a chronic disease that EK-1/A lists (dementia G30.1, COPD J44) |
| S16 hip fracture, 5 bills | blood at full price inside a package; early renewal of a device (MIAT); romosozumab report of 12 months | F5 b3 (blood), F5 b5 (romosozumab), F6 b3 (MIAT) | S5 is the hip-fracture patient. Its code-set window ends 2026-09-30, too short for a 6-month MIAT, so the walker twice goes to S6 (42 days apart, MIAT 1 year) |
| S19 COPD "frequent flyer", 5 bills | green-area visit, day bed under 24 h, 530000, drug quantity, vakabasi, pre-approval | F2 b3–b4 (S2 is the COPD patient; quantity, vakabasi, 530000), F7 b2 (S7: day bed), F8 b2 (S8: green area); pre-approval = F2 b5, conditional | each detector sits on the patient whose story it fits |

Other consequences: S13 b4 becomes F2 b2; `S25` (EK-2/G surcharge, revision 1) is unblocked by G5b and sits in the conditional extensions (X4); dormant bills D1/D2 are built now (X6/X7) because data production no longer waits for the engine.

### 5.3 The ordered list (work-package order)

| Item | WP | Patient and bills | Planted fault per bill (clean twin) | Newly triggered | N / E | Own d | Clinician |
|---|---|---|---|---|---|---|---|
| **New patients and bills of new patients** | | | | | | | |
| S9 | 1 (built) | lumbar stenosis, 1 bill (patient 9) | second operation at 25 % (clean: 50 %) | block `session_uplift` ✓ | 1 / 0 | 1.0 | neurosurgeon (light) |
| S11 | 2 | septic shock, ICU stay, 1 bill (patient 10) | package days at 50 % (clean: 100 %) | block `icu_puani` ✓ | 1 / 0 | 1.5 | intensivist |
| S12 | 3 | late-preterm newborn, 1 bill (patient 11) | Kuvöz on 3 of 6 days (clean: 6) | block `yenidogan_yatak` ✓ | 1 / 0 | 1.5 | neonatologist |
| S14 | 5 | bill 2 of patient 10: ward after the ICU | 510010 on the ICU discharge day | the first Wave A **financial** row ✓ | 1 / +1 | 1.0 | intensivist |
| S10 | 7 | GI bleeder, 2 bills (patient 12): ER, then admission | b1 CBC double; b2 colonoscopy without the add-on; MEDULA `0901` on b1 | blocks `lab`, `procedure_addon_uplift`, `medula_rejection_playbook`; ids `GENEL CERRAHİ-2…`, `tablo15_12…` ✓ | 5 / +1 | 2.0 | internist or gastroenterologist; billing officer |
| S20 | 10 | umbilical hernia day case, 1 bill (patient 13) | itemized instead of the package (clean: package) | none new | 0 / 0 | 1.0 | surgeon (light) |
| S17 | 12 | end-stage kidney disease, 2 bills (patient 14) | b1 ESA prescribed by the wrong branch | kind `prescriber_specialty_mismatch` ✓ | 1 / 0 | 2.0 | nephrologist |
| S18 | 13 | decompensated cirrhosis, 2 admissions (patient 15) | b1 albumin without the report; b2 transfusion without ISBT numbers | id `blood_component_isbt128_barcode` ✓; kinds `missing_board_report`, checklist `0612` ✓ | 3 / +1 | 2.0 | hepatologist or internist |
| S15 | 18 | bill 2 of patient 11: ward after the NICU | 510010 on days a newborn bed already pays | kind `yatak_newborn_overlap_double_billing` ✓ | 1 / 0 | 1.0 | neonatologist |
| S21 | 19 | cervical cancer radiotherapy course, 1 bill (patient 16) | once-per-course and once-per-day codes repeated | **12** ids with a financial row ✓ (`unavailable` by spec, EI-19) | 12 (rows) / 0 | 1.5 | radiation oncologist |
| **Follow-up bills on the patients of S1–S8** | | | | | | | |
| F4 | 6 | S4 (86, dementia, pyelonephritis): b2 control, b3 second visit 5 days later | b3 duplicate exam (clean: b3 on day 14) | ids `tablo15_2…`, `ORTAK-20`; checklist `ORTAK-5` ✓ | 3 / +13 | 1.5 | geriatrician (light) |
| F2 b2 | 9 | S2 (81, COPD): control 3 weeks after discharge, chronic report on file | none: the EK-1/A waiver is a patient benefit | the first money copay row (about 17 TL on an 85.73 visit at 20 %; research: 20.0 on a 100/80 test exam) | 1 / 0 | 1.0 | pulmonologist |
| F7 | 10 | S7 (58, ER chest pain): b2 observation under 24 h, b3 follow-up | b2 day bed `510120` not billed | kind `yatak_puani_day_bed` ✓ | 1 / 0 | 1.5 | emergency physician |
| F2 b3–b4 | 11 | S2: b3 readmission via the ER, b4 control 6 days later | b3 enoxaparin strength keyed as quantity; b4 control flagged as package component | ids `tablo15_11…`, `tablo15_3…` ✓ | 2 / +2 | 2.25 | pulmonologist |
| F6 | 14 | S6 (79, Parkinson): b2 neurology control + walker, b3 physiatry visit + second walker | b3 walker renewed after 42 days (MIAT 1 year) | kind `material_miat_interval` ✓ | 1 / 0 | 1.75 | neurologist, physiatrist |
| F5 | 15 | S5 (84, hip fracture): b2 ER precursor, b3 readmission, b4 control + walker, b5 geriatrics | b3 blood at full price inside the package; b5 romosozumab report of 12 months | kinds `blood_component_partial_bill`, `report_duration_mismatch` ✓ | 2 / 0 | 4.5 | orthopaedist, orthogeriatrician |
| F3 | 16 | S3 (77, lumbar stenosis): b2 pre-op takip, b3 control, b4 instrumentation | b4 neuromonitoring without an EK-2/D-4 primary | ids `BEYİN-2…`, `conditional_addon_ek2d_neuromonitoring` ✓ | 2 / 0 | 3.5 | neurosurgeon |
| F8 | 17 | S8 (47, cholecystectomy): b2 ER green area, b3 ERCP admission, b4 control | b2 tests beside the flat-fee visit; b3 ERCP codes at full price | ids `tablo15_7…`, `GENEL CERRAHİ-1…` ✓ | 2 / +1 | 3.0 | emergency physician, surgeon |
| F1 | 18 | S1 (34, appendectomy): b2 ER precursor, b3 control 6 days after discharge | b3 control inside the 10 days of the package (dormant, #337) | none today | 0 / 0 | 2.0 | surgeon (light) |
| **Conditional extensions (§6.6)** | | | | | | | |
| F2 b5 | tail | S2: home BPAP device | device flagged as needing approval, none recorded | id `tablo15_15…`, kind `material_pre_auth` ✓ | 2 / +1 | 0.75 | billing officer (EK-3/C-1 has no price) |
| X1 | tail | hip revision, `material_uplift` | cup `AP1390` not billed | block `material_uplift` (gated by EI-10) | 1 / 0 | 1.5 | orthopaedist |
| X2 | tail | rare detector hosts (transplant pair, blank material type) | donor visit as exam; surgical line beside `P609080`; blank type | up to 4 ids (2 `unavailable` by spec) | 4 / +2 | 5.0 | transplant surgeon |
| X3 | tail | specialty breadth: TB work-up, pregnancy, hand fracture, cardiac work-up | one coherent bundle per branch | ≈ 10 Fatura İnceleme ids keyed on billed codes | 10 / 0 | 6.0 | one per branch |
| X4 | tail | oncologic surgery with the EK-2/G surcharge | line on the EK-2/G list without the flag | surcharge alert (not a block) | 1 / 0 | 1.5 | billing officer |
| X5 | tail | special rooms 510100 / 510110 | room billed for 2 of 4 days | silent by design | 0 / 0 | 1.5 | haematologist or nuclear physician |
| X6, X7 | tail | dormant bills: S18 same-day outpatient visit before the admission; S4 second specialty on one date | engine-first (#337) | 0 today | 0 / 0 | 1.0 each | none |

Totals (skeleton, §6.4): through WP19 the cohort is **16 patients and 42 bills**, 15 blocks with output, 292 Wave A ids evaluated, 25 matched, 35 with a row (12 of them radiotherapy rows). N over the schedule is 40: 6 blocks, 12 Wave A ids, 12 radiotherapy rows and 10 finding kinds.

### 5.4 Cards: new-patient stories

#### S9 · Lumbar stenosis, second operation billed at 25 % (WP1, built: commit `bbd4b5fc`)
- **Scenario.** Patient born 1949, lumbar stenosis M48.06 + hypertension I10, neurosurgery (2400), `yatis`, 2 nights (3 dates). Decompression `615931` and foraminoplasty `615995` in one session, anaesthesia `550220` (multiple-operation code, group A3: the unreduced total puan is 11,584), ward `510010` ×3, companion `510121` ×2, hemogram. A sibling of the S3 pathway with an optional second operation; the window is narrowed to 2026-04-16..09-30 because the name of `550220` changes on 2026-04-16.
- **Fault / clean twin.** The second operation at 25 % (the package ratio) where hizmet-başı pays 30 % through the same incision and 50 % through a separate one. Clean twin 50 %: silent in `session_uplift` (built result; the engine writes a review row only for a billed amount between the strict 30 % and the lenient 50 % reading, e.g. at 40 %; the Wave A review `ORTAK-22` is on both bills).
- **Finding.** `session_uplift` 151.60 (built: strict 30 % reading; the record carries 758.01 = clean minus faulty, listed in `KNOWN_REPORT_DIVERGENCES`, same cause as S8: no incision field). SUT 2.2.2.A.(5): C000659, C000660 (30 %), C000661 (50 %), C000662 (+25 points across branches).
- **Triggers.** Block `session_uplift` ✓. N 1. **Builder.** G0 only; `set_billed_ratio 0.2500` is on the ladder; same-branch pair (the +25-point rule is not applied in `expand.py:21`, issue #295). **Clinician.** A neurosurgeon (three premises and the `judgment` items are in `reports/synthetic-data/2026-10-21-demo-stories-judgment-list.md`). **Size.** 1.0 d.

#### S11 · Septic shock, ICU stay with the package days under-billed (WP2)
- **Scenario.** Patient born 1950, urosepsis A41.9 + septic shock R57.1 + N39.0, intensive care, `yatis` 2026-06-02 to 06-07 (6 dates). `510090` on day 0, `P552002` (4,059.89 per day) on days 1–3, `510090` on day 4; day 5 is the transfer day. P552002 is used because a P552003 day needs documented organ support.
- **Fault / clean twin.** The three package days billed at 50 % of list (clean: 100 %, a 0 TL row).
- **Finding.** `icu_puani` row; by the engine's formula the shortfall is 6,089.84 (measured 4,871.88 at 60 %; the stay expects 13,664.87). SUT 2.4.4.H.(2) C001234, H.(8) C001243, H.(7) C001242, 2.2.2.B-1.(1).a C000685/686/699. Side effects (not faults): checklist ORTAK-21 (a misfire on a non-surgical package, EI-16), ORTAK-17, ORTAK-27.
- **Triggers.** Block `icu_puani` ✓. N 1.
- **Pin that only this story hits.** `tests/unit/domain/optimization/test_copay_rate_exposure.py:148-160` asserts that the cohort has **no flag or rate mismatch against the EK-2/C-1 list**; the ICU packages `P552001-3/6-8` are on that list at 100 % (checked: they are the only planned package codes that are; `608320` is the only other planned code on it) and the composer writes `copay_rate_applicable` False and payable == billed, so three package lines add three flag and three rate mismatches. WP2 narrows the assertion to non-ICU lines with a written reason (cheapest), or implements the 100 % rate in the composer (needs G5b and breaks `payable == billed`); the plan assumes the narrowing.
- **Builder.** G4a: kinds `icu_day`/`icu_package`, a `package.mode` exemption, per-kind stay coverage, `package_candidate` False for ICU packages; five check ids with registry entries and mutation cases. **Clinician.** An intensivist. **Size.** 1.5 d.

#### S12 · Late-preterm newborn, Kuvöz billed on 3 of 6 days (WP3)
- **Scenario.** Infant born 2026-07-10, P07.3 + P59.9 + Z38.0, department "Yenidoğan", `yatis` 6 dates: exam `520010`, Kuvöz `510070` ×3 on day 0, companion `510121` on days 0–4.
- **Fault / clean twin.** Kuvöz on 3 of 6 days (clean: 6). Finding: `yenidogan_yatak` 1,322.94 (expected 2,645.88). EK-2/B 510070/510081 rows under SUT 2.2.2 (no SUT clause names Kuvöz or Kot, `tasks/todo.md:705`).
- **Triggers.** Block `yenidogan_yatak` ✓. N 1. **Builder.** G4b: kind `newborn_bed`, `bed_day_codes`, age-aware vitals and lab bounds (`Boy 120–210 cm`, `Kilo 30–200 kg` are adult), composer `_BED_CODES`; age 0 is legal. **Clinician.** A neonatologist. **Size.** 1.5 d. **Risk.** Rooming-in is unreachable (EI-14). When S15 follows, the fault sits on the first days of the stay so that the last NICU day carries a Kuvöz line.

#### S14 · Septic shock continued: the ward bill (WP5, bill 2 of patient 10)
- **Scenario.** `yatis` 2026-06-07 to 06-10, internal medicine: `510010` ×4 from the ICU discharge day, companion `510121` ×3.
- **Fault / clean twin.** The transfer day billed by the ICU bill and again by the ward bill (clean: the ward bill starts the next day; generator form `use_sibling_pathway`). Finding: Wave A `yatak_icu_overlap_510010`, a financial review on the ward bill (observed amount = the 510010 line, 222.36), checklist ORTAK-29 ✓; the ward bill's bed expectation loses the overlap day. SUT 2.4.4.H.(8) C001243; EK-2/B 510090 text.
- **Triggers.** The first Wave A financial row. N 1, E +1. **Builder.** G2 and G4a paid. **Risk.** Do not use the single-claim variant (EI-17). **Size.** 1.0 d + the pin migration of WP5.

#### S10 · GI bleeder: ER visit, then admission (WP7)
- **Scenario.** Man born 1968. **b1** (`acil`, 2026-05-09, Acil Tip 4400): melena K92.1, `520020`, hemogram `L107020` and manual haematocrit `L103120`. **b2** (`yatis` 2026-05-11 to 05-13, Genel Cerrahi): K92.2 + D50.0 + D12.6, ward `510010` ×3, companion `510121` ×2, serial hemogram on day 0, colonoscopy `701450` on day 1 with the polypectomy `701460` not billed. A MEDULA event `0901` ("Mükerrer işlem: aynı gün tekrar faturalandırma") sits on b1's `L103120` line (the playbook entry's own text is "same procedure the same day or inside a package").
- **Faults / clean twins.** b1: the second CBC line (clean: one hemogram). b2: add-on omitted (clean: `701460` at 30 % or 50 %; at 100 % the engine shows an audit exposure of 439.86, EI-11). The repeated hemogram two days later is clinically right and is flagged on purpose as a warning.
- **Findings.** b1: `lab` `hemogram_unbundling` 5.88 ✓; playbook entry `0901` (rebill permitted at `fatura_kayit`) ✓. b2: `procedure_addon_uplift` 263.92 and `GENEL CERRAHİ-2…` matched ✓; `tablo15_12_duplicate_test` review ✓. SUT 2.2.2.A.(5) C000659–C000662; El Kitabı Tablo 15 #12 (the 7-day window is the detector's, unverified).
- **Triggers.** Blocks `lab`, `procedure_addon_uplift`, `medula_rejection_playbook`; ids `GENEL CERRAHİ-2…`, `tablo15_12…`. N 5, E +1. **New data.** `L103120` in `lab_reference.csv` with a lab state; one row in `medula_rejection_events`. **Builder.** G7a, G8 (G2 paid); the event date inside b1's single date (EI-18). **Clinician.** Internist or gastroenterologist; the billing officer confirms the rejection text. **Size.** 2.0 d. **Risk.** The `acil` bill is invisible to the payment-method rules (EI-1, #335).

#### S20 · Umbilical hernia as a day case (WP10)
- **Scenario.** Patient born 1985, K42.9, general surgery, `gunubirlik`, one date: itemized `603840` (1,914.43) with anaesthesia (clean: `P603840`, 7,169.60; the anaesthesia code follows the operation's puan group, so check it as S9 had to: `550220`, not `550230`). Finding: `billing_strategy` `compliance_violation` + uplift 5,255.17 (C003484: day cases pay as inpatient; §2.2.2.(1)); no bed row (C000649) and no companion row (C000650) for a day case with an EK-2/C procedure (the Wave A rules 2.2.2.(4)/(5) cannot match, EI-20). No new row kind. N 0; it covers the finished day-case item. **Builder.** G1 paid; **size** 1.0 d.

#### S17 · End-stage kidney disease: a month of haemodialysis (WP12)
- **Scenario.** Man born 1955, N18.0 + D63.8 + E21.1 + Z49.1 + Z99.2, nephrology (1062). **b1** (`gunubirlik`, date span 2026-05-04 to 05-29): 12 sessions `P704230` (5,445.77 each), darbepoetin (ARANESP, barcode 8699862950046, price 0) with a one-month report; no labs or heparin (C000969, C004117). **b2** (`yatis`, one date 2026-06-12): emergency haemodialysis `P704210` (C000963).
- **Fault.** b1: the ESA prescribed by "Genel Cerrahi" (clean: Nefroloji). Finding ✓: `drug_indication` `prescriber_specialty_mismatch`. SUT C000957, C000961, C000963, C000965, C000966, C000969, C000496, ESA C004192–C004196.
- **Why N is low.** The correct dialysis bill is informational by design; the day-bed *exclusion* for `704210`/`704230` can only be shown with the itemized codes, which the engine mis-signals (EI-7), so b2 uses the package form. **Builder.** G3 (date span), G9; whether SGK bills a month as one takip is unverified. **Clinician.** A nephrologist. **Size.** 2.0 d.

#### S18 · Decompensated cirrhosis: two admissions (WP13)
- **Scenario.** Man born 1963, K74.6 + K92.2 + I85.0. **b1** (`yatis` 2026-06-15 to 06-19, internal medicine): albumin (barcode 8699686690029, price 0) with the board-report flag False and inpatient supply True. The endoscopy is left out of the bill: the EGD codes `701540`/`701550` are triggers of the add-on rule `pairing.701540_701410` and the engine cannot know that no polyp existed (EI-11), so the skeleton's endoscopy line lit `procedure_addon_uplift` on this patient. **b2** (`yatis` 2026-07-13 to 07-16, rebleed): two red-cell units `705371` on an itemized stay, barcode empty.
- **Faults.** b1: albumin without the report (C006389). b2: no ISBT number (C007926). Findings ✓: `drug_indication` `missing_board_report`, checklist readiness `0612`; Wave A `detect_blood_component_isbt128_violations` evaluated and matched. N 3, E +1. **Builder.** G5a paid (barcode flag); albumin ≤ 2.5 g/dl must agree with the lab table. **Clinician.** Hepatologist or internist. **Size.** 2.0 d. Synthetic barcodes only.

#### S15 · Newborn continued: ward bill after the NICU (WP18, bill 2 of patient 11)
- **Scenario.** The baby moves to the ward; the ward bill (2026-07-15 to 07-19) bills Kot `510081` ×3 and the standard bed `510010` on a day that a newborn bed line already pays (clean: only the newborn line). Finding: `audit_exposure` `yatak_newborn_overlap_double_billing`, 222.36 per day ✓ (same-bill form; the cross-bill form reads `ctx.history`, `yatak_newborn_overlap.py:131-227`, read in code, not lit separately). N 1. **Builder.** G2, G4b paid; S12's NICU bill must end on a day with a Kuvöz line. **Size.** 1.0 d.

#### S21 · Cervical cancer radiotherapy course (WP19)
- **Scenario.** Woman born 1969, C53.9, radiation oncology (3200). One claim with the course: IMRT design `800110`, planning `800160`, dose `800220`, per-session `800440`, HDR brachytherapy design `800114`, dose `800260`, complex intracavitary `800520`, afterloading `800560`. Fault: the course keyed on once-per-course and once-per-day codes (`800440` ×25 on day 1, both planning codes, afterloading ×4 as one line); clean twin: one line per level and one session line per treatment day.
- **Finding ✓.** One 14-line claim lights all 12 emitting ids (`course_cap.*` ×8, `same_day_collapse.*` ×4), each a financial review with no confirmed amount, status **unavailable** (no course or session identity in the model, EI-19). Source: EK-2/B §8.1 explanatory cells; no SUT clause id. N 12 (rows only). **Builder.** The 8xxxxx codes are EK-2/B group 8, whose only grammar kind is `imaging`: accept the stretch or add a `radiotherapy` kind (inside the 1.5 d). **Clinician.** A radiation oncologist. High count, low evidential value: do not present it as 12 findings.

### 5.5 Cards: follow-up bills on the patients of S1–S8

Rules for all of them: the existing bill (`b1`) is not edited, so its bill-level report stays byte-identical (the off-repo 16-report gate and the committed S1–S8 proofs do not move once the proof is bill-scoped, WP4); follow-up bills are laid out chronologically in the tables, next to their patient, while claim ids stay stable in build order (G2); every bill gets its own pathway, recipe, clinical entry and, if it carries a fault, a fault record; precursor bills (F1 b2, F3 b2, F5 b2, F8 b2) are dated before or on the day of `b1`. "Pins" lists only what is specific to the patient; the common pins are in §7.5. **What every follow-up bill moves:** the registry counts and the twelve table digests (P1), the patient's `scenarios` entry, the docs that state counts (P8) and the patient's default pages, which show all bills (P12). **What it does not move:** the S1–S8 goldens, siblings and proof JSON, which are generated from the single-bill `PR/stories.py` (P3, P4), and any screenshot, because none is committed (a new capture is taken from a rebuilt cache).

#### F1 · S1 (man 34, appendectomy 2026-07-14 to 07-16, package `P610131`): the ER visit and a control inside the package period (WP18)
- **b2** (`acil`, 2026-07-14, Acil Tip 4400): the ER visit that the S1 pathway note says is billed on its own takip: exam `520020`, `L107020`, `L101850`, abdominal ultrasound `803602`. Clean. **b3** (`poliklinik`, 2026-07-22, Genel Cerrahi 1900): post-operative control 6 days after discharge, exam `520030`.
- **Fault (dormant).** C000714 (SUT 2.2.2.B-3.(1)): outpatient exams and routine tests within 10 days after discharge from a diagnosis-based package, same provider and branch, are inside the package payment and are not billed separately (corpus rule `2.2.2.B-3.(1).early_discharge_same_specialty_no_repeat_fee`, condition keys never derived, EI-12/#337). b3 bills the control on its own takip; clean twin: the control on day 12 (07-28). No fault record until #337 gives the engine a detector (`FaultSpec.detectors` must name an existing function).
- **Lights.** Nothing today (N 0); one Wave A id after #337. **Engine issues.** #335 (b2 is an `acil` bill), #337 (b3).
- **Pins.** S1 is the landing patient: `frontend/scripts/verify-workspace-views.mjs:146-149` (the revenue KPI must equal the landing fault amount on the default view) holds only because F1 adds no recoverable money; `tests/unit/domain/billing/test_drg_uplift_wiring.py:331-382`, `test_session_uplift_patient_0013.py:55-99`, `test_billing_strategy_exactness.py:30-52`, `test_orchestrator_claim_cohort_flow.py:14-48` read S1 at patient level (gap count 1, strategy exact): F1 must add no uplift or mandated-package gap; `test_bill_billing_report.py:44-133` re-keys the S2 and S5 bills under S1's patient (its own follow-ups now come along: rewrite that fixture); `test_cohort_plausibility_clean.py:1341-1376` removes "all rows of patient 1" to build the S1 twin world (filter by claim); `TS/test_cohort_clean.py:400-411` reads patient 1's drugs from the S1 sibling pathway (F1 has none).
- **Builder.** G1, G2 (chronological layout for b2). **Clinician.** A surgeon (light). **Size.** 2.0 d.

#### F2 · S2 (man 81, COPD exacerbation with pneumonia 2026-03-09 to 03-15, itemized): control with the report, readmission, control (WP9, WP11; b5 conditional)
- **b2** (`poliklinik`, 2026-04-06, Göğüs 1171): control 22 days after discharge; the patient's **chronic health report is on file** (S2's profile carries `has_chronic_health_report` True), the exam `520030` (85.73) carries `copay_rate_applicable` True and is billed 85.73 / payable 68.58: the app shows the EK-1/A waiver of the 20 % visit copay, about 17 TL (measured: 20.0 on a 100/80 test exam; 17.15 is the same arithmetic on 85.73/68.58; the waiver needs `poliklinik`, category `muayene`, the flag, billed > payable and the report). No fault. **b3** (`yatis`, 2026-04-20 to 04-23): readmission through the ER 36 days after discharge: `530000` on day 0 (critical ER bed: silent by design), exam `520010`, ward `510010` ×4, companion `510121` ×3, enoxaparin. **b4** (`poliklinik`, 2026-04-29): control 6 days after b3. **b5** (conditional, 2026-05-18): home BPAP device `DO1013`.
- **Faults.** b3: the enoxaparin strength keyed as the quantity (4,000 instead of 4 syringes): `detect_drug_quantity_error` review (> 999, a local heuristic; El Kitabı Tablo 15 #11). b4: the control exam flagged as a package component (vakabasi; Tablo 15 #3). b5: the device flagged as needing approval with none recorded (Tablo 15 #15). The waiver bill is not a fault: a "copay collected from an exempt patient" fault cannot be registered (`test_copay_rate_exposure.py:155` forbids a copay rule id in any fault).
- **Lights.** b2 the first money copay row (N 1); b3 `tablo15_11…` ✓; b4 `tablo15_3…` ✓ (N 2, E +2); b5 `tablo15_15…` + kind `material_pre_auth` ✓ (N 2, E +1). **S2's report changes on purpose:** with the flag True the patient moves from "partial exempt" to "exempt", loses the §1.8.2 20 % drug-copay row (`claim_copay.py:377`) and gains a `copay/exemption_review` action (0 TL on the admission, the waiver on b2); cohort KPIs: exempt 1 → 2 (of 12 patients at WP9, of 16 at the end). S3–S6 keep the partial state, so the demo shows both states side by side.
- **Engine issues.** None to build; #335 does not apply (b3 is `yatis`).
- **Pins.** `test_all_diagnoses_by_patient.py:162-166` (0002 list `["J44.0","I10","J18.9"]`: b3's J44.1/J96.0 extend it; b2 uses J44.0 + I10 only), `test_bill_billing_report.py:44-133` (S2 is a guest bill), `TS/test_cohort_labs.py:126,713` (rows per patient), the `patient_copay_profiles` digest (the flag), the S2 pathway window (ends 2026-08-28 because KLACID leaves EK-4A on 08-29; follow-up pathways have their own window), the pre-existing `claim_copay.py:377` behaviour (EI-25).
- **Builder.** G13 (WP8), G5b (WP9: `copay_rate_applicable`, `copay_rate`, payable below billed, header payable total, the relaxed plausibility check), G5a, G6 (WP11: `is_package_included`, `requires_pre_auth`, a quantity above the pathway bound of 999). **Clinician.** A pulmonologist (exacerbation timeline, readmission, the report); the billing officer for b5. **Size.** b2 1.0 d, b3–b4 2.25 d, b5 0.75 d.

#### F3 · S3 (woman 77, lumbar stenosis, decompression 2026-08-18 to 08-20, itemized): pre-op takip, control, instrumentation (WP16)
- **b2** (`poliklinik`, 2026-08-04, neurosurgery 2400, precursor): the pre-operative takip the S3 pathway note mentions: exam `520030`, lumbar MRI `R103410` (428.04), `L107020`, `L104780`. Clean. **b3** (`poliklinik`, 2026-09-01): control 12 days after discharge, exam `520030` + lumbar X-ray `801950`. Clean (itemized stay: not under C000714). **b4** (`yatis`, 2026-09-15 to 09-19): adjacent-level instability; posterior instrumentation `P614040` (6 or fewer segments, 16,765.09) with intra-operative neuromonitoring `P703365` (11,661.83).
- **Fault.** b4: the add-on is billable only with a primary on the EK-2/D-4 list (67 codes; `614050` for 7 or more segments is on it, `614040` is not): SUT 2.4.4.M.(1) C001389 → `conditional_addon_ek2d_neuromonitoring` (unavailable by spec; a review row). The code-keyed Fatura İnceleme rule `BEYİN-2.posterior_segmental_enstruman_artrodez` (arthrodesis is inside the instrumentation) matches on `P614040` without a fault. Implants (EK-3/E) are not priced by the composer and are left off; the neurosurgeon decides how the bill is presented.
- **Lights ✓.** `BEYİN-2…` matched, ek2d row: N 2. **Pins.** `test_all_diagnoses_by_patient.py:162-166` (0003 list), `TS/test_cohort_labs.py` rows per patient (17 → more) and lab states per billed lab, cross-bill predicates: b2's labs (08-04) are 15 days before claim 001's post-operative labs, beyond the 7-day duplicate-test window. **Builder.** G1, G2 (precursor). **Clinician.** A neurosurgeon (indication, segments, neuromonitoring, implants). **Size.** b2 0.75, b3 0.5, b4 2.25 = 3.5 d.

#### F4 · S4 (woman 86, pyelonephritis with dementia 2026-05-11 to 05-16, itemized): a control and a second visit (WP6)
- **b2** (`poliklinik`, 2026-05-26, İç Hastalıkları 1000): control 10 days after discharge: exam `520030`, `L107020`, `L104780`, urinalysis `L107010`, urine culture `905671`. Clean. **b3** (`poliklinik`, 2026-05-31): a second visit 5 days after b2, opened as a new takip.
- **Fault.** b3: a second outpatient visit of the same branch within 10 days (SUT 2.2.1.B-1.(2) C000573, ER visits excluded; El Kitabı Tablo 15 #2); clean twin: b3 on day 14 (06-09). Diagnoses N10 + G30.1 + I10 only, so S4's union list is unchanged.
- **Lights ✓.** `tablo15_2_duplicate_exam_10day` and `ORTAK-20` matched, checklist `ORTAK-5`, +13 evaluated (the first outpatient claims). N 3. **Dormant X7.** A second specialty on b2's date (`same_day_multi_specialty_outpatient`, C000576).
- **Pins (the first existing-patient follow-up: the whole §7.5 set).** `frontend/scripts/capture-screens.mjs:129-132` picks the "compliance" patient as the first `compliance_error` fault in registry order (S6 today): any new fault of that kind on a patient before S6 (F4's duplicate exam is one) changes the pick, so the script must choose by story; `frontend/scripts/lib/cohort-registry.test.mjs:24-25`; row-position tests `TS/test_cohort_clean.py:261-368,400-411,717-732,1045-1136`; `TS/test_cohort_build.py:301-307,654,674`; `TS/test_cohort_labs.py:2904`. **Builder.** G1, G2. **Clinician.** A geriatrician (light). **Size.** 1.5 d.

#### F5 · S5 (woman 84, hip fracture, hemiarthroplasty 2026-09-03 to 09-08, package `P612320`): ER precursor, readmission with blood, control, geriatrics (WP15)
- **b2** (`acil`, 2026-09-03): the ER visit after the fall (S5 pathway note): exam `520020`, pelvis X-ray `801880`, `L107020`, `L104780`, ECG `530100`. Clean. **b3** (`yatis`, 2026-09-16 to 09-19, 8 days after discharge and 12 after the operation, outside the package window of 10 days): readmission for a post-operative complication, billed as an EK-2/C package (the orthopaedist chooses: `P612500` removal of the hemiarthroplasty for infection, 7,531.59, or `P612472` femoral revision for a periprosthetic fracture, 26,100.19) with two units of red cells `705371` (4,462.65 each). **b4** (`poliklinik`, 2026-09-22): orthopaedic control and a walker `OP1106` (EK-3/C-2, 252.00, MIAT 1 year; first use). **b5** (`poliklinik`, 2026-09-24, geriatrics 1073): romosozumab (EVENITY, barcode 8699862950244, price 0) with a health-board report.
- **Faults.** b3: the blood billed at the full list price although inside an EK-2/C package (C000694: 36 % for 705371/705430/705440; C007927 §4.6.(4)) → `audit_exposure` `blood_component_partial_bill` (5,712.20 for two units, research); the uplift variant (blood at 25 %) needs #336. The clean twin (blood at 36 % of list) is not silent until #336: a correct 36 % bill with payable == billed shows a false exposure of 2,056.38 (EI-2). b5: report duration 12 months where the SUT allows 6 (C006166 §4.2.17.D.(1); age over 65, T-score −3.5 or lower, two or more fractures) → `report_duration_mismatch`. b2 and b4 are clean.
- **Lights ✓.** Two finding kinds (N 2). **Engine issues.** #335 (b2), #336 (blood uplift).
- **Pins.** `test_claim_strategy_sut.py:517-548` reads S5 at patient level and asserts one `paket` line over all claims (b3 adds a second); `TS/test_cohort_labs.py:706-713,126` and `test_cohort_plausibility_clean.py:1266-1274` assert that patients 5 and 8 have no lab rows and `package_candidate == [True, True]` (b2 bills labs, b3 and b4 are not package claims); `test_all_diagnoses_by_patient.py:162-166` (0005 list); `test_bill_billing_report.py:44-133` (S5 guest); `test_ingestion_optional_fields.py:129-146` (needs at least 3 material lines: there are 3 plus the walker). **Builder.** G1, G2, G5a (barcode), G7b (EK-3/C-2), G9 (duration). **Clinician.** The orthopaedist (complication and procedure), an orthogeriatrician (transfusion, romosozumab criteria), the billing officer (walker). **Size.** b2 0.75, b3 2.0, b4 0.75, b5 1.0 = 4.5 d.

#### F6 · S6 (man 79, aspiration pneumonia with Parkinson 2026-06-08 to 06-14): neurology control and a second walker (WP14)
- **b2** (`poliklinik`, 2026-06-29, Nöroloji 1300): control 15 days after discharge: exam `520030`, walker `OP1106` (first use). Clean. **b3** (`poliklinik`, 2026-08-10, Fiziksel Tıp ve Rehabilitasyon 1800): a second walker 42 days after the first.
- **Fault.** b3: the same EK-3/C-2 device inside its MIAT of 1 year (§3.1.2; clause id unverified) → `materials` `material_miat_interval` ✓ (N 1). Diagnoses on b2: G20 + R13 coded (S6's own fault is that G20 is missing from the admission).
- **Pins.** `test_claim_integration.py:75-110` asserts that S6's claim types are exactly `{yatis}` at patient level (rebind to bill level); `test_all_diagnoses_by_patient.py` (0006 list gains G20); `TS/test_cohort_labs.py` rows (40, no new labs). **Builder.** G1, G2, G7b. **Clinician.** A neurologist and a physiatrist. **Size.** 1.75 d.

#### F7 · S7 (woman 58, ER chest pain 2026-02-19, pulmonary embolism ruled out): observation under 24 hours and a follow-up (WP10)
- **b2** (`yatis`, one date 2026-02-25, Acil Tip observation): syncope R55 (+ R07.1): exam `520010`, ECG `530100`, troponin `L107360`, D-dimer `L102090` (repeated within 7 days of S7's ER bill: a `tablo15_12` duplicate-test review as a structural cross-bill hit with S7's own bill), no bed line. **b3** (`poliklinik`, 2026-03-12, Göğüs 1171): follow-up, exam `520030` + chest X-ray `801720`. Clean.
- **Fault.** b2: the day bed `510120` not billed on a stay under 24 hours (C000648; clean twin: `510120` billed) → action `yatak_puani_day_bed` 44.45 ✓ (N 1). Departments avoid "Kardiyoloji" (four Fatura İnceleme rules match any cardiology claim, EI-24).
- **Pins.** S7 is the clause/"compliance" patient of `verify-workspace-views.mjs:11-17` (`clausePatient = showcase_S7`) and of the capture states; `TS/test_cohort_labs.py:2299-2335` (S7's only lab gap is the PACS CT angiography; b2 and b3 bill their labs, so no new gap); the four performed lines belong to claim 001 only. **Builder.** G1, G2, G3 (one-date stay). **Clinician.** An emergency physician. **Size.** 1.5 d.

#### F8 · S8 (woman 47, cholecystectomy + umbilical hernia 2026-09-15 to 09-16, two packages): ER green area, ERCP admission, control (WP17)
- **b2** (`acil`, 2026-08-25, 3 weeks before): biliary colic, low acuity: green-area exam `520021` billed together with CRP `L101850` and abdominal ultrasound `803602`. **b3** (`yatis`, 2026-09-27 to 09-29, 11 days after the package discharge, outside any package window): retained common-bile-duct stone: ERCP `701360`, sphincterotomy `701370`, stone extraction `701440`. **b4** (`poliklinik`, 2026-09-30): post-ERCP control. Clean.
- **Faults.** b2: tests and imaging beside a flat-fee visit (Tablo 15 #7). b3: the ERCP codes at full price where the highest is paid in full and the others at 30 % (SUT 2.2.2.A(5)(a): C000659–C000661) → `GENEL CERRAHİ-1.endoskopik_bilier_islemler_bundling` matched ✓ and a session over-billing audit row (not separately measured). N 2, E +1.
- **Pins.** The "patients 5 and 8 have no lab rows" and `package_candidate == [True, True]` pins (as F5; b3 bills a lab and is not a package claim), `test_all_diagnoses_by_patient.py:162-166` (0008 list gains K80.5, K91.5), `CO/engine_proof.py:90-100` (S8's known divergence 3,584.80 vs 5,377.20, harmless once the proof is bill-scoped). **Engine issues.** #335 (b2). **Builder.** G1, G2. **Clinician.** An emergency physician, a general surgeon. **Size.** 3.0 d (b2 0.75, b3 1.75, b4 0.5).

### 5.6 Cards: conditional extensions (short)

- **F2 b5 · home BPAP (device `DO1013`, pre-approval).** EK-3/C-1 has no price in the curated list (`ek3c_list_price_missing`): a priced EK-3 device with the flag, or a plausibility exception, must be decided first. ≈ 0.75 d.
- **X1 · hip revision, `material_uplift`.** `P612480` (39,144.00) with the acetabular cup `AP1390` not billed: ceiling 3,295.04; the clean twin is not silent (549.17: KDV 20 % against ex-VAT billing) and the 12 pairings are `sut_derived_unverified` (EI-10). Build only after that verification.
- **X2 · rare detector hosts.** Living-donor liver transplant pair (donor visit as exam with `occupational_context` donor; recipient `P609080`, 908,561.20, plus a separate surgical line), a bone-cement line with a blank type, and the neuronavigation add-on `P614981` without a D-5 primary (the sibling id of F3's neuromonitoring). Four ids; two of them (the transplant scope and the neuronavigation add-on) are `unavailable` by spec. Dental general-anaesthesia stories stay out: the +30 % rule is not in the SUT corpus (EI-21).
- **X3 · specialty breadth (remainder).** Four coherent patients from the 40 code-keyed Fatura İnceleme rules (§2.4) that no bill above hosts: a TB work-up (`608320`, `908290`, `906180`; `608320` is on EK-2/C-1 at 20 %), a pregnancy (`803650`, `704541`, `620620`), a hand fracture (`610950`, `611320`), a cardiac work-up. Needs numeric lab codes in the lab kind (G7e). Check each rule's denial text against the story first; two rules are already hosted (`BEYİN-2…` by F3, `GENEL CERRAHİ-1…` by F8).
- **X4 · EK-2/G surcharge.** Oncologic surgery on the EK-2/G list (213 codes) without the flag: a patient-alert count, not a block; unblocked by G5b (WP9).
- **X5 · special rooms** `510100`/`510110`: silent by design; 444.72 on a partly billed room; heavy clinical review for almost no output.
- **X6 · dormant (S18):** a `poliklinik` bill on the day of b1's admission, same branch (C000575). **X7 · dormant (S4):** a second specialty on b2's date (C000576). Both expected to show nothing until #337.

### 5.7 Not proposed, with the reason

| Item | Reason |
|---|---|
| Physiotherapy sessions | no new matched rule is reachable: proxies force `unavailable`, the ESWT rule keys a nonexistent code, history is not read (EI-8) |
| `drg_uplift`, `care_setting_review`, the +100 % ICU ilave oran | need a basamak-3 facility: **decided, no second facility** (2026-10-21); `care_setting_review` is also unreachable at catalog prices (EI-22) |
| `drg_package_adequacy` | the rule corpus is clinically incoherent (EI-9) |
| Dental general anaesthesia | the +30 % basis is absent from the SUT corpus (EI-21) |
| `detect_inpatient_on_outpatient` | vocabulary artifact and a false positive on day-case `ameliyat` (EI-17) |
| `detect_normal_poliklinik_wrong_method`, the two non-emitting detectors | dead or non-emitting (EI-13) |
| Prior therapy (C003457), prior dental prosthesis (C000761) | no column holds a prior drug record; the window cannot hold a bill years earlier |
| Stem-cell add-on after an allogeneic transplant | heavy hematology timeline, report surfacing unverified |

## 6. Execution schedule: work packages WP2 to WP19

WP1 (slices G0 + G12 and story S9) was built by the session `demo-wp1-g0-g12-s9` (commit `bbd4b5fc` on `claude/charming-mestorf-1a365c`, CI-image gate green; push and PR were pending when this was written); this schedule takes it as given and starts after its merge. Everything below is ordered by dependency first and value second, and is **strictly sequential**: the generator core (`scripts/synthetic/cohort/`, `scripts/synthetic/pathways/`, `scripts/synthetic/faults/`) is shared, so no two writers ever touch it at once.

### 6.1 Rules of the program

1. **One work package = one session = one PR on `main`.** A package starts from a `main` that already contains the previous one (a session card's worktree always starts at `main`, so a package cannot build on an unmerged branch), and the next one starts only after Safa's push / PR / merge word. Staging is updated after a merge only on Safa's call.
2. **Brief.** Each session gets its card from §6.3 plus the pin classes of §7.5. It reports the G12 metric diff (before and after, §6.4 target) and the gate result at the end.
3. **The gate**, named in every card:
   - **B (backend)**: the CI-parity gate in the CI image, one at a time (about 3–4 minutes): `ruff check src/ scripts/`; `python -m pytest -q -n auto` (it contains the committed-data `build --check` and the golden `--check`); `python scripts/sut/compile_rules.py --check`; `python scripts/sut/audit_manifest_parity.py --drug-only`. Before it: `docker ps | grep -i bilun` and `free -g`; a foreign `bilun-ci-*` container counts as a gate. Locally one test fails on pandas 2.3.3 only (`tests/unit/scripts/test_curated_catalog_idempotence.py::test_pandas_string_storage_variation_does_not_change_decoded_semantics`), never attribute it to a change. The gate runs in the reviewed image `bilun-laptop-ci:20261008-runtime-complete`; a ready-made wrapper `~/.cache/bilun-p4-scratch/ci_gate.sh <label>` exists outside the repo (checked 2026-10-21; WP1 used it: 173 s). A second heavy job (vitest, a review harness, a full local pytest) counts as a gate.
   - **F (frontend)**, only where the card says so: `npx tsc --noEmit`, `npx vitest run`, `npm run build`, `python scripts/deploy/verify_public_assets.py --frontend .`.
   - **D (data)**, every package that changes committed data: `python -m scripts.synthetic.pathways.checks`, `python -m scripts.synthetic.faults.checks`, `python -m scripts.synthetic.cohort.build --check`, the golden exporter `--check`, `python -m scripts.synthetic.cohort.engine_proof`, the G12 diff (`python -m scripts.synthetic.cohort.coverage_metrics --out after.json --compare before.json`) equal to the card's target row, and the off-repo "16 showcase reports byte-identical" check: `python ~/.cache/bilun-newborn-scratch/baseline.py out.json` from the worktree root before and after, then `cmp` (a copy of the `bilun-puan-scratch` script; it dumps the 8 showcase stories at bill level, copay exempt and not, so it proves that claim 001 of S1–S8 did not change; there is no stored hash, because the dump format changes between sessions; a package that adds a bill to an existing patient reads the patient's other claims through `patient_history` and must keep this dump equal).
4. **Keep out of** `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`, `tests/*/deploy/**`. **Program-level consequence (P10):** every data package changes the 12 input files that the paused strict-release lane pins by hash (`scripts/deploy/verify_clinical_semantic_transition.py:652`); no CI test recomputes the hash, so nothing goes red, but that lane cannot pass until Safa re-reviews the inputs.
5. **Clinician items** never block a package; each pathway entry carries `basis` and `source` like the existing ones, each package adds its section to `reports/synthetic-data/2026-10-21-demo-stories-judgment-list.md` (created by WP1, S9 section) in the format of the first list, and the orchestrator carries the open items to issue #309.
6. **WP1 as delivered** (checked on 2026-10-21 against the assumptions of the first revision 2). **Met:** story ids `S<n>` with no upper limit, one per pathway, the first eight required and later ones optional; a fault is optional per bill (a clean bill has no record and no answer row); the additive registry key `scenarios` (`{S9: {patient_id, claim_ids}}`, `claim_ids` a list that later packages append to) at `schema_version` 1, roles unchanged (`default_landing`, `showcase_S1..S8`); the G12 script `scripts/synthetic/cohort/coverage_metrics.py` (`python -m scripts.synthetic.cohort.coverage_metrics --out X.json [--compare Y.json] [--claims-dir D] [--patients ID...]`, about 7 s; it passes no `copay_exemption` and no lab feed). **Not met:** the count pins of `tests/unit/synthetic/` were updated to the nine-patient literals, not re-pointed to registry-derived values. This moves into WP2 as the bounded step G0b (§6.3): the size pins (patients, claims, row counts) can come from `cohort.counts()`, while content pins (drawn lab values, abnormal counts) stay literal.
7. **Engine issues #335 (acil), #336 (blood ceiling), #337 (cross-bill inputs) stay open meanwhile.** The targets below assume they are open; after each is fixed, re-baseline with G12 and read the new numbers as a step of their own, not as a regression.

### 6.2 The schedule

| WP | Content | Bills added (patient) | Days | Cum. days | Gate |
|---|---|---|---|---|---|
| WP1 | G0 + G12 + S9 (built, commit `bbd4b5fc`) | S9 (9) | 3.5 | 3.5 | B, D |
| WP2 | count pins (G0b) + ICU grammar + S11 | S11 (10) | 5.0 | 8.5 | B, D |
| WP3 | newborn grammar + S12 | S12 (11) | 4.0 | 12.5 | B, D |
| WP4 | multi-encounter core (G2) | none | 4.0 | 16.5 | B, D (byte-identical) |
| WP5 | S14 + pin migration for new patients | S14 (10) | 2.0 | 18.5 | B, F, D |
| WP6 | visit grammar (G1) + F4 + pin migration for S1–S8 | F4 b2, b3 (4) | 4.5 | 23.0 | B, F, D |
| WP7 | lab code (G7a) + MEDULA events (G8) + S10 | S10 b1, b2 (12) | 4.0 | 27.0 | B, D |
| WP8 | chronic-report slice (G13) | none | 3.25 | 30.25 | B, F, D |
| WP9 | money flags (G5b) + F2 b2 (waiver) | F2 b2 (2) | 2.5 | 32.75 | B, D |
| WP10 | one-date stay (G3) + F7 + S20 | F7 b2, b3 (7); S20 (13) | 4.0 | 36.75 | B, D |
| WP11 | line flags (G5a) + fault ops (G6) + F2 b3, b4 | F2 b3, b4 (2) | 5.75 | 42.5 | B, D |
| WP12 | drug duration flag (G9) + S17 | S17 b1, b2 (14) | 3.0 | 45.5 | B, D |
| WP13 | S18 | S18 b1, b2 (15) | 2.0 | 47.5 | B, D |
| WP14 | EK-3/C-2 catalog (G7b) + F6 | F6 b2, b3 (6) | 3.25 | 50.75 | B, D |
| WP15 | F5 | F5 b2–b5 (5) | 4.5 | 55.25 | B, D |
| WP16 | F3 | F3 b2–b4 (3) | 3.5 | 58.75 | B, D |
| WP17 | F8 | F8 b2–b4 (8) | 3.0 | 61.75 | B, D |
| WP18 | F1 + S15 | F1 b2, b3 (1); S15 (11) | 3.0 | 64.75 | B, D |
| WP19 | S21 | S21 (16) | 1.5 | 66.25 | B, D |

Why this order. (1) Dark blocks first (WP1–WP3, WP7): the cheapest visible movement. (2) G2 (WP4) before any multi-bill data, on its own, with byte-identical committed data as the acceptance test, because it is the riskiest change of the program and everything after it builds on it. (3) The first new-patient multi-bill (WP5) and the first existing-patient follow-up (WP6) pay the two pin migrations once, in that order, with the smallest bills. (4) The chronic-report slice (WP8) comes right after WP7, which reaches the level of revision 1's batch 1, and before the bill that shows it (WP9). (5) Slice-first, story-second inside a package, and a slice is built by the first story that needs it (§7.1). (6) The patients with the longest reviews (S5, S3, S8) come late so that clinician answers can arrive meanwhile; the cheap structure-only bill (F1) and the high-count radiotherapy story come last.

### 6.3 Work package cards

Each card: **scope**; **files**; **pins that move** (classes of §7.5 plus what is specific); **target** (G12; cumulative; skeleton numbers, §6.4); **gate**; **unlocks**; **clinician**.

#### WP2 · Count pins (G0b) + ICU grammar + S11 (septic shock, ICU stay)
- **Scope.** **Step 0, G0b (≤ 0.5 d, stop when it passes):** derive the pure size pins of `tests/unit/synthetic/` (patients, claims, row counts, the `== 8`/`== 9`-style literals) from `cohort.counts()` and the registry instead of literals, as §6.1 rule 6 expected of WP1; leave content pins literal. Then G4a: kinds `icu_day` and `icu_package`, a `package.mode` exemption, `package.window` for ICU packages, per-kind stay coverage, `package_candidate` False for ICU packages, five check ids each with a registry entry and a mutation case. Story S11: pathway, fault (`set_billed_ratio 0.5` on the three `P552002` lines), recipe, clinical entry, story bill in `PR/stories.py`, golden and faulty golden, `prove.py S11`, `render.py`, direct-rows entry in `CO/engine_proof.py:539-548`.
- **Files.** `scripts/synthetic/pathways/{schema,checks,expand}.py`; `scripts/synthetic/cohort/{compose,plausibility,build,engine_proof}.py`; `data/synthetic/pathways/<icu pathway>.yaml`; `data/synthetic/faults/fault_registry.yaml`; `data/synthetic/cohort/{showcase_recipes,showcase_clinical}.yaml`; `reports/synthetic-data/2026-10-15-showcase-proofs/{stories,prove,render}.py` and `results/S11.json`; `tests/fixtures/pathways/golden{,_faulty}/`; the 12 tables and the registry.
- **Pins.** P1 (G0b makes the size pins registry-derived), P2 (residual), P3 (new story), **P11** (`tests/unit/domain/optimization/test_copay_rate_exposure.py:148-160`: the ICU packages are on EK-2/C-1 at 100 %; narrow the assertion with a written reason), the case auto-added for every `showcase_` role in `test_session_uplift_patient_0001.py:36-38` (the clean twin must show no session, DRG or headline uplift), P8, P10.
- **Target.** Blocks 10 → **11** (`icu_puani`); patients 9 → 10; bills 9 → 10; Wave A unchanged (evaluated 273, matched 14, rows 14).
- **Gate.** B, D. **Unlocks.** S14 (WP5), S15 (WP18). **Clinician.** An intensivist: ICU days, organ support, whether 510090 is billed on both end days.

#### WP3 · Newborn grammar + S12 (late-preterm newborn)
- **Scope.** G4b: kind `newborn_bed` (510070, 510081), `bed_day_codes`, age-aware vitals and lab bounds, department "Yenidoğan", composer `_BED_CODES`. Story S12 (fault: Kuvöz on the first days only, so that a later NICU bill can end on a Kuvöz day). No labs on the NICU bill unless the neonatologist supplies neonatal reference ranges.
- **Files.** As WP2 plus `scripts/synthetic/cohort/{clinical,plausibility_clean}.py` (vitals bounds `Boy 120–210 cm`, `Kilo 30–200 kg` are adult) and `data/synthetic/reference/code_sets.yaml` (510070/510081 are listed).
- **Pins.** P1–P3, P8, P10; `stay.bed_coverage`, `patient.age_gate`, `ana.vitals_bounds`; `tests/unit/synthetic/test_cohort_clinical.py` per-patient vitals dict.
- **Target.** Blocks 11 → **12** (`yenidogan_yatak`); patients 11; bills 11. **Gate.** B, D. **Unlocks.** S15 (WP18). **Clinician.** A neonatologist.

#### WP4 · Multi-encounter core (G2)
- **Scope.** Recipes gain `encounter_no`, optional per-encounter pins and an optional fault; the builder groups recipes by patient; claim and episode ids stay stable in build order (`claim_id(pid, k)`, ids allow 1..999) while the tables are laid out chronologically per patient (the lab, anadata and recete builders require patient-adjacent, date-ordered rows: `CO/labs.py:1240`, `CO/clean.py:581-614,641-660,811-817`); sex and birth year once per patient with the age-arithmetic check; one copay profile per patient; effective pins carried on `ComposedClaim`; lab draw `salt` raised for claim sequence ≥ 2 only, so single-claim patients stay byte-identical (`CO/labs.py:714-718,1323-1327`); roles and `default_landing` stop being overwritten (`CO/build.py:530-534`); `prove_showcase` and `TS/test_cohort_engine_proof.py:105` use `build_bill_claim_context` (`CO/engine_proof.py:798`). New tests use test-only two-encounter recipes in a temporary directory.
- **Files.** `scripts/synthetic/cohort/{recipes,build,clean,labs,clinical,engine_proof,plausibility}.py`; `tests/unit/synthetic/test_cohort_{recipes,build,clean,labs,clinical,engine_proof}.py`; `tests/fixtures/synthetic_cohort.py` (`fault(story)` keeps the last record of a repeated story). One story id per bill (§5.1a) keeps `fault.duplicate_story`, `fault(story)` and the JS `faultFor(story)` correct; WP4 only checks that no accessor returns the wrong record once a patient has two bills, and that `engine_proof.prove_story` is bill-scoped.
- **Pins.** P4 (engine proof scope), P6 (row-position and story-order assumptions, fixed here so WP6 only adds data), P1.
- **Target.** No metric change. **Acceptance: the 12 committed tables and the registry rebuild byte-identically (content-identically for parquet) and the 16-report gate is unchanged.**
- **Gate.** B, D. **Unlocks.** every multi-bill package. **Clinician.** None. **Risk.** The riskiest change of the program (14 assumptions, §7.3); stop-loss: if it passes 6 d, split into recipes/builder and clean/labs/proof.

#### WP5 · S14 (ward bill after the ICU) + pin migration for new multi-claim patients
- **Scope.** S14 as bill 2 of patient 10 (sibling pathway whose ward bill starts on the ICU discharge day; clean twin starts the next day). The first committed patient with two claims: the frontend and script pins that assume one claim per patient.
- **Files.** The pathway, sibling, recipe, clinical entry and story entries of S14; `frontend/scripts/lib/cohort-registry.test.mjs:24-25` (patient count now compared with `patient_copay_profiles`, not `anadata_clean`); `frontend/scripts/capture-screens.mjs:542-551,608-611`; `frontend/scripts/verify-workspace-views.mjs`; `frontend/scripts/RECORDING.md`; `data/synthetic/README.md` ("one claim each" model, counts).
- **Pins.** P7, P1, P8; `TS/test_cohort_labs.py:2299-2335` (a patient-level report must stay free of lab gaps).
- **Target.** Wave A matched 14 → **15**, rows 14 → **15** (the first financial row, `yatak_icu_overlap_510010`), evaluated 273 → 274; patients 11; bills 12; blocks 12.
- **Gate.** B, F (vitest), D. **Unlocks.** all follow-ups. **Clinician.** An intensivist.

#### WP6 · Visit grammar (G1) + F4 + pin migration for S1–S8
- **Scope.** G1: `poliklinik` and `gunubirlik` in `Pathway.claim_type`, every non-`yatis` type treated as a non-stay in the `acil` special cases. F4 b2 and b3 (patient 4; sibling for b3's fault, clean twin on day 14). The first follow-up on an existing patient pays the case-(i) pin migration (§7.5, P5–P7): the tests that read S1–S8 at patient level, the capture script picking its "compliance" patient by story, the revenue-KPI check scoped to the bill, the docs.
- **Files.** `scripts/synthetic/pathways/{schema,expand,checks}.py` and README; recipes; two pathways and one sibling; `tests/unit/cache/test_all_diagnoses_by_patient.py:157-166`; `TS/test_cohort_{clean,build,labs}.py` row-position and story-order assertions; `frontend/scripts/capture-screens.mjs:129-132`, `verify-workspace-views.mjs:146-149`; docs.
- **Pins.** P5, P6, P7, P9 (claim 001 byte-identical), P12 (the default pages of S4's patient), P1–P3, P8, P10.
- **Target.** Matched 15 → **17** (`tablo15_2_duplicate_exam_10day`, `ORTAK-20`), rows 15 → 16, evaluated 274 → **287** (the first outpatient claims), checklist `ORTAK-5`; patients 11; bills 14; blocks 12.
- **Gate.** B, F (script tests), D. **Unlocks.** every other follow-up, X7. **Clinician.** A geriatrician (light).

#### WP7 · Lab code (G7a) + MEDULA events (G8) + S10
- **Scope.** `L103120` in `lab_reference.csv` with a lab state; a recipe or fault input that yields `medula_rejection_events` rows (registry counts; the table was empty and skipped, `tables.py:318-321`); S10 b1 (`acil`) and b2 (`yatis`), sibling for the add-on omission, event `0901` on b1's `L103120` line.
- **Files.** `data/synthetic/reference/lab_reference.csv`; `scripts/synthetic/cohort/{build,tables,labs}.py`; `data/synthetic/cohort/showcase_clinical.yaml`; recipes; two pathways; story entries; `frontend/scripts/RECORDING.md:36-47` (the "known limit" of zero events); `tests/unit/synthetic/test_cohort_labs.py:110-124,333-336` (14 billed lab codes become 15).
- **Pins.** P1–P3, P8; `tests/unit/api/test_medula_rejection_queue_api.py:445-459` follows the registry (safe).
- **Target.** Blocks 12 → **15** (`lab`, `procedure_addon_uplift`, `medula_rejection_playbook`); matched 17 → **19**, rows 16 → **18**, evaluated 287 → **288**; patients 12; bills 16. This reproduces the batch-1 targets of revision 1.
- **Gate.** B, D. **Unlocks.** none. **Clinician.** An internist or gastroenterologist; the billing officer for the MEDULA text.

#### WP8 · Chronic-report slice (G13)
- **Scope.** The slices A, B and C of §7.4: the nullable column and its wiring, the generator carrier, the wording for the partial and the exempt state, tests; plus the G12 app-path copay mode if WP1's script has none (the waiver cannot show without the patient's `copay_exemption`, §7.4).
- **Files.** §7.4 table (about 20 files in `src/bilun/domain/claims`, `optimization`, `billing`, `api`, `scripts/synthetic`, `frontend/src`, the profile parquet and the registry digest).
- **Pins.** `tests/unit/synthetic/test_cohort_tables.py:742-751` (the 6-key literal), `test_cohort_build.py:218-256,331-333`, `test_cohort_tables.py:262,390-415`, the frontend tests of §7.4, `frontend/scripts/lib/numbers-parity.mjs:68-91` (the words "partial", "unverified" must survive), P10 (the profile parquet changes).
- **Target.** No Wave A or block change. App-path copay (G12 mode): rate corrections stay 11 until a flag is set; the UI shows "EK-1A match, report missing" for S2–S6 after a cache rebuild.
- **Gate.** B, F (tsc, vitest, build), D. **Unlocks.** WP9. **Clinician.** None (the billing officer reads the wording).

#### WP9 · Money flags (G5b) + F2 b2 (control with the chronic report)
- **Scope.** G5b minimal: a pathway field for a line's copay rate, the composer sets `copay_rate_applicable`, `copay_rate` and `expected_payable_try = billed × (1 − rate)` for that line only, the header payable total follows, and `money.payable_equals_billed` is relaxed for flagged lines. F2 b2 (poliklinik exam, 85.73 at 20 %); S2's profile carries `has_chronic_health_report` True through the carrier.
- **Files.** `scripts/synthetic/pathways/{schema,expand}.py`; `scripts/synthetic/cohort/{compose,plausibility,build}.py`; the S2 pathway pin and a new control pathway; `tests/unit/synthetic/test_cohort_plausibility.py:1661-1679,4203,4251,4273`, `test_cohort_compose.py:178-215`; the profile parquet; the registry.
- **Pins.** S2's app-path report changes on purpose (partial → exempt, the §1.8.2 row disappears, +1 `copay/exemption_review`), cohort KPIs exempt 1 → 2 of 12; `test_copay_rate_exposure.py:155` is respected because the waiver bill is not a fault; P1, P2, P10.
- **Target.** App-path copay: S2 exempt and the first money waiver on b2; Wave A and blocks unchanged; patients 12; bills 17.
- **Gate.** B, D, and one look at S2's patient page after a cache rebuild. **Unlocks.** X4. **Clinician.** A pulmonologist.

#### WP10 · One-date stay (G3) + F7 + S20
- **Scope.** G3: `nights: 0` (admission equals discharge) for `yatis`, and a `span:` for `gunubirlik`/`poliklinik` session claims, with the one-day window relaxed for non-stay claims. F7 b2 (observation under 24 h, day bed not billed) and b3. S20 (day-case hernia).
- **Files.** `scripts/synthetic/pathways/{schema,checks,expand}.py` (`:226-229,439,476-483,519-528`, `:544-549,558-576`, `:71-81`); `scripts/synthetic/cohort/plausibility.py:1216-1225,1347-1358`; three pathways; story entries.
- **Pins.** S7's patient pins: `frontend/scripts/verify-workspace-views.mjs:11-17` (`clausePatient = showcase_S7`) and the capture states; `TS/test_cohort_labs.py:2299-2335`; P1–P3, P8, P10.
- **Target.** Finding kind `yatak_puani_day_bed`; patients 13; bills 20; Wave A unchanged. **Gate.** B, D. **Unlocks.** S17 (date span). **Clinician.** An emergency physician; a surgeon (light).

#### WP11 · Line flags (G5a) + fault ops (G6) + F2 b3, b4
- **Scope.** G5a: `ProcedureFlags` (`isbt128_barcode`, `is_package_included`) and `MaterialFlags.requires_pre_auth`. G6: a quantity operation above the pathway bound of 999 (every operation must be used by some fault, `fault.op_coverage`). F2 b3 (readmission through the ER with `530000`, enoxaparin quantity fault) and b4 (control flagged as a package component).
- **Files.** `scripts/synthetic/pathways/schema.py:358-362,398`, `expand.py`; `scripts/synthetic/faults/{schema,mutate,checks}.py` (`:39-46`, `FA/checks.py:463-472`); `scripts/synthetic/cohort/compose.py:151-173,165,210`; two pathways; fault registry; story entries.
- **Pins.** S2's patient pins: `test_all_diagnoses_by_patient.py:162-166` (0002 list), `test_bill_billing_report.py:44-133` (S2 is a guest bill), `TS/test_cohort_labs.py:126,713`; the plausibility `material.stray_flag`; P1–P3, P8, P10.
- **Target.** Matched 19 → **21** (`tablo15_11_drug_quantity_error`, `tablo15_3_vakabasi_wrong_method`), rows 18 → 19, evaluated 288 → **290**; patients 13; bills 22. **Gate.** B, D. **Unlocks.** S18, F5. **Clinician.** A pulmonologist.

#### WP12 · Drug duration flag (G9) + S17
- **Scope.** G9: `drug_report_duration_months` settable from a pathway, drug routes for new patients. S17 b1 (a month of `P704230` as one `gunubirlik` claim with a date span, ESA prescribed by the wrong branch) and b2 (emergency dialysis `P704210`).
- **Files.** `scripts/synthetic/pathways/schema.py:365-370`, `expand.py:134`; `scripts/synthetic/cohort/compose.py:236-255`; `data/synthetic/cohort/showcase_clinical.yaml` (`drug_routes`); two pathways, a sibling; story entries.
- **Pins.** P1–P3, P8, P10; `P704230`/`P704210` are not on EK-2/C-1 (checked).
- **Target.** Finding kind `prescriber_specialty_mismatch`; patients 14; bills 24; Wave A unchanged. **Gate.** B, D. **Unlocks.** F5 b5. **Clinician.** A nephrologist.

#### WP13 · S18
- **Scope.** S18 b1 (albumin without the board report) and b2 (two red-cell units without ISBT numbers), lab states for albumin ≤ 2.5 g/dl. The endoscopy stays out of b1 (EI-11).
- **Files.** Two pathways, two fault records, recipes and clinical entries for patient 15 (`data/synthetic/pathways/`, `data/synthetic/faults/fault_registry.yaml`, `data/synthetic/cohort/`), the S18 entries of `PR/{stories,prove,render}.py` and `results/S18.json`, `CO/engine_proof.py:539-548`, the golden directories, the 12 tables and the registry.
- **Pins.** P1–P3, P8, P10; `TS/test_cohort_labs.py` lab-state keys.
- **Target.** Matched 21 → **22** (`blood_component_isbt128_barcode`), evaluated 290 → **291**, checklist readiness `0612` and kind `missing_board_report`; patients 15; bills 26. **Gate.** B, D. **Unlocks.** none. **Clinician.** A hepatologist or internist.

#### WP14 · EK-3/C-2 catalog (G7b) + F6
- **Scope.** G7b: a catalog parameter per EK-3 annex so that `OP1106` (EK-3/C-2, 252.00, MIAT 1 year) can be authored. F6 b2 (neurology control with the first walker) and b3 (physiatry visit with the second walker 42 days later).
- **Files.** `scripts/synthetic/cohort/catalogs.py:70-75,134-151`; `scripts/synthetic/pathways/checks.py:103-113`; `scripts/synthetic/cohort/plausibility.py:549-553`; two pathways, a sibling.
- **Pins.** S6's patient pins: `tests/unit/domain/billing/test_claim_integration.py:75-110` (claim types exactly `{yatis}` at patient level: rebind to bill level), `test_all_diagnoses_by_patient.py` (0006 list gains G20); P1–P3, P8, P10.
- **Target.** Finding kind `material_miat_interval`; patients 15; bills 28. **Gate.** B, D. **Unlocks.** F5 (walker). **Clinician.** A neurologist and a physiatrist; the billing officer (whether a hospital bills such devices).

#### WP15 · F5 (hip fracture follow-ups)
- **Scope.** F5 b2 (ER precursor), b3 (readmission with blood inside a package), b4 (control and walker), b5 (geriatrics, romosozumab with a 12-month report).
- **Files.** Four pathways, two fault records (b3, b5) and the sibling of b3's clean twin, recipes and clinical entries for patient 5 (lab states for b2 only), the 12 tables and the registry; the pins below.
- **Pins.** S5's patient pins: `tests/unit/domain/billing/test_claim_strategy_sut.py:517-548` (one `paket` line over all claims of the patient), `TS/test_cohort_labs.py:706-713,126` and `tests/unit/synthetic/test_cohort_plausibility_clean.py:1266-1274` (patients 5 and 8 have no labs and `package_candidate == [True, True]`), `test_all_diagnoses_by_patient.py:162-166`, `test_bill_billing_report.py:44-133`; P1–P3, P8, P10.
- **Target.** Finding kinds `blood_component_partial_bill` and `report_duration_mismatch`; patients 15; bills 32; Wave A unchanged. **Gate.** B, D. **Unlocks.** none. **Clinician.** An orthopaedist, an orthogeriatrician, the billing officer.

#### WP16 · F3 (lumbar stenosis follow-ups)
- **Scope.** F3 b2 (pre-operative takip, precursor), b3 (control), b4 (instrumentation with neuromonitoring).
- **Files.** Three pathways, one fault record (b4) with its clean-twin sibling, recipes and clinical entries for patient 3 (lab states for b2), the 12 tables and the registry; the pins below.
- **Pins.** `test_all_diagnoses_by_patient.py:162-166` (0003), `TS/test_cohort_labs.py` rows per patient (17 → more), P1–P3, P8, P10.
- **Target.** Matched 22 → **23** (`BEYİN-2…`), rows 19 → **21** (+ `conditional_addon_ek2d_neuromonitoring`, unavailable by spec); patients 15; bills 35. **Gate.** B, D. **Unlocks.** none. **Clinician.** A neurosurgeon.

#### WP17 · F8 (cholecystectomy follow-ups)
- **Scope.** F8 b2 (ER green area), b3 (ERCP admission), b4 (control).
- **Files.** Three pathways, two fault records (b2, b3) with the sibling of b3's clean twin (highest code in full, the others at 30 %), recipes and clinical entries for patient 8 (lab states for b2 and b3), the 12 tables and the registry; the pins below.
- **Pins.** The patients-5-and-8 lab and package pins (as WP15), `test_all_diagnoses_by_patient.py:162-166` (0008), P1–P3, P8, P10.
- **Target.** Matched 23 → **25** (`tablo15_7_green_area_bundled_extra`, `GENEL CERRAHİ-1…`), rows 21 → 23, evaluated 291 → **292**; patients 15; bills 38. **Gate.** B, D. **Unlocks.** none. **Clinician.** An emergency physician, a general surgeon.

#### WP18 · F1 (appendectomy follow-ups) + S15 (newborn ward bill)
- **Scope.** F1 b2 (ER precursor), b3 (control inside the 10 days after the package discharge, dormant). S15 as bill 2 of patient 11 (ward bill whose standard-bed lines overlap days a Kuvöz line already pays).
- **Files.** Two pathways for F1 (no fault record: b3 is dormant) and one pathway with sibling and fault record for S15, recipes and clinical entries for patients 1 and 11, the S15 entries of `PR/{stories,prove,render}.py` and `results/S15.json`, the 12 tables and the registry.
- **Pins.** S1 is the landing patient: the six S1 patient-level tests of F1 (`test_drg_uplift_wiring.py:331-382`, `test_session_uplift_patient_0013.py:55-99`, `test_billing_strategy_exactness.py:30-52`, `test_orchestrator_claim_cohort_flow.py:14-48`, `test_bill_billing_report.py:44-133`, `test_cohort_plausibility_clean.py:1341-1376`), `frontend/scripts/verify-workspace-views.mjs:146-149`; P1–P3, P8, P10.
- **Target.** Finding kind `yatak_newborn_overlap_double_billing`; patients 15; bills 41; Wave A unchanged. **Gate.** B, D. **Unlocks.** none. **Clinician.** A surgeon (light), a neonatologist.

#### WP19 · S21 (radiotherapy course)
- **Scope.** S21: one claim carrying the course; the 8xxxxx codes need a grammar kind (accept `imaging` or add `radiotherapy`); date span if outpatient (G3 paid).
- **Files.** `scripts/synthetic/pathways/{schema,checks}.py` (the grammar kind), one pathway with sibling and fault record, recipe and clinical entry for patient 16, the S21 entries of `PR/{stories,prove,render}.py` and `results/S21.json`, `CO/engine_proof.py:539-548`, the golden directories, the 12 tables and the registry.
- **Pins.** P1–P3, P8, P10.
- **Target.** Rows 23 → **35** (12 radiotherapy ids, financial reviews, `unavailable` by spec); patients 16; bills 42; matched and evaluated unchanged. **Gate.** B, D. **Unlocks.** none (end of the schedule; the conditional tail is §6.6). **Clinician.** A radiation oncologist.

### 6.4 Milestones (skeleton, cumulative; the G12 diff of each package is the real check)

| After | Patients | Bills | Blocks with output | Wave A evaluated | matched | rules with a row | What the user sees |
|---|---|---|---|---|---|---|---|
| Baseline `main` be4b9ec7 | 8 | 8 | 9 | 273 | 14 | 14 | |
| WP1 | 9 | 9 | 10 | 273 | 14 | 14 | `session_uplift` |
| WP2 | 10 | 10 | 11 | 273 | 14 | 14 | `icu_puani` |
| WP3 | 11 | 11 | 12 | 273 | 14 | 14 | `yenidogan_yatak` |
| WP4 | 11 | 11 | 12 | 273 | 14 | 14 | nothing (generator) |
| WP5 | 11 | 12 | 12 | 274 | 15 | 15 | first Wave A financial row |
| WP6 | 11 | 14 | 12 | 287 | 17 | 16 | S4 becomes a multi-bill patient; duplicate exam; `ORTAK-20`, `ORTAK-5` |
| **WP7** | 12 | 16 | **15** | **288** | **19** | **18** | `lab`, add-on, playbook (batch 1 of revision 1) |
| WP8 | 12 | 16 | 15 | 288 | 19 | 18 | partial-state wording on S2–S6 |
| WP9 | 12 | 17 | 15 | 288 | 19 | 18 | S2 exempt, first money waiver |
| WP10 | 13 | 20 | 15 | 288 | 19 | 18 | day bed under 24 h |
| WP11 | 13 | 22 | 15 | 290 | 21 | 19 | drug quantity, vakabasi |
| WP12 | 14 | 24 | 15 | 290 | 21 | 19 | `prescriber_specialty_mismatch` |
| WP13 | 15 | 26 | 15 | 291 | 22 | 19 | ISBT, `missing_board_report`, `0612` |
| WP14 | 15 | 28 | 15 | 291 | 22 | 19 | MIAT |
| WP15 | 15 | 32 | 15 | 291 | 22 | 19 | blood audit, duration mismatch |
| WP16 | 15 | 35 | 15 | 291 | 23 | 21 | `BEYİN-2…`, neuromonitoring |
| WP17 | 15 | 38 | 15 | 292 | 25 | 23 | green area, ERCP bundling |
| WP18 | 15 | 41 | 15 | 292 | 25 | 23 | newborn double billing |
| **WP19** | **16** | **42** | **15** | **292** | **25** | **35** | radiotherapy rows |

Not measurable on a skeleton (and therefore not in the table): the app-path copay changes of WP8 and WP9. They are measured with the G12 app-path mode (§7.4): rate corrections 11 now (7 by script), S2's status and the waiver.

### 6.5 Cost

| Part | Revision 1 (batches 1 and 2) | Revision 2 (WP1–WP19) |
|---|---|---|
| Generator slices | 23.0 | 25.5 (adds G5b 1.5, the G12 app-path mode 0.5 and G0b 0.5) |
| New-patient stories and their bills | 23.5 | 14.5 (S13, S16, S19 retired: −9.0) |
| Follow-up bills on S1–S8 | 0 | 21.0 |
| Pin migrations (first multi-claim patient 1.0, first existing-patient follow-up 1.5) | not budgeted | 2.5 |
| Chronic-report slice (slices A, B, C) | 0 (S13 b4 and G5b were batch 3) | 2.75 |
| **Total** | **46.5** | **66.25** (WP1 3.5 built; WP2–WP19 62.75) |

Clinical review is separate and comes in one pass per package. About 9 of the 63 days are pure pin and regeneration work. Conditional tail (§6.6): ≈ 20.75 d.

### 6.6 What the schedule does not include (conditional, in this order of cheapness)

| Item | Entry condition | Days |
|---|---|---|
| X4 EK-2/G surcharge | none after WP9 (G5b paid) | 1.5 |
| X6, X7 dormant bills | any time; expected to show nothing until #337 | 2.0 |
| F2 b5 home BPAP device | a price source or a plausibility exception for EK-3/C-1 devices | 0.75 |
| X1 hip revision (`material_uplift`) | the EI-10 verification (KDV 10 % against 20 %, 12 unverified pairings) | 1.5 |
| X5 special rooms (G4c) | Safa wants the finished item shown | 2.5 |
| X2 rare detector hosts | a transplant surgeon's time | 5.0 |
| X3 specialty breadth (+ G7e) | one clinician per branch | 7.5 |

None of them is needed to reach the block ceiling (15 of 20, or 16 with X1 and 17 after #336).

## 7. Generator slices, data-model gaps, the chronic-report slice and the pin classes

Paths: `PW/` = `scripts/synthetic/pathways/`, `CO/` = `scripts/synthetic/cohort/`, `FA/` = `scripts/synthetic/faults/`, `PR/` = `reports/synthetic-data/2026-10-15-showcase-proofs/`, `CL/` = `src/bilun/domain/claims/`, `SRC/` = `src/bilun/`, `TS/` = `tests/unit/synthetic/`. Evidence is from read-only research passes of 2026-10-20 and 2026-10-21; nothing was run in the generator and no gate was run.

### 7.1 Generator slices (priced once, built by the work package that first needs them)

| Slice | What changes | Evidence | Tests and pins that move | Days | Built in |
|---|---|---|---|---|---|
| **G0** un-lock S1–S8 | `Pins.story` `^S[1-8]$`, the `Story` literal and `SHOWCASE_STORIES`, `fault.story_coverage`/`fault.op_coverage`/`fault.duplicate_story`, `recipe.patient_numbers`/`recipe.duplicate_fault`, `clinical.patient_numbers`; goldens bijection and the sibling folder; a new top-level registry key `scenarios` (not new `roles`, so the three role pins stay) with accessors in the Python fixture and the JS reader; make `fault` optional per bill | `PW/schema.py:435`; `FA/schema.py:37,94,211`; `FA/checks.py:442-472`; `CO/recipes.py:186-216,243-260`; `CO/clinical.py:412-434`; hard-coded `PATHWAYS_DIR` at `PW/loader.py:21,175`, `CO/recipes.py:220`, `FA/checks.py:74,137`, `CO/build.py:488`, `CO/clean.py:406`, `CO/labs.py:1296`, `CO/clinical.py:358`, `CO/plausibility.py:496` | P1, P2 (`TS/test_pathways_roundtrip.py:30,194-200`; `test_pathways_golden.py:30,108-149`; `test_fault_siblings.py`; `test_pathways_schema.py`; `test_cohort_recipes.py:58,94,235`; `test_cohort_build.py:135,226-234,283-310,344-355`; `test_synthetic_cohort_fixture.py:30,63-65,161-167,217-224,299-308`; `frontend/scripts/lib/cohort-registry.test.mjs:17-19`) | 2.0 | WP1 (built) |
| **G12** measurement script | one repo script with the §9.2 map and a diff mode (prototypes `~/.cache/bilun-tools/demo_coverage_blocks.py`, `demo_coverage_inputs.py`) | §9.4 | none | 0.5 | WP1 (built) |
| **G4a** ICU grammar | kinds `icu_day` and `icu_package` in `Kind`/`KIND_GROUPS`; `package.mode` exemption and `package.window` for ICU packages; per-kind stay coverage so a bed and an ICU line cover each day once except the transfer day; `package_candidate` False for ICU packages | `PW/schema.py:175-177`; `PW/checks.py:45-48,267-277,385-425,580-602`; `CO/build.py:518`; plausibility already counts 510090/P55200x as bed days (`CO/plausibility.py:427-435`) | five check ids, each needing a registry entry and a mutation case (`PW/schema.py:32-33`); P11 | 3.0 | WP2 |
| **G4b** newborn grammar | kind `newborn_bed` (510070, 510081); `bed_day_codes`; age-aware vitals and lab bounds; department "Yenidoğan"; composer `_BED_CODES` | `PW/checks.py:267-272`; `CO/plausibility.py:228-233,427-435`; `CO/clinical.py:155-176`; `CO/plausibility_clean.py:357-365`; `CO/compose.py:32` | `stay.bed_coverage`, `patient.age_gate`, vitals bounds | 2.5 | WP3 |
| **G2** multi-encounter | `encounter_no` and optional per-encounter pins on the recipe; claim and episode sequence from the encounter, tables laid out chronologically per patient; one copay profile per patient; effective pins carried on `ComposedClaim`; lab draw salt for sequence ≥ 2 only; roles and `default_landing` no longer overwritten; `prove_showcase` bill-scoped. Details in §7.3 | `CO/recipes.py:85-90,186-216`; `CO/build.py:499-554`; `CO/clean.py:295-324,414,422-440,478-480,520-524`; `CO/labs.py:714-719,1261-1327`; `CO/engine_proof.py:795-804`; `CO/plausibility.py:1071-1089,1095-1126` | P1, P4, P6; acceptance = byte-identical committed data | 4.0 | WP4 |
| **G1** visit grammar | add `poliklinik` and `gunubirlik` to `Pathway.claim_type`; treat every non-`yatis` type as a non-stay in the `acil` special cases | `PW/schema.py:448,479-481,526`; the clean-table builder already knows both types (`CO/clean.py:126-131`); plausibility knows them (`CO/plausibility.py:273,1168-1224,1347-1358`); `expand`/`compose` need no change (`520030` is `muayene`, `CO/compose.py:78`) | `TS/test_pathways_schema.py`, `test_cohort_recipes.py`, goldens, pathways README | 1.5 | WP6 |
| **G7a** lab reference | `L103120` (manual haematocrit) in `data/synthetic/reference/lab_reference.csv` with lab states (the file holds 49 codes; `L103120` appears only inside a note, while `L101850` CRP is already a reference code) | `PW/checks.py:353`; `CO/labs.py` | lab tests (14 codes pinned at `TS/test_cohort_labs.py:110-124,333-336`) | 0.5 | WP7 |
| **G8** MEDULA events | a recipe or fault input that yields event rows; registry counts | `CO/build.py:560` (`medula_events=()`); serialization exists `CO/tables.py:246-254`; date rule `CL/validation/dates.py:17-31`, `CL/validation/links.py:116-140` | `frontend/scripts/RECORDING.md:36-47` ("known limit": zero rows) | 1.5 | WP7 |
| **G13** chronic-report slice | nullable `has_chronic_health_report` on the patient profile, one default in `build_copay_exemption_input`, a carrier in the generator, wording for the partial and the exempt state. Details in §7.4 | §7.4 | §7.4 | 2.75 | WP8 |
| **G12b** app-path copay mode | the measurement script passes the patient's `copay_exemption` (built as the cache does) so the waiver and the rate corrections are measured as the app shows them | §7.4, §9.4 | none | 0.5 | WP8 |
| **G5b** flags with money | a pathway field for a line's copay rate; the composer sets `copay_rate_applicable`, `copay_rate`, `expected_payable_try = billed × (1 − rate)` for that line only and the header payable total follows; `money.payable_equals_billed` relaxed for flagged lines (also `surcharge_applicable` for X4) | `CO/compose.py:164-168,274-298`; `CO/plausibility.py:114,1844-1855`; `CL/totals.py:55-61` | `tests/unit/domain/optimization/test_copay_rate_exposure.py:150-161,172-210`; `TS/test_cohort_plausibility.py:1661-1679,4203,4251,4273`; `test_cohort_compose.py:178-215` | 1.5 | WP9 |
| **G3** one-date stay and date span | `nights: 0` (admission == discharge) for `yatis`; a `span:` for `gunubirlik` and `poliklinik` session claims (`claim_end` from the span); relax the one-day window for non-stay claims | `PW/schema.py:226-229,439,476-483,519-528`; `PW/checks.py:544-549,558-576`; `PW/expand.py:71-81`; `CO/plausibility.py:1216-1225,1347-1358` | pathway schema mutation cases; plausibility `stay.dates_in_window` | 1.5 | WP10 |
| **G5a** line flags without money | `ProcedureFlags` (`isbt128_barcode`, `is_package_included`) and `MaterialFlags.requires_pre_auth` on pathway lines, passed through `expand` and `compose` | `CO/compose.py:151-173,165,210`; `PW/schema.py:358-362` | pathway schema; plausibility `material.stray_flag` | 1.5 | WP11 |
| **G6** fault ops | a quantity op (above the pathway bound `Drug.qty` 1..999), optionally a blank-value op for `material_type`, optionally several faults per bill | `FA/schema.py:39-46` (six ops); `PW/schema.py:379,398`; `FA/checks.py:463-472` (`fault.op_coverage` requires every op) | fault registry/mutations/answer-key tests | 2.0 | WP11 |
| **G9** drug flags | `drug_report_duration_months` settable from a pathway; drug routes for each new patient in `data/synthetic/cohort/showcase_clinical.yaml` | `PW/schema.py:365-370`; `PW/expand.py:134`; `CO/compose.py:236-255` | clean `recete` table | 1.0 | WP12 |
| **G7b** other EK-3 annexes | a catalog parameter per annex for EK-3/C-2 (`OP1106`, `OP1000`) | `CO/catalogs.py:70-75,134-151`; `PW/checks.py:103-113`; `CO/plausibility.py:549-553`; 26 priced EK-3 catalogs share the columns `sut_code, material_name, description, price_try`, only `ek3o` carries dates; `MaterialCode` `^[A-Z]{2}[0-9]{4}$` fits | material checks | 1.5 | WP14 |
| **G4c** special rooms | codes 510100/510110 in `data/synthetic/reference/code_sets.yaml` and a kind | `check_procedure_kinds` blocks them (`PW/checks.py:262-296`) | pathway checks | 1.0 | tail (X5) |
| **G7e** numeric lab and imaging codes | `lab` kind for numeric 9xxxxx codes needs reference rows and states | `KIND_GROUPS` pairs groups 9/10 with `lab` only | lab tests | 1.5 | tail (X3) |
| Pin migration, first multi-claim new patient | the frontend and script pins that assume one claim per patient (P7) | §7.5 | P7, P1 | 1.0 | WP5 |
| Pin migration, first follow-up on an existing patient | the patient-level readers of S1–S8 and the row-position tests (P5, P6, P7) | §7.5 | P5, P6, P7, P9 | 1.5 | WP6 |
| **G0b** count pins | derive the size pins of `tests/unit/synthetic/` (patients, claims, row counts) from `cohort.counts()` and the registry; content pins stay literal (WP1 updated the literals to nine patients and did not do this) | §6.1 rule 6; P1 | the files of P1 | 0.5 | WP2 |
| | **Total through WP19** (slices 25.5 + chronic slice 2.75 + pin migrations 2.5 = 30.75 d; the stories add 35.5) | | | **30.75** | |
| | **Tail slices** (G4c, G7e) | | | 2.5 | tail |

Slices alone: G0 2.0, G12 0.5, G4a 3.0, G4b 2.5, G2 4.0, G1 1.5, G7a 0.5, G8 1.5, G12b 0.5, G5b 1.5, G3 1.5, G5a 1.5, G6 2.0, G9 1.0, G7b 1.5 + G0b 0.5 = **25.5 d**. Revision 1 priced 23.0 d of slices for batches 1 and 2; the difference is G5b (1.5 d, was batch 3), G12b (0.5 d) and G0b (0.5 d).

### 7.2 Data-model gap list (fields and tables, with loader, schema and test touchpoints)

New tables: **none**. The paused strict-release lane pins exactly 12 input files (`scripts/deploy/generate_candidate_source_roster.py:30-45`, `scripts/deploy/verify_clinical_semantic_transition.py:652`); only columns and rows are added. Every new column needs a default (139 `ClaimHeader(` and 101 `ProcedureClaimLine(` constructor sites in tests, 3 in `src`: `CL/adapter.py`, `rule_engine.py`, `CL/parsing/row_parsers.py`), a parser entry, and the dtype map in `CO/tables.py`.

| # | Need | Exists? | Change | Loader / schema | Generator | Tests and pins | Used by |
|---|---|---|---|---|---|---|---|
| 1 | `has_chronic_health_report` | **no column**; only an argument of `build_copay_exemption_input` that no caller passes (EI-6) | **decided 2026-10-21:** nullable bool on `PatientCopayProfile`, default read in the one builder function (§7.4) | `CL/models.py:19-26`; `CL/parsing/row_parsers.py:131-160`; `SRC/domain/optimization/copay_exemption_context.py:11-52` | `CO/tables.py:105-118`; `CO/build.py:526-528` | §7.4 (the all-diagnoses fix is in `main` since #333) | F2 b2 (WP8–WP9) |
| 2 | incision code `ayniFarkliKesi` (optional) | **no field** | nullable column on `ProcedureClaimLine` | `CL/models.py:65-95`; `CL/parsing/row_parsers.py:258-308` | composer mapping from `session_role` (`PW/expand.py:18-33`) | call sites that pass `same_incision=None`: `billing/claim_strategy.py:714-746`, `claim_session_uplift.py:41-46`, `claim_audit_exposure.py:56`, `optimization/unbundling.py:64`, `prose_rules/drg_unbundling.py:354-386`; removes the documented S8 divergence (`CO/engine_proof.py:90-100`, 3,584.80 against 5,377.20) | S9 (optional; meaning of codes 2–5 unverified) |
| 3 | line flags | **columns exist**, constant in the composer (`isbt128_barcode` empty, `is_package_included` False, `requires_pre_auth` False, surcharge and copay flags False, payable == billed) | pathway flags (G5a, G5b) | none | `CO/compose.py:151-173,164-168,210` | G5b: `test_copay_rate_exposure.py:150-161,172-210` | F5, F2, S18, X4 |
| 4 | drug report duration | column exists, not settable | `DrugFlags` field (G9) | none | `PW/schema.py:365-370`; `PW/expand.py:134` | clean `recete` | F5 b5, S17 |
| 5 | quantity above 999, blank `material_type` | `Drug.qty` ≤ 999 and `MaterialType` is a Literal | fault ops (G6) | none | `PW/schema.py:379,398`; `FA/schema.py:39-46` | fault op coverage | F2 b3, X2 |
| 6 | MEDULA rejection rows | table and parser exist, 0 rows | rows plus builder input (G8) | `CL/validation/links.py:116-140` (claim, patient, episode must match); `CL/validation/dates.py:17-31` (timestamp inside the claim range) | `CO/build.py:560` | registry `counts`; `RECORDING.md:36-47` | S10 |
| 7 | materials outside EK-3/F-1 | 26 priced catalogs exist | catalog parameter (G7b) | none | `CO/catalogs.py:134-151` | material checks | F5 b4, F6 |
| 8 | previous-claim or takip reference | **none** (cross-bill rules infer relations from patient, dates and codes) | optional nullable header column, no engine reader | `CL/models.py:29-49` | — | — | only if EI-12 (#337) chooses an explicit link |
| 9 | newborn birth date | `birth_year` only; the engine reads `Z38`/`P00-P96` and the department, not age | none | — | — | — | — |
| 10 | `provider_contract_status` | **no column**; `provider_type` carries ownership and contract status (EI-3) | nullable string on `ClaimHeader` | `CL/models.py:29-49`; `CL/parsing/row_parsers.py:84-128` | `CO/build.py:515` | `prose_rules/gap_closing.py:435-438` | not needed by any story |
| 11 | rule-vocabulary service category | **no column**; composer writes 5 labels, rules read 113 (EI-5) | `service_category` column plus readers | `CL/models.py`; `CL/parsing/row_parsers.py:287` | `CO/compose.py:71-80` | all procedure-category readers | X3's 17 category-keyed rules |
| 12 | prior drug record (`medula_record_of_prior_drug`) | **none** | blocked (also needs EI-12) | — | — | — | prior-therapy bills |

### 7.3 Where the generator assumes one claim per patient (what G2 changes in WP4)

Acceptance of WP4: the 12 committed tables and the registry rebuild **byte-identically** (content-identically for the parquet files), the proofs `results/S1.json`…`S8.json` do not change, and the 16-report gate (§6.1) is unchanged. New tests use two-encounter recipes in a temporary directory; nothing is committed that has a second encounter before WP5.

| # | Assumption today | Where | What WP4 does |
|---|---|---|---|
| 1 | one recipe = one patient = one claim; a fault is mandatory | `CO/recipes.py:85-90,186-216,243-260`; `CO/clinical.py:412-436` (`recipe_by_no` keeps the last recipe) | recipes gain `encounter_no`; patient numbers may repeat across encounters; the fault is optional (G0); `recipe_by_no` is keyed by (patient, encounter) |
| 2 | claim and episode ids are `…-001` | `CO/build.py:507-509`; `CO/ids.py:36-53` (1..999 are allowed) | `claim_id(pid, k)` with `k` from the encounter, in build order, **stable** when a later package adds an encounter |
| 3 | one copay profile, one sex and birth year per recipe | `CO/build.py:526-528,551`; `CL/indexing.py:27` (a duplicate profile row is a load error); `CO/plausibility.py:1071-1089`; `CO/plausibility_clean.py:1551-1555` | one profile per patient from the first encounter; later encounters must agree (age-arithmetic check) |
| 4 | dates, age, nights, optional items and course days are read from `pathway.showcase` | `CO/build.py:504-505`; `CO/clean.py:433-440,517-524`; `CO/labs.py:1305-1308`; `CO/plausibility.py:521-545` (a follow-up with an optional item outside the pins trips `fit.pathway_membership`, `:1095-1126`) | effective pins travel on `ComposedClaim`; `expand` and `apply_fault` already accept `pins` (`PW/expand.py:53-55`, `FA/mutate.py:222-243`) |
| 5 | lab, anadata and recete rows must be patient-adjacent and date-ordered | `CO/labs.py:1240,1301-1318`; `CO/clean.py:581-614,641-660,811-817` | tables are laid out per patient in the chronological order of the encounters while claim ids keep build order (a precursor bill dated before `b1` gets a later id, so the id order is not the date order) |
| 6 | vitals and lab states are per patient | `CO/clean.py:422-427`; `CO/labs.py:1261-1283,1310`; `showcase_clinical.yaml` keyed by `patient_no` | keyed by patient and encounter; a state key must name a lab that the claim bills |
| 7 | two claims of one patient get identical lab values for the same code | `CO/labs.py:714-718,1323-1327,1371,1402` (the draw key restarts at `k = 1` per claim, salt always 0) | salt raised only for claim sequence ≥ 2, so single-claim patients stay byte-identical (pinned values `TS/test_cohort_labs.py:1285-1307`) |
| 8 | visit counts are constants (1 / 1 / 0) and `kohort` is the literal `showcase` | `CO/clean.py:478-480,497,540`; `CO/labs.py:116` | unchanged unless an engine reader needs them (none today) |
| 9 | roles and landing | `CO/build.py:530-534`: `story = fault.story or pins.story`; `roles[...]` is a plain assignment, so a second bill of a story overwrites it; `default_landing` follows `idx == 0 or story == "S1"` | roles and `default_landing` stop being overwritten; the `scenarios` key records patient → bills |
| 10 | one clean twin per recipe | `CO/build.py:521,548`; `TS/test_cohort_plausibility.py:2035-2047` (every twin header needs a fault record) | one twin per encounter; a clean bill needs no fault record |
| 11 | the engine proof is patient-level on the faulty side and bill-level on the clean side | `CO/engine_proof.py:175-195,798-804`; `TS/test_cohort_engine_proof.py:105` | bill-scoped context `build_bill_claim_context(patient, claim, loaded)` (`CL/patient_context.py:188-207`) |
| 12 | patient-level readers merge episodes | `SRC/cache/context.py:151-200` (age and sex from the first anadata row); `SRC/domain/optimization/shared.py:58-105` (diagnosis union, principal first, from #333); `SRC/domain/optimization/copay_exemption_context.py:27-38` | none: follow-up bills extend these lists on purpose (P5); the cache payload lists the first 10 claims per patient (`SRC/cache/payloads.py:101-145`), enough for 5 bills |
| 13 | cross-bill predicates make a bill's output depend on its patient's other claims | `CL/patient_context.py:110-140` (`patient_history`); readers `claim_audit_exposure.py:146`, `engine.py:292`, `claim_yatak_icu_overlap.py:46`, `claim_yenidogan_yatak.py:61`, `focused_legacy_materializer.py:71-108`, `focused_rule_projection.py:495-526`, `miat_interval.py:51`, `prose_rules/material_miat_ek3c2.py:18,67`, `prose_rules/sct_temporal_window.py:309` | none (they are the point); the 16-report gate proves that claim 001 of each story is unchanged (P9) |
| 14 | code constraints of the builder modules | `TS/test_cohort_clean.py:1363-1394` (no DataFrame loops in `clean.py`/`labs.py`); `TS/test_cohort_build.py:682-700`, `test_cohort_clinical.py:564-579`, `test_cohort_compose.py:403-407`, `test_cohort_tables.py:773` (no imports of `billing`, `prose_rules`, `reports`, pandas) | respected |

### 7.4 The chronic-health-report slice (G13)

**Decision (Safa, 2026-10-21):** add the column and wire it so that the EK-1/A waiver can show. This section is the exact scope; sizes are one focused day including tests, the backend gate in the image and a frontend `vitest` + `tsc` run.

**What the engine does today.** `evaluate_ek1a_exemption` (`SRC/domain/optimization/copay_exemption_rules/ek1a.py:41-94`) matches any diagnosis against a 98-row catalog (`data/gazette/curated/ek1a_chronic_exemptions.parquet`); with no report the source is *partial* (`counts_toward_exempt` False, `missing_requirements ["chronic_health_report"]`) and the patient is `partial_exempt`; with `has_chronic_health_report` True the patient is `exempt`. Nothing supplies the flag: the three callers (`SRC/cache/sut_context.py:508-516`, `SRC/domain/optimization/aggregator.py:353-359`, `SRC/api/routes/optimization.py:147-151`) pass none, and no ingest path for a report exists in the repository (a real source is unverified). Money is waived only on a **`poliklinik` exam line** (`claim_type == "poliklinik"` and `procedure_category == "muayene"` exactly, `copay_rate_applicable` True, billed > payable, flag True: `claim_copay.py:278-296`, `copay_line_waivers.py:174-211`); measured on a test line: 100 billed / 80 payable gives 20.0 waived; without the report 0 TL and a "savings not asserted" row.

**Slice A: model and wiring (0.75 d).**

| # | File | Change |
|---|---|---|
| 1 | `CL/models.py:19-26` | one field, `has_chronic_health_report: bool \| None = None`, last (frozen dataclass; the 8 constructor sites use keywords) |
| 2 | `CL/parsing/row_parsers.py:131-160` | one line with `optional_bool` (already imported); **not** `parse_bool`, which would turn "unknown" into False. A missing column gives None |
| 3 | `SRC/domain/optimization/copay_exemption_context.py:11-52` | the single wiring change: if the argument is None and a profile exists, read the flag from the profile. An explicit argument (even False) wins; `health_report_by_patient` stays the override hook. The three callers need no edit |
| 4 | `CO/tables.py:105-118`, `CO/build.py:526-528` | `copay_profile(..., has_chronic_health_report=None)` and the 7th key; the schema is derived from the dataclass, so the column appears by itself |
| 5 | `data/synthetic/sut/claims/patient_copay_profiles.parquet`, `data/synthetic/cohort_registry.json` | regenerate: the 7th column changes the profile digest even when it is all null (measured: all-null digest differs from the committed `58ecaee1…`); counts stay |
| 6 | `CL/README.md:37-41`; tests | one line on the optional column; `TS/test_cohort_tables.py:742-751` (the 6-key literal), `test_cohort_build.py:218-256,331-333`, `test_cohort_tables.py:262,390-415`; new tests: parser tri-state (None, True, False, "evet", NaN, column absent), builder default and override, alerts cache with a True profile, aggregator (patient and bill), optimization route payload |

No schema-spec, reader, loader or contract change is needed; the column stays optional, so a real export without it still loads. `data/gazette/sut_coverage_evidence.json` pins 165 files, none of them touched here (checked). The strict-release lane hash (P10) changes with this parquet, as with every data package.

**Slice B: the carrier in the generator (0.5 d).** The flag is a fact about the patient, not a bill fault: the committed data can show one state per patient, the fault registry has no kind for it and `test_copay_rate_exposure.py:155` forbids a copay rule id in any fault. Recommended carrier: `Pins.chronic_health_report: bool | None = None` (age and sex already live in `Pins`, `PW/schema.py:432-441`), with `data/synthetic/pathways/README.md` and schema tests; alternatives are the recipe (`CO/recipes.py:85-93`) or `showcase_clinical.yaml`.

**Slice C: wording (1.5 d).** The UI cannot tell "EK-1/A matched, no report" from "nothing matched" in eight places, and `public_contracts.json:101-121` drops `partial_exempt` and `has_chronic_health_report` before the frontend sees them. The partial state can still be derived from whitelisted fields (`exempt` false and an `ek1a_chronic` source with `counts_toward_exempt` false), so no backend or database change is needed; whitelisting the two fields and adding the TS fields is cleaner. The string "No EK-1A exemption matched" does not exist verbatim in the code; "Standard copay" exists as a table cell (`frontend/src/messages/en/optimizer.ts:54`, TR `tr/optimizer.ts:55`). Where it is rendered and what it says today:

| # | File | Today with a partial match |
|---|---|---|
| 1 | `frontend/src/components/tabs/sut/compliance/modules/CopayExemptionCompliance.tsx:143-163` | chip **"Standard copay"** and the action "Standard copay collection" while the matched diagnoses are listed in the next column (an acil exemption is also labelled "Exempt (EK-1A)") |
| 2 | `frontend/src/components/patient/SutPatientWorkspace.tsx:60-96` (`CopayExemptionSummary`) | headline "No exemption ground matched", body "No EK-1A, visit-type, or status exemption matched…", chip "Clear", yet the matched disease and ICD range are printed below: it contradicts itself |
| 3 | `frontend/src/components/patient/billing-report/SutOptimizationSection.tsx:39-57` | chip "Not exempt" with "2 EK-1A qualifying diagnoses" |
| 4 | `frontend/src/components/patient/billing-report/CopayOptimizationSection.tsx:73-171` (+ `.model.ts:30-66`) | chip "Not exempt"; the partial row is the raw English backend string (no `message_code`, `claim_copay.py:237-247`), so the TR UI shows English |
| 5 | `frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.tsx:380-487` | partial patients sit in "Non-Exempt … Standard copay applies" |
| 6 | `SRC/api/routes/chat.py:189-200,426-431` | the assistant sees `exempt: false, n_qualifying: 2` and cannot tell partial |
| 7 | `SRC/cache/sut_context.py:28-36` | `action: None` when partial |
| 8 | alert filter `SRC/api/routes/alerts.py:41`, `SRC/db/patient_alerts.py:469-473` | partial counts as `not_exempt` |

Proposed wording (EN / TR) for the partial state and the exempt state:

| Where | Proposed EN | Proposed TR |
|---|---|---|
| Workspace headline, partial | "EK-1A diagnosis matched; chronic health report not recorded" | "EK-1A tanısı eşleşti; kronik hastalık raporu kayıtlı değil" |
| Workspace body, partial | "{count} qualifying EK-1A {codeWord}. The outpatient copay waiver (§1.8.5(7)) needs a chronic health report; none is recorded, so no waiver is claimed." | "{count} EK-1A tanısı eşleşti. Ayakta katılım payı muafiyeti (§1.8.5(7)) kronik hastalık raporu gerektirir; kayıtlı rapor yok, bu yüzden muafiyet öne sürülmüyor." |
| Workspace chip, partial | "Report needed" (warning) | "Rapor gerekli" |
| Billing chip and cohort chip, partial (replaces "Not exempt" / "Standard copay") | "EK-1A match, report missing" | "EK-1A eşleşti, rapor yok" |
| Billing line, partial | "{count} EK-1A qualifying diagnoses; a chronic health report is needed for the waiver" | "{count} EK-1A uygun tanı; muafiyet için kronik hastalık raporu gerekir" |
| Cohort action, partial (replaces "Standard copay collection") | "Check for a chronic health report; if present, set the exemption flag before billing" | "Kronik hastalık raporunu kontrol edin; varsa faturadan önce muafiyet bayrağını uygulayın" |
| Cohort KPI sub | "Standard copay applies (includes EK-1A matches without a report)" | "Standart katılım payı uygulanır (raporsuz EK-1A eşleşmeleri dahil)" |
| Backend row text, report unknown (add `message_code`, register it in `frontend/src/lib/apiMessages.ts:514-570`) | "EK-1/A diagnosis matched; chronic health report status unknown, so the §1.8.5(7) waiver is not claimed." | "EK-1/A tanısı eşleşti; kronik hastalık raporu durumu bilinmiyor, bu yüzden §1.8.5(7) muafiyeti öne sürülmüyor." |
| Backend row text, report False | "EK-1/A diagnosis matched; no chronic health report on file, so the §1.8.5(7) waiver is not claimed." | "EK-1/A tanısı eşleşti; kayıtlı kronik hastalık raporu yok, bu yüzden §1.8.5(7) muafiyeti öne sürülmüyor." |
| Workspace headline, exempt with a report | "Exempt: EK-1A, chronic health report on file" | "Muaf: EK-1A, kronik hastalık raporu kayıtlı" |
| Billing notice, exempt but no waivable line | "EK-1A waives outpatient specialist examinations only. This bill has no such line, so no amount is waived." | "EK-1A yalnızca ayaktan uzman muayenesini muaf tutar. Bu faturada böyle bir satır yok, bu nedenle tutar düşülmüyor." |
| Cohort KPI `ek1aExemptSub` | "Chronic ICD-10 + health report" | "Kronik ICD-10 + sağlık raporu" |

About 12 keys in two locales, `frontend/src/lib/domains/sut.ts:184-188,254-261,330-337` (TS fields), one helper in `frontend/src/lib/copayExemption.ts` that returns exempt / partial / none, and the tests `SutPatientWorkspace.test.tsx:49-110`, `SutBillingReportSections.test.tsx:80-125,977,1255-1270`, `ComplianceModules.i18n.test.tsx:20-61` ("Standart katılım" must not appear in the EN render), `SUTOptimizerTab.test.tsx:74`, `copayExemption.test.ts:14`, `apiMessages.test.ts:124,243,325`, and on the backend `test_copay_outcome_kind.py:80-180`, `test_all_diagnoses_by_patient.py:137-139`, `test_claim_copay_cancer_context.py:227-250`. `frontend/scripts/lib/numbers-parity.mjs:68-91` treats the words "partial"/"kısmi" and "unverified" as honesty markers that must survive; the wording above removes none. A cohort "partial" KPI (aggregator fields, alert-table column, contract, UI) would add about 1.0 d and is not proposed.

**Slice D (money) is not extra work here:** G1 is paid in WP6 and G5b in WP9; F2 b2 is the bill that shows the waiver.

**Which stories show the waiver.** The patient diagnosis lists are the app-path lists (principal first, every episode diagnosis since #333).

| Patient | Diagnoses | EK-1/A match | Status without the report (now) | Status with the report | Money waived |
|---|---|---|---|---|---|
| S1 (0001) | K35.9 | none | none | none | no |
| **S2 (0002)** | J44.0, I10, J18.9 | J44; I10–I15 | partial | **exempt** | **yes, on F2 b2** (poliklinik exam, about 17 TL at 20 %) |
| S3 (0003) | M48.06, I10 | M00–M99; I10–I15 | partial | would be exempt | no (no poliklinik exam with the copay flag) |
| S4 (0004) | N10, F05.1, G30.1, I10 | G30–G32; I10–I15 | partial (new with #333) | would be exempt | no |
| S5 (0005) | S72.00, I10, M81.09, W19 | I10–I15; M00–M99 | partial (new with #333) | would be exempt | no |
| S6 (0006) | J69.0, I10, R13 | I10–I15 | partial (new with #333) | would be exempt | no |
| S7 (0007) | R07.1, R06.0 | none | exempt (`acil_servis`) | exempt | the flag changes nothing |
| S8 (0008) | K80.2, K42.9 | none | none | none | no |

(Catalog gaps, checked on 23 codes: G20, S72.00, J18.9, K80.2, K35.9, K42.9 and F05.1 match nothing; the curated list has not been compared with the legal annex, and a dotless code such as `E119` would not match `E00-E90`. Both are unverified for real data.)

**Recommendation and side effects.** The report is carried by **S2 only** (the COPD patient). Flipping S2 from partial to exempt, measured in memory with the existing hook: S2 loses the "§1.8.2 20 % drug copay" row (`claim_copay.py:377` skips it for any exempt patient, although EK-1/A waives §1.8.1 only: EI-25), gains one 0-TL `copay/exemption_review` action, and the cohort exempt count goes from 1 to 2. Putting the flag on S2–S6 instead would turn 6 of 8 patients exempt (75 %), erase 5 reports' drug-copay rows and is not credible as a demo; S3–S6 keep the partial state and show the new wording, so the demo shows both states side by side. A bill-level report of S2's admission `b1` does not change (it has no exam line).

**Size.** A 0.75 d + B 0.5 d + C 1.5 d = **2.75 d** (WP8), plus G12b 0.5 d. Revision 1 priced this at 1.0 d (the story) + 1.5 d (G5b); the story and G5b are now in WP9.

**Decisions and unverified.** (1) The one flag also drives the EK-4/D drug exemptions (`claim_copay.py:325-330`, `drugs/ek4d_exempt.py:195-206`): True turns a partial insight into a money waiver, None gives `ek4d_partial`. No demo drug matches EK-4/D (0 matches), so there is no demo effect, but real data would conflate "chronic report" and "EK-4/D health report": accepted and documented. (2) A single patient-level boolean cannot say which disease the report covers or its validity dates (`ek1a.py:80-93` applies it to every qualifying diagnosis); a dated report table would be the production shape and is not asked for. (3) Unverified: a real source for the flag, the legal annex against the curated list, dotted ICD codes in real MEDULA data, byte-identical regeneration of the other tables, rendering of the proposed wording (nothing frontend was run), and that Wave A is untouched (`1.8.5.(7).ek1a_chronic_no_copay_outpatient` is gated `builder_does_not_derive`, and `health_report_present` comes from drug lines).

### 7.5 The pin classes (what a work package must move)

Revision 1 listed these as "the pins every new patient touches" (§7.3). They are classes now; each card of §6.3 names the classes and the specifics.

| Class | What moves | Where | Paid in |
|---|---|---|---|
| **P1 counts and digests** | registry `counts` (9), `clean_counts` (3), the 12 table digests, `roles`, `encounters`, `faults`, `scenarios`; about 15 test files pin 8 / 117 / 207 / 19 / 21 or the patient set 1..8 | `TS/test_cohort_build.py:68-77,135,226-236,283-310,320-349,589`; `test_cohort_clean.py:238-240,376,757-823`; `test_cohort_labs.py:126,333-336,702,713,756-761,2299-2348,2587-2675`; `test_cohort_plausibility.py:143-170,1949-2047`; `test_cohort_plausibility_clean.py:104,1261-1263,1503,1958-2068`; `test_cohort_clinical.py:36-100,408,552`; `test_cohort_recipes.py:58,67-71,94,235-238`; `test_synthetic_cohort_fixture.py:29-30,64-65,161-167`; outside `TS/` nothing hard-codes the counts | WP1 updated the literals to nine patients; WP2 step G0b derives the size pins from the registry; every data package regenerates tables and registry |
| **P2 story, fault and recipe registries** | story regex, fault coverage, op coverage, recipe and clinical patient numbers; per new bill: `EXPECTED_FAULT_TRIPS`, `_EXPECTED_AMOUNTS_BY_STORY`, the probes of `test_synthetic_cohort_fixture.py:217-224,299-308` (they require `showcase_S9` and `fault("S9")` to raise `KeyError`: rename the probe id) | `PW/schema.py:435`; `FA/schema.py:37,94`; `FA/checks.py:442-472`; `TS/test_fault_registry.py:187,233,243-244`; `test_fault_answer_key.py`; `test_fault_mutations.py` | G0 (WP1), residual per package |
| **P3 per new story** | pathway + `showcase` pins, sibling for a faulty twin, fault record, recipe, clinical entry, story bill in `PR/stories.py`, both golden directories, `prove.py <story>`, `render.py`, `results/S<n>.json`, direct-rows entry in `CO/engine_proof.py:539-548`, and the automatic case of `tests/unit/domain/billing/test_session_uplift_patient_0001.py:36-38` (each `showcase_` role's clean twin must show no session, DRG or headline uplift) | `PR/export_clean_lines.py`, `PR/prove.py:103,159-175`, `PR/render.py:32`; `tests/fixtures/pathways/golden{,_faulty}/` | every new story |
| **P4 engine proof scope** | the faulty side is built over the whole patient, the clean twin over one bill; with a second claim all five comparison blocks differ | `CO/engine_proof.py:798`; `TS/test_cohort_engine_proof.py:105,177-488`; `TS/test_cohort_labs.py:2343-2348`; `data/synthetic/README.md:65-73` | WP4 |
| **P5 patient-level readers of S1–S8** | tests that read a showcase patient with all its claims | `tests/unit/cache/test_all_diagnoses_by_patient.py:157-166` (patients 1, 2, 4, 5, 8: the union list); `test_drg_uplift_wiring.py:331-382`, `test_session_uplift_patient_0013.py:55-99`, `test_billing_strategy_exactness.py:30-52`, `test_orchestrator_claim_cohort_flow.py:14-48` (S1); `test_claim_strategy_sut.py:517-548` (S5: one `paket` line over all claims); `test_claim_integration.py:75-110` (S6: claim types exactly `{yatis}`); `test_bill_billing_report.py:31-133` (the guests S2 and S5 are re-keyed under S1's patient and its follow-ups come along) | WP6, then per patient |
| **P6 row-position and story-order assumptions** | `ana_df.row(i)` is patient `i+1`, `zip(clean_claims, claims, start=1)` maps claim index to story, error texts quote row numbers | `TS/test_cohort_clean.py:261-368,400-411,717-732,1045-1136`; `TS/test_cohort_build.py:301-307,654,674`; `TS/test_cohort_labs.py:2904`; the "patients 5 and 8 have no labs" pins `TS/test_cohort_labs.py:708-713`, `test_cohort_plausibility_clean.py:1266-1274,1341-1375` | WP4 (fix the code), WP6 (add data), F5 and F8 |
| **P7 frontend and scripts that assume one claim per patient** | patient count compared with `anadata_clean` rows; the "compliance" patient picked as the first `compliance_error` fault in registry order; the revenue KPI compared with the landing fault amount on the default view; recording kit patients | `frontend/scripts/lib/cohort-registry.test.mjs:24-25`; `capture-screens.mjs:129-132,536-551,608-611`; `verify-workspace-views.mjs:11-17,146-149`; `frontend/scripts/RECORDING.md:36-47`; `recording-kit.test.mjs:38-46` | WP5 (new patient), WP6 (existing) |
| **P8 docs with counts** | "8 patients", "8 claims", "117 lines", "one claim each", the patient table, S1–S8 wording | `data/synthetic/README.md:3,5,13,14,18,19,22-24,34-47,77,79`; `data/synthetic/faults/README.md:29-30,94,135`; `data/synthetic/pathways/README.md:20,32,143,154,163,171-182`; `PR/README.md:3,14,20`; `CL/README.md:5,59`; `SRC/domain/README.md:23`; `SRC/domain/billing/README.md:62-67`; header comments of the recipes, clinical and fault YAML | every package |
| **P9 claim 001 stays unchanged at bill level** | a follow-up that has exam, lab, bed or material lines near claim 001's can add findings to the patient report through `patient_history` (§7.3 row 13); the claim-id order is not the date order for a precursor bill | the off-repo 16-report gate `~/.cache/bilun-newborn-scratch/baseline.py` (before/after `cmp`, §6.1 rule 3) builds bill-level contexts per story role, so it stays valid and is exactly the check; the committed `PR/results/S1–S8.json` do not move once the proof is bill-scoped | every follow-up |
| **P10 strict-release lane inputs** | the 12 input files named by path and pinned by `INPUT_BYTES_SHA256` | `scripts/deploy/generate_candidate_source_roster.py:29-47`; `scripts/deploy/verify_clinical_semantic_transition.py:648-655`; no CI test recomputes the hash, so nothing goes red; the lane cannot pass until Safa re-reviews (already unequal to today's data since the 50 patients were replaced by the 8); a 13th table would break the 12-file rule | every data package |
| **P11 EK-2/C-1 rate pin** | `test_copay_rate_exposure.py:148-160` asserts no flag or rate mismatch against the EK-2/C-1 list; the ICU packages `P552001-3/6-8` are on it at 100 % | `tests/unit/domain/optimization/test_copay_rate_exposure.py:148-160` | WP2 (narrow with a reason) |
| **P12 default patient pages and baselines** | the default view is "All bills" (patient level), so every number of a patient with a follow-up changes; no screenshot or recording baseline is committed (`capture-screens.mjs` writes to a new directory; `recording-kit.mjs:53-60` refuses outputs inside a checkout); "regenerate" means rebuilding the cache (`python scripts/bilun/build_cache.py --activate --payload-workers 2 --billing-workers 2`, about 3 min) and recapturing a new baseline | `frontend/src/app/patient/[id]/page.tsx:99-106,238-252,390-392`; `capture-screens.mjs:20-60`; unverified whether the Playwright browser is installed | WP6 and each package that adds a bill to an existing patient |

**Regeneration order for a data package** (assembled from five READMEs; the order itself is inferred): (1) author the inputs (pathway + pins, fault and sibling, recipe, clinical entry, `drug_routes` where the product name states no route, lab reference rows); (2) `python -m scripts.synthetic.pathways.checks` and `python -m scripts.synthetic.faults.checks`; (3) new stories only: the story bill in `PR/stories.py`, `python reports/synthetic-data/2026-10-15-showcase-proofs/export_clean_lines.py` (writes both golden directories; `--check` verifies), `prove.py <story>`, `render.py`; (4) `python -m scripts.synthetic.cohort.build`, then `--check`; (5) `python -m scripts.synthetic.cohort.engine_proof`; (6) tests and the CI-parity gate; (7) cache rebuild and UI recapture when `frontend/` changed; (8) counts in the docs. The pin fix and the regeneration go in **the same PR**, so CI is never red in between (`plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:243`). Local `polars` is 1.41.2 and the CI lock is 2.0.0: `build --check` compares by content, but whether committing locally written parquet bytes churns the 12 files is unverified.

**Do not touch** `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`, `tests/*/deploy/**`.

## 8. Engine-side issues (three filed, none fixed here)

These are engine, corpus or vocabulary problems, not stories. "Effect" says what each does to the demo or to this plan. Evidence is file:line from read-only passes of 2026-10-20 and 2026-10-21 unless marked ✓ (measured in memory). On 2026-10-21 three of them were filed as GitHub issues: **#335** (EI-1), **#336** (EI-2), **#337** (EI-12); the others are listed for filing. Data production does not wait for any of them (§10).

| ID | Issue | Evidence | Effect |
|---|---|---|---|
| EI-1 (#335) | `acil` (and `koruyucu`, `meslek_hastaligi`, `day_case`, "günübirlik" with ü) are not recognised claim types; `infer_care_setting("acil")` returns inpatient | `prose_rules/claim_utils.py:77-88`; `billing/payment_traceability_evaluations.py:116-132`; `treatment_pricing_evaluations.py:200-220`; `focused_rule_projection.py:60-77,484-485`; `rule_findings.py:36-38,312` | S7 alone causes 54 `unavailable: unrecognized claim_type: acil` evaluations (33 payment-method, 14 gap-closing, 7 fatura) ✓ and 2 `claim_type_unrecognized`; every `acil` bill (S10 b1, F1 b2, F5 b2, F8 b2) repeats it |
| EI-2 (#336) | `blood_uplift` reads the ceiling from `expected_payable_try`, which the loader, the composer and a plausibility rule force equal to billed; a correct 36 % bill with payable == billed also shows a **false** audit exposure (2,056.38) ✓ | `prose_rules/session_pricing.py:728-737` (use the EK-2/B list as `line_gazette_list_billed_try` does, `:507-547`); `drg_unbundling.py:233-280`; `claims/parsing/row_parsers.py:269-273`; `CO/compose.py:164` | the block is dark for any data; F5 b3 shows the full-price audit instead and the uplift after the fix |
| EI-3 | `provider_type` carries ownership ("Ozel") and contract status; there is no distinct contract marker. Setting `sozlesmeli` on all 8 lowers the evaluated count by 1 ✓ | `prose_rules/gap_closing.py:435-438`; `payment_traceability_evaluations.py:136-141`; `CO/build.py:515` | 15 payment-method and 40 gap-closing evaluations stay missing or unavailable; not a lever |
| EI-4 | The ICU tier-overbilling detector (#242, `icu_tier_overbilling`) fires for the demo facility but only inside `analyze_claim`; no patient report carries it, and the Wave A groups are pinned at 18 / 32 by an import-time error | `billing/engine.py:274-279`; `billing/focused_rule_projection.py:353-359` | S11 cannot show it; a decision on where to surface it |
| EI-5 | Category vocabulary conflict: the composer writes 5 labels, the rules read 113, and only 15 labels match any rule ✓ | `CO/compose.py:71-80`; `treatment_pricing` category sets | 17 Fatura İnceleme rules and most treatment-pricing rules cannot be reached by data; needs a `service_category` column |
| EI-6 | `has_chronic_health_report` is passed by no caller, so EK-1/A stays "partial exempt" forever; `ClaimDiagnosis.exemption_eligible` is a dead column. The all-diagnoses fix landed with #333 | `optimization/copay_exemption_rules/ek1a.py:80-93`; `optimization/shared.py:58-105`; `claims/models.py:62` | **decided 2026-10-21: slice G13 (WP8) adds the column and the wiring**; S2 becomes "exempt" in WP9, S3–S6 keep the partial state (§7.4) |
| EI-7 | Dialysis: an itemized `704230`/`704210` raises a payment-method violation and an audit exposure of 2,575.09 per session in the wrong direction (the package has no işlem grubu, so no package gap is computed); the 13 corpus dialysis rules and the heparin rule key on codes that do not exist (`P5010046/47/50`) or on literals no pipeline emits | `prose_rules/yatak_puani.py:262-305`; `data/gazette/prose_rules/treatment_pricing_2_4.json:109,131,150,166,185,206,224,974,989,1011,1028,1051,1067`; `drug_combination_4_2.json:136-144` | S17 uses package codes; dialysis stays a precision demo |
| EI-8 | Physiotherapy: the ESWT rule keys `P915010` (not a code; ESWT is `610820`/`P610820`); the proxies in `_PROXY_REASONS` force `unavailable`; cross-claim history is not read although `ctx.history` exists | `treatment_pricing_2_4.json:344`; `billing/treatment_pricing_evaluations.py:36-53`; `claims/patient_context.py:62-100` | no physiotherapy story |
| EI-9 | `drg_package_adequacy` corpus is clinically incoherent (609270 is a biliary-fistula package, 609300 an islet-cell transplant, 600150/600160 are cheek tumour excisions) | `data/gazette/prose_rules/drg_package_adequacy_prose.json` | block stays dark |
| EI-10 | `material_uplift`: ceiling includes KDV 20 % while the demo bills ex-VAT, so the clean twin shows 549.17; 12 pilot pairings are `sut_derived_unverified`; EK-3 prices are read as of today, not the claim date | `pricing/material_kdv.py:6`; `material_uplift.py:103,118-132,220`; `material_pairing_uplift.json` | X1 is gated; implant KDV 10 % against 20 % is unverified |
| EI-11 | `procedure_addon_uplift`: the clean twin at 100 % shows an audit exposure of 439.86; chapter-7 codes carry no `session_role`; the engine cannot know whether a polyp existed (any colonoscopy-only bill is flagged) | `prose_rules/procedure_addon_uplift.py:115-155`; research probe | S10's clean twin must bill the add-on at 30 % or 50 %; S18 b1 leaves its endoscopy out (the EGD codes are triggers) |
| EI-12 (#337) | The cross-bill inputs that Wave A names are **never derived** even with several bills: `same_day_outpatient_visit` (C000575), `same_day_multi_specialty_outpatient` (C000576), `visit_sequence`, `same_specialty_repeat_days_lt` (C000573/C000640/C000641), outpatient exams and routine tests within 10 days after discharge from a package, and repeat admissions, inside the package period (C000714; the corpus rule is `2.2.2.B-3.(1).early_discharge_same_specialty_no_repeat_fee`), `same_session_different_specialty` (a helper exists, `session_specialty.py:36-79`), `same_day_multi_level_icu` (C001242) ✓ | comment at `prose_rules/gap_closing.py:426-431`; `data/gazette/prose_rules/payment_method_2_2.json:210,228,470-495`; `gap_closing_treatment_2.json:89,200-204`; `treatment_pricing_2_4.json:486` | F1 b3 and the dormant bills X6 and X7 fire nothing, and the readmissions F2 b3, F5 b3 and F8 b3 show only their own faults |
| EI-13 | Dead or non-emitting detectors: `detect_normal_poliklinik_wrong_method` returns `[]`; `detect_exam_admission_date_mismatch` and `detect_admission_billing_window` cannot fire (inputs not ingested); the radiotherapy hyperthermia branch is never emitted | `prose_rules/common_billing_errors.py:487-508,348-363,634-647`; `focused_rule_projection.py:346-352` | 4 of the 32 focused ids can never light |
| EI-14 | Rooming-in ("Kot not billable beside the mother") is never passed to the newborn motor | `billing/claim_yenidogan_yatak.py:62-68` (`rooming_in_claim_ids` has no caller) | S12/S15 cannot show it |
| EI-15 | Turkish letters: the department keyword gates need the Turkish spelling (ASCII "Gogus", "Ic", "Goz", "Noroloji", "KBB" fail); `_branch_matches` lower-cases with Python `.lower()` | `prose_rules/fatura_inceleme.py` (`_BRANCH_KEYWORDS`, `_branch_matches`); `fatura_inceleme_checklist.py:114-124` | every new story writes departments with Turkish letters; today's S1–S8 use ASCII names |
| EI-16 | Checklist ORTAK-21 (surgery or biopsy documentation) fires on non-surgical EK-2/C packages such as ICU and dialysis packages, because any code starting with `P` counts as a surgical package | `prose_rules/fatura_inceleme_checklist.py:254,259` | S11 and S17 each add one false checklist row |
| EI-17 | `detect_inpatient_on_outpatient` flags a day-case `ameliyat` line; `detect_yatak_icu_overlap` treats any claim discharging on an ICU last day as ICU evidence (single-claim variants fire on a model artifact) | `common_billing_errors.py:128-130,873-924`; `yatak_icu_overlap.py:100-129`; `reports/rule-engine-surfacing/2026-09-27-wavea-financial-inventory.md` (Y1) | S14 uses the two-bill form only |
| EI-18 | A MEDULA rejection dated after discharge cannot be loaded: the loader requires the timestamp inside the claim's date range ✓ | `claims/validation/dates.py:17-31`; `validation/links.py:134-140` | S10's event sits on a single-date ER bill |
| EI-19 | 17 of the 28 reachable focused ids can never be `evaluated` by spec (EK-2/D add-ons 2, dental 2, radiotherapy 12, transplant 1); radiotherapy needs course and session identity the model does not carry | `focused_rule_projection.py:125-339,462-478` | S21's 12 ids are rows only |
| EI-20 | Wave A rules 2.2.2.(4) and (5) (day case: no day bed, no companion fee; C000649, C000650) need `care_setting` inpatient *and* `visit_type` `gunubirlik`, but `gunubirlik` maps to outpatient | `data/gazette/prose_rules/payment_method_2_2.json:575,592`; `prose_rules/gap_closing.py:329-346` | on a plain `gunubirlik` claim they are evaluated and never match (they appear among the 13 rules F4 newly evaluates ✓); S20 cannot light them |
| EI-21 | The dental general-anaesthesia "+30 %" rule has no clause in the SUT corpus (the real clauses are C000775, C000808, C000817) | `prose_rules/dental_ga_uplift.py`; `data/gazette/sut_clauses.parquet` | no dental story until the legal basis is verified |
| EI-22 | `care_setting_review` is practically unreachable: of 2,383 EK-2/C packages with an EK-2/B twin, none has the EK-2/B price above the package (maximum ratio 0.726) | `prose_rules/care_setting_review.py:140-200` | block stays dark |
| EI-23 | 47 `drug_combination_4_2` rules use blocked keys; 54 `gap_closing` rules read keys no builder produces | `billing/drug_combination_evaluations.py:69-126`; the gap-closing builders | 101 rules not movable |
| EI-24 | Four Fatura İnceleme rules have no condition and match every claim of their branch (KARDİYOLOJİ-4, KARDİYOLOJİ-9, KALP_VE_DAMAR_CERRAHİSİ-1, -4), and GÖĞÜS-6 matches any inpatient claim of that branch | `data/gazette/prose_rules/fatura_inceleme_prose.json` | "matched" without evidence; X3 must not count them |
| EI-25 | `claim_copay.py:377` skips the §1.8.2 20 % drug-copay row whenever the patient is exempt, although EK-1/A waives §1.8.1 (the outpatient visit copay) only (`ek1a.py:85`); with the chronic report on file a row that still applies disappears | `src/bilun/domain/billing/claim_copay.py:377`; `optimization/copay_exemption_rules/ek1a.py:85` | S2's page after WP9 shows no drug-copay row (measured: S2–S6 would all lose it); not fixed here, to be filed |


## 9. Measurement

### 9.1 The two prototype scripts

```bash
python ~/.cache/bilun-tools/demo_coverage_blocks.py /tmp/blocks.json   # blocks and per-rule Wave A counts, about 5.5 s
python ~/.cache/bilun-tools/demo_coverage_inputs.py                    # review, advisory and financial rules, missing inputs, about 5.5 s
```

Both run from the worktree root and read the committed claims tables. They omit the patient's `copay_exemption` and the lab feed (`lab_df_pl`), so copay and capture-gap stories must be measured through the cache or API path (§7.4). Script 1's "fired" count (5 at baseline) and script 2's block list (9 keys) use different definitions of "output" (§1.2). Re-run on 2026-10-21 after merging `main` be4b9ec7 (the all-diagnoses fix #333): the block and rule JSON is byte-identical to the one taken on `main` 4def9577. WP1 replaces both with the repository script G12 (§9.4).

### 9.2 Metric definitions (the ones this plan uses)

A block has **output** when at least one of its primary lists is non-empty on at least one patient:

| Block | Primary lists counted |
|---|---|
| `lab` | `flagged_tests` (or a non-zero `hemogram_bundling_savings`) |
| `copay` | `rate_corrections`, `exemption_sources` (or a non-zero savings) |
| `billing_strategy` | `recommendations` |
| `session_uplift`, `drg_uplift`, `blood_uplift`, `yatak_puani`, `icu_puani`, `yenidogan_yatak`, `refakatci`, `anestezi_puani`, `material_uplift`, `care_setting_review`, `procedure_addon_uplift`, `procedure_capture_gap`, `drg_package_adequacy` | `opportunities` |
| `medula_rejection_playbook` | `entries` (not `required_inputs_missing`) |
| `claim_submission_checklist` | `items` |
| `materials` | `pre_auth_required`, `miat_restricted`, `miat_interval_violations`, `bundled_separate_billing`, `prose_bundling_violations`, `specialty_prose_violations`, `kdv_price_reviews` |
| `drug_indication` | `violations`, `findings`, `evaluations` |

Wave A, per rule id: **evaluated** (≥ 1 evaluation with status `evaluated`), **matched** (≥ 1 evaluated row with decision `matched`), **rule with a row** (the id appears in reviews, advisories or financial rows). **Finding kinds**: the set of `surface:kind` of the recommended actions, the `claim_compliance` rule ids, the drug applicability and violation statuses, the audit-exposure kinds, and MIAT violations. Every metric is reported per patient and for the cohort. A bill is "done" when its expected blocks and ids appear on its own patient and on no other patient's bill, and when the clean twin does not add them.

### 9.3 Targets per work package

The targets are the milestone table of §6.4 (one row per package: patients, bills, blocks with output, Wave A evaluated, matched, rules with a row) and the **Target** line of each card in §6.3. Skeleton numbers are an approximation, not a promise: a final pathway differs from its skeleton in lines and prices, so the tolerance is "same blocks and same Wave A ids", not the same number of evaluated ids. Reading rules for a package's G12 diff:

1. The new blocks, ids and finding kinds of the card appear, on the card's patient and on no other (a follow-up bill changes its patient's patient-level numbers; the numbers of the other patients and of every bill-level report of an existing bill stay unchanged, P9).
2. A clean twin adds none of them (the faulty bill is the only difference).
3. After an engine fix (#335, #336, #337) take a new baseline first and read the changes as a step of their own, not as a regression of the package that happened to be next.
4. Copay figures come from the app path (G12b, WP8) or a cache rebuild, never from the two prototype scripts: today 11 rate corrections on the app path against 7 by script (§1.2).

### 9.4 What to build once

**G12 (0.5 d, built in WP1 as `scripts/synthetic/cohort/coverage_metrics.py`, `--out`, `--compare`, `--claims-dir`, `--patients`):** one repository script that applies the §9.2 map, takes a claims directory, writes a JSON with the per-patient and cohort metrics and prints a diff against a previous JSON; the targets above can then run as a test. **G12b (0.5 d, WP8):** an app-path copay mode: the script passes each patient's `copay_exemption`, built the way the cache builds it (`build_copay_exemption_input` from the patient's diagnoses, profile, claims and procedure codes, then `evaluate_copay_exemption`), and the lab feed, so the waiver, the partial state and the capture gap are measured as the app shows them. Each package reports the before and after JSON, the diff table and the gate result to Safa.

## 10. Decisions recorded and what is still open

### 10.1 Safa's answers of 2026-10-21 (the five questions of revision 1)

| # | Question of revision 1 | Answer | Where it is built in |
|---|---|---|---|
| 1 | Follow-up bills: new patients only, or also on S1–S8? | **All patients**: follow-up bills on S1–S8 too. Their reports, committed proofs, goldens and pins change on purpose and are regenerated deliberately | §5.5 (F1–F8); WP4–WP6 pay the pin migrations; §7.5 |
| 2 | How far to commit now? | **All of it**: batch 1, batch 2 and the batch-3 items that the other answers unblock | §6 (WP1–WP19); the rest in the conditional tail, §6.6 |
| 3 | The chronic-disease report (EK-1/A) | **Add it**: nullable `has_chronic_health_report` on the patient profile, wired to its callers | §7.4 (G13, WP8); F2 b2 (WP9) |
| 4 | A second, basamak-3 facility? | **No.** `drg_uplift`, `care_setting_review` and the +100 % ICU ilave oran stay dark and are named as such | §2.1 rows 17 and 19, §5.7 |
| 5 | Engine fixes before or after the stories? | The issues are filed: **#335** (EI-1, `acil` and other claim types), **#336** (EI-2, `blood_uplift` ceiling), **#337** (EI-12, cross-bill inputs). **Data production comes first** and does not wait for them | §8; dormant bills F1 b3, X6 and X7 are built without a fault record |

Instruction of the same message: WP1 (G0 + G12 + S9) is implemented by the session `demo-wp1-g0-g12-s9` (built, commit `bbd4b5fc`, not merged when this was written); this plan starts after its merge. The work packages run strictly one after another and each needs Safa's push / PR / merge word before the next starts.

### 10.2 Two decisions taken while applying the answers (say if you disagree)

1. **S13, S16 and S19 were re-hosted** on the patients whose story they fit (S2, S4, S5, S6, S7, S8), so three new patients disappear (19 → 16) and the bills of revision 1 (34) become 42. The rules, faults and clauses are unchanged (§5.2).
2. **S2 is the only patient whose profile carries the chronic report.** S2's page therefore moves from "partial" to "exempt" in WP9 (with one drug-copay row lost, EI-25) and S3–S6 keep the partial state with the new wording. Carrying it on S2–S6 would show 6 of 8 patients exempt (§7.4).

### 10.3 Open points

None blocks WP2. Two small ones, each with a default:

1. **The conditional tail (§6.6, about 20.75 d)**: build it after WP19 and only on Safa's word? *Default: yes, nothing from the tail starts without an explicit word.*
2. **Clinical review**: one pass per work package, by a clinician Safa names (§6.3 names the specialty per package). *Default: yes; the judgment items go to issue #309 and never block a package.*

## Appendix A. The 255 never-evaluated Wave A rules, by cause

Cause classes (from the classification of §2.2): **needs a planted positive hit** (a focused detector that certifies positives only), **data-fixable** (a line or claim type the builder can read), **input never produced by any builder** (the rule's condition key is produced by no context builder), **engine marks it unavailable** (with the engine's own reason). The 14 matched and 259 checked-without-hit rules are in the companion CSV. Two corrections to the "needs a planted positive hit" lists below: `tablo15_4_normal_poliklinik_wrong_method` is a dead stub (the detector returns `[]`, EI-13), and of the other focused ids a planted hit makes only 11 `evaluated` (the 17 ids of EK-2/D, dental, radiotherapy and transplant stay `unavailable` by spec, EI-19). The "story" mentions inside the lists below are the labels of revision 1 (S13, S16, S19, S22–S26); the companion CSV has the revision-2 mapping (`candidate_story`, `lit_by_work_package_in_skeleton`).


**`treatment_pricing_2_4`**
- data-fixable (line or claim type) (6): `2.4.4.F-2.(9).inpatient_physio_concomitant_services_fee_for_service`, `2.4.4.F-4.(4).eswt_no_combo_with_physio`, `2.4.4.F-4.(4).eswt_not_with_other_physio`, `2.4.4.F-5.(4).robotic_rehab_no_combo`, `2.4.4.F-5.(4).robotic_rehab_not_with_other_physio`, `2.4.4.R.(5).inpatient_pulmoner_rehab_fee_for_service`
- input never produced by any builder — `patient_communication_impaired_disabled, patient_communication_impaired_disabled_any` (1): `2.4.1.B-1.(3).non_communicative_disabled_ga_unit_documentation`
- input never produced by any builder — `treating_provider_is_board_signer_or_first_degree_relative_or_partner, treating_provider_is_board_signer_or_first_degree_relative_or_partner_any` (1): `2.4.1.B-3.(1).self_referral_board_signer_treatment_no_pay`
- input never produced by any builder — `procedure_in_ek2c_star_marked_or_section_7_1, procedure_in_ek2c_star_marked_or_section_7_1_any` (1): `2.4.1.B-3.(2).star_and_7_1_orthodontics_specialist_required`
- input never produced by any builder — `service_category, service_category_any` (1): `2.4.2.B-1.(10).foreign_sourcing_activation_cancellation_fees`
- input never produced by any builder — `same_day_multi_level_icu, same_day_multi_level_icu_any` (1): `2.4.4.H.(7).same_day_multi_level_one_icu_fee`
- engine marks it unavailable — `unsupported_predicate_shape` (14): `2.4.2.B-1.(9).marrow_cord_transport_euro_caps`, `2.4.4.E.(2).angio_ptca_same_session_25pct`, `2.4.4.G-1.(1).cytogenetic_tests_scope_header`, `2.4.4.G-1.(a).cytogenetic_molecular_3rd_step_public_service_procurement`, `2.4.4.G-1.(a_b).cytogenetic_3rd_step_public_or_licensed_ghdm`, `2.4.4.G-1.(b).cytogenetic_molecular_licensed_ghdm_facilities`, `2.4.4.G-2.(1).molecular_genetic_tests_scope_header`, `2.4.4.G-2.(3).molecular_genetic_self_requested_not_covered`, `2.4.4.G-2.(a).molecular_genetic_3rd_step_public_ghdm_procurement`, `2.4.4.G-2.(a_onc).molecular_genetic_oncologic_3rd_step_public_procurement`, `2.4.4.G-2.(b).molecular_genetic_licensed_ghdm_facilities_exceptions`, `2.4.4.G-2.(b_onc).molecular_genetic_oncologic_licensed_ghdm`, `2.4.4.H.(8).icu_admission_discharge_fee_for_service`, `2.4.4.M.(1).neuromonitoring_ek2d4_p703365_bypass_2_2_2b3`
- engine marks it unavailable — `treatment_board_report_not_established` (12): `2.4.3.(A).non_eip_vaccines_high_risk_report`, `2.4.3.(D).hepatitis_a_vaccine_max_2_yearly_seronegative`, `2.4.4.B.(2).hbo_health_board_report`, `2.4.4.C.(1).radiosurgery_board_report_required`, `2.4.4.F-1.health_report_required`, `2.4.4.F-6.(1).sports_med_ecology_health_report_required`, `2.4.4.I-1.(6).ivf_separate_board_report_per_treatment`, `2.4.4.J.(1).thermal_spa_board_report_required`, `2.4.4.L.(2).diskoplasty_3_specialty_board_report_required`, `2.4.4.O.(a).bariatric_bmi40_4_specialty_board_report`, `2.4.4.O.(b).bariatric_bmi35_40_comorbidity_board_report`, `2.4.4.R.(2).pulmoner_rehab_board_report_requires_chest_specialist`
- engine marks it unavailable — `facility_type_vocabulary_not_derived` (10): `2.4.1.A.(1).contracted_public_dental_ek2c_prosthesis_inclusive`, `2.4.1.A.(2).disabled_or_special_need_child_ga_sedo_2x`, `2.4.1.B-1.(1).private_uncontracted_dental_default_no_pay`, `2.4.1.B-1.(2).disabled_child_private_dental_report_10_biz_days`, `2.4.1.B-1.(5).orthodontics_3_dentist_board_report_6mo`, `2.4.1.B-1.(6).post_treatment_control_form_public_dentist_approval`, `2.4.1.B-2.(1).disabled_or_special_need_child_ek2c_fee`, `2.4.1.B-2.(2).private_uncontracted_orthodontics_per_2_4_1_4`, `2.4.1.B-2.(4).disabled_prosthesis_no_separate_material_casting_labor`, `2.4.1.B.(1).private_uncontracted_dental_units_scope`
- engine marks it unavailable — `cross_claim_history_unavailable` (4): `2.4.4.F-2.(5).physio_annual_region_session_caps`, `2.4.4.F-2.(a).physio_star_diagnosis_90_sessions_annual`, `2.4.4.F-5.(5).robotic_rehab_30_sessions_annual_8_daily_per_system`, `2.4.4.F-6.(2).sports_ecology_annual_region_session_caps`
- engine marks it unavailable — `facility_tier_vocabulary_not_derived` (4): `2.4.4.F-2.(5).physio_respiratory_diagnosis_additional_30_sessions`, `2.4.4.G-1.tier3_public_facility_only`, `2.4.4.G-2.tier3_public_facility_only`, `2.4.4.N.(1).eb_wound_care_3rd_step_public`
- engine marks it unavailable — `source_review_required` (3): `2.4.2.A.(2).non_covered_donor_organ_tissue_no_pay`, `2.4.2.A.(4).domestic_organ_transfer_per_2_6`, `2.4.2.A.(5).cadaver_donor_procurement_p911146_ek2c`
- engine marks it unavailable — `board_report_date_unavailable` (3): `2.4.4.B.(6).hbo_start_10d_gap_7_biz_days`, `2.4.4.F-2.(7).physio_start_within_15d`, `2.4.4.R.(4).pulmoner_rehab_start_within_15d`
- engine marks it unavailable — `physician_identity_or_workload_unavailable` (3): `2.4.4.F-3.(c2).private_pmr_outpatient_daily_exam_cap_48`, `2.4.4.F-3.(d).private_outpatient_physio_group_caps_8h`, `2.4.4.I.(2).ophthalmology_outpatient_daily_exam_cap_45`
- engine marks it unavailable — `traffic_accident_origin_unverified` (2): `2.4.4.B.(13).hbo_traffic_accident_no_session_limit`, `2.4.4.F-2.(10).traffic_accident_physio_controls_isolated`
- engine marks it unavailable — `procedure_counts_not_treatment_sessions` (2): `2.4.4.B.(7).hbo_one_session_per_day`, `2.4.4.F-2.(4).physio_session_cap_per_day`
- engine marks it unavailable — `diagnosis_category_mapping_unverified` (2): `2.4.4.F-2.(12).disaster_provision_amputation_fracture_additional_30`, `2.4.4.F-4.(2).eswt_indication_limited`
- engine marks it unavailable — `procedure_dates_not_treatment_sessions` (1): `2.4.4.F-1.(a).physio_up_to_30_sessions_specialist_or_3rd_step`
- engine marks it unavailable — `pmr_supervision_not_established` (1): `2.4.4.F-3.(1b).physio_pmr_specialist_supervision_required`
- engine marks it unavailable — `prescriber_specialty_not_established` (1): `2.4.4.F-6.(3).sport_hydro_physio_p915030`
- engine marks it unavailable — `claim_type_unrecognized + unsupported_predicate_shape` (1): `2.4.4.I.(3).ophthalmology_15day_revisit_ek2a2_only`

**`fatura_inceleme_prose`**
- input never produced by any builder — `drug_category_any` (1): `ORTAK-26.ilac_dozi_endikasyon`

**`drug_combination_4_2`**
- engine marks it unavailable — `unsupported_condition_inputs` (45): `4.2.1.C-1.(2).as_nsaid_failure_required`, `4.2.1.C-7.(3).anakinra_with_biologic_dmard_no_pay`, `4.2.1.C.(3).dual_anti_tnf_or_biologic_combo_no_pay`, `4.2.10.B-3.(4).ms_treatment_switch_6mo_rule`, `4.2.12.B-1.(ivig_indication_required)`, `4.2.12.B-2.(birdshot_retinochoroidopathy_no_pay)`, `4.2.14.C.(alk).alk_tki_after_progression_seq_combo_no_pay`, `4.2.14.C.(atezo_hcc_bevacizumab).tier_c_review`, `4.2.14.C.(atezo_nsclc_adjuvant_pdl1_50).tier_c_review`, `4.2.14.C.(atezo_nsclc_pdl1_50).tier_c_review`, `4.2.14.C.(atezo_sclc_2l).tier_c_review`, `4.2.14.C.(atezo_sclc_extensive_1l).tier_c_review`, `4.2.14.C.(breast).fulvestrant_after_ai_adjuvant`, `4.2.14.C.(breast).ribociclib_palbociclib_after_ai_progression`, `4.2.14.C.(durva_biliary_pdl1_1).tier_c_review`, `4.2.14.C.(durva_nsclc_stage3_pdl1_1).tier_c_review`, `4.2.14.C.(glioblastoma).bevacizumab_after_temozolomide`, `4.2.14.C.(melanoma).braf_sequential_no_pay`, `4.2.14.C.(myeloma).cross_resistance_daratumumab_isatuximab_no_pay`, `4.2.14.C.(pembro_nasopharyngeal).tier_c_review`, `4.2.14.C.(pembro_nsclc_pdl1_ge_50).tier_c_review`, `4.2.14.C.(pembro_nsclc_pdl1_lt_50).tier_c_review`, `4.2.14.C.(pembro_tnbc_neoadjuvant).tier_c_review`, `4.2.14.C.(pembro_tnbc_pdl1_cps10).tier_c_review`, `4.2.14.C.(renal).rcc_tki_sequential_combo_no_pay`, `4.2.14.C.(renal).temsirolimus_poor_prognosis_3of6`, `4.2.16.(8).out_of_ek4b_no_pay`, `4.2.17.B.(1).calcitonin_6mo_cap`, `4.2.23.(3).antifungal_prophylaxis_neutropenia_10d`, `4.2.24.A.(7).laba_iks_mono_offlabel_no_pay`, `4.2.24.B.(laba_lama_iks_combo_no_pay)`, `4.2.28.C.(3).bile_acid_sequestrant_t2dm_no_pay`, `4.2.3.(6).allergy_vaccine_oral_no_pay`, `4.2.30.A.(9).epoprostenol_dialysis_no_pay`, `4.2.33.(8).loading_dose_required_before_switch`, `4.2.33.(c).anti_vegf_same_eye_combo_no_pay`, `4.2.34.(2).ms_dmt_clinically_isolated_syndrome_no_pay`, `4.2.35.A.(5).capsaicin_postherpetic_diabetic_neuralgia`, `4.2.38.(8).empagliflozin_linagliptin_combo_indication`, `4.2.38.(c).dpp4_combo_no_pay`, `4.2.49.C.(5).sma_smn2_modifier_1yr_switch_no_pay`, `4.2.5.(3).out_of_indication_no_pay`, `4.2.7.(3).heparin_in_hemodialysis_no_pay`, `4.2.7.(4).distinct_lmw_heparin_combo_no_pay`, `4.2.71.(3).tafamidis_advanced_heart_failure_no_pay`
- engine marks it unavailable — `facility_tier_vocabulary_not_derived` (1): `4.2.25.(3).pregabalin_2nd_3rd_step`
- engine marks it unavailable — `semantic_indication_not_derived` (1): `4.2.9.A.(1).epoetin_out_of_indication`

**`gap_closing_misc`**
- input never produced by any builder — `drug_overseas_sourced` (3): `4.3.(3).ek4c_overseas_listed_only`, `4.3.(5).ek4d_overseas_no_copay`, `4.3.(8).overseas_drug_domestic_license_continues`
- input never produced by any builder — `drug_in_ek4d_list, drug_specialty_board_report_present` (2): `1.8.2.(3).ek4d_exempt_no_copay`, `1.8.5.(8).inpatient_drugs_ek4d_no_copay`
- input never produced by any builder — `facility_uses_medula_hospital` (1): `1.10.(1).medula_health_report_format_required`
- input never produced by any builder — `patient_under_specific_ssk_60c_exception` (1): `1.5.1.(1).ssk_60c_exception_no_pay`
- input never produced by any builder — `facility_uncontracted_private` (1): `1.5.1.(3).uncontracted_private_non_emergency_no_pay`
- input never produced by any builder — `patient_proxy_service_fraud` (1): `1.6.(3).third_party_service_fraud_prohibited`
- input never produced by any builder — `diagnosis_in_ek1a_chronic_list, drug_specialty_board_report_present` (1): `1.8.5.(7).ek1a_chronic_no_copay_outpatient`
- input never produced by any builder — `extra_fee_charged` (1): `1.9.1.(5).extra_fee_written_consent_mandatory`
- input never produced by any builder — `material_in_ek3_list` (1): `3.1.1.(10).ek3_prices_kdv_excluded`
- input never produced by any builder — `material_in_ek3b_list` (1): `3.1.1.(7).ek3b_listed_materials_no_pay`
- input never produced by any builder — `material_entered_as_medula_free_code` (1): `3.1.3.(7).medula_free_code_entry_no_pay`
- input never produced by any builder — `material_type_any` (1): `3.1.3.(8).fixed_asset_repair_spare_part_no_pay`
- input never produced by any builder — `material_reusable` (1): `3.1.3.(9).reusable_material_no_pay`
- input never produced by any builder — `requires_prior_drug_use_condition` (1): `4.1.(2).medula_prior_drug_use_record_required`
- input never produced by any builder — `health_report_not_compliant` (1): `4.1.3.(1).health_report_medula_compliance`
- input never produced by any builder — `drug_in_ek4d` (1): `4.1.4.(b).ek4d_non_star_drugs_exempt_offlabel_approval`
- input never produced by any builder — `offlabel_approval_present` (1): `4.1.4.(c).offlabel_approval_max_1_year_validity`
- input never produced by any builder — `offlabel_prescription` (1): `4.1.4.(c).offlabel_prescriber_must_be_relevant_specialist`
- input never produced by any builder — `drug_off_label` (1): `4.1.4.(d).off_label_use_ministry_approval_required`
- input never produced by any builder — `case_type_any` (1): `4.1.5.(10).work_injury_traffic_must_be_eprescription`
- input never produced by any builder — `drug_in_ek4g_list` (1): `4.1.7.(2).ek4g_inpatient_only`
- input never produced by any builder — `drug_in_ek4f_list` (1): `4.1.8.(3).ek4d_no_copay_ek4f_copay`
- input never produced by any builder — `drug_not_in_ek4a_list` (1): `4.1.9.(1).ek4a_listed_only`
- input never produced by any builder — `equivalence_group` (1): `4.4.2.(a).cheapest_unit_basis_ek2b`
- input never produced by any builder — `pharmacy_uncontracted` (1): `4.5.1.(2).uncontracted_pharmacy_non_emergency_no_pay`
- input never produced by any builder — `medula_provision_unavailable` (1): `5.2.(2).medula_outage_provision_documented`
- input never produced by any builder — `drug_category_any` (1): `5.2.2.(b).blood_hemophilia_prescription_2x_monthly`
- input never produced by any builder — `prescriptions_consolidated_into_single_invoice` (1): `5.2.2.(separate).prescriptions_billed_separately`
- input never produced by any builder — `facility_uses_medula` (1): `5.3.1.C.(1).medula_service_detail_required`
- input never produced by any builder — `material_acquired_after_20120728` (1): `6.3.2.(b).same_function_prior_material_warranty_no_pay`
- engine marks it unavailable — `provider contracting status is not established by this provider type` (3): `1.5.2.(2).uncontracted_provider_non_emergency_no_pay`, `1.5.2.(3).contracted_provider_must_accept`, `1.8.3.(1b).uncontracted_dental_prosthesis_copay`
- engine marks it unavailable — `emergency_care_setting_not_derived + unrecognized claim_type: acil` (2): `1.8.5.(5).emergency_except_green_area_no_copay`, `1.9.1.(6).er_stabilization_24h_before_extra_fee`
- engine marks it unavailable — `unsupported predicate: drug_indication` (1): `4.1.4.(f).drug_not_reimbursed_indication_no_pay`
- engine marks it unavailable — `unsupported predicate: prescription_period` (1): `5.2.2.(a).monthly_prescription_period_close`

**`gap_closing_treatment_2`**
- input never produced by any builder — `patient_overseas_temp_or_permanent_assignment` (2): `2.5.1.(3).overseas_assignment_insurance_no_pay`, `2.5.1.(5).overseas_no_travel_daily_companion`
- input never produced by any builder — `treatment_overseas` (2): `2.5.2.(1).overseas_reciprocity_required`, `2.5.3.A.(1).overseas_referral_only_if_not_domestic`
- input never produced by any builder — `overseas_treatment` (2): `2.5.3.A-3.(6).overseas_unrelated_treatment_no_pay`, `2.5.3.A-3.(8).overseas_unauthorized_different_treatment`
- input never produced by any builder — `patient_died_before_drg_procedure` (1): `2.2.2.B-2.(1).pre_procedure_death_fee_for_service`
- input never produced by any builder — `early_discharge` (1): `2.2.2.B-3.(1).early_discharge_same_specialty_no_repeat_fee`
- input never produced by any builder — `same_session_different_specialty` (1): `2.2.2.B.(3b).different_specialty_25pt_uplift`
- input never produced by any builder — `stabilized_within_24h` (1): `2.3.1.(5).unstabilized_24h_inpatient_sut`
- input never produced by any builder — `patient_in_trnc` (1): `2.5.1.(6).trnc_contracted_exists_no_uncontracted`
- input never produced by any builder — `patient_turkish_citizen` (1): `2.5.2.(2).trnc_as_overseas`
- input never produced by any builder — `overseas_organ_transplant` (1): `2.5.3.A-2.(4).organ_transplant_wait_in_host_country`
- input never produced by any builder — `overseas_lab_sample_only` (1): `2.5.3.B.(1).overseas_sample_only_no_patient_travel`
- input never produced by any builder — `patient_assigned_vehicle` (1): `2.6.1.B-3.(3).vehicle_assigned_no_companion_travel`
- input never produced by any builder — `referral_arrival_same_day_as_treatment_end` (1): `2.6.2.(3).same_day_referral_no_daily_allowance`
- input never produced by any builder — `inpatient_treatment` (1): `2.6.3.(2).companion_bed_meal_bundled_inpatient`
- input never produced by any builder — `control_checkup` (1): `2.6.4.(c).non_listed_control_checkups_no_pay`
- input never produced by any builder — `patient_died_unreferred` (1): `2.6.8.(2).unreferral_death_no_funeral`
- input never produced by any builder — `travel_within_settlement` (1): `2.6.9.(1).intra_settlement_no_travel_daily`
- input never produced by any builder — `outside_settlement_no_referral` (1): `2.6.9.(2).unreferral_outside_settlement_no_travel`
- engine marks it unavailable — `provider contracting status is not established by this provider type` (2): `2.3.1.(4).uncontracted_emergency_fee_for_service`, `2.4.4.J.(4).thermal_daily_allowance_until_contracted`
- engine marks it unavailable — `absence of an emergency tag does not establish non-emergency care + unsupported predicate: hours_since_onset` (1): `2.3.(1).emergency_24h_window`
- engine marks it unavailable — `unsupported predicate: overseas_treatment_days` (1): `2.5.3.A-2.(2).overseas_duration_cannot_exceed_report`

**`payment_method_2_2`**
- data-fixable (line or claim type) (1): `2.2.(12).no_pay_without_documentation`
- claim-type gate (3): `2.2.(8).contracted_tetkik_mandatory`, `2.2.2.(4).gunubirlik_no_day_bed`, `2.2.2.(5).gunubirlik_no_companion_fee`
- input never produced by any builder — `requires_health_committee_report` (1): `2.2.(14).committee_report_exam_fee`
- input never produced by any builder — `same_day_outpatient_visit` (1): `2.2.1.B-1.(4).same_day_outpatient_to_inpatient`
- input never produced by any builder — `same_day_multi_specialty_outpatient` (1): `2.2.1.B-1.(5).multi_specialty_same_day_no_visit`
- input never produced by any builder — `cross_specialty, payment_method_path` (1): `2.2.2.A.cross_specialty_uplift_25pt`
- engine marks it unavailable — `unrecognized claim_type: acil + unsupported predicate: line_type` (2): `2.2.2.A(3).companion_fee_itemized`, `2.2.2.A(4).ivd_kit_control_no_pay`
- engine marks it unavailable — `unrecognized claim_type: acil + unsupported predicate: event_type` (2): `2.2.2.C.(1).complication_itemized_discount`, `2.2.2.C.(2).comorbidity_itemized`
- engine marks it unavailable — `unsupported predicate: line_type` (1): `2.2.(13).health_report_single_bill`
- engine marks it unavailable — `unsupported predicate: billing_purpose` (1): `2.2.(3).aesthetic_must_not_bill`
- engine marks it unavailable — `unsupported predicate: facility_class` (1): `2.2.1.(20).class3_package_surcharge`
- engine marks it unavailable — `unsupported predicate: procedure_only_in_annex` (1): `2.2.1.B-1.b`
- engine marks it unavailable — `unrecognized claim_type: acil + unsupported predicate: service_category` (1): `2.2.1.B-2.(2).g.no_visit_fee`
- engine marks it unavailable — `unrecognized claim_type: acil + unsupported predicate: procedure_not_in_annex` (1): `2.2.2.(1).itemized`
- engine marks it unavailable — `unrecognized claim_type: acil + unsupported predicate: stay_duration_hours_lt` (1): `2.2.2.(3).short_stay_day_bed`

**`dental_2_4_1`**
- data-fixable (line or claim type) (2): `2.4.1.(2).bone_implant_no_pay_default`, `2.4.1.B-3.(1).treating_physician_continuity`
- input never produced by any builder — `patient_category_any, procedure_under_ga_or_sedoanalgesia` (2): `2.4.1.A.(2).disabled_special_needs_2x_pricing`, `2.4.1.A.(3).disabled_ga_no_extra_50pct_surcharge`
- input never produced by any builder — `board_from, board_includes, implant_count_specified_in_report…` (1): `2.4.1.(2).bone_implant_exception_board_report`
- input never produced by any builder — `is_traffic_or_work_injury, years_since_last_prosthesis` (1): `2.4.1.(3).prosthesis_4yr_renewal_cap`
- input never produced by any builder — `patient_age, treatment_started_before_18` (1): `2.4.1.(4a).orthodontics_over_18_no_pay`
- input never produced by any builder — `procedure_code_not_in` (1): `2.4.1.A.(1).university_dental_faculty_50pct_surcharge`
- input never produced by any builder — `patient_category_not_in` (1): `2.4.1.B-1.(1).private_uncontracted_dental_no_pay`
- input never produced by any builder — `disability_or_special_needs_documented, patient_category_any, treatment_started_within_10_business_days_of_report` (1): `2.4.1.B-1.(2).disabled_special_needs_doc_and_10_day_start`
- input never produced by any builder — `ga_facility_with_anesthesiology_reanimation_specialist, ga_performed_by_specialist_documented, patient_category_any…` (1): `2.4.1.B-1.(3).disabled_ga_sedo_facility_gate`
- input never produced by any builder — `board_report_states_non_aesthetic_and_malocclusion_type, three_dentist_board_report, treatment_started_within_6_months_of_board_report` (1): `2.4.1.B-1.(5).orthodontics_3_dentist_board_6_month_start`
- input never produced by any builder — `patient_category_any, procedure_in_ek2c_list` (1): `2.4.1.B-2.(1).private_disabled_payment_ek2c_list_basis`
- input never produced by any builder — `patient_category_any, within_ek2c_duration_and_quantity_limits` (1): `2.4.1.B-2.(3).ek2c_duration_quantity_compliance`
- input never produced by any builder — `patient_category_any` (1): `2.4.1.B-2.(4).private_disabled_prosthesis_no_pay`
- input never produced by any builder — `stage_completed_per_ek2c3_form` (1): `2.4.1.B-2.(5).orthodontics_stage_payment`
- input never produced by any builder — `performed_by_specialist_or_doctor_dentist, procedure_in_ek2c_star_marked_or_section_7_1` (1): `2.4.1.B-3.(2).specialist_or_doctor_required_for_star_and_7_1`

**`detect_admission_billing_window`**
- engine marks it unavailable — `billing_period_closure_date_not_ingested` (1): `tablo15_9_admission_billing_window`

**`detect_blood_component_isbt128_violations`**
- needs a planted positive hit (1): `blood_component_isbt128_barcode`

**`detect_conditional_addon_ek2d_opportunities`**
- needs a planted positive hit (2): `conditional_addon_ek2d_neuromonitoring`, `conditional_addon_ek2d_neuronavigation`

**`detect_dental_ga_uplift_violations`**
- needs a planted positive hit (2): `2-04.1.4_dental_ga_double_billed_anesthesia`, `2-04.1.4_dental_ga_missing_uplift`

**`detect_donor_prep_as_exam`**
- needs a planted positive hit (1): `tablo15_24_donor_prep_as_exam`

**`detect_drug_quantity_error`**
- needs a planted positive hit (1): `tablo15_11_drug_quantity_error`

**`detect_duplicate_exam_10day`**
- needs a planted positive hit (1): `tablo15_2_duplicate_exam_10day`

**`detect_duplicate_tests`**
- needs a planted positive hit (1): `tablo15_12_duplicate_test`

**`detect_exam_admission_date_mismatch`**
- engine marks it unavailable — `patient_acceptance_date_not_ingested` (1): `tablo15_22_exam_admission_date_mismatch`

**`detect_green_area_bundled_extras`**
- needs a planted positive hit (1): `tablo15_7_green_area_bundled_extra`

**`detect_inpatient_on_outpatient`**
- needs a planted positive hit (1): `tablo15_21_inpatient_on_outpatient`

**`detect_material_preauth_missing`**
- needs a planted positive hit (1): `tablo15_15_material_preauth_missing`

**`detect_material_type_missing`**
- needs a planted positive hit (1): `tablo15_16_material_type_missing`

**`detect_normal_poliklinik_wrong_method`**
- needs a planted positive hit (1): `tablo15_4_normal_poliklinik_wrong_method`

**`detect_radiation_oncology_violations`**
- needs a planted positive hit (12): `radiation_oncology.course_cap.brachytherapy_design`, `radiation_oncology.course_cap.brachytherapy_dose`, `radiation_oncology.course_cap.external_rt_design`, `radiation_oncology.course_cap.external_rt_dose`, `radiation_oncology.course_cap.linac_application`, `radiation_oncology.course_cap.rt_application`, `radiation_oncology.course_cap.rt_planning`, `radiation_oncology.course_cap.special_devices`, `radiation_oncology.same_day_collapse.afterloading`, `radiation_oncology.same_day_collapse.brachy_application`, `radiation_oncology.same_day_collapse.linac_application`, `radiation_oncology.same_day_collapse.rt_application`
- engine marks it unavailable — `same_day_hyperthermia_branch_unreachable` (1): `radiation_oncology.same_day_collapse.hyperthermia`

**`detect_transplant_package_scope_violations`**
- needs a planted positive hit (1): `transplant_bundled_surgical_procedure`

**`detect_vakabasi_wrong_method`**
- needs a planted positive hit (1): `tablo15_3_vakabasi_wrong_method`

**`detect_yatak_icu_overlap`**
- needs a planted positive hit (1): `yatak_icu_overlap_510010`

## Appendix B. Per-patient skeleton numbers after WP19

Measured on the scratch skeletons of §5 in the order of §6, patient-level report over all bills of a patient. Existing patients show baseline → after WP19. Every `yatis` patient also shows `yatak_puani`, `refakatci` and the checklist (the bare-stay rows, trap T3), which is why most rows list 5 to 7 blocks. The conditional bill F2 b5 (BPAP) is not included.

| Patient | Story / bills | Bills | Blocks with output | Blocks gained | Wave A evaluated | matched |
|---|---|---|---|---|---|---|
| 0001 | S1 + F1 | 1 → 3 | 6 → 6 | — | 256 → 281 | 7 → 12 |
| 0002 | S2 + F2 | 1 → 4 | 6 → 6 | — | 191 → 206 | 9 → 13 |
| 0003 | S3 + F3 | 1 → 4 | 7 → 7 | — | 264 → 279 | 9 → 16 |
| 0004 | S4 + F4 | 1 → 3 | 6 → 6 | — | 191 → 205 | 9 → 12 |
| 0005 | S5 + F5 | 1 → 5 | 6 → 7 | drug_indication | 254 → 284 | 7 → 11 |
| 0006 | S6 + F6 | 1 → 3 | 6 → 7 | materials | 192 → 282 | 10 → 11 |
| 0007 | S7 + F7 | 1 → 3 | 4 → 7 | claim_submission_checklist, refakatci, yatak_puani | 231 → 279 | 4 → 12 |
| 0008 | S8 + F8 | 1 → 4 | 4 → 4 | — | 250 → 275 | 7 → 13 |
| 0009 | S9 | 1 | 6 | session_uplift | 258 | 9 |
| 0010 | S11 + S14 | 2 | 5 | icu_puani | 189 | 14 |
| 0011 | S12 + S15 | 2 | 5 | yenidogan_yatak | 185 | 10 |
| 0012 | S10 | 2 | 7 | lab, procedure_addon_uplift, medula_rejection_playbook | 260 | 12 |
| 0013 | S20 | 1 | 2 | — | 255 | 7 |
| 0014 | S17 | 2 | 6 | — | 199 | 8 |
| 0015 | S18 | 2 | 7 | — | 193 | 10 |
| 0016 | S21 | 1 | 4 | — | 258 | 9 |

Reading: only the new patients of S9, S10, S11 and S12 light dark blocks (their value is the block). Follow-up bills add no block to the patients of S1–S4 and S8, one block each to S5 (`drug_indication`, the romosozumab bill) and S6 (`materials`, the walkers) and three to S7 (checklist, `refakatci`, `yatak_puani`, from the observation stay); their value is Wave A ids, finding kinds and the multi-bill structure. Patient-level matched counts rise most on the patients with the largest follow-ups (S3 9 → 16, S1 7 → 12, S8 7 → 13). The jump of the evaluated figure on S6 (192 → 282), S7 and S5 most likely comes from the new departments (neurology, physical medicine, orthopaedics, geriatrics, pulmonology) that bring in branch-keyed Fatura İnceleme rules (not analysed rule by rule). S20 shows two blocks because day-case bills carry no bed rows; S18's seven blocks include `procedure_addon_uplift`, an artifact of the skeleton's endoscopy line that the real pathway leaves out (EI-11).

## Appendix C. Method, limits and what is unverified

**Method.** Revision 1 (2026-10-20): five read-only research passes (silent uplift blocks; bed, ICU, newborn, copay, checklist and MEDULA; sessions, drugs, blood, day cases and history across bills; the data model and generator; the focused detector groups) and a scratch harness that edits in-memory copies of the nine claims tables, rebuilds the dataset through the real loader (`SUTClaimDataset.from_rows`) and calls `compute_patient_billing_report`. Revision 2 (2026-10-21): two more read-only passes (the chronic-health-report slice from model to wording; every pin that moves for a follow-up bill on S1–S8) and a third family of skeletons (follow-up bills on the eight existing patients and the 19-package sequence of §6, measured cumulatively in work-package order). Revision 2.1 (2026-10-21, later): read the WP1 commit, its hand-over and its report (no code run) and corrected the plan where the built S9 differed. The harness and its skeletons live outside the repository. The only repository changes are this plan and its two CSV files.

**What the skeleton numbers are not.** They are measured on scratch bills with the right codes, claim types, departments and dates, not on generator output: a final pathway has other lines and prices. Examples: the ward-bed lines of F2 b3 and F5 b3 are in the skeleton but their prices are not final; the endoscopy line of S18 b1 makes `procedure_addon_uplift` fire on the S18 patient in the skeleton (the EGD codes `701540`/`701550` are triggers of the rule `pairing.701540_701410`, EI-11), so the real S18 pathway leaves the endoscopy out. Targets are therefore "same blocks and same Wave A ids", not the same number of evaluated ids. The skeleton of F7 once used a cardiology department and matched four condition-less Fatura İnceleme rules (EI-24); departments were changed to avoid it.

**Unverified (named so nobody builds on them as facts).**
- The regulatory premises of several focused detectors come from detector docstrings and constants, not from a primary clause: the 10-day and 7-day windows, the green-area flat fee, donor-preparation handling. The dental +30 % rule is absent from the SUT corpus (EI-21).
- The SUT clause id for the MIAT rule (cited in code as §3.1.2); the 5,712.20 blood exposure and the 6,089.84 ICU shortfall are research-probe or formula figures (the ICU shortfall at 60 % was measured: 4,871.88). The 17 TL waiver of F2 b2 is arithmetic (20 % of 85.73) extrapolated from the measured 20.0 on a 100/80 test line; it is not generator output.
- Whether a hospital bills EK-3/C-2 devices (walkers, crutches) on its own claims; whether SGK bills a dialysis month as one takip; the romosozumab criteria as the engine encodes them; the fraction schedule and design level of a radiotherapy course; whether the post-operative complications of F5 b3 (infection or periprosthetic fracture) are the right package choice.
- The cross-bill form of the newborn audit detector (read in code, not lit); the single-claim ICU overlap as a true overlap; whether a typical follow-up bill fires a `patient_history` predicate on claim 001 (only the tests of those predicates were read: the off-repo 16-report gate decides).
- How the frontend renders `poliklinik` and `gunubirlik` claims, whether it pages above 8 patients (10 per page), and whether any component assumes one bill per patient (none found in `frontend/src`, but not every component was read).
- The production vocabulary of procedure categories (`ameliyat`, `cerrahi`, `anestezi`, `dental_ga*`): found only in detectors and tests.
- A real source for the chronic-report flag, the legal EK-1/A annex against the curated list (no G20), dotted ICD codes in real MEDULA data, the rendering of the proposed wording (nothing frontend was run), byte-identical regeneration of the 12 tables with the CI polars version, and whether the paused strict-release lane is still meant to run.

**Strict-release lane.** Every data package changes the 12 input files that `scripts/deploy/verify_clinical_semantic_transition.py:648-655` pins by `INPUT_BYTES_SHA256`. No CI test recomputes the hash, so nothing goes red, but that lane cannot pass until Safa re-reviews the inputs (the hash was already unequal to today's data after the 50 patients were replaced by the 8). The plan does not touch `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml` or `data/synthetic/demo_vignettes.json`.

**Hygiene.** No patient data, credentials or real donation numbers appear in this plan or in the CSVs; ISBT numbers are to be synthetic values of the documented format only. Drug lines stay at price 0 ("fiyat yok"); the EK-4A barcodes cited are public product codes. The two `ilay` folders (`data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/`) do not exist in this worktree and were not opened. The claims parquet files directly under `data/synthetic/sut/claims/` were read (allowed). Process disclosures of the research passes: (1) one pass in revision 1 ran two recursive text searches rooted at the repository root (patterns `Tablo 15` and `Algoritma Rehberi`, limited to `.md`, `.json`, `.yaml`, `.txt` and `.py` files), which may have scanned the few tracked files under a folder named `raw data`; no path or content from that folder was printed, kept or used; (2) one pass in revision 2 ran one repository-root `git grep -c` with the three forbidden paths excluded by pathspec (file counts only), and another listed the git index with a repository-root pathspec whose output was filtered, printing nothing under a `raw data` path; (3) the isolated-mode Python runs of one pass wrote 264 `.pyc` files into gitignored `__pycache__` folders under `src/` and `scripts/` (`git status` stayed clean; they can be removed with `find src scripts -path '*/__pycache__/*.pyc' -newermt '2026-10-21 11:30' -delete`). Nothing under `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml` or `data/synthetic/demo_vignettes.json` was touched.

