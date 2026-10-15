# Showcase stories — draft for Safa's review

Date: 2026-10-15. Status: **draft for Safa's review.** The proof scripts and their outputs are in `reports/synthetic-data/2026-10-15-showcase-proofs/`.
Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D1–D6, Q1–Q6 answered).

## In short

- Eight stories, eight different engine rules. Each story is one patient and one bill.
- Each bill was built twice: clean, and with exactly one injected fault.
- **All 8 proven:** the target rule fires on the faulty bill and stays silent on the clean bill (scripts below; output in `results/`).
- **But no clean bill is fully silent today.** Other rules misfire on correct bills (section "Noise on clean bills"). I list thirteen causes (N1–N13); twelve look like engine defects and one (N7) needs your call. None is in the known list (#226/#227/#255/#256). Fix them, or the demo shows findings on bills that are correct.
- Codes, names and prices come from the curated catalogs in force on each line date. Drug prices are "TBD (Q4)". ICD-10 codes are WHO codes from memory (no ICD list in the repo yet; Q5).

## Summary table

| Story | Patient | Setting (dates 2026) | Injected fault | Engine rule | Proven? |
|---|---|---|---|---|---|
| S1 | M 34, acute appendicitis | Yatış, Genel Cerrahi (14–16 Jul) | Laparoscopic appendectomy billed hizmet başı (EK-2B 610131 + anaesthesia + beds + labs + pathology + drugs) instead of the mandatory EK-2C package P610131 | §2.2 payment method → `billing_strategy` (`claim_strategy.py`, `payment_method.py`) | Yes: "must use package billing per 2.2.2.(1)". TL figure is defective (see S1) |
| S2 | M 81, COPD + pneumonia | Yatış, Göğüs Hast. (9–15 Mar, 6 nights) | Only 4 of 7 bed days (510010) billed | `yatak_puani` | Yes: +667,08 TL |
| S3 | F 77, lumbar spinal stenosis | Yatış, Beyin Cerrahisi (18–20 Aug) | Anaesthesia line 550160 (B grubu) missing for itemized 615931 | `anestezi_puani` | Yes: +928,09 TL |
| S4 | F 86, dementia + pyelonephritis | Yatış, İç Hast. (11–16 May, 5 nights) | Companion stayed (doctor's order) but 510121 not billed | `refakatci` | Yes: +370,50 TL |
| S5 | F 84, femoral neck fracture | Yatış, Ortopedi (3–8 Sep) | Femoral stem AP2070 billed without completed ÜTS notification | `material_bundling` rule 3.1.1.(2) | Yes: 12.630,99 TL at risk (no_pay) + MEDULA 0704 checklist item |
| S6 | M 79, Parkinson + aspiration pneumonia | Yatış, İç Hast. (8–14 Jun) | IV amantadine (PK-MERZ IV) billed; G20 not coded on the bill | §4.2 `drug_indication` (`indication_mismatch`) | Yes: error on the drug line (amount TBD) |
| S7 | F 58, pleuritic chest pain | Acil (19 Feb) | CT pulmonary angiography R101450 done (PACS log) but not on the bill | `procedure_capture_gap` | Yes: +1.138,22 TL |
| S8 | F 47, gallstones + umbilical hernia | Yatış, Genel Cerrahi (15–16 Sep) | Second package P603840 billed at 100 % instead of 25 % (same session, same incision) | §2.2.2.B(3) session rule → `drg_unbundling` → audit exposure | Yes: 5.377,20 TL at risk |

Why these eight (one line each):
- **S1** is the product's core §2.2 decision; private 2nd–3rd tier hospitals have no §2.2.2(2) choice, so the package is mandatory.
- **S2, S3, S4** are the three classic itemized "missing line" leaks (bed, anaesthesia, companion); all three are computed from dates and codes.
- **S5** is a real deduction cause since ÜTS usage notification became mandatory; it also produces the pre-submission MEDULA 0704 reminder.
- **S6** shows the §4.2 link between a drug and the coded diagnosis; it avoids the specialty dimension (#256).
- **S7** shows a second data source (PACS/EMR log) and the ER setting.
- **S8** is a classic SGK deduction (seans/kesi rule) with real money.

## Common setup

- **Facility.** One SGK-contracted private hospital. `facility_tier = 2_3_basamak_ozel`, `provider_type = Ozel` (accepted at `src/bilun/domain/prose_rules/facility_tier.py:26-30`). The engine maps it to basamak 2, so the §2.2.2(2) EK-2B/EK-2C choice never applies (`payment_method.py:126`). That matches SUT §2.2.2(2), which grants the choice only to EAH and university hospitals.
- **Prices.** EK-2B/EK-2C rows from `data/gazette/curated/ek2b_catalog_history.parquet` and `ek2c_catalog_history.parquet`, row in force on the line date. Dates in July–September use the 2026-07-07 list. Dates in February–June use the 2026-01-31 list; none of the codes used is among the 46 rows amended in-row on 16.04.2026.
- **Materials.** EK-3F-1 (Yür. 13.12.2025) as consolidated in the 2026-10-02 SUT (`data/gazette/curated/ek3f1_arthroplasty_materials.parquet`; raw `data/gazette/raw/annex=EK-3F-1/effective_date=2025-12-13/`). EK-3 prices are KDV hariç (SUT §3.1.1(10)); bills show the list price.
- **Drugs.** EK-4A products valid on the date (`ek4a_history.parquet`, rows from 2025-04-26). Price "TBD (Q4)". They enter the engine at 0 TL.
- **Billed amount** = SUT price × quantity, except S8's second package (25 %).
- **Extra fee (ilave ücret).** Not on any SGK bill. The hospital may collect it from the patient only with prior written consent (SUT §1.9.1(5)). None is allowed for S1 and S7 (ER-admitted emergency, §1.9.1(6)).
- **Exams on inpatient bills.** Ward visits are inside 510010 ("Yemek, yatak, hasta vizit hizmetlerini kapsar", EK-2B row 510010). The visit that led to admission sits on its own outpatient/ER takip, not on these bills. Consultations by other branches are billed (520010).
- **Bed-day count.** Clean bills bill one 510010 line per calendar day, admission and discharge day included, because the engine counts that way (`yatak_puani.py:123`). The companion rule counts nights (`refakatci.py:154`). See open question 1.
- **Specialty per line.** Each line carries an EK-2A branch code (Genel Cerrahi 1900, Anesteziyoloji 3100, …), as MEDULA lines carry the doctor's branch.

## Noise on clean bills (engine behaviour on correct bills)

The table counts what still shows on each **clean** bill. "Actions" are rows in `recommended_actions`; "header" means a summary number.

| Misfire | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | Defect |
|---|---|---|---|---|---|---|---|---|---|
| Bed days expected inside the EK-2C package window | 444,72 | – | – | – | 1.111,80 | – | – | 222,36 | N1 |
| Companion expected inside the package window | 148,20 | – | – | – | 370,50 | – | – | 74,10 | N1 |
| "Normal Poliklinik" compliance error on every inpatient package line (tablo15_4) | 1 | – | – | – | 1 | – | – | 2 | N2 |
| Session rule applied to anaesthesia/bed/lab/exam lines → audit exposure header | – | 1.258,57 | 621,76 | 425,46 | – | 422,73 | 222,67 | – | N3 |
| "Must not bill separately" on the hip prosthesis (EK-2C says "Protez ayrıca faturalandırılır") | – | – | – | – | 18.022,88 | – | – | – | N4 |
| Bone-cement clause on a "ÇİMENTOSUZ" stem (info) | – | – | – | – | 1 | – | – | – | N5 |
| LOS density anomaly (counts bed/companion/lab lines) | – | 1 | – | 1 | – | – | – | – | N6 |
| R-code principal diagnosis on an ER bill | – | – | – | – | – | – | 1 | – | N7 (Safa's call) |
| Same-session combined operation flagged as time overlap | – | – | – | – | – | – | – | 1 | N8 |
| Fatura İnceleme documentation reminders (advisory) | 3 | 2 | 2 | 2 | 4 | 2 | 0 | 3 | by design |

Also on every bill, at info level only: Wave A review rows (ORTAK-*, including "ORTAK-14.onkolojik_ek2b" on non-oncology bills) and transplant rules `2.4.2.A.*` in the validation core.

### New engine defects found (not in #226/#227/#255/#256)

| # | Defect | Evidence (file:line) | Effect |
|---|---|---|---|
| N1 | Bed and companion ignore the EK-2C package window. SUT §2.2.2.B-1(1)(a),(h) put "Yatak bedeli" and "Refakatçi bedeli" inside the package for A 15 / B 10 / C 8 / D 5 / E 3 days (§2.2.2.B-1(3)). The engine bundles only the surgery day and never gates the companion. | `yatak_puani.py:127-139`; `refakatci.py:136-226` | FP on every package stay. On an ICU-only claim the bed rule also expected 444,72 TL (side test) |
| N2 | `tablo15_4` reads `is_package_included` inverted: a correct package line (flag False, as in the data) is reported as "billed Normal Poliklinik". | `common_billing_errors.py:500-552` (check at :527) | Error-level compliance row on every inpatient package line |
| N3 | §2.2.2.A(5) session factors are applied to every line on the date (anaesthesia, bed, companion, labs, ER exam). On clean S3 the correct 550160 line itself is reported as over-billed by 417,64 TL (treated as a secondary procedure at 55 %). | `drg_unbundling.py:104-180`; `claim_audit_exposure.py:10-32` | Audit-exposure header on every itemized bill |
| N4 | `3.1.1.(15).separate_billing_not_authorized` looks for "ayrıca faturalandırılabilir" in the EK-3 row only; EK-3F-1 prostheses never qualify, although EK-2C P612320 and SUT §3.1.4(2)(ç) say they are billed separately. | `material_bundling.py:209-226` | 12.630,99 + 5.391,89 TL "must not bill separately" on a correct implant bill |
| N5 | Bone-cement keyword matches "ÇİMENTOSUZ". | rule `3.1.4.(b).bone_cement`, keyword match `material_bundling.py:135-142` | Info row |
| N6 | LOS density counts every line, so a normal 6-night stay with daily bed/companion lines and an admission panel exceeds 5 lines per night. | `temporal_anomaly.py:206-224` | Warning on medical stays |
| N7 | All R-codes are "never principal". WHO ICD-10 allows a symptom code as principal when no definitive diagnosis is found (S7: PE ruled out). | `diagnosis_coding_quality.py:164` | Needs your call |
| N8 | Time overlap flags two surgical lines on the same date and branch, which is exactly the legal same-session case. | `temporal_anomaly.py:104` | Warning on S8 |
| N9 | Session cross-specialty uses the EK-2C **İŞLEM GRUBU** (A1–E) as a "specialty" when the branch is empty, so P609235 (B) + P603840 (C) get +25 points (50 % instead of 25 %). | `session_specialty.py:58-61` | FP 896,20 TL on clean S8 without branch codes |
| N10 | Hemogram unbundling treats "Glike hemoglobin (Hb A1c)" as a CBC component (keyword "hemoglobin"). | `claim_lab.py:32`; `constants.py:228-244` | 26,34 TL compliance finding when CBC + HbA1c share a day (side test) |
| N11 | Anaesthesia bands switch at 2026-07-07, but the EK-2B rows carry "(Değişik: RG-08/04/2026-33218/9-a md. Yürürlük: 16/04/2026)". | `anestezi_puani.py:133`; raw `annex=EK-2B/effective_date=2026-01-31`, rows 124-137 | Side test: 615995 (5.113 puan) on 2026-05-10 billed C → engine expects B, false 397,76 TL. Same bill on 2026-07-20 is silent |
| N12 | Capture gap skips package lines when it builds "what was submitted". An OR log on a correct package bill turns the packaged operation into "performed, not submitted". | `procedure_capture_gap.py:45` | Side test: S8 +4.099,42 and +1.914,43; S5 +3.688,87; S1 +3.022,31 TL |
| N13 | Three §4.2.27.A PCC rules list "konakion", "k vitamini" as drug names; the clause (C006358–C006359) is about prothrombin complex concentrates. | `drug_indication_prose.json` lines 16079, 16210, 16455 (`4.2.27.anticoagulant_bleed_reversal_one_day`, `…coumarin_active_bleed_one_day`, `…pcc_acquired_coagulopathy_board`) | Vitamin K would be judged against PCC routes |

Smaller items:
- `capture_gap_try` is cast to int (1.138 instead of 1.138,22): `report_totals.py:56` with the default `scalar_default=0`.
- Anaesthesia, companion and ICU results have **no action rows** on the patient page (`billing_actions.py:319-358` lists the other uplift blocks only; no patient component renders them). S3 and S4 show only inside the header total. S8 shows only as the audit-exposure header; there is no row naming P603840.
- The companion rule has no eligibility input (doctor's order, age, documents). It fires on every non-ICU stay without 510121.
- Catalog `price_try` is puan × 0,593 rounded half-up. SUT §2.2(15) says two decimals "yuvarlama işlemi yapılmaksızın". 71 of 122 line-dates here are 1 kuruş high (e.g. 510010: 222,357 → catalog 222,36).

---

## S1 — Package billed as itemized (laparoscopic appendectomy)

**Patient.** Male, 34 (born 1992). No chronic disease. Right lower quadrant pain for 18 hours.
**Diagnosis.** K35.8 Acute appendicitis, other and unspecified (primary).
**Episode.** ER (separate acil takip: exam, labs, ultrasound) → admitted to Genel Cerrahi 14.07.2026 evening → laparoscopic appendectomy the same night → discharged 16.07.2026 (2 nights). EK-2C group C: 8-day package window.

**Correct bill (clean).** One package line. Bed, anaesthesia, labs, pathology, drugs and companion are inside it (SUT §2.2.2.B-1(1)).

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source |
|---|---|---|---|---|---|---|
| 07-14 | P610131 | Appendektomi, laparoskopik | 1 | 8.636,51 | 8.636,51 | EK-2C from 2026-07-07 (group C, *) |

Total 8.636,51 TL.

**Fault.** The stay was billed hizmet başı, as if no package existed:

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source |
|---|---|---|---|---|---|---|
| 07-14 | 610131 | Appendektomi, laparoskopik | 1 | 3.022,31 | 3.022,31 | EK-2B from 2026-07-07 |
| 07-14 | 550170 | Anestezi C grubu | 1 | 530,33 | 530,33 | EK-2B from 2026-07-07 (5.096,64 puan → C, 3005–6000) |
| 07-14, 07-15, 07-16 | 510010 | Standart yatak tarifesi | 3 | 222,36 | 667,08 | EK-2B from 2026-07-07 |
| 07-14, 07-15 | L107020 | Tam Kan Sayımı (Hemogram) | 2 | 19,73 | 39,46 | EK-2B from 2026-07-07 |
| 07-14, 07-15 | L101850 | C reaktif protein (CRP) | 2 | 16,46 | 32,92 | EK-2B from 2026-07-07 |
| 07-15 | 910230 | Apendiks, insidental dışında | 1 | 258,54 | 258,54 | EK-2B from 2026-07-07 |
| 07-14 | 8699508270224 | IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU (seftriakson) | 3 | TBD | TBD | EK-4A A03721 |
| 07-14 | 8697637691743 | NEOFLEKS %0,5 METRONIDAZOL I.V. ENJ COZ 100 ML (SETLI) | 6 | TBD | TBD | EK-4A A15078 |
| 07-14 | 8699606694649 | PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK (parasetamol) | 1 | TBD | TBD | EK-4A A14359 |

Total 4.550,64 TL + drugs. The hospital under-bills by about 4.086 TL minus the drug amounts (the package covers the drugs).

**SUT.** §2.2.2(1) (C000646): "İkinci ve üçüncü basamak sağlık hizmeti sunucularında yatarak verilen sağlık hizmetlerinin bedelleri, SUT eki EK-2/C Listesinde yer alıyorsa "tanıya dayalı işlem üzerinden ödeme" yöntemi ile … faturalandırılır."

**Engine rule.** `check_payment_method_compliance` and `recommend_billing_strategy_from_claims` (`claim_strategy.py:534-796`). Expected: a compliance violation on 610131 and a claim-level "package mandated" row.

**Proof (actual output).**
- Clean: `check_payment_method_compliance('610131', billed_as_package=True)` → `DRG_MANDATORY, compliant`. Strategy: "Claim C-SH01 is billed correctly as package per SUT §2.2.2(1). Package total 8636.51 TRY." No violation.
- Faulty: `compliance_violation` on 610131: "Procedure 610131 must use package billing (tanıya dayalı işlem üzerinden ödeme) per 2.2.2.(1)." Claim row: "SUT §2.2 mandates package billing … Package total 8636.51 TRY vs itemized 1231.00 TRY", `savings_try 0.0`. Audit exposure 3.558,29 TL (3.022,31 = the 610131 line + 535,98 session noise N3).
- **Defect in the amount.** The "itemized 1231.00" leaves out the operation line itself (non-compliant lines are dropped, `claim_strategy.py:293-325`), and savings are floored at 0 when the package is higher (`:383-403`). So the engine detects the error but does not show the ~4.086 TL the hospital loses.

**Noise on the clean bill.** N1 (444,72 + 148,20 TL), N2, 3 documentation reminders.

**Open questions.** Would MEDULA even accept EK-2B 610131 on a private hospital's inpatient takip, or reject it at entry? Is "ER → OR, takip left as hizmet başı" the realistic way this happens?

---

## S2 — Bed days under-billed (COPD exacerbation with pneumonia)

**Patient.** Male, 81 (born 1945). COPD (ex-smoker), hypertension.
**Diagnoses.** J44.0 COPD with acute lower respiratory infection (primary); J18.9 Pneumonia, unspecified; I10.
**Episode.** Admitted from the outpatient clinic to Göğüs Hastalıkları 09.03.2026; discharged 15.03.2026 (6 nights). Companion stayed with a doctor's order (age, oxygen need).

**Clean bill** (total 4.149,89 TL + drugs; all rows EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 03-09…03-15, daily | 510010 | Standart yatak tarifesi | 7 | 222,36 | 1.556,52 |
| 03-09…03-14, daily | 510121 | Refakat | 6 | 74,10 | 444,60 |
| 03-09, 03-12 | L107020 | Tam Kan Sayımı (Hemogram) | 2 | 19,73 | 39,46 |
| 03-09, 03-12 | L101850 | C reaktif protein (CRP) | 2 | 16,46 | 32,92 |
| 03-09 | L102890 / L104780 / L107420 / L106910 / L106150 / L100300 / L101280 | Glukoz, Kreatinin, Üre, Sodyum, Potasyum (Serum/Plazma); ALT; AST | 1 each | 6,57–7,20 | 49,14 |
| 03-09, 03-12 | L103900 | Kan gazları | 2 | 33,57 | 67,14 |
| 03-09 | L106240 | Prokalsitonin (Serum/Plazma) | 1 | 167,91 | 167,91 |
| 03-09 | 906020 | Kan kültürü (Aerob-anaerob) otomatik sistem | 1 | 65,82 | 65,82 |
| 03-09 | 905675 | Balgam Kültürü | 1 | 16,46 | 16,46 |
| 03-09, 03-13 | 801720 | Akciğer grafisi P.A. (Tek yön) | 2 | 44,75 | 89,50 |
| 03-09 (3/day × 6 days) | 530350 | Nebülizatör ile ilaç uygulaması | 18 | 66,29 | 1.193,22 |
| 03-09 (first 48 h) | 530360 | Oksijen inhalasyon tedavisi, saatlik | 48 | 8,90 | 427,20 |
| 03-09 | 8699508270224 | IESEF 1 G IV (seftriakson) | 7 | TBD | TBD (EK-4A A03721) |
| 03-09 | 8680741521174 | IPRAVENT 0.5MG/2.5ML + 2.5MG/2.5ML NEBULIZAYON … (20 FLAKON) (ipratropium + salbutamol) | 1 | TBD | TBD (EK-4A A17700) |

Nebulizer and oxygen are one line each here for brevity; the generator should date them per day.

**Fault.** The bed charge stopped after 12.03 (ward transfer): 4 lines of 510010 instead of 7. Billed 889,44 TL instead of 1.556,52.

**SUT.** §2.2.2.A(1) (C000652): "Hizmet başına ödeme yönteminde sağlık hizmeti bedelleri, SUT eki EK-2/B ve EK-2/Ç Listesi esas alınarak faturalandırılır." The day count is not in the SUT text (open question 1).

**Engine rule.** `detect_yatak_puani_opportunities` (`yatak_puani.py:69-194`).

**Proof.**
- Clean: 7 billable bed days, expected 1.556,52, billed 1.556,52, recoverable 0,00.
- Faulty: "Standart yatak (510010): 7 billable bed-day(s) (gross LOS 7 day(s) at 222.36 TRY/day) = 1556.52 TRY", billed 889,44, **recoverable 667,08 TL**. Shown as a `yatak_puani` action.

**Noise on the clean bill.** Audit exposure 1.258,57 TL (N3); LOS density warning (N6; 33 lines over 6 nights); 2 documentation reminders.

**Open question.** If SGK counts nights (6), the correct bill has 6 bed days, the fault is 2 days (444,72 TL), and the engine over-states every stay by one day.

---

## S3 — Anaesthesia missing on an itemized operation (lumbar decompression)

**Patient.** Female, 77 (born 1949). Hypertension, controlled. ASA 2 (so the standard group applies; the "75 yaş üstü ve ASA 3-4" geriatric codes 550270–550346 do not).
**Diagnoses.** M48.0 Spinal stenosis (lumbar, neurogenic claudication) (primary); I10.
**Episode.** Elective. Pre-op exam and labs on an earlier outpatient takip. Admitted to Beyin ve Sinir Cerrahisi 18.08.2026, unilateral decompression the same day under general anaesthesia, discharged 20.08.2026 (2 nights). Companion with a doctor's order (post-op fall risk).
**Why itemized.** 615931 has no EK-2C package (no P615931 in the 2026-07-07 EK-2C list), so the stay is hizmet başı with a separate anaesthesia line.

**Clean bill** (total 5.607,62 TL + drugs; EK-2B from 2026-07-07):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 08-18 | 615931 | Dar spinal kanalda unilateral dekompresyon (6.471,03 puan) | 1 | 3.837,32 | 3.837,32 |
| 08-18 | 550160 | Anestezi B grubu (1.565,07 puan) | 1 | 928,09 | 928,09 |
| 08-18, 08-19, 08-20 | 510010 | Standart yatak tarifesi | 3 | 222,36 | 667,08 |
| 08-18, 08-19 | 510121 | Refakat | 2 | 74,10 | 148,20 |
| 08-19 | L107020 | Tam Kan Sayımı (Hemogram) | 1 | 19,73 | 19,73 |
| 08-19 | L104780 | Kreatinin (Serum/Plazma) | 1 | 7,20 | 7,20 |
| 08-18 | 8699606694649 | PARACEROL 10 MG/ML IV INF … (parasetamol) | 1 | TBD | TBD (EK-4A A14359) |

Group check: 6.471,03 puan is B under both band tables (B 6001–9000 since 16.04.2026; 5001–7583 before). The date is after 07.07, so N11 does not touch it.

**Fault.** The anaesthesia record never reached billing: 550160 is missing.

**SUT and annex.** §2.2.2.A(1) (C000652, quoted in S2) plus EK-2B section 4 row "B grubu 6001-9000" (raw 2026-07-07 EK-2B, row 127) and code 550160 "Anestezi B grubu".

**Engine rule.** `detect_anestezi_puani_opportunities` (`anestezi_puani.py:212-335`).

**Proof.**
- Clean: group B, 550160, expected 928,09, billed 928,09, recoverable 0,00.
- Faulty: "Anestezi B grubu (550160): surgical procedure 615931 (puan 6471.03) → anestezi puan 1565.07 × katsayı 0.593 = 928.09 TRY", **recoverable 928,09 TL**. Counted in the header SGK total; no action row (see smaller items).

**Noise on the clean bill.** Audit exposure 621,76 TL (N3): 550160 417,64 + bed 100,06 + companion 85,21 + labs 18,85, all treated as secondary procedures of 615931. 2 documentation reminders.

---

## S4 — Companion bed not billed (dementia, pyelonephritis)

**Patient.** Female, 86 (born 1940). Alzheimer's disease, hypertension.
**Diagnoses.** N10 Acute tubulo-interstitial nephritis (pyelonephritis) (primary); F05.1 Delirium superimposed on dementia; G30.1 Alzheimer's disease with late onset; I10.
**Episode.** Admitted to İç Hastalıkları 11.05.2026, discharged 16.05.2026 (5 nights). Her daughter stayed every night; the ward doctor ordered a companion (delirium, fall risk) and the refakatçi belgesi is on file.

**Clean bill** (total 1.941,97 TL + drugs; EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 05-11…05-16, daily | 510010 | Standart yatak tarifesi | 6 | 222,36 | 1.334,16 |
| 05-11…05-15, daily | 510121 | Refakat | 5 | 74,10 | 370,50 |
| 05-11, 05-13 | L107020 | Tam Kan Sayımı (Hemogram) | 2 | 19,73 | 39,46 |
| 05-11, 05-13 | L101850 | C reaktif protein (CRP) | 2 | 16,46 | 32,92 |
| 05-11, 05-13 | L104780 | Kreatinin (Serum/Plazma) | 2 | 7,20 | 14,40 |
| 05-11 | L102890 / L107420 / L106910 / L106150 / L100300 / L101280 | Glukoz, Üre, Sodyum, Potasyum, ALT, AST | 1 each | 6,57–7,20 | 41,94 |
| 05-11 | L107010 | Tam idrar analizi (Strip+Mikroskopi) | 1 | 26,31 | 26,31 |
| 05-11 | 905671 | İdrar Kültürü | 1 | 16,46 | 16,46 |
| 05-11 | 906020 | Kan kültürü (Aerob-anaerob) otomatik sistem | 1 | 65,82 | 65,82 |
| 05-11 | 8699508270224 | IESEF 1 G IV (seftriakson) | 5 | TBD | TBD (EK-4A A03721) |
| 05-11 | 8699606694649 | PARACEROL 10 MG/ML IV INF … (parasetamol) | 1 | TBD | TBD (EK-4A A14359) |

**Fault.** The five 510121 lines were never entered.

**SUT.** §2.6.3(2) (C001628): "Kişilerin yatarak tedavileri sırasında hekimin veya diş hekiminin tıbben göreceği lüzum üzerine; … refakatçisinin yatak ve yemek giderleri, … SUT eki EK-2/B Listesinde yer alan "refakat" puanı esas alınarak karşılanır …". Billing route: §2.2.2.A(3) (C000654).

**Engine rule.** `detect_refakatci_opportunities` (`refakatci.py:101-259`).

**Proof.**
- Clean: 5 companion days, expected 370,50, billed 370,50, recoverable 0,00.
- Faulty: "Refakat (510121): 5 companion day(s) at 124.95 puan × 0.593 katsayı = 74.10 TRY/day → 370.50 TRY", **recoverable 370,50 TL**. Header total only; no action row.

**Caveat.** The rule cannot tell an eligible patient from an ineligible one. It would fire the same way for a 40-year-old without a companion. The story is honest; the rule's precision is not.

**Noise on the clean bill.** Audit exposure 425,46 TL (N3); LOS density warning (N6); 2 documentation reminders.

---

## S5 — Implant billed without ÜTS notification (hip hemiarthroplasty)

**Patient.** Female, 84 (born 1942). Hypertension, postmenopausal osteoporosis. Fell at home.
**Diagnoses.** S72.0 Fracture of neck of femur (primary); I10; M81.0 Postmenopausal osteoporosis.
**Episode.** ER → admitted to Ortopedi ve Travmatoloji 03.09.2026; bipolar hemiarthroplasty 04.09.2026; discharged 08.09.2026 (5 nights). EK-2C group B: 10-day window, so bed, labs, drugs and companion are inside the package.

**Clean bill** (total 36.413,68 TL):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source |
|---|---|---|---|---|---|---|
| 09-04 | P612320 | Büyük eklem parsiyel protezleri, primer | 1 | 18.390,80 | 18.390,80 | EK-2C from 2026-07-07 (group B); açıklama "Protez ayrıca faturalandırılır." |
| 09-04 | AP2070 | KALÇA / PRİMER / FEMORAL STEM / ÇİMENTOSUZ / CoCr/TİTANYUM / KAPLAMALI - KUMLAMA | 1 | 12.630,99 | 12.630,99 | EK-3F-1 list price 12.630,993375 |
| 09-04 | AP1880 | KALÇA / PRİMER / FEMORAL BIPOLAR BAŞ (SHELL + İNSERT) / TÜM BOYLAR / CoCr | 1 | 5.391,89 | 5.391,89 | EK-3F-1 list price 5.391,8865; row amended 24.01.2026 (material wording) |

Both implants are allowed for a fracture: EK-3F-1 Genel Hükümler (2) and (17) bar revision stems and tumour prostheses for proximal femur fractures, (11) limits calcar stems to trochanteric fractures, (15) accepts a bipolar head as one barcode. KDV is added at payment (SUT §3.1.1(10)).

**Fault.** The hospital never completed the ÜTS usage notification for the stem (`uts_registered = False` on the AP2070 line). Everything else is identical.

**SUT.** §3.1.1(2) (C002740): "TİTUBB/ÜTS kayıt/bildirim işlemi tamamlanmamış tıbbi malzemelerin bedelleri Kurumca karşılanmaz."

**Engine rule.** `check_material_bundling_for_context` → rule `3.1.1.(2).titubb_uts_incomplete` (`material_bundling.py:202-207`). Also the readiness checklist.

**Proof.**
- Clean: the rule is silent.
- Faulty: `3.1.1.(2).titubb_uts_incomplete`, severity error, AP2070, `risk_amount 12630.99`, outcome `no_pay`, message "TİTUBB/ÜTS kayıt-bildirim tamamlanmamış — Kurumca karşılanmaz (§3.1.1(2))." Plus checklist item `claim_readiness.material_uts_barcode_missing`: "Malzeme satırında ÜTS/TİTUBB barkod kaydı eksik — MEDULA 0704 red riski."

**Noise on the clean bill — serious for this story.** N4 puts "must not bill separately" warnings on both implants (12.630,99 and 5.391,89 TL), so the clean bill already shows an 18.022,88 TL material warning; the fault only changes the stem's message. Also N1 (1.111,80 + 370,50), N2, N5, 4 documentation reminders. Fix N4 before demoing S5.

**Open questions.** Cemented stem plus bone cement is the usual choice at 84; no bone-cement code was found in the curated EK-3 lists, so the story uses a cementless stem. Which code does the hospital bill for cement?

---

## S6 — Drug billed without its indication diagnosis (IV amantadine)

**Patient.** Male, 79 (born 1947). Advanced Parkinson's disease, hypertension.
**Diagnoses (clean).** J69.0 Pneumonitis due to food and vomit (primary); R13 Dysphagia; G20 Parkinson's disease; I10.
**Episode.** Admitted to İç Hastalıkları 08.06.2026 with aspiration pneumonia, nil by mouth; neurology consultation the same day; PK-MERZ IV started 09.06 for 3 days (one 500 ml bottle a day) while oral levodopa was impossible. The neurologist's specialist report (uzman hekim raporu) for amantadine is on file. Discharged 14.06.2026 (6 nights). Companion with a doctor's order.

**Clean bill** (total 2.311,13 TL + drugs; EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 06-08…06-14, daily | 510010 | Standart yatak tarifesi | 7 | 222,36 | 1.556,52 |
| 06-08…06-13, daily | 510121 | Refakat | 6 | 74,10 | 444,60 |
| 06-08 | 520010 | Konsültasyon (Her bir branş için) — Nöroloji | 1 | 33,17 | 33,17 |
| 06-08, 06-11 | L107020 | Tam Kan Sayımı (Hemogram) | 2 | 19,73 | 39,46 |
| 06-08, 06-11 | L101850 | C reaktif protein (CRP) | 2 | 16,46 | 32,92 |
| 06-08 | L102890 / L104780 / L107420 / L106910 / L106150 / L100300 / L101280 | Glukoz, Kreatinin, Üre, Sodyum, Potasyum, ALT, AST | 1 each | 6,57–7,20 | 49,14 |
| 06-08 | 906020 | Kan kültürü (Aerob-anaerob) otomatik sistem | 1 | 65,82 | 65,82 |
| 06-08, 06-12 | 801720 | Akciğer grafisi P.A. (Tek yön) | 2 | 44,75 | 89,50 |
| 06-08 | 8699508270224 | IESEF 1 G IV (seftriakson) | 7 | TBD | TBD (EK-4A A03721) |
| 06-08 | 8697637691743 | NEOFLEKS %0,5 METRONIDAZOL I.V. ENJ COZ 100 ML (SETLI) | 21 | TBD | TBD (EK-4A A15078) |
| 06-09 | 8699708690525 | PK-MERZ IV INF. COZ. 2x500 ML (amantadin sülfat) | 2 boxes | TBD | TBD (EK-4A A12140) |

**Fault.** The coder entered only the admission problems (J69.0, R13, I10). G20 is missing from the bill.

**SUT.** §4.2.36(3) (C006824): "Amantadin sülfat; parkinson hastalığının tedavisi ile ilaçlara bağlı oluşmuş ekstrapiramidal reaksiyonların tedavisinde …, nöroloji veya geriatri uzmanı tarafından veya bu uzman hekimlerin düzenlediği uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilir."

**Engine rule.** `evaluate_drug_indication_line_detailed` (route `4.2.36.amantadine_sulfate_report`, ICD G20/G21/G24/G25); finding via `evaluate_drug_indication_findings`. The drug matches by name ("pk-merz"), so no INN crosswalk is needed. No prescriber-specialty check in this route, so #256 does not apply.

**Proof.**
- Clean: `applicability_status eligible`, route `4.2.36.amantadine_sulfate_report`, no violation.
- Faulty: `indication_mismatch`, severity error: "Faturada I10, J69.0, R13 tanıları bulundu. PK-MERZ IV INF. COZ. 2x500 ML için kodlanmış SGK geri ödeme yolları G20, G21, G24, G25 tanılarını kapsıyor. Mevcut tanılar bu yollarla eşleşmiyor." Shown as a `drug_indication` action. TL at risk = the drug line (TBD, Q4).
- Alternative fault, also proven: report flag False → `missing_board_report` (error).

**Noise on the clean bill.** Audit exposure 422,73 TL (N3); 2 documentation reminders.

**Open questions.** How is a partial box billed on an inpatient invoice (3 bottles = 1,5 boxes of "2x500 ML")? The story bills 2 boxes.

---

## S7 — ER: CT angiography done but not billed

**Patient.** Female, 58 (born 1968). No chronic disease. Pleuritic chest pain and dyspnoea three days after a long-haul flight.
**Diagnoses.** R07.1 Chest pain on breathing (primary); R06.0 Dyspnoea. Pulmonary embolism ruled out.
**Episode.** ER only, 19.02.2026, no admission (no stay): exam, ECG, IV line, labs (troponin at 0 and 3 h, quantitative D-dimer raised), chest X-ray, CT pulmonary angiography (normal). Discharged home. ER services at 2nd–3rd tier providers are billed hizmet başı.

**Clean bill** (total 1.633,02 TL + drugs; EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 02-19 | 520020 | Acil poliklinik muayenesi | 1 | 85,73 | 85,73 |
| 02-19 | 530100 | Elektrokardiyogram | 1 | 16,66 | 16,66 |
| 02-19 | 530080 | Damar yolu açılması | 1 | 35,74 | 35,74 |
| 02-19 | L107020 | Tam Kan Sayımı (Hemogram) | 1 | 19,73 | 19,73 |
| 02-19 | L107360 | Troponin I (0 h and 3 h) | 2 | 59,26 | 118,52 |
| 02-19 | L102090 | D-dimer (Kantitatif) | 1 | 145,50 | 145,50 |
| 02-19 | L104780 / L102890 / L106910 / L106150 | Kreatinin, Glukoz, Sodyum, Potasyum | 1 each | 6,57–7,20 | 28,17 |
| 02-19 | 801720 | Akciğer grafisi P.A. (Tek yön) | 1 | 44,75 | 44,75 |
| 02-19 | R101450 | BT anjiografi, pulmoner arter | 1 | 1.138,22 | 1.138,22 |
| 02-19 | 8699688771559 | OMNIPAQUE 350 MGL/ML 100 ML FLK (iohexol, contrast) | 1 | TBD | TBD (EK-4A A05705) |
| 02-19 | 8699606694649 | PARACEROL 10 MG/ML IV INF … (parasetamol) | 1 | TBD | TBD (EK-4A A14359) |

EMR/PACS log attached to the bill: 530100, 530080, 801720 (EMR) and R101450 (PACS), all 19.02.

**Fault.** The CT line never reached the invoice (RIS → HBYS transfer). The PACS log still shows it.

**SUT.** §2.2.1.B-2(2) (C000604/C000607/C000617): "İkinci ve üçüncü basamak … sağlık hizmeti sunucularında; a) Acil sağlık hizmetleri, … "hizmet başına ödeme yöntemi" ile faturalandırılır."

**Engine rule.** `detect_procedure_capture_gaps` (`procedure_capture_gap.py:66-133`); report block `procedure_capture_gap`.

**Proof.**
- Clean: silent (every logged code is billed).
- Faulty: `performed_not_submitted`, R101450 "BT anjiografi, pulmoner arter", source `pacs`, list price 1.138,22, **recoverable 1.138,22 TL**, "EMR log shows R101450 performed on 2026-02-19 (pacs) but claim submission has 0.00 TRY billed." Shown as an action; the header shows 1.138 (int cast).

**Noise on the clean bill.** Audit exposure 222,67 TL (N3); `never_principal_diagnosis_blocklist` on R07.1 (N7).

**Open question.** Should an ER bill with PE ruled out carry R07.1 as principal (WHO rule), or does MoH guidance want something else?

---

## S8 — Second operation in the same session billed at full points

**Patient.** Female, 47 (born 1979). Symptomatic gallstones; small umbilical hernia found at the pre-op exam.
**Diagnoses.** K80.2 Calculus of gallbladder without cholecystitis (primary); K42.9 Umbilical hernia without obstruction or gangrene.
**Episode.** Elective. Admitted to Genel Cerrahi 15.09.2026; laparoscopic cholecystectomy and primary repair of the hernia through the umbilical port (same session, same incision); discharged 16.09.2026 (1 night). EK-2C groups B and C: 10- and 8-day windows.

**Clean bill** (total 13.858,13 TL):

| Date | Code | Name (catalog) | Qty | Unit TL (list) | Billed TL | Source |
|---|---|---|---|---|---|---|
| 09-15 | P609235 | Kolesistektomi, laparoskopik | 1 | 12.065,73 | 12.065,73 (100 %) | EK-2C from 2026-07-07 (group B, *) |
| 09-15 | P603840 | Greftsiz umblikal herni onarımı | 1 | 7.169,60 | 1.792,40 (25 %) | EK-2C from 2026-07-07 (group C, *) |

The unit price stays the list price; the billed amount carries the reduction (open question 4).

**Fault.** P603840 billed at 7.169,60 TL (100 %).

**SUT.** §2.2.2.B(3)(a) (C000670): "Aynı seansta aynı kesi ile birden fazla işlem yapılması halinde; işlem puanı yüksek olan tanıya dayalı işlemin puanı tam olarak, diğer işlemler ise kendi tanıya dayalı işlem puanının %25'i alınarak," (… faturalandırılır, C000674).

**Engine rule.** `analyze_claim_unbundling(...).session_violations` (`drg_unbundling.py:104-180`) → `audit_exposure_try`.

**Proof.**
- Clean: no session violation; audit exposure 0.
- Faulty: rule `2.2.2.B.a`, P603840, primary P609235, factor 0.25, expected 1.792,40, billed 7.169,60, **risk 5.377,20 TL**: "Secondary procedure billed at full rate; SUT §2.2.2.B.a requires 25% point factor in same session." Shown only as the audit-exposure header.
- Without branch codes on the lines the clean bill is flagged too (N9: factor 0.50, 896,20 TL). The story sets branch 1900 on both lines.

**Noise on the clean bill.** N1 (222,36 + 74,10), N2 (both lines), N8, 3 documentation reminders.

**Open questions.** Is the umbilical-port repair "aynı kesi" (25 %) or a separate incision (50 %)? Does the hospital send the reduced amount, or does MEDULA apply §2.2.2.B(3) itself?

---

## Candidates considered and replaced

- **MEDULA rejection playbook (e.g. ÜTS 0704).** Not used as a story. It maps a rejection the hospital already received to a template; it does not detect anything on the bill. The playbook's codes have no documented source (the audit marked them "not checked"). S5 covers the same ground before submission and emits the "MEDULA 0704 red riski" checklist item.
- **Material inside the EK-2C package billed separately.** The code-based check misfires on correct implants (N4). The other variant reads an input flag (`diagnosis_package_material_unbundled`), so it would not be a real detection.
- **Session uplift (under-billing).** The engine cannot know same vs separate incision (no field), so it cannot detect a second operation billed at 30 % instead of 50 %. Replaced by the over-billing case (S8).
- **Drug needing a report.** Proven as S6's alternative fault; the diagnosis variant was kept because it is computed from codes, not from a flag.
- **IVIG, albumin, etelcalcetide, infliximab, Konakion.** IVIG routes to a clinical-constraint path with the same "review" result on clean and faulty bills. Albumin's SUT condition is the lab value (≤ 2,5 g/dl, §4.2.27.Ç(1)), which the engine cannot read. Etelcalcetide is a reçete drug (§4.2.9.E(3)); infliximab day-case use is, in my judgment, also pharmacy-supplied and its AS routes carry the "fiziksel tıp ve rehabilitasyon" specialty (#256). Konakion is mis-encoded (N13). Most hospital IV drugs (seftriakson, metronidazol …) are not in the encoded corpus or not matchable by name (brand names lack the INN).
- **ICU (tiering, bundled ventilation, transfer-day bed).** Left out. #255 is open; the engine models ICU as its own claim; a side test of a clean ICU claim produced N1 and N2 noise. The bundled-service rule (oxygen/nebulizer billed on a 510090 day) did fire correctly in that side test.
- **Outpatient lab capture gap.** Dropped. Outpatient visits at private 2nd–3rd tier hospitals are paid per visit from EK-2/A by hospital class (SUT §2.2.1.B-1(1)); only EK-2/A-2 items are billed on top. The repo has no curated current EK-2/A-2 list (the raw snapshots are 2020, 2021 and an undated MÜLGA file), and the engine does not read EK-2/A, so I could not build a correct outpatient bill.
- **Laterality (sağ/sol).** Its code prefixes are stale: "80102" now hits 801020 Hepatobiliyer Sintigrafi, "80319" hits 803190 Perkütan ablasyon tedavisi, and cataract is 617341, not 516xxx.

## Open questions for Safa

1. **Bed-day count.** Does SGK pay 510010 for nights (6 for a 9→15 stay) or calendar days including discharge (7)? The bed rule counts days; the companion rule counts nights. No SUT sentence settles it.
2. **Package window.** Do you read §2.2.2.B-1(1),(3) the same way: bed and companion inside the package for the whole A/B/C/D/E window? If yes, N1 is a real defect on every package bill.
3. **S1 realism.** Would MEDULA accept EK-2B 610131 on a private hospital's inpatient takip?
4. **Session reductions.** Does the hospital send the reduced amount for the second package, or does MEDULA compute it?
5. **S8 incision.** Umbilical-port hernia repair: same incision (25 %) or separate (50 %)?
6. **Implants.** Cemented stem + cement is usual at 84; which bone-cement code? Is KDV sent on MEDULA material lines, and at 10 % or 20 % (the engine uses 20 %)?
7. **Partial drug boxes** on inpatient invoices (S6).
8. **R-codes as principal** on ER bills (S7, N7).
9. **Companion.** Is a doctor's order enough to bill 510121 for elderly inpatients (S2, S3, S6 rely on it)? Should the engine get an eligibility input before the demo?
10. **Rounding.** SUT §2.2(15) says no rounding; the catalog rounds half-up (1 kuruş per line). Which does MEDULA use?
11. **ICU.** Is an ICU stay its own takip in MEDULA (the engine assumes so)?
12. **ICD-10.** Codes are WHO 4-character codes from memory (K35.8, M48.0, S72.0 …). Confirm against the Q5 list, including whether MEDULA wants 5th characters (M48.06, S72.00).
13. **Which noise to fix first.** My order: N1, N2, N3, N4 (they hit S1, S5, S8 and every itemized bill), then N12 before any OR log is attached, then the surfacing gap for anaesthesia/companion/session rows.

## Reproduction

Scratch folder: `/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/showcase_stories/`.
- `harness.py`: builds `ClaimHeader`/`ProcedureClaimLine`/`MaterialClaimLine`/`DrugClaimLine` as the unit tests do, prices each line from the catalog row in force (fails if not exactly one row), enriches materials with the loader's `_enrich_material_regulatory_flags`, runs `compute_patient_billing_report` and `analyze_claim`.
- `stories.py`: the eight stories, clean and faulty.
- `prove.py`: calls each target detector directly, then diffs the full outputs. Output: `results/S1.json` … `results/S8.json`, `results/prove_output.txt`.
- `checks.py`, `exp_emr_pkg.py`, `exp_icu.py`, `exp_drug.py`, `exp_session2.py`: side tests behind N3, N9–N12 and the replaced candidates.
- Run: `cd <scratch> && /home/safa/Documents/Bilun/.venv/bin/python prove.py` (about 15 s).
- Run context: branch `claude/synthetic-v3-p0-p1`. During the run another session committed 0a205223 (reference data, scripts, tests, reports only; no file under `src/` changed), so the engine code tested equals main at 1c22ee9c.
