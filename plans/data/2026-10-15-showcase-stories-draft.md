# Showcase stories — draft for Safa's review

Date: 2026-10-15; corrected 2026-10-16 after the review on Safa's behalf ([review report][review]). Status: **reviewed; corrections applied; the field questions stay open.** The proof scripts and their outputs are in `reports/synthetic-data/2026-10-15-showcase-proofs/`.
Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D1–D6, Q1–Q6 answered).

## In short

- Eight stories, eight different engine rules. Each story is one patient and one bill.
- Each bill was built twice: clean, and with exactly one injected fault.
- **All 8 proven on 2026-10-16** (engine = `main` 257d1e89, `src/` unchanged): the target rule fires on the faulty bill, and **every clean bill carries 0 TL**.
- **The noise of the first run is fixed.** The 2026-10-15 run found 13 misfires on correct bills (N1–N13). PRs #272–#278, #283–#285 and #288 closed all of them except N7, which the review calls a defect. N7 shows only on S7, as a 0 TL error row.
- **Corrected after the review.**
  - Clinical: one pre-op antibiotic dose in S1; steroid, macrolide, thromboprophylaxis and fluids where the guidelines expect them; a cemented stem with bone cement at 84.
  - Billing: the EK-2B açıklama limits on S2 (nebulizer once a day, oxygen at most 16 h a day, no Na/K beside the blood gas); no separate contrast line next to R101450 on S7.
  - Codes: SKRS leaf ICD-10 codes. S5's cement needed a catalog fix on this branch (EK-3/F-1 bone cements, see S5).
- Codes, names and prices come from the curated catalogs in force on each line date. The harness fails if not exactly one row matches. ICD-10 codes are SKRS leaf codes (`data/synthetic/reference/icd10_tr.parquet`, `is_leaf`). Drug prices are "TBD (Q4)".

## Summary table

