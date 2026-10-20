# Demo coverage-first plan: the stories after S8

Date: 2026-10-20
Status: **plan only.** No code, data or gate was touched; every number marked ✓ or called "skeleton" was measured in memory (a scratch harness that edits copies of the 9 claims tables, rebuilds the dataset through the real loader and calls `compute_patient_billing_report`; nothing was written to the repo); the rest is file:line evidence from read-only research passes, marked "research" where a probe gave the figure. Branch `claude/clever-roentgen-5cbbda`, base `main` 4def9577.
Ask (Safa, 2026-10-20): "growing 8 patients to 50 adds nothing by itself". The demo data should trigger engine rules that no current patient triggers, and some patients should carry several bills (the legacy 50 had them).
Companion files: `reports/synthetic-data/2026-10-20-demo-coverage-matrix.csv` (the 20 blocks and 25 Wave A groups), `reports/synthetic-data/2026-10-20-demo-coverage-wavea-rules.csv` (all 528 Wave A rule ids: group, class, evaluated/matched on which of the 8 patients, cause, candidate story).
Existing design this plan builds on: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`, `plans/data/2026-10-15-showcase-stories-draft.md`, `data/synthetic/pathways/README.md`, `data/synthetic/faults/README.md`, `reports/synthetic-data/2026-10-17-pathways-judgment-list.md`.

Contents: 1 Where the demo stands · 2 Coverage matrix (blocks, Wave A groups, levers, specialty breadth) · 3 Capability map for the finished engine work · 4 Multi-bill patterns · 5 Story list and cards · 6 Recommended first batch · 7 Generator slices and data-model gaps · 8 Engine issues · 9 Measurement · 10 Questions · Appendix A never-evaluated Wave A rules by cause · Appendix B per-patient skeleton numbers · Appendix C method, limits and what is unverified.

## Kısaca (Türkçe)

1. **Öneri:** 8 hastayı 50'ye çıkarmayın. Motorun bugün hiç tetiklenmeyen parçalarını tetikleyen az sayıda hasta ekleyin; her hasta, adı konmuş bir kuralla ya da adı konmuş bir çok-fatura örüntüsüyle yerini hak etsin.
2. **Bugün (yeniden ölçüldü, sizin rakamlarınızla aynı):** 20 rapor bloğundan 9'u çıktı veriyor. Wave A'da 528 kuraldan 273'ü değerlendiriliyor, yalnızca 14'ü eşleşiyor, mali satır 0. 11 blok hiç ışık vermiyor; bunların altısı hikâyeyle yakılabilir (YBÜ, yenidoğan, oturum, ek işlem, laboratuvar, MEDULA).
3. **Veriyle tavan:** veri tek başına 20 bloğun en çok 16'sını yakar (4 blok motor, tesis veya kural bankası yüzünden karanlık kalır). Wave A'da hiç değerlendirilmeyen 255 kuralın 214'ü hiçbir demo hastasıyla oynatılamaz (motor 135, girdi hiçbir yerde üretilmiyor 79).
4. **İlk grup (S9–S14): 5 yeni hasta, 9 fatura.** İskelet ölçümü: bloklar 9→15, eşleşen Wave A kuralı 14→19, değerlendirilen kural 273→288, ilk Wave A mali satırı (YBÜ→servis devrinde 510010). Çok faturalı üç hasta: ER→yatış, ayakta kontrol üçlüsü, YBÜ→servis.
5. **İkinci grup (S15–S21): 6 yeni hasta, 17 fatura.** Bloklar sabit (15); eşleşen 19→24, satırı olan kural 18→33 (12'si radyoterapi, durumu "unavailable"), dokuz yeni bulgu türü (ISBT, MIAT, ilaç raporu durumları, kuvöz+servis çifte faturası…). Kalça kırığı hastası 5, KOAH "sık gelen hasta" 5 faturalı.
6. **Darboğaz hikâye değil, jeneratör:** çok-fatura 4 gün, YBÜ + yenidoğan dili 5,5 gün, satır bayrakları 3 gün, tek-tarihli yatış/tarih aralığı 1,5 gün. İlk grubun kendisi ≈24 iş günü (jeneratör 15,5 + hikâye 8,5); klinik inceleme ayrıca.
7. **Motor tarafında 24 sorun bulundu** (§8, EI-1…EI-24); bunlar hikâye değil motor işi, düzeltilmedi. En önemlileri: `acil` tipi tanınmıyor (EI-1), kan bloğu `payable == billed` iken kapalı (EI-2), çok-fatura girdileri hiç türetilmiyor (EI-12).
8. **Sorular (en fazla 5, varsayılanlarıyla) §10'da.**

## In one paragraph

Wave A and the 20 report blocks are mostly dark for the 8 showcase patients not because the patients are too few but because each patient is one clean-or-faulty bill of one kind. The plan therefore adds *stories*, not patients: each one is a clinically coherent timeline of one to five bills that lights something no current patient lights (a silent block, a Wave A rule, a cross-bill rule that no single bill can trigger). Batch 1 (S9–S14) lights six dark blocks and the first cross-bill rules; batch 2 (S15–S21) adds depth on the finished engine work (newborn and ICU transfers, transfusion, dialysis, drug reports, short stays, day cases, radiotherapy) and the detector family; batch 3 is conditional on three decisions (a model column for the chronic-disease report, a second facility, engine fixes). Most of the effort sits in the generator (one recipe = one patient = one claim today), so the plan prices the generator slices separately from the stories and orders the stories so that each slice is paid once.

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
| **N** (value of a story) | newly triggered items = new blocks (B) + new matched or row-bearing Wave A ids (M) + new finding kinds that are not already counted (K). E (newly evaluated Wave A ids) is reported next to it, not added |
| **skeleton** | a scratch bill with the codes, claim types, department, dates and lines a planned story would have, built only to be measured. Skeleton numbers are not generator output; the clinical content is not complete |
| **data-fixable / model / engine / facility** | what must change for a silent row to fire (definitions at the top of §2) |
| **dormant bill** | a bill whose data is plausible today but whose rule cannot be derived yet (engine-first); it is built only when the engine issue is closed |

## 1. Where the demo stands (re-measured on `main` 4def9577)

Both scripts of the orchestrator ran here in about 5.5 s each (`python ~/.cache/bilun-tools/demo_coverage_blocks.py <out.json>` and `python ~/.cache/bilun-tools/demo_coverage_inputs.py`, from the worktree root). **Every number of the brief reproduced** (20 blocks, 9 with output, 528 Wave A rule ids in 25 groups, 273 evaluated, 255 never evaluated, 8 review rules, 6 advisory rules, 0 financial, 1,106 missing-input evaluations over 107 names). Where this plan adds a number it says how it was measured.

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

### 1.2 Three readings of the brief that did not reproduce exactly

1. **"9 blocks with output" is a count of two different sets.** Script 1 prints "with >=1 opportunity on some patient: 5" (it reads only `opportunities`/`recommendations`). Script 2 prints nine keys, but one of them is `medula_rejection_playbook` with only a `required_inputs_missing` list (no real output), and it hides `billing_strategy` on purpose. The set that this plan counts (primary list non-empty, §9.2) is: `billing_strategy`, `copay`, `claim_submission_checklist`, `drug_indication`, `yatak_puani`, `refakatci`, `anestezi_puani`, `procedure_capture_gap`, `materials`. It is also nine, so the number agrees, but **do not compare the scripts' sets by count**: after S10 lights the playbook, script 2 would show no change for that block. §9.4 proposes one measurement script with the §9.2 map.
2. The copay block shows **7** rate corrections with the two scripts and **8** on the app's path (P1 1, P2 2, P3 2, P4 1, P5 1, P6 1): the scripts, like `engine_proof.py`, call `compute_patient_billing_report(pid, claim_context=ctx)` without the patient's `copay_exemption` and without the lab feed (`lab_df_pl`). A story aimed at the copay exemption or at the lab capture-gap must be measured through the cache/API path, not through the two scripts.
3. "The exemption check now reads all diagnoses" is **not in `main`**: it is commit `3218922d`, reachable only from branch `claude/loving-vaughan-cd0a8c`. Until it lands, a chronic disease coded as a secondary diagnosis never reaches EK-1/A (`src/bilun/cache/patient_slice.py:67-86` reads `TANIKODU` only).

### 1.3 The fact that shapes the plan

The loader, the model and the engine already carry several bills per patient (`build_patient_claim_context`, `slice_for_claim`, `ctx.history`, per-bill reports; precedent `tests/unit/domain/billing/test_bill_billing_report.py:44-70`). **The blockers are in the generator**: `scripts/synthetic/cohort/` and the pathway/fault schemas assume "one recipe = one patient = one claim = one of eight stories". §7 lists what must change and prices it. Most of the effort of any batch is generator work, not story writing.

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
| 2 | `copay` | S1–S7: generic §1.8.2 20 % drug row; EK-1/A "partial exempt" on S2, S3; §1.8.3 material rate on S5; S7 acil exemption review. 7 corrections by script, 8 on the app path | money needs `copay_rate_applicable` True and billed > payable on a line, plus an exempt ground: status (yeşil kart, gazi, vatani hizmet), occupational context, acil, koruyucu. All columns exist but the generator hard-codes them (`compose.py:164-168`). **EK-1/A with a chronic report has no carrier** | DATA (status, occupational, acil) / **MODEL** (EK-1/A report) | `claim_copay.py:232-247`, `copay_line_waivers.py:174-211`; `optimization/copay_exemption_rules/ek1a.py:80`; `has_chronic_health_report` is passed by no caller (`src/bilun/cache/sut_context.py:508-516`, `aggregator.py:353-359`, `api/routes/optimization.py:147-151`); ✓ with the report True: 20.0 waived on a 100/80 exam, without: `partial_exempt`, 0 TL | S13 b4 (after the model decision, Q3) |
| 3 | `claim_submission_checklist` | S1–S6, S8: 19 items, **6 of 51 emit-able ids** (ORTAK-17/21/27/29, ORTOPEDİ-6, readiness `0704`) | new ids: poliklinik claim → ORTAK-5; drug flag False → readiness `0612`; TPN line → ORTAK-24; `acil` + "Acil Tip" + burn codes → ACIL-1; department names need Turkish letters | DATA | `fatura_inceleme_checklist.py:114-297`, `claim_readiness.py:117-170`; ✓ the planned stories add exactly **2 ids (6 → 8 of 51)**: ORTAK-5 (S13, S16, S19) and `0612` (S18) | S13, S18 |
| 4 | `drug_indication` | 19 evaluations on 6 patients; 1 violation (S6, amantadine without G20) | other statuses from the drug flags that exist on `DrugClaimLine` (1 of 19 lines sets them today); report duration needs the `DrugFlags` extension | DATA (+ G9) | ✓ `report_duration_mismatch` (S16), `prescriber_specialty_mismatch` (S17), `missing_board_report` (S18) | S16, S17, S18 |
| 5 | `yatak_puani` | 7 yatis claims (S2 +667.08; the rest are 0 TL rows) | a one-date stay (day bed 510120) needs `nights` 0 in the pathway grammar | DATA / generator (G3) | ✓ one-date stay, nothing billed: 44.45 action `yatak_puani_day_bed`; `yatak_puani.py:394-526` | S19 b2 |
| 6 | `refakatci` | 7 (S4 +370.50) | — | — (active) | `refakatci.py:161-166` | — |
| 7 | `anestezi_puani` | S3 (+928.09) | — | — (active) | — | — |
| 8 | `procedure_capture_gap` | S7 (+1,138.22) | EMR/PACS log; the lab feed (`lab_df_pl`) is a second path no script measures | — (active) | `lab_bill_merge.py` | — |
| 9 | `materials` | S5 (UTS violation 6,465.27 at risk; cement info) | MIAT interval needs two bills with the same EK-3/C-2 code; the composer reads EK-3/F-1 only; pre-auth needs a flagged line | DATA / generator (G7b, G5a) | ✓ MIAT: OP1000 crutch twice, 168 days < 365 → action `material_miat_interval`; ✓ `material_pre_auth` action; `miat_interval.py:51` reads `ctx.history` | S16 b3–b4, S19 b5 |
| 10 | `lab` | none | two CBC lines (L107020 + L103120, or two L107020) on one date of one claim; `L103120` is not in `data/synthetic/reference/lab_reference.csv`, so the pathway check refuses it | DATA (G7a) | ✓ L107020 + L103120 same day: 5.88 TL `hemogram_unbundling`; `claim_lab.py:59-119` | S10 b1 |
| 11 | `session_uplift` | none | two operations on one date, the second billed below the strict rate; itemized pair at 0.25 (on the ladder) → 151.60 | DATA | ✓ S3 base + 615995 at 25 %: 151.60; at the correct 50 % the clean twin shows a 0 TL "kesi bilgisi yok" row (T1); `session_uplift.py:109-118,385-397` | S9 |
| 12 | `blood_uplift` | none | a package line + a blood code (705371…) billed below 0.36 × `expected_payable_try`. **Closed while payable == billed** (loader default, composer, plausibility rule) | **ENGINE** (EI-2: price the ceiling from the EK-2/B list) | ✓ fires only with payable ≠ billed: 2,213.11 / 2,320.58; `blood_uplift.py:73-74`, `session_pricing.py:728-737` | S16 b1 (today shows the full-price audit instead; the uplift after the fix) |
| 13 | `icu_puani` | none | an inpatient claim with ≥ 1 line 510090 or P552001-3/6-8; a row only if the ICU lines are billed **below** the expectation (a missing day-rate unit while packages are billed, or a price shortfall) | DATA / generator (G4a) | ✓ ICU stay, package at 50 %: row; clean ICU stay: 0 TL row; `icu_puani.py:277-368` | S11 |
| 14 | `yenidogan_yatak` | none | `Z38.x` or `P00-P96` diagnosis, or a department named yenidoğan/neonatal; ≥ 1 procedure line; a Kuvöz/Kot day not billed | DATA / generator (G4b) | ✓ Z38.0 + P07.3, 6 dates, Kuvöz on 3: 1,322.94; clean Kuvöz ×6: 0; `yenidogan_yatak.py:129-198,275-327` | S12 |
| 15 | `material_uplift` | none | one of 16 trigger codes billed without its paired EK-3 material. **12 pilot heuristics, `sut_derived_unverified`**; ceiling uses KDV 20 % while the demo bills ex-VAT, so the clean twin is not silent (549.17); the composer reads EK-3/F-1 only, so only 612480/612510 + AP1390 can be authored | DATA (one pair) / **verification** (EI-10) | `material_pairing_uplift.json` provenance note; `material_uplift.py:118-132` | S22 (optional) |
| 16 | `procedure_addon_uplift` | none | colonoscopy 701450 (or the 5 other endoscopy triggers) billed, add-on 701460 absent that date; `sut_derived_unverified`; the engine cannot tell whether a polyp existed (EI-11) | DATA | ✓ 701450 alone: 263.92 + Wave A `GENEL CERRAHİ-2.kolonoskopi_ozefagogastroskopi_bundling` matched; the clean twin must bill the add-on at 30 % or 50 % (at 100 % it shows an audit exposure of 439.86) | S10 b2 |
| 17 | `drg_uplift` | none | package billed + billed itemized lines + `package_candidate` False + a DRG_OVERRIDABLE code at a basamak-3 facility; the builder forbids the shape | **ENGINE + FACILITY** | `claim_drg_uplift.py:67-146`; unit tests patch the resolver | — |
| 18 | `drg_package_adequacy` | none | billed package 609270 + billed 600150 (+600160). The **rule corpus is clinically incoherent** (609270 = biliary-fistula package, 609300 = islet-cell transplant, 600150/600160 = cheek tumour excisions) | **ENGINE** (EI-9) | `drg_package_adequacy_prose.json`; ✓ the shape fires with placeholders | — |
| 19 | `care_setting_review` | none | `gunubirlik` claim (or same-day yatis) at a **basamak-3** facility with a package and itemized alternatives; silent at the demo facility, and practically unreachable at catalog prices (EI-22) | **FACILITY** + generator | ✓ test claim fires at `egitim_arastirma`, silent at `2_3_basamak_ozel`; `care_setting_review.py:140-217` | — |
| 20 | `medula_rejection_playbook` | none (status `not_applicable`) | rows in `medula_rejection_events` (table exists, 0 rows) with a `sonuc_kodu` among the 11 playbook entries; the date must lie inside the claim's range (a real post-discharge rejection is refused by the loader, EI-18) | DATA / generator (G8) | ✓ event `0901` on the second CBC line of the ER bill: 1 playbook entry (and the `lab` row); `claim_medula_rejection.py:23-54`, `validation/links.py:134-140` | S10 b2 |

Reading of the table: **11 dark blocks = 6 DATA (lab, session, icu, yenidogan, addon, playbook) + 1 DATA with a verification gate (material_uplift) + 1 ENGINE-first (blood) + 3 not reachable by data (drg_uplift, drg_package_adequacy, care_setting_review)**. With the demo facility, data alone can take the cohort from 9 to at most 16 blocks with output (17 after the blood fix); batch 1 reaches 15.

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
| `detect_duplicate_exam_10day` (1) | two **outpatient** claims (not `yatis`, not `acil`), exam line category `muayene`, same non-empty branch code, 0–10 days apart; the finding lands on the later bill ✓ (SUT analogue C000573) | evaluated; unpriced finding | DATA, multi-bill | S13 |
| `detect_duplicate_tests` (1) | the same code, category in {laboratuvar, radioloji, radyoloji, patoloji, test}, on two different claims ≤ 7 days apart; any claim type (`acil` then `yatis` works) ✓ | evaluated; review | DATA, multi-bill | S10 |
| `detect_blood_component_isbt128_violations` (1) | a blood line (705371/705430/705440/705372/705373/705441-3) with an empty or malformed barcode (`=` or `A` + 13–16 alphanumerics) ✓ (SUT §4.6: C007926, C007927) | evaluated; unpriced finding | DATA (needs the barcode flag, G5a) | S18 b2 (S16 b1 carries valid barcodes) |
| `detect_drug_quantity_error` (1) | a drug line with quantity ≤ 0 (finding) or > 999 (review; a local heuristic) ✓ | evaluated | DATA (fault op, G6) | S19 b3 |
| `detect_green_area_bundled_extras` (1) | code `520021` plus any other line on the claim, any claim type ✓ | evaluated; one review per extra line | DATA | S19 b1 |
| `detect_vakabasi_wrong_method` (1) | an exam line with `is_package_included` True on an outpatient claim ✓ | evaluated; finding | DATA (flag, G5a) | S19 b4 |
| `detect_material_preauth_missing` (1) | a material line with `requires_pre_auth` True (the model has no approval field) ✓ | evaluated; review | DATA (flag, G5a) | S19 b5 |
| `detect_material_type_missing` (1) | a material line with blank `material_type` ✓ | evaluated; finding | DATA (fault op, G6) | S23 |
| `detect_inpatient_on_outpatient` (1) | a line categorised `ameliyat/cerrahi/anestezi/yatis/gunubirlik` on an outpatient claim ✓ | evaluated; finding | **vocabulary artifact**: the composer never writes those labels; false positive on day-case `ameliyat` (EI-17) | skip |
| `detect_donor_prep_as_exam` (1) | an exam line on a claim whose `occupational_context` is `donor…` ✓ | evaluated; review | needs a transplant donor patient | S23 |
| `detect_transplant_package_scope_violations` (1) | `P609080` plus a separate `islem` line ✓ (P609080 alone is ≈ 29× the largest demo bill) | **unavailable** by spec; financial row per extra line | needs a transplant pathway | S23 |
| `detect_conditional_addon_ek2d_opportunities` (2) | `P703365` without a D-4 primary, or `P614981` without a D-5 primary ✓ (SUT C001389, C001413) | **unavailable** by spec; review | DATA, neurosurgery host | S23 |
| `detect_dental_ga_uplift_violations` (2) | a dental code + a `550xxx` line (double-billed), or dental lines with a `dental_ga*` category (missing uplift) ✓ | **unavailable** by spec; claim-level financial row | needs dental pathways; **legal basis of the +30 % not found in the SUT corpus (EI-21)** | skip until verified |
| `detect_radiation_oncology_violations` (12 emitting ids; 13th non-emitting) | RT family codes 800070–800590 repeated beyond the course/day limits; one 14-line claim lights all 12 ✓ | **unavailable** by spec; one financial row per participant line | DATA, rows only; evaluated would need course and session identity (model gap, EI-19) | S21 |
| `detect_normal_poliklinik_wrong_method` (1) | none: the detector returns `[]` (payment-method compliance owns the verdict) | cannot fire | **ENGINE (dead rule, EI-13)** | none |
| `detect_admission_billing_window`, `detect_exam_admission_date_mismatch` (2) | none: non-emitting | cannot fire | **ENGINE (EI-13)** | none |

### 2.3 Cheap levers measured in memory

Each row is one edit of the 8-patient tables (or one added claim), rebuilt through the real loader and measured with the §9 metrics. Baseline: 9 blocks, 273 evaluated, 14 matched.

| Lever | Δ blocks | Δ evaluated | Δ matched | Verdict |
|---|---|---|---|---|
| add any `poliklinik` or `gunubirlik` claim (one exam line) | 0 | +12 (`payment_method_2_2`) | +1 (`ORTAK-20.ayaktan_ek2a_yatis_ek2b`) | worth it once, with S13 |
| two outpatient bills, same branch, 5 days apart | 0 | +13 | +2 (ORTAK-20, `tablo15_2_duplicate_exam_10day`) | S13 |
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

Seven coherent branch patients built as skeletons (Göğüs TB work-up, ERCP, hand fracture, delivery with tubal ligation, urology, eye, cardiology) added **+17 matched** Fatura İnceleme rules with 0 new blocks; 13 are keyed on billed codes, 3 on branch or setting alone, and 1 fired only because the skeleton wrote a service category the composer cannot write (so 16 count). Two cautions: a rule keyed on a code alone matches even when the clinical context differs from its denial text (the eye-laser rule names trichiasis; a retinopathy patient would match it), and every branch patient needs its own clinician pass. This lever is **optional and low value per patient** (§5, S24); it is the only way to move the "matched" count by more than a handful once the blocks are lit.

## 3. Capability map: the finished engine work

Thirteen pieces of engine work are finished and none is visible in the demo. Each row says which story shows it, what the user will see, and what stands in the way. "Silent by design" means the engine's job there is to *not* flag (an exclusion), so the story is a precision demo, not a finding.

| # | Finished engine work | Story | What the user sees | Class / blocker |
|---|---|---|---|---|
| 1 | ICU days 510090 and EK-2/C ICU packages (P552001-3, P552006-8) | S11, S14 | an `icu_puani` row when the package days are billed below the expectation (package at 50 %: row; clean stay: a 0 TL row); the 510010 billed on the transfer day as a Wave A financial row and ORTAK-29 | DATA + G4a. The +100 % ilave oran needs a basamak-3 header (FACILITY); the tier-overbilling detector #242 is not surfaced in the report (EI-4) |
| 2 | Newborn bed 510070 / 510081 with `Z38` / `P00-P96` | S12, S15 | `yenidogan_yatak` row (Kuvöz billed on 3 of 6 days: 1,322.94); the standard-bed block loses the newborn-owned days | DATA + G4b. Rooming-in ("Kot not billable beside the mother") is unreachable (EI-14) |
| 3 | Stays under 24 h priced at the day bed 510120 | S19 b2 | a one-date stay with nothing billed for the bed: action `yatak_puani_day_bed`, 44.45 | DATA + G3 (one-date stay) |
| 4 | ER critical bed 530000 | S19 b3 | **silent by design**: 530000 on day 0 removes that bed day from the expectation; the unbilled ward days after it still show 667.08 and the detail names 530000 | DATA; no block of its own |
| 5 | Special rooms 510100 (sterile) / 510110 (radioiodine) | S26 (optional) | silent by design (days paid by the room are removed); partly billed room: 444.72 | DATA + G4c; heavy clinician need; low value |
| 6 | Hemodialysis 704210 / 704230 | S17 | the monthly `P704230` bill is informational; a one-date stay with `P704210` shows no day bed (through the package window; the control without it shows 44.45). The day-bed *exclusion* for the itemized codes cannot be shown without triggering EI-7 | DATA + G1, G3. **An itemized 704230 is mis-signalled by the engine (EI-7): do not use it as a fault** |
| 7 | Day case (`gunubirlik`) with an EK-2/C procedure | S20 | clean `P603840`: informational; itemized `603840`: `compliance_violation` + uplift 5,255.17 (the S1 fault in a day-case claim) | DATA + G1. `care_setting_review` stays dark (FACILITY, EI-22); Wave A 2.2.2.(4)/(5) are evaluated but cannot match a plain `gunubirlik` claim (EI-20) |
| 8 | 510010-beside-newborn audit detector | S15 | audit exposure row `yatak_newborn_overlap_double_billing` (222.36 for one day), across the NICU bill and the ward bill | DATA + G2, G4b |
| 9 | EK-1/A exemption with a chronic health report | S13 b4 | the visit copay waived (20.0 on a 100/80 exam) instead of "partial exempt" | **MODEL** (no carrier for the report, EI-6) + the all-diagnoses fix not in main; poliklinik grammar (G1); payable ≠ billed (G5b) |
| 10 | Surcharge EK-2/G | S25 (optional) | the surcharge alert counts a line on the EK-2/G list that does not carry the flag | G5b (flags + payable ≠ billed); patient alert, not one of the 20 blocks |
| 11 | Drug indication with health-board reports | S16 b5, S17, S18 | `report_duration_mismatch`, `prescriber_specialty_mismatch`, `missing_board_report` (plus `eligible` on the clean lines) | DATA + G9 (`report_duration_months` is not settable from a pathway). Drug prices stay 0 / "fiyat yok" |
| 12 | Blood products | S16 b1, S18 b2 | full-price blood inside a package: audit exposure `blood_component_partial_bill` (5,712.20 for two units); missing barcode: ISBT finding | DATA + G5a. **The uplift side (`blood_uplift`) is ENGINE-first (EI-2)** |
| 13 | Sessions: dialysis and physiotherapy | S17 (dialysis); physio: none | dialysis: see 6. Physiotherapy: no new matched rule is reachable (proxies force `unavailable`, EI-8; corpus codes do not exist), so **no story** | physio is ENGINE-bound |

## 4. Multi-bill patterns

Safa's list, one row each. "Today" says what the engine does with the pattern now; "dormant" means the data is plausible today but the rule input is never derived (EI-12), so the bill is built only when the engine issue is closed.

| Pattern | Where | Engine status today | Rules that fire (measured ✓) |
|---|---|---|---|
| **Outpatient follow-up after admission** | S16 b2 (control 16 days after discharge), S19 b4 (control 5 days after discharge) | the post-discharge control inside the package window (SUT 2.2.2.B-3.(1) = C000714) has **no implemented rule**; the bill adds the outpatient baseline only | ORTAK-5 (checklist), ORTAK-20 (once), 12 payment-method evaluations (once) ✓; S19 b4 also carries the vakabasi fault |
| **Readmission** | S19 b2 → b3 (6 days later), S18 b1 → b2 (4 weeks later) | no readmission rule is implemented (C000714 unwired, `early_discharge` and `same_specialty_readmission_within_package_window` are keys no builder produces) | none; the bills are plausible and clean, and S19 b3/S18 b2 carry their own faults |
| **Same-day multi-specialty outpatient** | dormant bills D2 (on S13) | `same_day_multi_specialty_outpatient` (C000576) is a rule condition that **no builder derives** (EI-12) | none today (expected 0, to be confirmed when built) |
| **Same-day outpatient visit, then admission** | dormant bill D1 (on S18) | `same_day_outpatient_visit` (C000575) never derived (EI-12) | none today |
| **Prior therapy** | not buildable | `requires_prior_drug_use_condition` (C003457) needs `medula_record_of_prior_drug`, a column that does not exist (model gap) and a derivation that does not exist | none |
| **Prior prosthesis** | MIAT on S16 b3/b4 (crutch twice) works today; the dental form is blocked | `years_since_last_prosthesis` (C000761, 4 years) is never produced and the pathway window (2026-02..09) cannot hold a bill years earlier | MIAT ✓ (168 days < 365) |
| **Bills that together trigger a rule no single bill does** | S10 (duplicate test), S13 (duplicate exam), S14 (ICU overlap), S15 (newborn double billing, cross-bill form), S16 (MIAT) | the first, second, third and fifth were lit with two or more bills; S15's detector also fires inside one bill, and its cross-bill form was read in code (`ctx.history`) but not lit separately | `tablo15_12_duplicate_test` ✓, `tablo15_2_duplicate_exam_10day` ✓, `yatak_icu_overlap_510010` ✓ (financial), `yatak_newborn_overlap_double_billing` ✓, `material_miat_interval` ✓ |
| Stem-cell add-on after an allogeneic transplant (60 / 90 days, `sct_temporal_window.py`) | not proposed | a real cross-claim rule, but a hematology transplant timeline (heavy clinical review) and its report surfacing was not verified | unverified |

## 5. The story list (continuing after S8)

### 5.1 How to read the list

- A **story** is one patient with one to five bills. A bill is one claim (one `claim_id`, one episode). Ids continue after S8 and follow the recommended build order inside each batch; delivery order is in §6. `S11` and `S14` are two bills of one patient (the ICU bill and the ward bill); the same holds for `S12`/`S15`; the other multi-bill stories list their bills as `b1…b5`.
- **One planted fault per bill** (the answer key and the recipe grammar assume it). Cross-bill hits (a duplicate test, an ICU overlap) are *structural consequences* of two bills that are each clinically right, and are declared as expected hits in the story, not as faults.
- Every bill keeps `payable == billed`, prices on the 2026-07-07 EK-2/B and EK-2/C lists, drug prices at 0 ("fiyat yok"), the demo facility (`2_3_basamak_ozel`, `Ozel`), department names with Turkish letters, ICD codes from the SKRS table, and a `basis`/`source` per pathway entry like the existing pathways. Clean twins are stated per story.
- **N** = newly triggered items (B blocks + M Wave A ids matched or with a row + K finding kinds), **N per day** = N divided by the story's own days plus the slice days it is first to need in the delivery order of §6 (the value score), **E** = newly evaluated Wave A ids, both measured on skeletons in the order of the table (cumulative; §9.3). **Days** = working days of one engineer incl. tests and docs; "own" excludes generator slices, "slices" are the ones this story is first to need (§7). Clinical review is separate and is named per story.
- Numbers marked ✓ were measured; numbers marked (research) come from a read-only research probe of the same day.

### 5.2 The ordered list

| Story | Patient and bills | Planted fault (clean twin) | Newly triggered | N / E | Slices it first needs (in delivery order, §6) | Own d | N per day | Clinician |
|---|---|---|---|---|---|---|---|---|
| **Batch 1: dark blocks and the first cross-bill rules** | | | | | | | | |
| S9 | lumbar stenosis, 1 bill | second operation billed at 25 % (clean: 50 %, shows a 0 TL review row) | block `session_uplift` ✓ | 1 / 0 | G0 | 1.0 | 0.33 | neurosurgeon (light) |
| S10 | GI bleeder, 2 bills: ER visit, then admission 2 days later | b1 hemogram + manual haematocrit billed together; b2 colonoscopy without the polypectomy add-on; b1 carries a MEDULA `0901` event | blocks `lab`, `procedure_addon_uplift`, `medula_rejection_playbook` ✓; Wave A `GENEL CERRAHİ-2…` and `tablo15_12_duplicate_test` matched ✓ | 5 / +1 | G7a, G8 | 2.0 | 1.25 | internist or gastroenterologist; billing officer for the MEDULA text |
| S11 | septic shock, ICU stay, 1 bill (bill 2 is S14) | ICU package days billed at 50 % (clean: 100 %, a 0 TL row) | block `icu_puani` ✓ | 1 / 0 | G4a | 1.5 | 0.22 | intensivist |
| S12 | late-preterm newborn, 1 bill (bill 2 is S15) | Kuvöz billed on 3 of 6 days (clean: all 6) | block `yenidogan_yatak` ✓ | 1 / 0 | G4b | 1.5 | 0.25 | neonatologist |
| S13 | type 2 diabetes + hypertension, 3 poliklinik bills (day 0, 6, 42) | b2 opened as a new takip 6 days after b1, same branch (b3 clean) | Wave A `tablo15_2_duplicate_exam_10day` and `ORTAK-20` matched, checklist `ORTAK-5` ✓ | 3 / +13 | G1, G2 | 1.5 | 0.43 | internist (light) |
| S14 | S11's patient, bill 2: ward bill | 510010 billed on the ICU discharge day (clean: ward bill starts next day) | Wave A `yatak_icu_overlap_510010`, the first **financial** row ✓ | 1 / +1 | none | 1.0 | 1.0 | intensivist |
| **Batch 2: depth on the finished engine work and the detector family** | | | | | | | | |
| S15 | S12's patient, bill 2: ward after the NICU | standard bed 510010 billed on days a Kuvöz line already pays | finding kind `yatak_newborn_overlap_double_billing` ✓ (same-bill form) | 1 / 0 | none | 1.0 | 1.0 | neonatologist |
| S16 | hip fracture, 5 bills over 7 months | b1 blood at full list price inside the package; b4 second crutch 168 days after the first; b5 romosozumab report of 12 months where 6 are allowed | kinds `blood_component_partial_bill`, `material_miat_interval`, `report_duration_mismatch` ✓ | 3 / 0 | G7b, G9 | 3.5 | 0.5 | orthogeriatrician; physiatrist |
| S17 | end-stage kidney disease, 2 bills | b1 darbepoetin prescribed by the wrong branch (month of `P704230` sessions otherwise clean); b2 emergency dialysis stay (clean) | kind `prescriber_specialty_mismatch` ✓ | 1 / 0 | none | 2.0 | 0.5 | nephrologist |
| S18 | decompensated cirrhosis, 2 admissions 4 weeks apart | b1 albumin without the board report; b2 two red-cell units without ISBT numbers | Wave A `blood_component_isbt128_barcode` matched ✓; kinds `missing_board_report`, checklist `0612` ✓ | 3 / +1 | G5a | 2.0 | 0.86 | hepatologist or internist |
| S19 | COPD "frequent flyer", 5 bills (ER, observation < 24 h, readmission, control, home device) | b1 green-area visit with extras; b2 under-24 h stay without the day bed; b3 heparin quantity 25,000; b4 control visit flagged as package component; b5 home device without approval (the 530000 bed on b3 is clean and silent by design) | Wave A `green_area`, `drug_quantity`, `vakabasi`, `material_preauth` matched ✓; kinds `yatak_puani_day_bed`, `material_pre_auth` ✓ | 6 / +4 | G3, G6 | 4.0 | 0.8 | pulmonologist; billing officer for b5 |
| S20 | umbilical hernia day case, 1 bill | itemized `603840` instead of the package (clean: `P603840`) | none new (day-case variant of the S1 fault) | 0 / 0 | none | 1.0 | 0 | surgeon (light) |
| S21 | cervical cancer radiotherapy course, 1 bill | the course keyed on once-per-course and once-per-day codes | **12** Wave A ids with a financial row ✓, all `unavailable` by spec (EI-19) | 12 (rows only) / 0 | none | 1.5 | 8.0 (rows only) | radiation oncologist |
| **Batch 3: conditional (§6.4)** | | | | | | | | |
| S13 b4 | S13's patient, EK-1/A visit with a chronic report | copay waived (clean) / partial (fault) | the first money copay row | 1 / 0 | G5b + model column | 1.0 | 0.4 | none |
| S22 | revision hip arthroplasty | acetabular cup `AP1390` not billed | block `material_uplift` (gated by EI-10) | 1 / 0 | none | 1.5 | 0.67 | orthopaedist |
| S23 | rare detector hosts: living-donor liver transplant pair, long spinal fusion, hip bone-cement line | donor visit as exam; separate surgical line beside `P609080`; `P703365`/`P614981` without a primary; blank material type | up to 5 ids (3 `unavailable` by spec) | 5 / +2 | G6 | 7.0 | 0.7 | transplant surgeon, neurosurgeon |
| S24 | specialty breadth, 4 patients, 6 bills | one coherent billed bundle per branch | ≈ 12 Fatura İnceleme ids keyed on billed codes | 12 / 0 | G7e | 6.0 | 1.6 (weak) | one clinician per branch |
| S25 | oncologic surgery with the EK-2/G surcharge | line on the EK-2/G list without the surcharge flag | surcharge alert (not one of the 20 blocks) | 1 / 0 | G5b | 1.5 | 0.67 | billing officer |
| S26 | special rooms 510100 / 510110 | room billed for 2 of 4 days | silent by design; 444.72 on the partly billed room | 0 / 0 | G4c | 1.5 | 0 | haematologist or nuclear physician |
| D1, D2 | dormant bills on S18 and S13 | same-day outpatient visit before an admission; two specialties on one date | 0 today (engine-first, EI-12) | 0 / 0 | none | 1.0 each | 0 | none |

Batch totals (skeleton, cumulative; patients 8 → 13 → 19, bills 8 → 17 → 34): **batch 1** blocks 9 → 15, matched 14 → 19, rows 14 → 18, evaluated 273 → 288, N = 12. **Batch 2** blocks 15 → 15, matched 19 → 24, rows 18 → 33 (12 of them radiotherapy), evaluated 288 → 293, nine new finding kinds, N = 26 (12 rows only). §9.3 has the step-by-step table.

### 5.3 Story cards

Each card gives: scenario; planted fault and clean twin; expected finding with SUT clause ids; what it triggers; new data; pathway and builder work; clinician; size, risks. Clause ids were checked against `data/gazette/sut_clauses.parquet`; El Kitabı rows are "Tablo 15 #n" (a handbook, not a SUT clause).

#### S9 · Lumbar stenosis, second operation billed at 25 % (batch 1, 1 bill)
- **Scenario.** Woman born 1949, lumbar stenosis M48.06 + hypertension I10, neurosurgery (2400), `yatis`, 2 nights (3 dates). Decompression `615931` and foraminoplasty `615995` in one session, anaesthesia `550230`, ward `510010` ×3, companion `510121` ×2, hemogram. It is a sibling of the S3 pathway with an optional second operation.
- **Fault / clean twin.** The second operation is billed at 25 % (the package ratio) where hizmet-başı pays 30 % through the same incision and 50 % through a separate one. Clean twin: 50 %; it still shows a 0 TL "kesi bilgisi yok" row (no claim line carries the incision), so the clean twin is *not silent* (trap T1).
- **Finding.** `session_uplift` money 151.60 (research: 615931 + 615995 at 25 %). SUT 2.2.2.A.(5): C000659, C000660 (30 %), C000661 (50 %), C000662 (+25 points across branches); package form C000669–C000674.
- **Triggers.** Block `session_uplift` ✓. N 1, E 0.
- **New data.** None. Optional: the MEDULA incision code `ayniFarkliKesi` as a nullable column on `ProcedureClaimLine` (removes the review row; §7.2 row 2).
- **Builder.** G0 only; `set_billed_ratio 0.2500` exists and is on the ladder {1, 0.5, 0.25}. Use a same-branch pair: the +25-point cross-branch rule is not applied in `expand.py:21` (issue #295).
- **Clinician.** A neurosurgeon confirms that a foraminoplasty after decompression is a separate procedure of the same session.
- **Size/risks.** 1.0 d. T1; the 0.25 rung is the only one that fits the builder ladder.

#### S10 · GI bleeder: ER visit, then admission (batch 1, 2 bills)
- **Scenario.** Man born 1968. **b1** (`acil`, 2026-05-09, Acil Tip 4400): melena K92.1, ER exam `520020`, hemogram `L107020` and manual haematocrit `L103120`. **b2** (`yatis`, 2026-05-11 to 05-13, Genel Cerrahi): K92.2 + D50.0 + D12.6, ward `510010` ×3, companion `510121` ×2, serial hemogram `L107020` on day 0, colonoscopy `701450` on day 1 with the polypectomy `701460` not billed. A MEDULA event `0901` ("Mükerrer işlem: aynı gün tekrar faturalandırma") sits on b1's `L103120` line.
- **Faults / clean twins.** b1: the second CBC line the same day (clean: one hemogram). b2: add-on omitted (clean: `701460` at 30 % or 50 %; at 100 % the engine shows an audit exposure of 439.86, EI-11). The repeated hemogram two days later is clinically right and is flagged on purpose as a warning.
- **Findings.** b1: `lab` `hemogram_unbundling` 5.88 TL ✓; playbook entry `0901` (rebill permitted at `fatura_kayit`) ✓. b2: `procedure_addon_uplift` 263.92 and Wave A `GENEL CERRAHİ-2.kolonoskopi_ozefagogastroskopi_bundling` matched ✓; `tablo15_12_duplicate_test` review ✓. SUT 2.2.2.A.(5) (C000659–C000662) for the add-on; the lab rule's source is the EK-2/B hemogram row (no SUT clause); the duplicate test is El Kitabı Tablo 15 #12; the 7-day window is the detector's (unverified against the handbook).
- **Triggers.** Blocks `lab`, `procedure_addon_uplift`, `medula_rejection_playbook`; Wave A ids `GENEL CERRAHİ-2…` and `tablo15_12…`. N 5, E +1.
- **New data.** `L103120` in `data/synthetic/reference/lab_reference.csv` with a lab state (G7a); one row in `medula_rejection_events` (table exists, 0 rows); no new column.
- **Builder.** G2 (two bills, one `acil` and one `yatis`; the `acil` pathway exists as S7), G7a, G8; the event date must lie inside b1's single date (EI-18).
- **Clinician.** Internist or gastroenterologist: serial haemoglobin, colonoscopy timing; the billing officer confirms the rejection text. No transfusion in this story (S18 carries it).
- **Size/risks.** 2.0 d. The `acil` bill is invisible to the payment-method rules (EI-1) but not to `lab`; the answer key must declare the duplicate-test review as an expected structural hit (a line-level `deduction_risk` on the later claim fits the existing record, `build.py:198-215`).

#### S11 · Septic shock, ICU stay with the package days under-billed (batch 1, 1 bill)
- **Scenario.** Woman born 1950, urosepsis A41.9 + septic shock R57.1 + N39.0, intensive care, `yatis` 2026-06-02 to 06-07 (6 dates). `510090` on day 0, `P552002` on days 1–3 (one line per day), `510090` on day 4; day 5 is the transfer day and carries no ICU line. P552002 (4,059.89 per day) is used because a P552003 day needs documented organ support.
- **Fault / clean twin.** The three package days are billed at 50 % of list. Clean twin: 100 %; the block still shows a 0 TL row.
- **Finding.** `icu_puani` row; by the engine's formula the shortfall is 6,089.84 (measured 4,871.88 at 60 %; the stay expects 13,664.87). SUT 2.4.4.H.(2) C001234 (ICU on EK-2/C points), H.(8) C001243 (first and exit day at the day rate), H.(7) C001242, 2.2.2.B-1.(1).a C000685/686/699.
- **Also lights (side effects, not faults).** Checklist ORTAK-21 (surgery documentation, a misfire on an ICU package, EI-16), ORTAK-17, ORTAK-27, and an EK-2/C-1 copay-rate alert (P552001-3 carry 100 %).
- **Triggers.** Block `icu_puani` ✓. N 1, E 0.
- **New data.** None.
- **Builder.** G4a: kinds `icu_day`/`icu_package` in `Kind` and `KIND_GROUPS`, a `package.mode` exemption (ICU packages sit beside itemized lines), per-kind stay coverage, `package_candidate` False for ICU packages; plausibility already counts 510090 and P55200x as bed days.
- **Clinician.** An intensivist: ICU days, organ support, whether the hospital bills 510090 on both end days.
- **Size/risks.** 1.5 d. The +100 % ilave oran needs a basamak-3 header (FACILITY); the tier-overbilling detector #242 fires but is not surfaced (EI-4).

#### S12 · Late-preterm newborn, Kuvöz billed on 3 of 6 days (batch 1, 1 bill)
- **Scenario.** Infant born 2026-07-10, P07.3 + P59.9 + Z38.0, department "Yenidoğan", `yatis` 6 dates. Exam `520010`, Kuvöz `510070` ×3 on day 0, companion `510121` on days 0–4.
- **Fault / clean twin.** Kuvöz billed for 3 of 6 days. Clean twin: Kuvöz ×6; the companion motor still asks for 5 × 74.10 unless `510121` is billed (it is).
- **Finding.** `yenidogan_yatak` 1,322.94 (expected 2,645.88); the standard-bed block loses the newborn-owned days. EK-2/B 510070/510081 rows under SUT 2.2.2 (no SUT clause names Kuvöz or Kot, `tasks/todo.md:705`).
- **Triggers.** Block `yenidogan_yatak` ✓. N 1, E 0.
- **Builder.** G4b: kind `newborn_bed` (510070/510081), `bed_day_codes`, age-aware vitals and lab bounds (`Boy 120–210 cm`, `Kilo 30–200 kg` are adult), composer `_BED_CODES`. Age 0 is already legal.
- **Clinician.** A neonatologist: gestational age and weight, incubator against cot, phototherapy, newborn drugs and labs.
- **Size/risks.** 1.5 d. Rooming-in is unreachable (EI-14).

#### S13 · Type 2 diabetes + hypertension, control visits (batch 1, 3 poliklinik bills; b4 in batch 3)
- **Scenario.** Man born 1961, E11.9 + I10, internal medicine (1000). Bills on 2026-04-06, 04-12 and 05-18, each an exam `520030` plus hemogram.
- **Fault / clean twin.** b2 is a new takip 6 days after b1 for the same branch (SUT 2.2.1.B-1.(2) C000573: a second outpatient visit within 10 days, ER excluded; El Kitabı Tablo 15 #2). b1 and b3 are clean; b3 is 36 days after b2.
- **Finding.** A `claim_compliance` finding on **b2 only** (patient and bill reports agree) ✓. First outpatient claims also evaluate 12 more payment-method rules and match `ORTAK-20.ayaktan_ek2a_yatis_ek2b`; the checklist gains `ORTAK-5` ✓.
- **Triggers.** Wave A `tablo15_2_duplicate_exam_10day` and `ORTAK-20`; checklist `ORTAK-5`. N 3, E +13 (the +12/+1 is a one-time gain for the first outpatient bill, not per bill).
- **Builder.** G1 (`poliklinik` in the pathway `claim_type`; `expand`/`compose` need no change), G2. `520030` is already `muayene` in the composer.
- **b4 (batch 3).** EK-1/A: the diabetes visit with a chronic health report and `copay_rate_applicable` True, billed 100 and payable 80: waived 20.0 instead of "partial exempt". Needs the model column and payable ≠ billed (G5b) and the all-diagnoses fix.
- **Dormant D2.** A fourth outpatient bill on one date in another branch (eye check): 0 today (`same_day_multi_specialty_outpatient`, C000576, is never derived).
- **Clinician.** An internist (visit cadence); the billing officer decides whether b2 is a control or a new episode.
- **Size/risks.** 1.5 d. The duplicate-exam rule needs both bills outpatient (not `acil`, not `yatis`).

#### S14 · Septic shock continued: the ward bill (batch 1, bill 2 of S11)
- **Scenario.** `yatis` 2026-06-07 to 06-10, internal medicine: `510010` ×4 starting on the ICU discharge day, companion `510121` ×3.
- **Fault / clean twin.** The transfer day is billed by the ICU bill and again by the ward bill. Clean twin: the ward bill starts the next day. Generator form: `use_sibling_pathway` with a ward bill that begins a day early.
- **Finding.** Wave A `yatak_icu_overlap_510010`, a financial review on the ward bill (the observed amount is the 510010 line, 222.36; status evaluated), checklist ORTAK-29 ✓. The ward bill's standard-bed expectation loses the overlap day. SUT 2.4.4.H.(8) C001243; EK-2/B 510090 text ("yemek, yatak, hasta vizit").
- **Triggers.** The first Wave A financial row. N 1, E +1.
- **Builder.** G2 and G4a are already paid; no new slice.
- **Risks.** The detector treats every claim that discharges on an ICU last day as ICU evidence (EI-17): do not use the single-claim variant (510010 on the claim's own last day), it fires on a model artifact.

#### S15 · Newborn continued: ward bill after the NICU (batch 2, bill 2 of S12)
- **Scenario.** The baby moves from the NICU to the ward; the ward bill (2026-07-15 to 07-19) bills Kot `510081` ×3 and the standard bed `510010` on a day that the Kuvöz or Kot line already pays.
- **Fault / clean twin.** `510010` beside a newborn bed line (clean: only the newborn bed line).
- **Finding.** `audit_exposure` action `yatak_newborn_overlap_double_billing`, 222.36 per day (SUT 2.2.2, EK-2/B rows). ✓ for the same-bill form; the cross-bill form uses the same detector over `ctx.history` (`yatak_newborn_overlap.py:131-227`, read in code) but was not lit separately.
- **Triggers.** One finding kind; the finished audit detector (item 8). N 1, E 0.
- **Builder.** None beyond G2 and G4b. For the cross-bill form S12's NICU bill must end on a day that carries a Kuvöz line, so S12's fault (some days unbilled) is placed on the first days of the stay, not the last.
- **Risk.** Two simultaneous claims over the same days are not validated by the loader; keep the stays consecutive.

#### S16 · Hip fracture, five bills over seven months (batch 2)
- **Scenario.** Woman born 1947, femoral neck fracture S72.00 + D62 + osteoporosis M81.09. **b1** (`yatis` 2026-03-02 to 03-07, orthopaedics 2600): hemiarthroplasty package `P612320` (18,390.80) and two red-cell units `705371` (4,462.65 each) with valid synthetic ISBT numbers. **b2** (poliklinik, 2026-03-23, 16 days after discharge): control exam `520030`. **b3** (poliklinik, 04-13, FTR 1800): crutch `OP1000` (EK-3/C-2, 63.84, MIAT 1 year). **b4** (poliklinik, 09-28): the crutch again. **b5** (poliklinik, 09-29, geriatrics): romosozumab (EVENITY, EK-4A barcode 8699862950244, price 0) with a health-board report.
- **Faults / clean twins.** b1: the blood is billed at the full list price although inside an EK-2/C package (C000694: 36 % for 705371/705430/705440; C007927 §4.6.(4)). b4: early renewal, 168 days against a MIAT of 365. b5: report duration 12 months where the SUT allows 6 (C006166, §4.2.17.D.(1); criteria: age over 65, T-score −3.5 or lower, two or more fractures). b2 and b3 are clean.
- **Findings ✓.** `audit_exposure` `blood_component_partial_bill` (5,712.20 for two units, research probe); `materials` `material_miat_interval` (§3.1.2, clause id unverified); `drug_indication` `report_duration_mismatch`. The post-discharge control (b2) has no rule yet (C000714, EI-12).
- **Triggers.** Three finding kinds. N 3, E 0. After EI-2 is fixed, billing the blood at 25 % (on the ladder) lights `blood_uplift` too (+1 block).
- **New data.** `isbt128_barcode` per line (G5a); `OP1000` through an EK-3/C-2 catalog parameter (G7b); `drug_report_duration_months` (G9). No new column.
- **Builder.** G1, G2 already paid; the material line links to b3's exam line.
- **Clinician.** Orthogeriatrician (transfusion trigger, units), physiatrist (crutch), endocrinologist or geriatrician (romosozumab criteria).
- **Size/risks.** 3.5 d, the largest review of the plan. Hospital billing of EK-3/C-2 devices is unverified (contracted suppliers usually bill them): ask the billing officer before building b3/b4. Never use a real donation number.

#### S17 · End-stage kidney disease: a month of haemodialysis (batch 2, 2 bills)
- **Scenario.** Man born 1955, N18.0 + D63.8 + E21.1 + Z49.1 + Z99.2, nephrology (1062). **b1** (`gunubirlik`, date span 2026-05-04 to 05-29): 12 sessions `P704230` (5,445.77 each), darbepoetin (ARANESP, barcode 8699862950046, price 0) with a one-month report; no labs or heparin (bundled, C000969, C004117). **b2** (`yatis`, one date 2026-06-12): emergency haemodialysis `P704210` for hyperkalaemia (C000963).
- **Fault / clean twin.** b1: the ESA prescribed by "Genel Cerrahi" (clean: Nefroloji). b2 is clean.
- **Finding ✓.** `drug_indication` `prescriber_specialty_mismatch`. SUT: C000957, C000961, C000963, C000965, C000966, C000969 (§2.4.4.D-1), C000496 (haemodialysis is a day case), ESA C004192–C004196.
- **Triggers.** One finding kind. N 1, E 0. Copay stays "partial exempt" (EI-6).
- **Why N is low.** The correct dialysis bill is informational by design. The day-bed *exclusion* for `704210`/`704230` can only be shown with the itemized codes, which the engine mis-signals (an itemized 704230 adds a payment-method violation and an audit exposure of 2,575.09, EI-7), so b2 uses the package form: the day bed disappears through the package window, not through the exclusion.
- **Builder.** G1 (`gunubirlik`), G3 (a date span on a non-stay claim; `expand` sets `claim_end = claim_start`), G9. Whether SGK bills a month as one takip is unverified.
- **Clinician.** A nephrologist: prescription, ESA dose with Hb, ferritin, TSAT, access.
- **Size/risks.** 2.0 d. Corpus dialysis rules key on codes that do not exist (`P5010046/47/50`, EI-7): none can fire.

#### S18 · Decompensated cirrhosis: two admissions (batch 2)
- **Scenario.** Man born 1963, K74.6 + K92.2 + I85.0. **b1** (`yatis` 2026-06-15 to 06-19, internal medicine): endoscopy `701540`, albumin infusion (barcode 8699686690029, price 0) with the board-report flag False and inpatient supply True. **b2** (`yatis` 2026-07-13 to 07-16, rebleed): two red-cell units `705371`, itemized EK-2/B stay, barcode empty.
- **Faults / clean twins.** b1: albumin without the report (C006389: only to inpatients with albumin ≤ 2.5 g/dl on a specialist report). b2: no ISBT number (C007926: components on EK-2/B are paid only if the epicrisis names the ISBT numbers).
- **Findings ✓.** b1: `drug_indication` `missing_board_report`, checklist readiness `0612`. b2: Wave A `detect_blood_component_isbt128_violations` evaluated and matched, a `claim_compliance` error.
- **Triggers.** N 3, E +1. Variants kept as data notes: `inpatient_supply_required` (K70.3 with supply False; coherent only as an outpatient prescription line).
- **Dormant D1.** A poliklinik bill on the day of b1's admission, same branch (`same_day_outpatient_visit`, C000575).
- **Builder.** G5a (barcode), G9 not needed; albumin ≤ 2.5 g/dl must agree with the lab table.
- **Clinician.** Hepatologist or internist: albumin criteria, transfusion trigger, endoscopy timing.
- **Size/risks.** 2.0 d. Synthetic barcodes only.

#### S19 · COPD "frequent flyer": five bills (batch 2)
- **Scenario.** Man born 1954, J44.1 with respiratory failure J96.0/J96.1. **b1** (`acil`, 2026-05-04): green-area exam `520021` billed with CRP and a chest X-ray. **b2** (`yatis`, one date 2026-05-18, pulmonology 1171): observation, exam `520010` and hemogram, nothing for the bed. **b3** (`yatis` 2026-05-24 to 05-27, six days after b2): admitted through the ER, critical bed `530000` and exam on day 0; heparin 25,000 IU vial (barcode 8681697770029, price 0). **b4** (poliklinik 2026-06-01, five days after discharge): control exam. **b5** (poliklinik 2026-06-22): home BPAP device (`DO1013`).
- **Faults / clean twins.** b1: tests and imaging beside a flat-fee visit (Tablo 15 #7). b3: the IU strength keyed as quantity 25,000 (Tablo 15 #11; the 999 bound is a local heuristic). b4: the control visit flagged as a package component (Tablo 15 #3). b5: the device flagged as needing approval, no approval recorded (Tablo 15 #15). b2: the day bed `510120` is not billed on a stay under 24 hours (C000648 prices such a stay at the day bed; clean twin: `510120` billed, silent). The `530000` bed on b3 is a precision demo, clean and silent by design (it removes its own bed day); the real b3 pathway bills the ward bed on days 1–3 and the companion on days 0–2, which the skeleton left out (without them the bed block would show an unplanned 667.08 row).
- **Findings ✓.** Wave A `tablo15_7_green_area_bundled_extra` (a review per extra line), `tablo15_11_drug_quantity_error` (review), `tablo15_3_vakabasi_wrong_method` (finding), `tablo15_15_material_preauth_missing` (review); kinds `yatak_puani_day_bed`, `materials/material_pre_auth`.
- **Triggers.** Four Wave A ids, two kinds. N 6, E +4. Readmission (b2 → b3) and the post-discharge control (b4) carry no rule yet (EI-12).
- **Builder.** G1, G2, G3 (one-date stay), G5a (`is_package_included`, `requires_pre_auth`), G6 (a quantity above the `Drug.qty` bound of 999). Each bill is independently deliverable; build b1–b3 first.
- **Clinician.** A pulmonologist (exacerbation timeline, observation, anticoagulation); the billing officer for b5 (home devices are normally supplied outside the inpatient bill; the pre-approval column is the only handle).
- **Size/risks.** 4.0 d. `acil` b1 is invisible to Wave A payment rules (EI-1). Two other detectors of the family (inpatient-on-outpatient, donor prep) need category or context values the composer cannot write and are kept out (S23).

#### S20 · Umbilical hernia as a day case (batch 2, 1 bill)
- **Scenario.** Patient born 1985, K42.9, general surgery, `gunubirlik`, one date: itemized `603840` (1,914.43) with anaesthesia `550230`.
- **Fault / clean twin.** Itemized instead of the package (clean: `P603840`, 7,169.60).
- **Finding.** `billing_strategy` `compliance_violation` plus an uplift of 5,255.17 (C003484: day cases pay as inpatient; §2.2.2.(1)); no bed row (C000649) and no companion row (C000650) for a day case with an EK-2/C procedure (the matching Wave A rules 2.2.2.(4)/(5) cannot match, EI-20). No new row kind (S1 shows the inpatient form).
- **Triggers.** N 0; it covers the finished day-case item (7). `care_setting_review` stays dark (FACILITY, EI-22).
- **Builder.** G1 (`gunubirlik`); package mode exists. **Clinician.** A surgeon, light. **Size.** 1.0 d.

#### S21 · Cervical cancer radiotherapy course (batch 2, 1 bill)
- **Scenario.** Woman born 1969, C53.9, radiation oncology (3200). One claim with the course: IMRT design `800110`, planning `800160`, dose `800220`, per-session `800440`, HDR brachytherapy design `800114`, dose `800260`, complex intracavitary `800520`, afterloading `800560`.
- **Fault / clean twin.** The course keyed on once-per-course and once-per-day codes (whole course as `800440` ×25 on day 1; both planning codes; afterloading ×4 as one line). Clean twin: one design, one planning, one dose line, one session line per treatment day.
- **Finding ✓.** One 14-line claim lights all 12 emitting ids (`course_cap.*` ×8, `same_day_collapse.*` ×4), each a financial review row with no confirmed amount, status **unavailable** (the model carries no course or session identity, EI-19). Source: EK-2/B §8.1 explanatory cells, current as of 2026-07-07 (module docstring); no SUT clause id.
- **Triggers.** N 12 (rows only), E 0; twelve financial rows beside the ICU-overlap one of S14.
- **Builder.** The 8xxxxx codes belong to EK-2/B group 8, whose only grammar kind is `imaging` (`KIND_GROUPS`): either accept the stretch or add a `radiotherapy` kind; a date span if outpatient (G3).
- **Clinician.** A radiation oncologist: fraction schedule and design level.
- **Size/risks.** 1.5 d. High count, low evidential value; do not present it as 12 findings.

#### Batch 3 cards (short)
- **S13 b4 · EK-1/A with a chronic report.** MODEL: a nullable `has_chronic_health_report` on `PatientCopayProfile` and wiring (Q3). 1.0 d + G5b.
- **S22 · Hip revision, `material_uplift`.** `P612480` (39,144.00) with the acetabular cup `AP1390` not billed: ceiling 3,295.04. The clean twin is not silent (549.17: KDV 20 % against ex-VAT billing) and the 12 pairings are `sut_derived_unverified` (EI-10). Build only after a decision.
- **S23 · Rare detector hosts.** Living-donor liver transplant (donor visit as exam, `donor` occupational context; recipient `P609080` plus a separate surgical line, 908,561.20, ≈ 29× the largest demo bill), spinal fusion with `P703365`/`P614981` and no D-4/D-5 primary (C001389, C001413), a bone-cement line with a blank material type. Three of the five ids are `unavailable` by spec. ≈ 7 d, transplant and neurosurgery clinicians. Dental general-anaesthesia stories are **not** proposed: the +30 % rule is not in the SUT corpus (EI-21).
- **S24 · Specialty breadth.** Four coherent patients chosen from the 40 code-keyed Fatura İnceleme rules (§2.4): TB work-up (bronchoscopy `608320`, TB PCR `908290`, culture `906180`), a pregnancy (antenatal biometry `803650`, then delivery with `704541` and tubal ligation `620620`), a hand fracture (`610950`, later pin removal `611320`), a cardiac work-up. Needs lab and imaging kinds for numeric lab codes (G7e). Check each rule's denial text against the story before building.
- **S25 · EK-2/G surcharge.** Oncologic surgery on the EK-2/G list (213 codes) without the flag: a patient-alert count, not a block.
- **S26 · Special rooms.** Sterile room `510100` (neutropenia) or radioiodine room `510110`: silent by design; 444.72 on a partly billed room. Heavy clinical review for almost no visible output.

#### Dormant bills (optional, engine-first)
D1 (S18) and D2 (S13) are plausible outpatient bills whose cross-bill rules (C000575, C000576) have no derivation yet. Build them only when EI-12 is closed; expected 0 findings today, to be confirmed when built. "Prior therapy" (C003457) and "prior prosthesis" (C000761) cannot even be written as data today: no column holds a prior drug record, and the pathway window (2026-02..09) cannot hold a bill years earlier.

### 5.4 Not proposed, with the reason

| Item | Reason |
|---|---|
| Physiotherapy sessions | no new matched rule is reachable: proxies force `unavailable`, the ESWT rule keys a nonexistent code, history is not read (EI-8) |
| `drg_uplift`, `care_setting_review` | FACILITY (basamak 3) and, for the latter, unreachable at catalog prices (EI-22) |
| `drg_package_adequacy` | the rule corpus is clinically incoherent (EI-9) |
| Dental general anaesthesia | the +30 % basis is absent from the SUT corpus (EI-21); needs a dental catalog |
| `detect_inpatient_on_outpatient` | vocabulary artifact and a false positive on day-case `ameliyat` (EI-17) |
| `detect_normal_poliklinik_wrong_method`, the two non-emitting detectors | dead or non-emitting (EI-13) |
| Stem-cell add-on after an allogeneic transplant | heavy hematology timeline, report surfacing unverified |
| A second facility | decision in §10 (Q4); two dark blocks and the ICU ilave oran depend on it |

## 6. Recommended first batch

### 6.1 The batch: S9–S14 (5 new patients, 9 new bills)

| Order of delivery | Story | Why it is in |
|---|---|---|
| 1 | **S9** lumbar stenosis, second operation | the cheapest dark block (one generator slice, G0, which every story needs anyway); proves the S-id widening on a single bill |
| 2 | **S11** septic shock, ICU stay | lights `icu_puani` and is the base of the first cross-bill rule (S14); G4a is the biggest grammar change and is worth starting early |
| 3 | **S12** late-preterm newborn | lights `yenidogan_yatak`; G4b is independent of G4a, so it can run in parallel; base of S15 |
| 4 | **S13** diabetes + hypertension, three outpatient bills | the first multi-bill patient and the cheapest (G1 + G2 only); the only story that adds the 12 outpatient payment-method evaluations and `ORTAK-20` |
| 5 | **S10** GI bleeder, ER then admission | the richest single story (three blocks and two Wave A ids); it waits for G2 (from S13) and needs the two small slices G7a and G8 |
| 6 | **S14** ward bill after the ICU | one extra bill on S11's patient: the first Wave A financial row, no new slice |

Reasons in one line each: (1) six of the eleven dark blocks are data-reachable and all six are lit here; (2) every story is clinically ordinary (sepsis, GI bleed, newborn, diabetes), so one clinical pass can cover the batch; (3) the batch builds the two generator capabilities that everything later needs, multi-bill (G2) and the bed-family grammar (G4a, G4b); (4) it contains three kinds of multi-bill patient, ER → ward, outpatient series, ICU → ward; (5) each story is independently reviewable and a clean twin exists for each.

### 6.2 Build order and milestones

Two tracks can run in parallel after the shared start:

- **Start (shared):** G0 (lock relax and the `scenarios` key) and G12 (the measurement script), 2.5 d.
- **Track A, multi-bill:** G2 (4 d) → G1 (1.5 d) → S13 → G7a, G8 → S10. After G2, S14 follows S11.
- **Track B, bed family:** S9 (1 d) → G4a (3 d) → S11 → S14; G4b (2.5 d) → S12.

Metrics after each milestone (skeleton, cumulative, in this delivery order; §9.3 explains the harness):

| Milestone | Blocks with output | Wave A evaluated | matched | rules with a row |
|---|---|---|---|---|
| Baseline (8 patients) | 9 | 273 | 14 | 14 |
| S9 | 10 | 273 | 14 | 14 |
| S11 | 11 | 273 | 14 | 14 |
| S12 | 12 | 273 | 14 | 14 |
| S13 | 12 | 286 | 16 | 15 |
| S10 | 15 | 287 | 18 | 17 |
| S14 | **15** | **288** | **19** | **18** |

### 6.3 Cost of the batch

| Part | Days |
|---|---|
| Generator slices: G0 2.0, G1 1.5, G2 4.0, G4a 3.0, G4b 2.5, G7a 0.5, G8 1.5, G12 0.5 | 15.5 |
| Stories: S9 1.0, S10 2.0, S11 1.5, S12 1.5, S13 1.5, S14 1.0 | 8.5 |
| **Total** | **24.0** (about five weeks of one engineer; two tracks shorten the elapsed time) |
| Clinical review (not an engineering cost): one pass over six pathways, plus a billing-officer check of the MEDULA text in S10 | separate |

Value for the batch: N = 12 (6 blocks, 5 Wave A ids, 1 checklist id) for 24 d, 0.5 per day. Per delivery, with the slices charged to the story that first needs them: S9 0.33, S11 0.22, S12 0.25, S13 0.43 (it pays for G1 and G2), S10 1.25, S14 1.0. **The ratio is a property of the generator, not of the stories**: the same six stories on a generator that already had G2 and G4 would cost about 8.5 d.

### 6.4 Batch 2 and what must be decided before batch 3

- **Batch 2 (S15–S21; 6 new patients, 17 new bills; ≈ 22.5 d: 15 d of stories plus G3, G5a, G6, G7b, G9).** Order by value per day, slices charged to the first story that needs them: S15 1.0, S18 0.9 (it pays for G5a), S19 0.8 (it pays for G3 and G6), then S16 and S17 at 0.5 (S16 pays for G7b and G9 and is the largest review), S21 (the cheapest per count, but rows only), S20 (coverage only, 0). It adds no block; it adds 5 matched Wave A ids, 12 radiotherapy rows, nine finding kinds, and covers the finished engine items 3, 4, 6, 7, 8, 11, 12 of §3.
- **Batch 3 (conditional).** S13 b4 needs the model column (Q3); S22 needs the `material_uplift` verification (EI-10); S23 and S26 need specialist clinicians for one or two ids each; S24 is optional breadth. None is needed to reach the block ceiling.
- **What the plan does not reach.** After batch 1 the block count is 15 of 20. The five dark blocks left are `blood_uplift` (EI-2, then +1 through S16), `material_uplift` (S22 after EI-10, +1), and three that no data can light (`drg_uplift`, `drg_package_adequacy`, `care_setting_review`). The ceiling by data alone is therefore 16, and 17 after the blood fix.

## 7. Generator slices and the data-model gap list

Paths: `PW/` = `scripts/synthetic/pathways/`, `CO/` = `scripts/synthetic/cohort/`, `FA/` = `scripts/synthetic/faults/`, `CL/` = `src/bilun/domain/claims/`, `TS/` = `tests/unit/synthetic/`. Evidence is from a read-only research pass of 2026-10-20; nothing was run in the generator.

### 7.1 Generator slices (priced once, charged to the first story that needs them)

| Slice | What changes | Evidence | Tests and pins that move | Days | First needed by |
|---|---|---|---|---|---|
| **G0** un-lock S1–S8 | `Pins.story` `^S[1-8]$`, the `Story` literal and `SHOWCASE_STORIES`, `fault.story_coverage`/`fault.op_coverage`/`fault.duplicate_story`, `recipe.patient_numbers`/`recipe.duplicate_fault`, `clinical.patient_numbers`; goldens bijection and the sibling folder; a new top-level registry key `scenarios` (not new `roles`, so the three role pins stay) with accessors in the Python fixture and the JS reader; make `fault` optional | `PW/schema.py:435`; `FA/schema.py:37,94,211`; `FA/checks.py:442-472`; `CO/recipes.py:186-216,243-260`; `CO/clinical.py:412-434`; hard-coded `PATHWAYS_DIR` at `PW/loader.py:21,175`, `CO/recipes.py:220`, `FA/checks.py:74,137`, `CO/build.py:488`, `CO/clean.py:406`, `CO/labs.py:1296`, `CO/clinical.py:358`, `CO/plausibility.py:496` | `TS/test_pathways_roundtrip.py:30,194-200`; `test_pathways_golden.py:30,108-149`; `test_fault_siblings.py`; `test_pathways_schema.py` (one mutation case per check id); `test_cohort_recipes.py:58,94,235`; `test_cohort_build.py:135,226-234,283-310,344-355`; `test_synthetic_cohort_fixture.py:30,63-65,161-167,217-224,299-308`; `frontend/scripts/lib/cohort-registry.test.mjs:17-19` | 2.0 | S9 |
| **G1** visit grammar | add `poliklinik` and `gunubirlik` to `Pathway.claim_type`; treat every non-`yatis` type as a non-stay in the `acil` special cases | `PW/schema.py:448,479-481,526`; the clean-table builder already knows both types (`CO/clean.py:126-131`); plausibility knows them (`CO/plausibility.py:273,1168-1224,1347-1358`); `expand`/`compose` need no change (`520030` is `muayene`, `CO/compose.py:78`) | `TS/test_pathways_schema.py`, `test_cohort_recipes.py`, goldens, pathways README | 1.5 | S13 |
| **G2** multi-encounter | `encounter_no` and optional per-encounter pins on the recipe; claim and episode sequence from the encounter (ids allow 1..999, `CO/ids.py`); sex and birth year once per patient with the age-arithmetic check; one copay profile per patient; effective pins carried on `ComposedClaim` so the clean and lab builders stop reading `pathway.showcase`; lab draw key includes the episode (today two claims of one patient get identical values for the same code); vitals per encounter; `prove_showcase` switches to bill-scoped contexts | `CO/recipes.py:85-90,186-216`; `CO/build.py:499-554` (claim and episode hard-coded to 1 at `:507-509`); `CO/clean.py:295-324,414,422-440,478-480,520-524`; `CO/labs.py:714-719,1261-1327`; `CO/engine_proof.py:795-804`; `CO/plausibility.py:1071-1089,1095-1126` | `test_cohort_build.py`, `test_cohort_clean.py:238-240,376,757-788`, `test_cohort_labs.py:109,702,756-758,2299-2331`, `test_cohort_clinical.py`, `test_cohort_engine_proof.py:485`; **frontend `cohort-registry.test.mjs:24-25` (patient count must equal `anadata_clean` rows: breaks as soon as a patient has two claims)** and `capture-screens.mjs:575,726` | 4.0 | S13 |
| **G3** one-date stay and date span | `nights: 0` (admission == discharge) for `yatis`; a `span:` for `gunubirlik` and `poliklinik` session claims (`claim_end` from the span); relax the one-day window for non-stay claims | `PW/schema.py:226-229,439,476-483,519-528`; `PW/checks.py:544-549,558-576`; `PW/expand.py:71-81`; `CO/plausibility.py:1216-1225,1347-1358` | pathway schema mutation cases; plausibility `stay.dates_in_window` | 1.5 | S19 |
| **G4a** ICU grammar | kinds `icu_day` and `icu_package` in `Kind`/`KIND_GROUPS`; `package.mode` exemption and `package.window` for ICU packages; per-kind stay coverage so a bed and an ICU line cover each day once except the transfer day; `package_candidate` False for ICU packages | `PW/schema.py:175-177`; `PW/checks.py:45-48,267-277,385-425,580-602`; `CO/build.py:518`; plausibility already counts 510090/P55200x as bed days (`CO/plausibility.py:427-435`) | five check ids, each needing a registry entry and a mutation case (`PW/schema.py:32-33`) | 3.0 | S11 |
| **G4b** newborn grammar | kind `newborn_bed` (510070, 510081); `bed_day_codes`; age-aware vitals and lab bounds; department "Yenidoğan"; composer `_BED_CODES` | `PW/checks.py:267-272`; `CO/plausibility.py:228-233,427-435`; `CO/clinical.py:155-176`; `CO/plausibility_clean.py:357-365`; `CO/compose.py:32` | `stay.bed_coverage`, `patient.age_gate`, vitals bounds | 2.5 | S12 |
| **G4c** special rooms | codes 510100/510110 in `data/synthetic/reference/code_sets.yaml` and a kind | `check_procedure_kinds` blocks them (`PW/checks.py:262-296`); not in `data/synthetic/reference/code_sets.yaml` | pathway checks | 1.0 | S26 (optional) |
| **G5a** line flags without money | `ProcedureFlags` (`isbt128_barcode`, `is_package_included`) and `MaterialFlags.requires_pre_auth` on pathway lines, passed through `expand` and `compose` | `CO/compose.py:151-173,165,210`; `PW/schema.py:358-362` | pathway schema; plausibility `material.stray_flag` | 1.5 | S18 |
| **G5b** flags with money | `surcharge_applicable`, `copay_rate_applicable`, `copay_rate`, `expected_payable_try < billed`; relax `money.payable_equals_billed` and the header payable total | `CO/compose.py:164-168,298`; `CO/plausibility.py:114,1844-1855`; `CL/totals.py:55-61` | `tests/unit/domain/optimization/test_copay_rate_exposure.py:150-161,172-210` (cohort-wide zero mismatches) | 1.5 | S13 b4, S25 |
| **G6** fault ops | a quantity op (above the pathway bound `Drug.qty` 1..999), a blank-value op for `material_type`, optionally several faults per bill | `FA/schema.py:39-46` (six ops); `PW/schema.py:379,398`; `FA/checks.py:463-472` (`fault.op_coverage` requires every op) | fault registry/mutations/answer-key tests | 2.0 | S19 |
| **G7a** lab reference | `L103120` (manual haematocrit), `L101850` (CRP) in `data/synthetic/reference/lab_reference.csv` with lab states | `PW/checks.py:353`; `CO/labs.py` | lab tests (14 codes pinned at `test_cohort_labs.py:109`) | 0.5 | S10 |
| **G7b** other EK-3 annexes | a catalog parameter per annex for EK-3/C-2 (`OP1000`) | `CO/catalogs.py:70-75,134-151`; `PW/checks.py:103-113`; `CO/plausibility.py:549-553`; 26 priced EK-3 catalogs share the columns `sut_code, material_name, description, price_try`, only `ek3o` carries dates; `MaterialCode` `^[A-Z]{2}[0-9]{4}$` fits | material checks | 1.5 | S16 |
| **G7e** numeric lab and imaging codes | `lab` kind for numeric 9xxxxx codes needs reference rows and states | `KIND_GROUPS` pairs groups 9/10 with `lab` only | lab tests | 1.5 | S24 (optional) |
| **G8** MEDULA events | a recipe or fault input that yields event rows; registry counts | `CO/build.py:560` (`medula_events=()`); serialization exists `CO/tables.py:246-254`; date rule `CL/validation/dates.py:17-31`, `CL/validation/links.py:116-140` | `frontend/scripts/RECORDING.md:36-47` ("known limit": zero rows) | 1.5 | S10 |
| **G9** drug flags | `drug_report_duration_months` settable from a pathway; drug routes for each new patient in `data/synthetic/cohort/showcase_clinical.yaml` | `PW/schema.py:365-370`; `PW/expand.py:134`; `CO/compose.py:236-255` | clean `recete` table | 1.0 | S16 |
| **G12** measurement script | one repo script with the §9.2 map and a diff mode | §9.4 | none | 0.5 | start |
| | **Total of all slices** (batch 1: 15.5, batch 2: 7.5, batch 3: G4c, G5b, G7e = 4.0) | | | **27.0** | |

Batch 1 needs G0, G1, G2, G4a, G4b, G7a, G8, G12 = 15.5 d. Batch 2 adds G3, G5a, G6, G7b, G9 = 7.5 d.

### 7.2 Data-model gap list (fields and tables, with loader, schema and test touchpoints)

New tables: **none**. The paused strict-release lane pins exactly 12 input files (`scripts/deploy/generate_candidate_source_roster.py:30-45`, `scripts/deploy/verify_clinical_semantic_transition.py:652`); only columns and rows are added. Every new column needs a default (139 `ClaimHeader(` and 101 `ProcedureClaimLine(` constructor sites in tests, 3 in `src`: `CL/adapter.py`, `rule_engine.py`, `CL/parsing/row_parsers.py`), a parser entry, and the dtype map in `CO/tables.py`.

| # | Need | Exists? | Change | Loader / schema | Generator | Tests and pins | Used by |
|---|---|---|---|---|---|---|---|
| 1 | `has_chronic_health_report` | **no column**; only an argument of `build_copay_exemption_input` that no caller passes (EI-6) | nullable bool on `PatientCopayProfile` and wiring to the three callers | `CL/models.py:19-26`; `CL/parsing/row_parsers.py:131-160`; `optimization/copay_exemption_context.py:11-52`; callers `cache/sut_context.py:508-516`, `optimization/aggregator.py:353-359`, `api/routes/optimization.py:147-151` | `CO/tables.py:105-118`; `CO/build.py:528` | copay exemption tests; plus the all-diagnoses fix `3218922d` (not in `main`) | S13 b4 (Q3) |
| 2 | incision code `ayniFarkliKesi` (optional) | **no field** | nullable column on `ProcedureClaimLine` | `CL/models.py:65-95`; `CL/parsing/row_parsers.py:258-308` | composer mapping from `session_role` (`PW/expand.py:18-33`) | call sites that pass `same_incision=None`: `billing/claim_strategy.py:714-746`, `claim_session_uplift.py:41-46`, `claim_audit_exposure.py:56`, `optimization/unbundling.py:64`, `prose_rules/drg_unbundling.py:354-386`; removes the documented S8 divergence (`CO/engine_proof.py:90-100`, 3,584.80 against 5,377.20) | S9 (optional; meaning of codes 2–5 unverified) |
| 3 | line flags | **columns exist**, constant in the composer (`isbt128_barcode` empty, `is_package_included` False, `requires_pre_auth` False, surcharge and copay flags False, payable == billed) | pathway flags (G5a, G5b) | none | `CO/compose.py:151-173,164-168,210` | G5b: `tests/unit/domain/optimization/test_copay_rate_exposure.py:150-161,172-210` | S16, S18, S19, S25 |
| 4 | drug report duration | column exists, not settable | `DrugFlags` field | none | `PW/schema.py:365-370`; `PW/expand.py:134` | clean `recete` | S16, S17 |
| 5 | quantity above 999, blank `material_type` | `Drug.qty` ≤ 999 and `MaterialType` is a Literal | fault ops (G6) | none | `PW/schema.py:379,398`; `FA/schema.py:39-46` | fault op coverage | S19, S23 |
| 6 | MEDULA rejection rows | table and parser exist, 0 rows | rows plus builder input | `CL/validation/links.py:116-140` (claim, patient, episode must match); `CL/validation/dates.py:17-31` (timestamp inside the claim range) | `CO/build.py:560` | registry `counts`; `RECORDING.md:36-47` | S10 |
| 7 | materials outside EK-3/F-1 | 26 priced catalogs exist | catalog parameter (G7b) | none | `CO/catalogs.py:134-151` | material checks | S16 |
| 8 | previous-claim or takip reference | **none** (cross-bill rules infer relations from patient, dates and codes) | optional nullable header column, no engine reader | `CL/models.py:29-49` | — | — | only if EI-12 chooses an explicit link |
| 9 | newborn birth date | `birth_year` only; the engine reads `Z38`/`P00-P96` and the department, not age | none | — | — | — | — |
| 10 | `provider_contract_status` | **no column**; `provider_type` carries ownership and contract status (EI-3) | nullable string on `ClaimHeader` | `CL/models.py:29-49`; `CL/parsing/row_parsers.py:84-128` | `CO/build.py:515` | `prose_rules/gap_closing.py:435-438` | not needed by any story |
| 11 | rule-vocabulary service category | **no column**; composer writes 5 labels, rules read 113 (EI-5) | `service_category` column plus readers | `CL/models.py`; `CL/parsing/row_parsers.py:287` | `CO/compose.py:71-80` | all procedure-category readers | S24's 17 category-keyed rules |
| 12 | prior drug record (`medula_record_of_prior_drug`) | **none** | blocked (also needs EI-12) | — | — | — | prior-therapy bills |

### 7.3 The pins every new patient touches

Registry and fixtures (`data/synthetic/cohort_registry.json`: 9 table digests, counts, roles, 8 encounters, 8 faults; `tests/fixtures/synthetic_cohort.py`; `frontend/scripts/lib/cohort-registry.mjs:18-19,33,60-66`, which requires every fault to have a unique `S<n>` and a `showcase_S<n>` role: **a fault with `story: null` fails**). New stories add a `showcase_S<n>` role automatically (`CO/build.py:534`), which breaks `test_synthetic_cohort_fixture.py:161-167` and `test_cohort_build.py:344-355` unless G0 relaxes them; the `scenarios` key avoids that. Patient-count pins: 8 patients, 8 claims, 117 procedure lines, 207 lab rows, 19 drug lines, spread over `tests/unit/synthetic/` (`test_cohort_build.py`, `test_cohort_clean.py`, `test_cohort_labs.py`, `test_cohort_clinical.py`, `test_cohort_recipes.py`, `test_cohort_engine_proof.py` with the committed proofs `reports/synthetic-data/2026-10-15-showcase-proofs/results/` (`S1.json` to `S8.json`), `test_cohort_plausibility*.py`, `test_fault_*.py`, `test_pathways_*.py`, `test_synthetic_cohort_fixture.py`), `tests/unit/domain/billing/test_top_action_type.py:85,144-158` and `tests/unit/domain/test_optimization_claim_context.py:92-93` (every patient needs a procedure line). Docs to update: `data/synthetic/README.md:3,5,13,14,34-47`, `data/synthetic/faults/README.md`, `data/synthetic/pathways/README.md`, `src/bilun/domain/claims/README.md:5`, `src/bilun/domain/README.md:23`, `src/bilun/domain/billing/README.md:62`. Do not touch `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json` (pinned by the paused strict lane).

## 8. Engine-side issues found (to file, not fixed here)

These are engine, corpus or vocabulary problems, not stories. "Effect" says what each does to the demo or to this plan. Evidence is file:line from read-only passes of 2026-10-20 unless marked ✓ (measured in memory).

| ID | Issue | Evidence | Effect |
|---|---|---|---|
| EI-1 | `acil` (and `koruyucu`, `meslek_hastaligi`, `day_case`, "günübirlik" with ü) are not recognised claim types; `infer_care_setting("acil")` returns inpatient | `prose_rules/claim_utils.py:77-88`; `billing/payment_traceability_evaluations.py:116-132`; `treatment_pricing_evaluations.py:200-220`; `focused_rule_projection.py:60-77,484-485`; `rule_findings.py:36-38,312` | S7 alone causes 54 `unavailable: unrecognized claim_type: acil` evaluations (33 payment-method, 14 gap-closing, 7 fatura) ✓ and 2 `claim_type_unrecognized`; every `acil` bill in S10 and S19 repeats it |
| EI-2 | `blood_uplift` reads the ceiling from `expected_payable_try`, which the loader, the composer and a plausibility rule force equal to billed; a correct 36 % bill with payable == billed also shows a **false** audit exposure (2,056.38) ✓ | `prose_rules/session_pricing.py:728-737` (use the EK-2/B list as `line_gazette_list_billed_try` does, `:507-547`); `drg_unbundling.py:233-280`; `claims/parsing/row_parsers.py:269-273`; `CO/compose.py:164` | the block is dark for any data; S16 shows the full-price audit instead and the uplift after the fix |
| EI-3 | `provider_type` carries ownership ("Ozel") and contract status; there is no distinct contract marker. Setting `sozlesmeli` on all 8 lowers the evaluated count by 1 ✓ | `prose_rules/gap_closing.py:435-438`; `payment_traceability_evaluations.py:136-141`; `CO/build.py:515` | 15 payment-method and 40 gap-closing evaluations stay missing or unavailable; not a lever |
| EI-4 | The ICU tier-overbilling detector (#242, `icu_tier_overbilling`) fires for the demo facility but only inside `analyze_claim`; no patient report carries it, and the Wave A groups are pinned at 18 / 32 by an import-time error | `billing/engine.py:274-279`; `billing/focused_rule_projection.py:353-359` | S11 cannot show it; a decision on where to surface it |
| EI-5 | Category vocabulary conflict: the composer writes 5 labels, the rules read 113, and only 15 labels match any rule ✓ | `CO/compose.py:71-80`; `treatment_pricing` category sets | 17 Fatura İnceleme rules and most treatment-pricing rules cannot be reached by data; needs a `service_category` column |
| EI-6 | `has_chronic_health_report` is passed by no caller, so EK-1/A is "partial exempt" forever; the all-diagnoses fix is only on `claude/loving-vaughan-cd0a8c`; `ClaimDiagnosis.exemption_eligible` is a dead column | `optimization/copay_exemption_rules/ek1a.py:80-93`; `cache/patient_slice.py:67-86`; `claims/models.py:62` | S13 b4 is blocked; S2 and S3 keep showing "partial" |
| EI-7 | Dialysis: an itemized `704230`/`704210` raises a payment-method violation and an audit exposure of 2,575.09 per session in the wrong direction (the package has no işlem grubu, so no package gap is computed); the 13 corpus dialysis rules and the heparin rule key on codes that do not exist (`P5010046/47/50`) or on literals no pipeline emits | `prose_rules/yatak_puani.py:262-305`; `data/gazette/prose_rules/treatment_pricing_2_4.json:109,131,150,166,185,206,224,974,989,1011,1028,1051,1067`; `drug_combination_4_2.json:136-144` | S17 uses package codes; dialysis stays a precision demo |
| EI-8 | Physiotherapy: the ESWT rule keys `P915010` (not a code; ESWT is `610820`/`P610820`); the proxies in `_PROXY_REASONS` force `unavailable`; cross-claim history is not read although `ctx.history` exists | `treatment_pricing_2_4.json:344`; `billing/treatment_pricing_evaluations.py:36-53`; `claims/patient_context.py:62-100` | no physiotherapy story |
| EI-9 | `drg_package_adequacy` corpus is clinically incoherent (609270 is a biliary-fistula package, 609300 an islet-cell transplant, 600150/600160 are cheek tumour excisions) | `data/gazette/prose_rules/drg_package_adequacy_prose.json` | block stays dark |
| EI-10 | `material_uplift`: ceiling includes KDV 20 % while the demo bills ex-VAT, so the clean twin shows 549.17; 12 pilot pairings are `sut_derived_unverified`; EK-3 prices are read as of today, not the claim date | `pricing/material_kdv.py:6`; `material_uplift.py:103,118-132,220`; `material_pairing_uplift.json` | S22 is gated; implant KDV 10 % against 20 % is unverified |
| EI-11 | `procedure_addon_uplift`: the clean twin at 100 % shows an audit exposure of 439.86; chapter-7 codes carry no `session_role`; the engine cannot know whether a polyp existed (any colonoscopy-only bill is flagged) | `prose_rules/procedure_addon_uplift.py:115-155`; research probe | S10's clean twin must bill the add-on at 30 % or 50 % |
| EI-12 | The cross-bill inputs that Wave A names are **never derived** even with several bills: `same_day_outpatient_visit` (C000575), `same_day_multi_specialty_outpatient` (C000576), `visit_sequence`, `same_specialty_repeat_days_lt` (C000573/C000640/C000641), readmission and `early_discharge` inside the package window (C000714), `same_session_different_specialty` (a helper exists, `session_specialty.py:36-79`), `same_day_multi_level_icu` (C001242) ✓ | comment at `prose_rules/gap_closing.py:426-431`; `data/gazette/prose_rules/payment_method_2_2.json:210,228,470-495`; `gap_closing_treatment_2.json:89,200-204`; `treatment_pricing_2_4.json:486` | S16 b2, S19 b2–b4 and the dormant bills D1, D2 fire nothing |
| EI-13 | Dead or non-emitting detectors: `detect_normal_poliklinik_wrong_method` returns `[]`; `detect_exam_admission_date_mismatch` and `detect_admission_billing_window` cannot fire (inputs not ingested); the radiotherapy hyperthermia branch is never emitted | `prose_rules/common_billing_errors.py:487-508,348-363,634-647`; `focused_rule_projection.py:346-352` | 4 of the 32 focused ids can never light |
| EI-14 | Rooming-in ("Kot not billable beside the mother") is never passed to the newborn motor | `billing/claim_yenidogan_yatak.py:62-68` (`rooming_in_claim_ids` has no caller) | S12/S15 cannot show it |
| EI-15 | Turkish letters: the department keyword gates need the Turkish spelling (ASCII "Gogus", "Ic", "Goz", "Noroloji", "KBB" fail); `_branch_matches` lower-cases with Python `.lower()` | `prose_rules/fatura_inceleme.py` (`_BRANCH_KEYWORDS`, `_branch_matches`); `fatura_inceleme_checklist.py:114-124` | every new story writes departments with Turkish letters; today's S1–S8 use ASCII names |
| EI-16 | Checklist ORTAK-21 (surgery or biopsy documentation) fires on non-surgical EK-2/C packages such as ICU and dialysis packages, because any code starting with `P` counts as a surgical package | `prose_rules/fatura_inceleme_checklist.py:254,259` | S11 and S17 each add one false checklist row |
| EI-17 | `detect_inpatient_on_outpatient` flags a day-case `ameliyat` line; `detect_yatak_icu_overlap` treats any claim discharging on an ICU last day as ICU evidence (single-claim variants fire on a model artifact) | `common_billing_errors.py:128-130,873-924`; `yatak_icu_overlap.py:100-129`; `reports/rule-engine-surfacing/2026-09-27-wavea-financial-inventory.md` (Y1) | S14 uses the two-bill form only |
| EI-18 | A MEDULA rejection dated after discharge cannot be loaded: the loader requires the timestamp inside the claim's date range ✓ | `claims/validation/dates.py:17-31`; `validation/links.py:134-140` | S10's event sits on a single-date ER bill |
| EI-19 | 17 of the 28 reachable focused ids can never be `evaluated` by spec (EK-2/D add-ons 2, dental 2, radiotherapy 12, transplant 1); radiotherapy needs course and session identity the model does not carry | `focused_rule_projection.py:125-339,462-478` | S21's 12 ids are rows only |
| EI-20 | Wave A rules 2.2.2.(4) and (5) (day case: no day bed, no companion fee; C000649, C000650) need `care_setting` inpatient *and* `visit_type` `gunubirlik`, but `gunubirlik` maps to outpatient | `data/gazette/prose_rules/payment_method_2_2.json:575,592`; `prose_rules/gap_closing.py:329-346` | on a plain `gunubirlik` claim they are evaluated and never match (they appear among the 13 rules S13 newly evaluates ✓); S20 cannot light them |
| EI-21 | The dental general-anaesthesia "+30 %" rule has no clause in the SUT corpus (the real clauses are C000775, C000808, C000817) | `prose_rules/dental_ga_uplift.py`; `data/gazette/sut_clauses.parquet` | no dental story until the legal basis is verified |
| EI-22 | `care_setting_review` is practically unreachable: of 2,383 EK-2/C packages with an EK-2/B twin, none has the EK-2/B price above the package (maximum ratio 0.726) | `prose_rules/care_setting_review.py:140-200` | block stays dark |
| EI-23 | 47 `drug_combination_4_2` rules use blocked keys; 54 `gap_closing` rules read keys no builder produces | `billing/drug_combination_evaluations.py:69-126`; the gap-closing builders | 101 rules not movable |
| EI-24 | Four Fatura İnceleme rules have no condition and match every claim of their branch (KARDİYOLOJİ-4, KARDİYOLOJİ-9, KALP_VE_DAMAR_CERRAHİSİ-1, -4), and GÖĞÜS-6 matches any inpatient claim of that branch | `data/gazette/prose_rules/fatura_inceleme_prose.json` | "matched" without evidence; S24 must not count them |

## 9. Measurement

### 9.1 The two scripts

```bash
python ~/.cache/bilun-tools/demo_coverage_blocks.py /tmp/blocks.json   # blocks and per-rule Wave A counts, about 5.5 s
python ~/.cache/bilun-tools/demo_coverage_inputs.py                    # review, advisory and financial rules, missing inputs, about 5.5 s
```

Both run from the worktree root and read the committed claims tables. They omit the patient's `copay_exemption` and the lab feed (`lab_df_pl`), so copay and capture-gap stories must be measured through the cache or API path. Script 1's "fired" count (5 at baseline) and script 2's block list (9 keys) use different definitions of "output" (§1.2).

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

Wave A, per rule id: **evaluated** (≥ 1 evaluation with status `evaluated`), **matched** (≥ 1 evaluated row with decision `matched`), **rule with a row** (the id appears in reviews, advisories or financial rows). **Finding kinds**: the set of `surface:kind` of the recommended actions, the `claim_compliance` rule ids, the drug applicability and violation statuses, the audit-exposure kinds, and MIAT violations. Every metric is reported per patient and for the cohort. A story is "done" when its expected blocks and ids appear on its own patient and on no other, and when the clean twin does not add them.

### 9.3 Targets per batch (skeleton harness; the real numbers come from the generated data)

| Step | Patients | Bills | Blocks with output | Wave A evaluated | matched | rules with a row |
|---|---|---|---|---|---|---|
| Baseline, `main` 4def9577 | 8 | 8 | 9 | 273 | 14 | 14 |
| Batch 1 after S9, S11, S12 | 11 | 11 | 12 | 273 | 14 | 14 |
| after S13 | 12 | 14 | 12 | 286 | 16 | 15 |
| after S10, S14 (**batch 1 target**) | 13 | 17 | **15** | **288** | **19** | **18** |
| Batch 2 after S15, S16, S17 | 15 | 25 | 15 | 288 | 19 | 18 |
| after S18 | 16 | 27 | 15 | 289 | 20 | 18 |
| after S19, S20 | 18 | 33 | 15 | 293 | 24 | 21 |
| after S21 (**batch 2 target**) | 19 | 34 | 15 | 293 | 24 | 33 |

(Patient and bill counts: S9, S11, S12 add three patients and three bills; S13 adds a patient and three bills; S10 adds a patient and two; S14 adds a bill; S15 a bill; S16 a patient and five; S17 a patient and two; S18 a patient and two; S19 a patient and five; S20 a patient and one; S21 a patient and one.) The skeleton's counts are an approximation, not a promise: a final pathway differs from its skeleton in lines and prices. The tolerance is "same blocks and same Wave A ids", not the same number of evaluated ids.

Per new patient (skeleton): see Appendix B.

### 9.4 What to build once

One repository script (`G12`, 0.5 d) that applies the §9.2 map, takes a claims directory, writes a JSON with the per-patient and cohort metrics and prints a diff against a previous JSON. It would replace the two scripts' ad-hoc definitions, and the batch targets above could then run as a test. Until then, rerun both scripts after each delivery and compare the §9.3 rows by hand.

## 10. Questions for Safa (at most five, each with a default)

1. **Follow-up bills: new patients only, or also on S1–S8?** Putting follow-up bills on the existing eight (for example a control visit for S5) would add no patients, but it changes eight reports you have reviewed and the committed S1–S8 proofs. *Default: new patients only; S1–S8 stay byte-identical.*
2. **How far to commit now?** *Default: approve batch 1 (S9–S14, about 24 days, 5 patients) and decide batch 2 after reviewing it; batch 2 adds 6 patients and 17 bills and mostly deepens finished work.*
3. **The chronic-disease report (EK-1/A).** Showing the copay waiver needs a new nullable column `has_chronic_health_report` on the patient profile plus wiring to three callers, and the all-diagnoses fix that is only on `claude/loving-vaughan-cd0a8c`. *Default: not now; S13 b4 waits, the other batches do not depend on it.*
4. **A second, basamak-3 facility?** Two blocks (`drg_uplift`, `care_setting_review`) and the +100 % ICU ilave oran need a third-tier header; the demo hospital is one private "2./3. basamak özel" hospital that the project maps to basamak 2. It also needs a regulatory check of whether a private hospital can be a class-3 provider (unverified). *Default: no; those blocks stay dark and are named as such.*
5. **Engine fixes before or after the stories?** EI-1 (`acil`), EI-2 (blood ceiling) and EI-12 (cross-bill inputs) decide whether S16's blood uplift, the post-discharge and readmission bills and the two dormant bills ever fire. *Default: file all three as issues now, do not block batch 1, and build the dormant bills only when EI-12 closes.*

Two smaller points I decided without asking (say if you disagree): (a) every new pathway gets a clean twin and one planted fault per bill; (b) the clinical review is one pass per batch by a clinician you name, since the plan only flags what needs one.

## Appendix A. The 255 never-evaluated Wave A rules, by cause

Cause classes (from the classification of §2.2): **needs a planted positive hit** (a focused detector that certifies positives only), **data-fixable** (a line or claim type the builder can read), **input never produced by any builder** (the rule's condition key is produced by no context builder), **engine marks it unavailable** (with the engine's own reason). The 14 matched and 259 checked-without-hit rules are in the companion CSV. Two corrections to the "needs a planted positive hit" lists below: `tablo15_4_normal_poliklinik_wrong_method` is a dead stub (the detector returns `[]`, EI-13), and of the other focused ids a planted hit makes only 11 `evaluated` (the 17 ids of EK-2/D, dental, radiotherapy and transplant stay `unavailable` by spec, EI-19).


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
## Appendix B. Per new patient (skeleton, patient-level report over all of its bills)

Measured on the scratch skeletons of §5 added to the 8 showcase patients. Every `yatis` patient also shows `yatak_puani`, `refakatci` and the checklist (the bare-stay rows, trap T3), which is why most rows list 5 to 7 blocks. For comparison the 8 showcase patients show 4 to 7 blocks, 191 to 264 evaluated and 4 to 10 matched Wave A ids (§1.1).

| Story | Bills | Blocks with output | Dark block(s) lit by this patient | Wave A evaluated | matched |
|---|---|---|---|---|---|
| S9 | 1 | 6 | session_uplift | 258 | 9 |
| S10 | 2 | 7 | lab, procedure_addon_uplift, medula_rejection_playbook | 260 | 12 |
| S11 + S14 | 2 | 5 | icu_puani | 189 | 14 |
| S12 + S15 | 2 | 5 | yenidogan_yatak | 185 | 10 |
| S13 | 3 | 2 | — | 189 | 9 |
| S16 | 5 | 7 | — | 283 | 11 |
| S17 | 2 | 6 | — | 199 | 8 |
| S18 | 2 | 7 | — | 193 | 10 |
| S19 | 5 | 7 | — | 286 | 15 |
| S20 | 1 | 2 | — | 255 | 7 |
| S21 | 1 | 4 | — | 258 | 9 |

Reading: only S9, S10, S11 and S12 light dark blocks (their value is the block); S13 and S16–S21 are valued by Wave A ids, finding kinds and the multi-bill structure, not by blocks. S13 shows only two blocks because outpatient bills carry no bed rows.

## Appendix C. Method, limits and what is unverified

**Method.** Five read-only research passes (silent uplift blocks; bed, ICU, newborn, copay, checklist and MEDULA; sessions, drugs, blood, day cases and history across bills; the data model and generator; the 16 focused detector groups) and a scratch harness that edits in-memory copies of the nine claims tables, rebuilds the dataset through the real loader (`SUTClaimDataset.from_rows`) and calls `compute_patient_billing_report`. The harness and its skeletons live outside the repository. The only repository changes are this plan and its two CSV files.

**What the skeleton numbers are not.** They are measured on scratch bills with the right codes, claim types, departments and dates, not on generator output: a final pathway has other lines and prices. The S19 skeleton, for example, omitted the ward-bed lines of b3 that the real pathway must bill. Targets are therefore "same blocks and same Wave A ids", not the same number of evaluated ids.

**Unverified (named so nobody builds on them as facts).**
- The regulatory premises of several focused detectors come from detector docstrings and constants, not from a primary clause: the 10-day and 7-day windows, the green-area flat fee, donor-preparation handling. The dental +30 % rule is absent from the SUT corpus (EI-21).
- The SUT clause id for the MIAT rule (cited in code as §3.1.2); the 5,712.20 blood exposure and the 6,089.84 ICU shortfall are research-probe or formula figures (the ICU shortfall at 60 % was measured: 4,871.88).
- Whether a hospital bills EK-3/C-2 devices (crutches) on its own claims; whether SGK bills a dialysis month as one takip; the romosozumab criteria as the engine encodes them; the fraction schedule and design level of a radiotherapy course.
- The cross-bill form of the newborn audit detector (read in code, not lit); the single-claim ICU overlap as a true overlap.
- How the frontend renders `poliklinik` and `gunubirlik` claims, and whether it pages above 8 patients.
- The production vocabulary of procedure categories (`ameliyat`, `cerrahi`, `anestezi`, `dental_ga*`): found only in detectors and tests.
- Whether a private hospital can be a class-3 ICU provider (Q4).

**Hygiene.** No patient data, credentials or real donation numbers appear in this plan; ISBT numbers are to be synthetic values of the documented format only. Drug lines stay at price 0 ("fiyat yok"); the EK-4A barcodes cited are public product codes. The two `ilay` folders (`data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/`) do not exist in this worktree and were not opened. One research pass ran two recursive text searches rooted at the repository root (patterns `Tablo 15` and `Algoritma Rehberi`, limited to `.md`, `.json`, `.yaml`, `.txt` and `.py` files), which may have scanned the few tracked files under a folder named `raw data`; no path or content from that folder was printed, kept or used. The claims parquet files directly under `data/synthetic/sut/claims/` were read (allowed). Nothing under `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml` or `data/synthetic/demo_vignettes.json` was touched.