| Story | Patient | Setting (dates 2026) | Injected fault | Engine rule | Proven? |
|---|---|---|---|---|---|
| S1 | M 34, acute appendicitis | Yatış, Genel Cerrahi (14–16 Jul) | The coder keyed EK-2B 610131, so the stay went out hizmet başı (610131 + anaesthesia + beds + labs + pathology + drugs) instead of the mandatory EK-2C package P610131 | §2.2 payment method → `billing_strategy` (`claim_strategy.py`, `payment_method.py`) | Yes: "must use package billing per 2.2.2.(1)" and a package gap of 4.122,06 TL |
| S2 | M 81, COPD + pneumonia | Yatış, Göğüs Hast. (9–15 Mar, 6 nights) | Only 4 of 7 bed days (510010) billed | `yatak_puani` | Yes: +667,08 TL |
| S3 | F 77, lumbar spinal stenosis | Yatış, Beyin Cerrahisi (18–20 Aug) | Anaesthesia line 550160 (B grubu) missing for itemized 615931 | `anestezi_puani` | Yes: +928,09 TL |
| S4 | F 86, dementia + pyelonephritis | Yatış, İç Hast. (11–16 May, 5 nights) | Companion stayed (doctor's order, refakatçi belgesi) but 510121 not billed | `refakatci` | Yes: +370,50 TL |
| S5 | F 84, femoral neck fracture | Yatış, Ortopedi (3–8 Sep) | Cemented femoral stem AP2000 billed without completed ÜTS notification | `material_bundling` rule 3.1.1.(2) | Yes: 6.465,27 TL at risk (no_pay) + MEDULA 0704 checklist item |
| S6 | M 79, Parkinson + aspiration pneumonia | Yatış, İç Hast. (8–14 Jun) | IV amantadine (PK-MERZ IV) billed; G20 not coded on the bill | §4.2 `drug_indication` (`indication_mismatch`) | Yes: error on the drug line (amount TBD) |
| S7 | F 58, pleuritic chest pain | Acil (19 Feb) | CT pulmonary angiography R101450 done (PACS log) but not on the bill | `procedure_capture_gap` | Yes: +1.138,22 TL |
| S8 | F 47, gallstones + umbilical hernia | Yatış, Genel Cerrahi (15–16 Sep) | Second package P603840 billed at 100 % instead of 25 % (same session, same incision) | §2.2.2.B(3) session rule → `drg_unbundling` → audit exposure | Yes: 5.377,20 TL at risk with the incision known; the report header shows 3.584,80 TL (see S8) |

Why these eight (one line each):
- **S1** is the product's core §2.2 decision; private 2nd–3rd tier hospitals have no §2.2.2(2) choice, so the package is mandatory.
- **S2, S3, S4** are the three classic itemized "missing line" leaks (bed, anaesthesia, companion); all three are computed from dates and codes.
- **S5** is a real deduction cause since ÜTS usage notification became mandatory; it also produces the pre-submission MEDULA 0704 reminder.
- **S6** shows the §4.2 link between a drug and the coded diagnosis; its route has no prescriber-specialty check.
- **S7** shows a second data source (PACS/EMR log) and the ER setting.
- **S8** is a classic SGK deduction (seans/kesi rule) with real money.

## Common setup

- **Facility.** One SGK-contracted private hospital. `facility_tier = 2_3_basamak_ozel`, `provider_type = Ozel` (accepted at `src/bilun/domain/prose_rules/facility_tier.py:26-30`). The engine maps it to basamak 2, so the §2.2.2(2) EK-2B/EK-2C choice never applies (`payment_method.py:375-378`). That matches SUT §2.2.2(2), which grants the choice only to EAH and university hospitals.
- **Prices.** EK-2B/EK-2C rows from `data/gazette/curated/ek2b_catalog_history.parquet` and `ek2c_catalog_history.parquet`, row in force on the line date. Dates in July–September use the 2026-07-07 list. Dates in February–June use the 2026-01-31 list; none of the 38 codes used has a row amended in-row on 16.04.2026.
- **Rounding.** SUT §2.2(15) (C000544) truncates the kuruş: 510010 = 222,35, not 222,36. The curated catalog rounds half-up (`scripts/sut/catalogs/price_history.py:117,153,235`), so 76 of the 127 line-dates here are 1 kuruş high. That is an engine defect to file. The bills keep the catalog price, so the engine compares like with like. They switch with the catalog fix. What MEDULA itself displays: sahada sorulmalı.
- **Materials.** EK-3F-1 (Yür. 13.12.2025) as consolidated in the 2026-10-02 SUT (`data/gazette/curated/ek3f1_arthroplasty_materials.parquet`; raw `data/gazette/raw/annex=EK-3F-1/effective_date=2025-12-13/`). The harness takes each material's name and price from that list.
  - The curated list lacked the bone cements AP3180–AP3250 until this branch fixed the extractor (S5).
  - **KDV:** the hospital declares the rate on each material line and MEDULA adds it to the KDV-exclusive SUT price (C002886, C002748; Kılavuz p.243, p.126). Implants: 10 % since 10.07.2023 (8 % from 01.04.2022).
  - The claim model has no KDV field, so the bills show the list price. The engine's ceiling uses 20 % (`src/bilun/domain/pricing/material_kdv.py:7`), a defect to file.
- **Drugs.** EK-4A products in force on the line date (`ek4a_history.parquet`), each with an active ingredient in `data/synthetic/reference/drug_crosswalk.parquet`; the harness checks both. Price "TBD (Q4)"; they enter the engine at 0 TL.
  - **Quantity = units used.** MEDULA accepts decimal box quantities (Kılavuz p.21–22).
  - `DrugClaimLine.quantity` is an int (`src/bilun/domain/claims/models.py:266`), so a part box is billed as whole units (bottle, syringe, tablet) at box price ÷ units per box. For example, PK-Merz is 3 bottles at box price ÷ 2, not 1,5 boxes. The int is a defect to file.
- **Billed amount** = SUT price × quantity, except S8's second package (25 %).
- **Session cuts.** MEDULA computes them. The hospital sends, per operation, an incision code (`ayniFarkliKesi` 1–5) and no reduced amount; MEDULA returns each line's amount, and a wrong code is cut at audit (Kılavuz p.190, p.280; F000027). The claim model has no such field, so S8 carries the cut in its billed amount with the list unit price.
- **Extra fee (ilave ücret).** Not on any SGK bill. The hospital may collect it from the patient only with prior written consent (SUT §1.9.1(5)). None is allowed for S1 and S7 (ER-admitted emergency, §1.9.1(6)).
- **Exams on inpatient bills.** Ward visits are inside 510010 ("Yemek, yatak, hasta vizit hizmetlerini kapsar", EK-2B row 510010). The visit that led to admission sits on its own outpatient/ER takip, not on these bills. Consultations by other branches are billed (520010).
- **Bed days.** One 510010 per calendar day, admission and discharge day included (9→15 March = 7); a stay under 24 h gets 510120. Sources: Kılavuz p.62 (bed records for every day of the stay) and p.168 (`yatisBitisTarihi` = discharge date), the El Kitabı, C000648 (güçlü çıkarım). The engine counts the same way (`yatak_puani.py:337-338`).
- **Companion.** A doctor's medical-necessity decision plus the hospital's refakatçi belgesi; no age condition. Never on day cases, ICU days or inside an EK-2C window (C001628, C001629, C000650, C000698).
  - MEDULA takes `refakatciGunSayisi` as the hospital enters it from the belge (Kılavuz p.264).
  - The stories bill one 510121 per night, the days the belge covers. The engine counts nights (`refakatci.py`), a formula with no source. Whether hospitals count the discharge day: sahada sorulmalı.
- **ICU.** Its own takip (type Y), linked or not to the ward takip (Kılavuz p.83, p.156). No story has an ICU stay.
- **Specialty per line.** Each line carries an EK-2A branch code (Genel Cerrahi 1900, Anesteziyoloji 3100, …), as MEDULA lines carry the doctor's branch.

## Noise on clean bills: history

The first run (2026-10-15, engine at `1c22ee9c`) found 13 misfires on correct bills. All are fixed except N7.

| # | Misfire on 2026-10-15 | Stories | Closed by |
|---|---|---|---|
| N1 | Bed and companion expected inside the EK-2C package window (§2.2.2.B-1(1),(3)) | S1, S5, S8 | issue #259, PR #285; package-mandated itemized bills too, PR #288 |
| N2 | `tablo15_4` read `is_package_included` as "billed as package": a "Normal Poliklinik" error on every package line | S1, S5, S8 | issue #260, PR #277 |
| N3 | §2.2.2.A(5) session factors on anaesthesia, bed, companion, lab and exam lines: an audit-exposure header on every itemized bill | S2, S3, S4, S6, S7 | issue #261, PR #283 |
| N4 | "Must not bill separately" on the hip prosthesis (18.022,88 TL) | S5 | issue #262, PR #284 |
| N5 | The bone-cement keyword matched "ÇİMENTOSUZ" | S5 | issue #262, PR #284 |
| N6 | LOS density counted every bed, companion and lab line | S2, S4 | issue #263, PR #274 |
| N7 | Every R code blocked as principal diagnosis (error) | S7 | **open**: the review calls it a defect (to file) |
| N8 | Two operations in one session flagged as a time overlap | S8 | issue #263, PR #274 |
| N9 | EK-2C işlem grubu read as a specialty (+25 points) | S8 | issue #264, PR #283 |
| N10 | "Glike hemoglobin (Hb A1c)" read as a CBC component | side test | issue #270, PR #272 |
| N11 | Anaesthesia band cutovers off the list's Yürürlük dates | side test | issue #265, PR #273 |
| N12 | Capture gap ignored package lines | side test | issue #266, PR #275 |
| N13 | Vitamin K and FFP listed as PCC drugs in §4.2.27.A | side test | issue #267, PR #278 |

Also closed from this work:
- #268 (work accidents read as traffic accidents through "kaza"), PR #276;
- #269 (S1's strategy amount), PRs #283 and #288;
- the wrong lab codes in `BILUN_TO_SUT_CODE`, PR #271;
- `capture_gap_try` cast to int, PR #288.

**On 2026-10-16** (corrected stories, engine at 257d1e89): every clean bill carries 0 TL. What is left on a clean bill:

| Row (0 TL) | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|
| Fatura İnceleme documentation reminders (by design) | 3 | 2 | 2 | 2 | 4 | 2 | 0 | 3 |
| Info: bone cement is paid outside the package (§3.1.4(b)) | – | – | – | – | 1 | – | – | – |
| N7: `never_principal_diagnosis_blocklist` on R07.1 (error, validation core) | – | – | – | – | – | – | 1 | – |
| Session "Kontrol et" review: the bill has no incision field (see S8) | – | – | – | – | – | – | – | 1 |

Also on every bill, at info level only: Wave A review rows (ORTAK-*, including "ORTAK-14.onkolojik_ek2b" on non-oncology bills) and the transplant rules `2.4.2.A.*` in the validation core.

Still open from the first run's smaller items:
- Anaesthesia, companion and ICU results have **no action rows** on the patient page (`billing_actions.py:319-358` lists the other uplift blocks only). S3 and S4 show only inside the header SGK total. Faulty S8 shows only as the audit-exposure header.
- The companion rule has no eligibility input (doctor's order, belge) and counts nights.
- Catalog rounding (see Common setup).

**Engine defects found by the review** (11, to file; [list][defects]): KDV 20 % on implants; half-up rounding; the session list price taken from the bill and no `ayniFarkliKesi` field; the companion day count and eligibility; the int drug quantity; no rule for EK-2B açıklama frequency caps (the old S2 had 952,28 TL unbillable); no rule for contrast billed next to R101450 (the old S7); N7; the drug-indication matcher missing leaf codes under a listed parent; the EK-3/F-1 cements (fixed on this branch); the KGAZ line in `docs/medula/medula_capabilities.md:273`.

---

## S1 — Package billed as itemized (laparoscopic appendectomy)

**Patient.** Male, 34 (born 1992). No chronic disease. Right lower quadrant pain for 18 hours.
**Diagnosis.** K35.9 "AKUT APANDİSİT, TANIMLANMAMIŞ" (primary). SKRS has no K35.8.
**Episode.** ER (separate acil takip: exam, CBC/CRP, ultrasound) → admitted to Genel Cerrahi 14.07.2026 evening → laparoscopic appendectomy the same night → discharged 16.07.2026 (2 nights). Uncomplicated appendicitis: one pre-operative antibiotic dose, none after (WSES 2020). EK-2C group C: 8-day package window.

**Correct bill (clean).** One package line. Bed, anaesthesia, labs, pathology, drugs and companion are inside it (SUT §2.2.2.B-1(1)).

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source |
|---|---|---|---|---|---|---|
| 07-14 | P610131 | Appendektomi, laparoskopik | 1 | 8.636,51 | 8.636,51 | EK-2C from 2026-07-07 (group C, *) |

Total 8.636,51 TL.

**Fault.** The coder keyed EK-2B 610131 in the HBYS, so the stay went out hizmet başı, as if no package existed:

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source |
|---|---|---|---|---|---|---|
| 07-14 | 610131 | Appendektomi, laparoskopik | 1 | 3.022,31 | 3.022,31 | EK-2B from 2026-07-07 |
| 07-14 | 550170 | Anestezi C grubu | 1 | 530,33 | 530,33 | EK-2B from 2026-07-07 (5.096,64 puan → C, 3005–6000) |
| 07-14, 07-15, 07-16 | 510010 | Standart yatak tarifesi | 3 | 222,36 | 667,08 | EK-2B from 2026-07-07 |
| 07-15 | L107020 | Tam Kan Sayımı (Hemogram) | 1 | 19,73 | 19,73 | EK-2B from 2026-07-07 |
| 07-15 | L101850 | C reaktif protein (CRP) | 1 | 16,46 | 16,46 | EK-2B from 2026-07-07 |
| 07-15 | 910230 | Apendiks, insidental dışında | 1 | 258,54 | 258,54 | EK-2B from 2026-07-07 |
| 07-14 | 8699508270224 | IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU (seftriakson) | 1 vial | TBD | TBD | EK-4A A03721 |
| 07-14 | 8697637691743 | NEOFLEKS %0,5 METRONIDAZOL I.V. ENJ COZ 100 ML (SETLI) | 1 bottle | TBD | TBD | EK-4A A15078 |
| 07-14 | 8699844770716 | PARTEMOL 1 G/100 ML INF ICIN COZ ICEREN 1 FLK (parasetamol) | 5 vials | TBD | TBD | EK-4A A13408 |

Total 4.514,45 TL + drugs. The 07-14 CBC and CRP belong to the ER takip, so the ward bill repeats them only on 07-15. The hospital loses, or gets rejected, about 4.122 TL minus the drug amounts (the package covers the drugs).

**SUT.** §2.2.2(1) (C000646): "İkinci ve üçüncü basamak sağlık hizmeti sunucularında yatarak verilen sağlık hizmetlerinin bedelleri, SUT eki EK-2/C Listesinde yer alıyorsa "tanıya dayalı işlem üzerinden ödeme" yöntemi ile … faturalandırılır."

**Engine rule.** `check_payment_method_compliance` and `recommend_billing_strategy_from_claims` (`claim_strategy.py`). Expected: a compliance violation on 610131 and a claim-level "package mandated" row.

**Proof (actual output).**
- Clean: `check_payment_method_compliance('610131', billed_as_package=True)` → `DRG_MANDATORY, compliant`. Strategy: "Claim C-SH01 is billed correctly as package per SUT §2.2.2(1). Package total 8636.51 TRY." No violation.
- Faulty: `compliance_violation` on 610131: "Procedure 610131 must use package billing (tanıya dayalı işlem üzerinden ödeme) per 2.2.2.(1)."
  - Claim row: "SUT §2.2 mandates package billing for claim C-SH01 (EK-2/C procedure present). Package total 8636.51 TRY vs itemized 4514.45 TRY". `savings_try` 4.122,06.
  - Shown as a `billing_strategy` action and in the SGK total (4.122,06 TL). Audit exposure 0.
- The amount defect of the first draft (#269: the operation line left out of the itemized total, savings floored at 0) is fixed by PRs #283 and #288.

**Noise on the clean bill.** None with money; 3 documentation reminders (by design). N1 and N2 are closed.

**Question answered (review Q3).** No document says a normal ward takip rejects EK-2B 610131. The realistic fault is a coder keying it, which Bilun catches before submission. Whether MEDULA accepts it on a ward takip: sahada sorulmalı.

---

## S2 — Bed days under-billed (COPD exacerbation with pneumonia)

**Patient.** Male, 81 (born 1945). COPD (ex-smoker), hypertension.
**Diagnoses.** J44.0 COPD with acute lower respiratory infection (primary); J18.9 Pneumonia, unspecified; I10.
**Episode.** Admitted from the outpatient clinic to Göğüs Hastalıkları 09.03.2026; discharged 15.03.2026 (6 nights).
- Treatment: ceftriaxone plus clarithromycin (ATS/IDSA 2019), methylprednisolone 40 mg for 5 days (GOLD), enoxaparin 40 mg a day, nebulizer and oxygen.
- A companion stayed on the doctor's order (age, oxygen need); the refakatçi belgesi covers the 6 nights.

**Clean bill** (total 3.263,43 TL + drugs; all rows EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 03-09…03-15, daily | 510010 | Standart yatak tarifesi | 7 | 222,36 | 1.556,52 |
| 03-09…03-14, daily | 510121 | Refakat | 6 | 74,10 | 444,60 |
| 03-09, 03-12 | L107020 | Tam Kan Sayımı (Hemogram) | 2 | 19,73 | 39,46 |
| 03-09, 03-12 | L101850 | C reaktif protein (CRP) | 2 | 16,46 | 32,92 |
| 03-09 | L102890 / L104780 / L107420 / L100300 / L101280 | Glukoz, Kreatinin, Üre (Serum/Plazma); ALT; AST | 1 each | 6,57–7,20 | 34,74 |
| 03-09, 03-12 | L103900 | Kan gazları | 2 | 33,57 | 67,14 |
| 03-09 | L106240 | Prokalsitonin (Serum/Plazma) | 1 | 167,91 | 167,91 |
| 03-09 | 906020 | Kan kültürü (Aerob-anaerob) otomatik sistem (2 sets) | 2 | 65,82 | 131,64 |
| 03-09 | 905675 | Balgam Kültürü | 1 | 16,46 | 16,46 |
| 03-09, 03-13 | 801720 | Akciğer grafisi P.A. (Tek yön) | 2 | 44,75 | 89,50 |
| 03-09…03-14, daily | 530350 | Nebülizatör ile ilaç uygulaması | 6 | 66,29 | 397,74 |
| 03-09, 03-10 | 530360 | Oksijen inhalasyon tedavisi, saatlik | 2 × 16 h | 8,90 | 284,80 |
| 03-09 | 8699508270224 | IESEF 1 G IV (seftriakson) | 7 vials | TBD | TBD (EK-4A A03721) |
| 03-09 | 8699548270482 | KLACID 500 MG IV 1 FLK (klaritromisin), 500 mg twice a day for 5 days | 10 vials | TBD | TBD (EK-4A A04309) |
| 03-09 | 8699541791007 | PREDNOL-L 40 MG 1 AMP (metilprednizolon) | 5 ampoules | TBD | TBD (EK-4A A06313) |
| 03-09 | 8680741521174 | IPRAVENT 0.5MG/2.5ML + 2.5MG/2.5ML NEBULIZAYON … (20 FLAKON) (ipratropium + salbutamol) | 1 box | TBD | TBD (EK-4A A17700) |
| 03-09 | 8699809950696 | CLEXANE 4000 ANTI-XA IU/0.4 ML 10 KULL HAZIR ENJ (enoksaparin) | 6 syringes | TBD | TBD (EK-4A A10398) |

**EK-2B açıklama limits** (corrected 2026-10-16):
- 530350 "Günde bir adet faturalandırılır": one line a day, 6 lines.
- 530360 "Günlük en fazla 16 saat ödenir": 16 h on each of the first two days; the epikriz states the duration.
- L103900 "… L106150, … L106910 … ile birlikte faturalandırılmaz. Tüm parametreler dahildir": no serum Na/K on 03-09; they are blood-gas parameters.
- The first draft billed 18 nebulizer lines, 48 h of oxygen and serum Na/K beside the gas: 952,28 TL that SGK would not pay. The engine has no rule for these limits yet (to file), so it did not notice.
- Drug lines carry the total quantity on the first day; the generator should date them per day.

**Fault.** The bed charge stopped after 12.03 (ward transfer): 4 lines of 510010 instead of 7. Billed 889,44 TL instead of 1.556,52.

**SUT.** §2.2.2.A(1) (C000652): "Hizmet başına ödeme yönteminde sağlık hizmeti bedelleri, SUT eki EK-2/B ve EK-2/Ç Listesi esas alınarak faturalandırılır." The day count comes from the Kılavuz (see Common setup).

**Engine rule.** `detect_yatak_puani_opportunities` (`yatak_puani.py`).

**Proof.**
- Clean: 7 billable bed days, expected 1.556,52, billed 1.556,52, recoverable 0,00.
- Faulty: "Standart yatak (510010): 7 billable bed-day(s) (gross LOS 7 day(s) at 222.36 TRY/day) = 1556.52 TRY (inclusive LOS, discharge day billed).", billed 889,44, **recoverable 667,08 TL**. Shown as a `yatak_puani` action.

**Noise on the clean bill.** None with money; 2 documentation reminders. N3 and N6 are closed.

**Question answered (review Q1).** SGK pays calendar days, discharge day included (güçlü çıkarım), so 7 is right.

---

## S3 — Anaesthesia missing on an itemized operation (lumbar decompression)

**Patient.** Female, 77 (born 1949). Hypertension, controlled. ASA 2 (so the standard group applies; the "75 yaş üstü ve ASA 3-4" geriatric codes 550270–550346 do not).
**Diagnoses.** M48.06 "SPİNAL STENOZ, LOMBER BÖLGE" (primary, neurogenic claudication); I10.
**Episode.** Elective. Pre-op exam and labs on an earlier outpatient takip.
- Admitted to Beyin ve Sinir Cerrahisi 18.08.2026; unilateral decompression the same day under general anaesthesia; discharged 20.08.2026 (2 nights).
- Cefazolin 2 g once before the incision (ASHP 2013). Companion on the doctor's order (post-op fall risk), with the refakatçi belgesi.
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
| 08-18 | 8699814270253 | EQIZOLIN 1 GR IM/IV 1 FLK (sefazolin) | 2 vials | TBD | TBD (EK-4A A02786) |
| 08-18 | 8699844770716 | PARTEMOL 1 G/100 ML … 1 FLK (parasetamol) | 6 vials | TBD | TBD (EK-4A A13408) |

Group check: 6.471,03 puan is B under both band tables (B 6001–9000 since 16.04.2026; 5001–7583 before).

**Fault.** The anaesthesia record never reached billing: 550160 is missing.

**SUT and annex.** §2.2.2.A(1) (C000652, quoted in S2) plus EK-2B section 4 row "B grubu 6001-9000" (raw 2026-07-07 EK-2B, row 127) and code 550160 "Anestezi B grubu".

**Engine rule.** `detect_anestezi_puani_opportunities` (`anestezi_puani.py`).

**Proof.**
- Clean: group B, 550160, expected 928,09, billed 928,09, recoverable 0,00.
- Faulty: "Anestezi B grubu (550160): surgical procedure 615931 (puan 6471.03) → anestezi puan 1565.07 × katsayı 0.593 = 928.09 TRY", **recoverable 928,09 TL**. Counted in the header SGK total; no action row (see "Still open").

**Noise on the clean bill.** None with money; 2 documentation reminders. N3 is closed.

---

## S4 — Companion bed not billed (dementia, pyelonephritis)

**Patient.** Female, 86 (born 1940). Alzheimer's disease, hypertension.
**Diagnoses.** N10 Acute tubulo-interstitial nephritis (pyelonephritis) (primary); F05.1 Delirium superimposed on dementia; G30.1 Alzheimer's disease with late onset; I10.
**Episode.** Admitted to İç Hastalıkları 11.05.2026, discharged 16.05.2026 (5 nights).
- Ceftriaxone 2 g a day (EAU), two blood-culture sets, a urinary-tract ultrasound, enoxaparin 40 mg a day.
- Her daughter stayed every night; the ward doctor ordered a companion (delirium, fall risk) and the refakatçi belgesi is on file.

**Clean bill** (total 2.108,52 TL + drugs; EK-2B from 2026-01-31):

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
| 05-11 | 906020 | Kan kültürü (Aerob-anaerob) otomatik sistem (2 sets) | 2 | 65,82 | 131,64 |
| 05-11 | 803580 | Üriner sistem US | 1 | 100,73 | 100,73 |
| 05-11 | 8699508270224 | IESEF 1 G IV (seftriakson), 2 g a day for 5 days | 10 vials | TBD | TBD (EK-4A A03721) |
| 05-11 | 8699606694649 | PARACEROL 10 MG/ML IV INF … 12 FLK (parasetamol) | 1 box | TBD | TBD (EK-4A A14359) |
| 05-11 | 8699809950696 | CLEXANE 4000 ANTI-XA IU/0.4 ML 10 KULL HAZIR ENJ (enoksaparin) | 5 syringes | TBD | TBD (EK-4A A10398) |

**Fault.** The five 510121 lines were never entered.

**SUT.** §2.6.3(2) (C001628): "Kişilerin yatarak tedavileri sırasında hekimin veya diş hekiminin tıbben göreceği lüzum üzerine; … refakatçisinin yatak ve yemek giderleri, … SUT eki EK-2/B Listesinde yer alan "refakat" puanı esas alınarak karşılanır …". Billing route: §2.2.2.A(3) (C000654).

**Engine rule.** `detect_refakatci_opportunities` (`refakatci.py`).

**Proof.**
- Clean: 5 companion days, expected 370,50, billed 370,50, recoverable 0,00.
- Faulty: "Refakat (510121): 5 companion day(s) at 124.95 puan × 0.593 katsayı = 74.10 TRY/day → 370.50 TRY (admission IN, discharge OUT).", **recoverable 370,50 TL**. Header total only; no action row.

**Caveat.** The rule still cannot tell an eligible patient from an ineligible one: it has no input for the doctor's order or the belge, so it would fire the same way for a 40-year-old without a companion. The review files this (without the input: a review row, not TL). The story is honest; the rule's precision is not.

**Noise on the clean bill.** None with money; 2 documentation reminders. N3 and N6 are closed.

---

## S5 — Implant billed without ÜTS notification (cemented hip hemiarthroplasty)

**Patient.** Female, 84 (born 1942). Hypertension, postmenopausal osteoporosis (no DXA on file). Fell at home. Before the fall she walked outdoors with a walker, so a hemiarthroplasty, not a total hip replacement, is the indicated choice (NICE CG124 1.6.3).
**Diagnoses.** S72.00 "FEMUR BOYUN KIRIĞI, KAPALI" (primary); W19 "DÜŞME, TANIMLANMAMIŞ"; I10; M81.09 "POSTMENAPOZAL OSTEOPOROZ, YER TANIMLANMAMIŞ".
**Episode.** ER → admitted to Ortopedi ve Travmatoloji 03.09.2026; cemented bipolar hemiarthroplasty 04.09.2026 (NICE CG124 1.6.4, AAOS 2021, WHiTE 5); discharged 08.09.2026 (5 nights). EK-2C group B: 10-day window, so bed, labs, drugs and companion are inside the package.

**Clean bill** (total 31.233,66 TL):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL | Source |
|---|---|---|---|---|---|---|
| 09-04 | P612320 | Büyük eklem parsiyel protezleri, primer | 1 | 18.390,80 | 18.390,80 | EK-2C from 2026-07-07 (group B); açıklama "Protez ayrıca faturalandırılır." |
| 09-04 | AP2000 | KALÇA / PRİMER / FEMORAL STEM / ÇİMENTOLU / ÇELİK / PARLATILMIŞ | 1 | 6.465,27 | 6.465,27 | EK-3F-1 list price 6.465,2713125 |
| 09-04 | AP1880 | KALÇA / PRİMER / FEMORAL BIPOLAR BAŞ (SHELL + İNSERT) / TÜM BOYLAR / CoCr | 1 | 5.391,89 | 5.391,89 | EK-3F-1 list price 5.391,8865; row amended 24.01.2026 (material wording) |
| 09-04 | AP3220 | PRİMER/REVİZYON / KEMİK ÇİMENTOSU - NORMAL / STANDART - 40 gr / PMMA | 2 | 492,85 | 985,70 | EK-3F-1 list price 492,848125 |

- **The implants fit a fracture.** EK-3F-1 Genel Hükümler (2) and (17) bar revision stems and tumour prostheses for proximal femur fractures. (11) limits calcar stems (AP2010–AP2040) to trochanteric fractures. (15) accepts a bipolar head as one barcode.
- **Cement.** It is billed outside the package (§3.1.4(2)(b), C002859). Two 40 g packs is a choice; the pack count is a field question.
- **Cement in the catalog.** The curated EK-3/F-1 list lacked AP3180–AP3250 until this branch.
  - Root cause: `scripts/sut/catalogs/orthopedic_materials.py` skipped every row whose first descriptive cell (UYGULAMA YERİ) was blank. RG 21/04/2024-32524 (Yürürlük 30/04/2024) repealed only the "KALÇA/DİZ" site cell of the eight cement rows. They kept their prices (the same ×1,4 update as the stems in the 13.12.2025 list).
  - The extractor now keeps a coded row with a blank first cell. The list was rebuilt in the CI image: 337 → 345 rows, nothing else changed.
- **KDV.** It is 10 % on each material line, declared by the hospital and added by MEDULA. The bill shows the KDV-exclusive list price (see Common setup).

**Fault.** The hospital never completed the ÜTS usage notification for the stem (`uts_registered = False` on the AP2000 line). Everything else is identical.

**SUT.** §3.1.1(2) (C002740): "TİTUBB/ÜTS kayıt/bildirim işlemi tamamlanmamış tıbbi malzemelerin bedelleri Kurumca karşılanmaz."

**Engine rule.** `check_material_bundling_for_context` → rule `3.1.1.(2).titubb_uts_incomplete` (`material_bundling.py`). Also the readiness checklist.

**Proof.**
- Clean: the rule is silent.
- Faulty: `3.1.1.(2).titubb_uts_incomplete`, severity error, AP2000, `risk_amount 6465.27`, outcome `no_pay`, message "TİTUBB/ÜTS kayıt-bildirim tamamlanmamış — Kurumca karşılanmaz (§3.1.1(2))." Plus the checklist item `claim_readiness.material_uts_barcode_missing`: "Malzeme satırında ÜTS/TİTUBB barkod kaydı eksik — MEDULA 0704 red riski."

**Noise on the clean bill.** None with money. N1, N2, N4 and N5 are closed.
- An info row on the cement confirms the separate billing: "Kemik çimentosu tanıya dayalı ödeme kapsamında değildir; bedeli SUT hükümleri doğrultusunda Kurumca ayrıca karşılanır (§3.1.4(b))."
- 4 documentation reminders.

**Questions answered (review Q6a, Q6b).**
- Cemented stem plus cement at 84 (güçlü kanıt).
- KDV is declared per material line, 10 % for implants (kesin).
- Which stem and how many cement packs a hospital bills, and whether the cement restrictor (AP2200) is billed: sahada sorulmalı (orthopaedist).

---

## S6 — Drug billed without its indication diagnosis (IV amantadine)

**Patient.** Male, 79 (born 1947). Advanced Parkinson's disease, hypertension. Creatinine 1,1 mg/dL at 72 kg: CrCl ≈ 55 mL/min (Cockcroft-Gault). The Turkish SmPC halves the amantadine dose only at CrCl 30–50, so no dose reduction.
**Diagnoses (clean).** J69.0 Pneumonitis due to food and vomit (primary); R13 Dysphagia; G20 Parkinson's disease; I10.
**Episode.** Admitted to İç Hastalıkları 08.06.2026 with aspiration pneumonia, nil by mouth. Discharged 14.06.2026 (6 nights).
- Day 1: neurology consultation and a baseline ECG for the QT interval.
- Days 1–3: IV NaCl 0,9 %, 1000 ml a day.
- Days 2–4: PK-MERZ IV, one 500 ml bottle a day, while oral levodopa is impossible.
- Day 3: a nasogastric tube; levodopa (MADOPAR) goes through it from then on.
- Ceftriaxone without metronidazole (ATS/IDSA 2019: no routine anaerobic cover); enoxaparin 40 mg a day.
- The neurologist's specialist report (uzman hekim raporu) for amantadine is on file. A companion stays on the doctor's order.

**Clean bill** (total 2.416,40 TL + drugs; EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 06-08…06-14, daily | 510010 | Standart yatak tarifesi | 7 | 222,36 | 1.556,52 |
| 06-08…06-13, daily | 510121 | Refakat | 6 | 74,10 | 444,60 |
| 06-08 | 530100 | Elektrokardiyogram (baseline QT) | 1 | 16,66 | 16,66 |
| 06-08 | 520010 | Konsültasyon (Her bir branş için) — Nöroloji | 1 | 33,17 | 33,17 |
| 06-08, 06-11 | L107020 | Tam Kan Sayımı (Hemogram) | 2 | 19,73 | 39,46 |
| 06-08, 06-11 | L101850 | C reaktif protein (CRP) | 2 | 16,46 | 32,92 |
| 06-08 | L102890 / L104780 / L107420 / L106910 / L106150 / L100300 / L101280 | Glukoz, Kreatinin, Üre, Sodyum, Potasyum, ALT, AST | 1 each | 6,57–7,20 | 49,14 |
| 06-08 | 906020 | Kan kültürü (Aerob-anaerob) otomatik sistem | 1 | 65,82 | 65,82 |
| 06-08, 06-12 | 801720 | Akciğer grafisi P.A. (Tek yön) | 2 | 44,75 | 89,50 |
| 06-10 | 530340 | Nazogastrik sonda uygulaması | 1 | 88,61 | 88,61 |
| 06-08 | 8699508270224 | IESEF 1 G IV (seftriakson) | 7 vials | TBD | TBD (EK-4A A03721) |
| 06-08 | 8697637690128 | NEOFLEKS %0,9 IZOTONIK SODYUM KLORUR … PP-TORBA 1000 ML(SETLI), days 1–3 | 3 bags | TBD | TBD (EK-4A A09604) |
| 06-08 | 8699809950696 | CLEXANE 4000 ANTI-XA IU/0.4 ML 10 KULL HAZIR ENJ (enoksaparin) | 6 syringes | TBD | TBD (EK-4A A10398) |
| 06-09 | 8699708690525 | PK-MERZ IV INF. COZ. 2x500 ML (amantadin sülfat), days 2–4 | 3 bottles at box price ÷ 2 | TBD | TBD (EK-4A A12140) |
| 06-10 | 8699525094841 | MADOPAR 125 MG 30 TB (levodopa + benserazid), via the NG tube, days 3–7 | 20 tablets | TBD | TBD (EK-4A A04817) |

PK-Merz is billed by the bottle: MEDULA would record 1,5 boxes; the claim model's int quantity forces 3 bottles at box price ÷ 2 (see Common setup).

**Fault.** The coder entered only the admission problems (J69.0, R13, I10). G20 is missing from the bill.

**SUT.** §4.2.36(3) (C006824): "Amantadin sülfat; parkinson hastalığının tedavisi ile ilaçlara bağlı oluşmuş ekstrapiramidal reaksiyonların tedavisinde …, nöroloji veya geriatri uzmanı tarafından veya bu uzman hekimlerin düzenlediği uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilir."

**Engine rule.** `evaluate_drug_indication_line_detailed` (route `4.2.36.amantadine_sulfate_report`, ICD G20/G21/G24/G25); finding via `evaluate_drug_indication_findings`. The drug matches by name ("pk-merz"), so no INN crosswalk is needed. This route has no prescriber-specialty check.

**Proof.**
- Clean: `applicability_status eligible`, route `4.2.36.amantadine_sulfate_report`, no violation.
- Faulty: `indication_mismatch`, severity error: "Faturada I10, J69.0, R13 tanıları bulundu. PK-MERZ IV INF. COZ. 2x500 ML için kodlanmış SGK geri ödeme yolları G20, G21, G24, G25 tanılarını kapsıyor. Mevcut tanılar bu yollarla eşleşmiyor." Shown as a `drug_indication` action. TL at risk = the drug line (TBD, Q4).
- Alternative fault (first draft): report flag False → `missing_board_report` (error).

**Noise on the clean bill.** None with money; 2 documentation reminders. N3 is closed. The new drugs (Madopar, enoxaparin, NaCl) raise no finding.

**Questions answered (review Q7).** Drugs are billed by units used, and fractions are allowed (Kılavuz kesin). Whether a neurologist would bridge with IV PK-Merz or use NG levodopa alone: sahada sorulmalı.

---

## S7 — ER: CT angiography done but not billed

**Patient.** Female, 58 (born 1968). No chronic disease. Pleuritic chest pain and dyspnoea three days after a long-haul flight.
**Diagnoses.** R07.1 Chest pain on breathing (primary); R06.0 Dyspnoea. Pulmonary embolism ruled out.
**Episode.** ER only, 19.02.2026, no admission (no stay). Discharged home. ER services at 2nd–3rd tier providers are billed hizmet başı.
- Exam, ECG, IV line, chest X-ray.
- Troponin at 0 and 2 h (ESC 2023 0/2 h algorithm). D-dimer 920 ng/mL FEU, above the age-adjusted cut-off of 580.
- CT pulmonary angiography, normal.

**Clean bill** (total 1.633,02 TL + drugs; EK-2B from 2026-01-31):

| Date | Code | Name (catalog) | Qty | Unit TL | Billed TL |
|---|---|---|---|---|---|
| 02-19 | 520020 | Acil poliklinik muayenesi | 1 | 85,73 | 85,73 |
| 02-19 | 530100 | Elektrokardiyogram | 1 | 16,66 | 16,66 |
| 02-19 | 530080 | Damar yolu açılması | 1 | 35,74 | 35,74 |
| 02-19 | L107020 | Tam Kan Sayımı (Hemogram) | 1 | 19,73 | 19,73 |
| 02-19 | L107360 | Troponin I (0 h and 2 h) | 2 | 59,26 | 118,52 |
| 02-19 | L102090 | D-dimer (Kantitatif) | 1 | 145,50 | 145,50 |
| 02-19 | L104780 / L102890 / L106910 / L106150 | Kreatinin, Glukoz, Sodyum, Potasyum | 1 each | 6,57–7,20 | 28,17 |
| 02-19 | 801720 | Akciğer grafisi P.A. (Tek yön) | 1 | 44,75 | 44,75 |
| 02-19 | R101450 | BT anjiografi, pulmoner arter | 1 | 1.138,22 | 1.138,22 |
| 02-19 | 8699844770716 | PARTEMOL 1 G/100 ML … 1 FLK (parasetamol) | 1 vial | TBD | TBD (EK-4A A13408) |

No contrast line: the R101450 açıklama reads "Kontrast ilaçlar ve sarf malzemeleri ayrıca faturalandırılmaz". The first draft billed OMNIPAQUE beside it; the engine has no rule for this yet (to file).

EMR/PACS log attached to the bill: 530100, 530080, 801720 (EMR) and R101450 (PACS), all 19.02.

**Fault.** The CT line never reached the invoice (RIS → HBYS transfer). The PACS log still shows it.

**SUT.** §2.2.1.B-2(2) (C000604/C000607/C000617): "İkinci ve üçüncü basamak … sağlık hizmeti sunucularında; a) Acil sağlık hizmetleri, … "hizmet başına ödeme yöntemi" ile faturalandırılır."

**Engine rule.** `detect_procedure_capture_gaps` (`procedure_capture_gap.py`); report block `procedure_capture_gap`.

**Proof.**
- Clean: silent (every logged code is billed).
- Faulty: `performed_not_submitted`, R101450 "BT anjiografi, pulmoner arter", source `pacs`, list price 1.138,22, **recoverable 1.138,22 TL**, "EMR log shows R101450 performed on 2026-02-19 (pacs) but claim submission has 0.00 TRY billed." Shown as an action; the header shows 1.138,22 (the int cast is fixed, PR #288).

**Noise on the clean bill.** No money and no action. N3 is closed. **N7 is still open:** `never_principal_diagnosis_blocklist` (error, validation core) on R07.1.

**Question answered (review Q8).** R07.1 is a correct principal diagnosis when no diagnosis is made (WHO ICD-10 Vol. 2 §4.5; TİG guide 2019; güçlü kanıt). N7 is a defect: block an R principal only when a related definitive diagnosis is also coded. R07.1 or Z03.5 on an acil takip, and whether MEDULA rejects either: sahada sorulmalı.

---

## S8 — Second operation in the same session billed at full points

**Patient.** Female, 47 (born 1979). Symptomatic gallstones; a small umbilical hernia (defect 0,8 cm) found at the pre-op exam.
**Diagnoses.** K80.2 Calculus of gallbladder without cholecystitis (primary); K42.9 Umbilical hernia without obstruction or gangrene.
**Episode.** Elective. Admitted to Genel Cerrahi 15.09.2026; discharged 16.09.2026 (1 night). EK-2C groups B and C: 10- and 8-day windows.
- Laparoscopic cholecystectomy, then a primary repair of the hernia through the umbilical camera port: same session, same incision.
- A defect under 1 cm can be sutured (EHS/AHS 2020). The op note records the pre-existing hernia, the defect size and the sac.

**Clean bill** (total 13.858,13 TL):

| Date | Code | Name (catalog) | Qty | Unit TL (list) | Billed TL | Source |
|---|---|---|---|---|---|---|
| 09-15 | P609235 | Kolesistektomi, laparoskopik | 1 | 12.065,73 | 12.065,73 (100 %) | EK-2C from 2026-07-07 (group B, *) |
| 09-15 | P603840 | Greftsiz umblikal herni onarımı | 1 | 7.169,60 | 1.792,40 (25 %) | EK-2C from 2026-07-07 (group C, *) |

In MEDULA the hospital sends P603840 with `ayniFarkliKesi` = 1 ("Aynı seans + aynı kesi") and no reduced amount; MEDULA applies the 25 % (Kılavuz p.190). The claim model has no such field, so the bill keeps the list unit price and puts the 25 % in the billed amount.

**Fault.** P603840 billed at 7.169,60 TL (100 %). In MEDULA terms, a wrong incision code made the line pay in full; an auditor cuts the excess (F000027).

**SUT.** §2.2.2.B(3)(a) (C000670): "Aynı seansta aynı kesi ile birden fazla işlem yapılması halinde; işlem puanı yüksek olan tanıya dayalı işlemin puanı tam olarak, diğer işlemler ise kendi tanıya dayalı işlem puanının %25'i alınarak," (… faturalandırılır, C000674).

**Engine rule.** `analyze_claim_unbundling(...).session_violations` (`drg_unbundling.py`) → `audit_exposure_try`.

**Proof.**
- Clean: no session violation; audit exposure 0.
- Faulty, incision given (`same_incision=True`): rule `2.2.2.B.a`, P603840, primary P609235, factor 0.25, expected 1.792,40, billed 7.169,60, **risk 5.377,20 TL**. Message: "Secondary procedure billed at full rate; SUT §2.2.2.B.a requires 25% point factor in same session."
- Faulty, patient report: audit exposure **3.584,80 TL**, shown only as the header.
  - The bill carries no incision. Since PR #288 the engine claims money only on the reading every legal case allows: the excess over the separate-incision reading, 50 % (7.169,60 − 3.584,80).
  - With `ayniFarkliKesi` on the claim it would show 5.377,20.
- The N9 issue of the first draft (+25 points from the işlem grubu) is fixed by PR #283.

**Noise on the clean bill.** No money.
- One 0 TL "Kontrol et" review row: "faturada kesi bilgisi yok … Ayrı kesi ise SUT §2.2.2.B.b %50 ile 3584.80 TRY ödenir …; aynı kesi ise SUT §2.2.2.B.a %25 ile 1792.40 TRY ödenir. Ameliyat notundaki kesi bilgisini kontrol edin." It goes away once the claim carries the incision code.
- 3 documentation reminders. N1, N2 and N8 are closed.

**Questions answered (review Q4, Q5).**
- MEDULA computes the session cuts (Kılavuz kesin).
- The umbilical-port repair is the same incision, 25 % (klinik yargı). It is 50 % only with a separate skin incision.
- Whether auditors challenge it as a port-site closure: sahada sorulmalı (general surgeon).

---

## Candidates considered and replaced

- **MEDULA rejection playbook (e.g. ÜTS 0704).** Not used as a story. It maps a rejection the hospital already received to a template; it does not detect anything on the bill. The playbook's codes have no documented source (the audit marked them "not checked"). S5 covers the same ground before submission and emits the "MEDULA 0704 red riski" checklist item.
- **Material inside the EK-2C package billed separately.** The code-based check misfired on correct implants (N4, fixed by PR #284); not re-tested as a story. The other variant reads an input flag (`diagnosis_package_material_unbundled`), so it would not be a real detection.
- **Session uplift (under-billing).** The claim has no incision field, so the engine cannot tell a second operation billed at 30 % from one owed 50 %. Since PR #288 such a line gets a 0 TL review row instead of money. MEDULA's `ayniFarkliKesi` would settle it (review defect 3). Replaced by the over-billing case (S8).
- **Drug needing a report.** Proven as S6's alternative fault; the diagnosis variant was kept because it is computed from codes, not from a flag.
- **IVIG, albumin, etelcalcetide, infliximab, Konakion.**
  - IVIG routes to a clinical-constraint path with the same "review" result on clean and faulty bills.
  - Albumin's SUT condition is the lab value (≤ 2,5 g/dl, §4.2.27.Ç(1)), which the engine cannot read.
  - Etelcalcetide is a reçete drug (§4.2.9.E(3)).
  - Infliximab day-case use is, in my judgment, also pharmacy-supplied. Its AS routes carry the "fiziksel tıp ve rehabilitasyon" specialty; the specialty matching was fixed in #256 (PR #285).
  - Konakion was mis-encoded (N13, fixed by PR #278).
  - Most hospital IV drugs (seftriakson, metronidazol …) are not in the encoded corpus or not matchable by name (brand names lack the INN).
- **ICU (tiering, bundled ventilation, transfer-day bed).** Left out. #255 (PR #285), N1 and N2 are fixed, and the review confirms ICU is its own takip (type Y). Not re-tested here. In the first side test, the bundled-service rule (oxygen/nebulizer billed on a 510090 day) fired correctly.
- **Outpatient lab capture gap.** Dropped. Outpatient visits at private 2nd–3rd tier hospitals are paid per visit from EK-2/A by hospital class (SUT §2.2.1.B-1(1)); only EK-2/A-2 items are billed on top.
  - Since PR #288 the engine reads a curated EK-2/A-2 history (`ek2a2_outpatient_additional_procedures.parquet`), but only for the outpatient package mandate.
  - The engine still prices no EK-2/A visit: `lookup_ek2a_visit_price_try` has no caller outside the catalog module. So a correct outpatient bill cannot be built yet.
- **Laterality (sağ/sol).** Its code prefixes are stale: "80102" now hits 801020 Hepatobiliyer Sintigrafi, "80319" hits 803190 Perkütan ablasyon tedavisi, and cataract is 617341, not 516xxx.

## Open questions for Safa: answered 2026-10-16

The review answered each question on Safa's behalf; links go to the review report ([story answers][answers]). Field questions stay open ([list][field]).

1. **Bed-day count.** Answered ([Q1][answers]): calendar days, discharge day included; under 24 h, 510120 (güçlü çıkarım). Companion days come from the refakatçi belgesi (Q1b). Whether hospitals count the discharge day in `refakatciGunSayisi`: sahada sorulmalı.
2. **Package window.** Answered on 2026-10-16 and implemented in PR #285 (C000685): days before the operation on the same takip are inside the package.
3. **S1 realism.** Answered ([Q3][answers]): the realistic fault is a coder keying 610131; whether MEDULA accepts it on a ward takip: sahada sorulmalı.
4. **Session reductions.** Answered ([Q4][answers]): MEDULA computes them from `ayniFarkliKesi` (Kılavuz kesin). The engine should take the session list price from the catalog, not the bill (`session_pricing.py:507-519`), and the claim model needs the incision field ([defect 3][defects]). The +25 points per session or per line: #295.
5. **S8 incision.** Answered ([Q5][answers]): same incision, 25 % (klinik yargı). Whether auditors challenge it: sahada sorulmalı.
6. **Implants.** Answered ([Q6a, Q6b][answers]): cemented stem + cement AP3220 (güçlü kanıt), applied in S5; KDV 10 % per material line (kesin). Stem, pack count and restrictor: sahada sorulmalı.
7. **Partial drug boxes.** Answered ([Q7][answers]): units used, fractions allowed (Kılavuz kesin). The claim model's int quantity is [defect 5][defects].
8. **R-codes as principal.** Answered ([Q8][answers]): R07.1 is correct (güçlü kanıt); N7 is a defect. R07.1 or Z03.5 on an acil takip: sahada sorulmalı.
9. **Companion.** Answered ([Q9][answers]): a doctor's order plus the refakatçi belgesi; no age condition (SUT kesin). The engine needs an eligibility input ([defect 4][defects]).
10. **Rounding.** Answered ([Q10][answers]): truncate (SUT kesin). What MEDULA displays for 510010 (222,35 or 222,36): sahada sorulmalı.
11. **ICU.** Answered ([Q11][answers]): its own takip, type Y (Kılavuz kesin). The engine's separate-claim model holds.
12. **ICD-10.** Answered ([Q12][answers]) and applied: K35.9 (S1), M48.06 (S3), S72.00 and M81.09 (S5). Leaf codes come from `icd10_tr.parquet` (`is_leaf`). Whether MEDULA rejects a parent code is unverified.
13. **Which noise to fix first.** Answered by events: N1–N13 are fixed except N7 (see the history table).

## Reproduction

Folder: `reports/synthetic-data/2026-10-15-showcase-proofs/` (see its README).
- `harness.py`: builds `ClaimHeader`/`ProcedureClaimLine`/`MaterialClaimLine`/`DrugClaimLine` as the unit tests do. It prices each EK-2B/EK-2C line from the catalog row in force and each EK-3/F-1 material from the curated list, and names each drug from the EK-4A row in force, which must have an ingredient in the crosswalk. It fails if not exactly one row matches. It enriches materials with the loader's `_enrich_material_regulatory_flags` and runs `compute_patient_billing_report` and `analyze_claim`.
- `stories.py`: the eight stories, clean and faulty.
- `prove.py`: calls each target detector directly, then diffs the full outputs. Output: `results/S1.json` … `results/S8.json`. It ends with a summary and exits 1 unless every target fires on the faulty bill only and every clean bill carries 0 TL.
- `render.py`: `results/S*_tables.md`.
- `checks.py`: the first draft's side checks (historical; its last block reads a scratch folder that no longer exists).
- Run from the repo root: `.venv/bin/python reports/synthetic-data/2026-10-15-showcase-proofs/prove.py`, then `render.py` (about 10 s).
- Run context (2026-10-16): engine = `main` 257d1e89 (`src/` unchanged on this branch) with the curated EK-3/F-1 list rebuilt on this branch.

[review]: ../../reports/synthetic-data/2026-10-16-v3-drafts-review.md
[answers]: ../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#answers-story-questions-plansdata2026-10-15-showcase-stories-draftmd
[defects]: ../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#engine-defects-found-to-file
[field]: ../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#questions-for-a-field-expert
