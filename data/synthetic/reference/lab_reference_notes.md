# Lab reference table (synthetic demo v3, P1)

Status: **reviewed 2026-10-16, corrections applied** (review: [`reports/synthetic-data/2026-10-16-v3-drafts-review.md`](../../../reports/synthetic-data/2026-10-16-v3-drafts-review.md); first draft 2026-10-15). Table: `lab_reference.csv` in this folder. `tests/unit/synthetic/test_reference_lab_table.py` checks every code, name and price against the catalog and pins the review corrections.

- **Facts:** codes, catalog names and prices come from `data/gazette/curated/ek2b_catalog_history.parquet` and are machine-verified.
- **Judgment:** every unit, range, abnormal state and panel. They are common adult values; analyzers differ.

## Reading the CSV

- **Rows and billed lines:**
  - One row per result parameter.
  - One `ek2b_code` is one billed line.
  - Multi-parameter tests emit every parameter under that one line: hemogram 15, urinalysis 10, blood gas 10, reticulocytes 2, PT 2.
  - The price repeats on each row. Never sum it across parameters.
- **Derived rows** are not billed: eGFR (CKD-EPI 2021), INR (computed from PT), transferrin saturation (Fe/TIBC) and Martin-Hopkins LDL (under total cholesterol, only when TG < 400). Emit each one only with its parent test.
- **Blood gas sample type:** two test keys bill the same L103900.
  - `blood_gas_arterial` has arterial ranges. Panels: icu_daily, respiratory, vte.
  - `blood_gas_venous` has venous ranges: pH about 0.03 lower, pCO2 about 5 mmHg and HCO3 about 1 mmol/L higher than arterial. Panels: dka_hhs, infection. Most ED, DKA and ward gases are venous.
  - Venous pO2 and sO2 are printed but not interpreted.
  - Na, K, iCa and BE have the same limits in both. Lactate: venous 0.5–2.2, arterial 0.5–1.6 mmol/L.
- **Blank reference cells** mean a one-sided limit:
  - Total cholesterol, LDL and triglycerides use decision limits.
  - HDL, eGFR and folate have no upper limit.
  - The qualitative urinalysis strip rows are graded `Negatif/Eser/+…++++`.
- **Age-adjusted limits are in the notes column:** ESR (M age/2, F (age+10)/2), D-dimer (age×10 above 50), NT-proBNP (450 at age ≥75), urea (55 above age 60, judgment). Creatinine follows eGFR (see Generation rules).
- **`abnormal_states`** has the form `state: range`, separated by `; `. The generator picks the state that matches the patient's condition.
  - A range that differs by sex is written `M a–b, F c–d`.
  - Creatinine states are eGFR bands.

## Panels (judgment)

| Panel | Tests |
|---|---|
| admission_routine | hemogram, glucose, urea, creatinine(+eGFR), sodium, potassium, alt, ast, crp |
| preop | admission_routine minus crp, plus pt_inr, aptt |
| outpatient_checkup | hemogram, glucose, urea, creatinine, alt, ast, lipids×4, tsh, urinalysis, esr, crp, ferritin, vitamin_b12 |
| diabetes | glucose, poc_glucose, hba1c, creatinine, lipids×4, urinalysis, urine_acr, alt |
| dka_hhs | glucose, poc_glucose, beta_hydroxybutyrate, hba1c, blood_gas_venous, sodium, potassium, chloride, urea, creatinine, magnesium, phosphorus, urinalysis, hemogram |
| ckd | creatinine, urea, sodium, potassium, calcium, phosphorus, pth, albumin, hemogram, ferritin, iron, tibc, urinalysis, urine_acr |
| liver_biliary | alt, ast, alp, ggt, total/direct bilirubin, albumin, lipase, pt_inr, crp, hemogram |
| acs | troponin_i (serial), ck_mb, ck, hemogram, glucose, hba1c, urea, creatinine, sodium, potassium, magnesium, lipids×4, pt_inr, aptt |
| heart_failure | nt_probnp, troponin_i, sodium, potassium, magnesium, urea, creatinine, alt, ast, albumin, hemogram, ferritin, iron, tibc, tsh |
| anticoagulation | pt_inr, aptt, hemogram, creatinine, alt, potassium, magnesium, tsh |
| vte | d_dimer, troponin_i, nt_probnp, blood_gas_arterial, hemogram, pt_inr, aptt, creatinine |
| infection | hemogram, crp, procalcitonin, lactate, blood_gas_venous, urea, creatinine, sodium, potassium, alt, ast, total_bilirubin, albumin, pt_inr, aptt, fibrinogen, d_dimer, urinalysis |
| icu_daily | every ICU day, 20 tests: hemogram, glucose, poc_glucose, urea, creatinine, sodium, potassium, chloride, calcium, magnesium, phosphorus, alt, ast, total_bilirubin, albumin, crp, pt_inr, aptt, lactate, blood_gas_arterial |
| icu_every_48_72h | procalcitonin, d_dimer, fibrinogen: every 48–72 h in the ICU, not daily |
| respiratory | blood_gas_arterial, hemogram, crp, procalcitonin, nt_probnp, urea, creatinine, sodium, potassium |
| anemia | hemogram, ferritin, iron, tibc, vitamin_b12, folate, reticulocytes |
| thyroid | tsh, free_t4 |

- lipids×4 = total cholesterol, HDL, triglycerides and LDL. LDL is the derived Martin-Hopkins row when TG < 400 and billed L105000 when TG ≥ 400.
- Six panels clash with same-date exclusions. The panels stay; see Generation rules.

## Catalog facts (verified)

- **Codes:**
  - All 50 codes (49, and L103120 since WP7) are in force on each of the 242 days from 2026-02-01 to 2026-09-30, with one row per day.
  - Names do not change across the window. No price changes in it (I1).
  - Added on 2026-10-16: L101560 "Beta hidroksibütirat (Serum/Plazma)" (28.30 TL), L102480 "Folat (Serum/Plazma)" (42.80 TL), L106530 "Retikülosit sayımı (Otomatik sistem)" (55.96 TL) and L105960 "Parathormon (PTH) (Serum/Plazma)" (46.06 TL).
- **Hemogram** is one line, L107020 "Tam Kan Sayımı (Hemogram)" (19.73 TL). EK-2B has no per-parameter codes. L103120 "Hematokrit (Manuel)" exists; never bill it next to a hemogram. Since WP7 (2026-10-21) it is a row of the CSV (`hematocrit_manual`, one parameter, the hemogram HCT's limits and states, plus `acute_gi_bleed: 20–33`), because story S10 bills it beside the hemogram on purpose, as its planted fault. Its value is an independent draw: it is not reconciled with the HCT the hemogram of the same sample derives from MCV and RBC.
- **eGFR, INR and BUN have no lab code** (I2).
  - The only GFR codes are nuclear-medicine measurements (801120–801122).
  - INR comes from the PT line L106430.
  - Urea is billed as "Üre".
- **Not L-codes:** cultures, serology and blood group use numeric codes. All are in force across the window (H5) and give qualitative results, so they are kept out of the CSV:
  - blood culture 906010/906020, urine culture 905671, culture with susceptibility 906060;
  - HBsAg 907440/907450, anti-HCV 906630/906640, anti-HIV 906660/906670;
  - ABO+Rh 705130/705140.
- **EK-2B "AÇIKLAMA"** is identical for all 49 codes in the 2026-01-31 and 2026-07-07 raw snapshots (I3):
  - L103900 Kan gazları: "Tüm parametreler dahildir". It is not billed with L101670/L101680, L103820/L103830, L103860, L104890/L104900, L106150/L106160 or L106910/L106920.
  - L100330 urine ACR is not billed with L104780, the serum creatinine.
  - L102820 HbA1c: once every 3 months.
  - L106220 NT-proBNP:
    - only when one of 7 specialties orders it (acil tıp, çocuk, göğüs hastalıkları, göğüs cerrahisi, iç hastalıkları, kardiyoloji, KVC);
    - never with BNP;
    - the Fatura İnceleme rule KARDİYOLOJİ-3 adds once per ED visit or admission.
  - L106530 automated reticulocytes is not billed with L106520, the manual count.
  - L101560, L102480 and L105960 have no açıklama.
- **MEDULA blood-gas result codes:** SGK's *MEDULA Hastane Web Servisleri Kullanım Kılavuzu* v3.1.1 (18.09.2026), p.254, lists blood-gas result codes KGAZ01–17. The PDF is not in the repo; this is the 2026-10-16 review's reading.
  - They include Na, K and iCa. Those values are reported as KGAZ05–07 parameters of the L103900 line.
  - They do not include lactate, so lactate is not a blood-gas result code. The `Laktat (kan gazı)` rows stay as analyzer values; how a hospital reports them to MEDULA is unverified.
  - `docs/medula/medula_capabilities.md:273` says blood gases go only through `KanBilgisiDVO`. That contradicts p.254 and is being filed as an issue.
- **Package bills:** on EK-2C package bills, lab tests are inside the package price (SUT 2.2.2.B-1(1)(ğ)). The window counts from the procedure date: A 15, B 10, C 8, D 5 and E 3 days (2.2.2.B-1(3)).

## Candidate codes: the pick and why

| Test | Picked | Alternatives | Reason |
|---|---|---|---|
| CRP | L101850 | L101840 latex, L106680 hsCRP | Quantitative mg/L. Latex and quantitative CRP are mutually exclusive. EK-2B orders hsCRP only when CRP is below the cut-off. |
| HbA1c | L102820 | L102830 HPLC, L102840 electrophoresis | EK-2B limits those two to diabetic patients at 3rd-level providers. |
| Troponin | L107360 I | L107370 T | Keep I (review Q3); S7 uses L107360. Choose one per facility. The limits are Abbott's sex-specific hs-cTnI 99th percentiles (M 34.2, F 15.6 ng/L). |
| CK-MB | L104770 mass | L104760 activity | Mass is fine (review Q3). The limits are Roche's 99th percentiles (M 6.22, F 4.88 ng/mL), so the two cardiac rows do not describe one analyzer. |
| Natriuretic peptide | L106220 NT-proBNP | L101320 BNP | Same price and mutually exclusive. The Fatura İnceleme rule names NT-proBNP. |
| D-dimer | L102090 quantitative | L102080 qualitative | Mutually exclusive. The quantitative test allows the age-adjusted cut-off. ng/mL FEU, cut-off 500 (review Q3). |
| Calcium | L103860 total | L103820/L103830 ionized | Routine. Ionized calcium comes with the blood gas (iCa row under L103900). |
| Urinalysis | L107010 | L103560 strip, L103570 microscopy | Mutually exclusive with both. |
| Blood gas | L103900 | L103910 with co-oximetry | Co-oximetry is needed only for CO poisoning or MetHb. Arterial or venous is the test key, not the code. |
| Lactate | L104890 plasma | L104900 blood; inside L103900 | Standalone only on days without a blood gas. |
| Ferritin / Na / K | serum codes | "(Kan)" variants | The serum and "(Kan)" codes are pairwise exclusive. |
| LDL | derived row under L104520 (TG < 400); L105000 direct (TG ≥ 400) | none | L105000 is the only LDL code, and nothing restricts it (review Q1). |
| β-hydroxybutyrate | L101560 serum | L104130/L104140 ketone bodies; L101570/L101580 urine | ADA 2024 uses serum BHB ≥3.0 mmol/L as the DKA ketone criterion. |
| Folate | L102480 serum | L102490 erythrocyte | Same price. Serum folate is the routine test. |
| Reticulocytes | L106530 automated | L106520 manual | Mutually exclusive. Hemogram analyzers count reticulocytes; manual counts are rare (judgment). |
| PTH | L105960 serum | L105970 body fluid; L105980/L105990 intraoperative | The serum test is the CKD-MBD test. |

## Engine behaviour the new cohort will hit (verified by probes)

1. **Hemogram unbundling: fixed.**
   - Until 2026-10-15, `_is_hemogram_subtest_line` matched CBC lines by name substrings of `HEMOGRAM_TESTS`, so "Glike hemoglobin (Hb A1c)" counted as a CBC line. Probe before the fix: 26.34 TL of "savings" on a clean bill.
   - Fixed in dff95fb8 (#270/#272). It now matches the CBC codes in `_CBC_CODES` (`src/bilun/domain/billing/claim_lab.py:25-27`: L107020, L103120) or an exact parameter name (`claim_lab.py:35-45`; names from `HEMOGRAM_TESTS`, `src/bilun/domain/constants.py:235-251`).
   - A clean claim with L107020 and L102820 on the same date is no longer flagged.
2. **Lab capture gap** (`detect_lab_capture_gaps`, `src/bilun/domain/prose_rules/lab_capture_gap.py:42-132`): it collects the L-codes in the lab feed's `test_name` (`:69-75`) and reports every one with no billed lab line (`:80-91`).
   - Derived rows must therefore carry the parent's code, whose billed line covers them.
   - Labs in an EK-2C package period, ACR on a creatinine date, and Na/K/Ca/lactate on a blood-gas date will show false gaps if their results are emitted under their own codes.
   - Review Q1 says `lab_capture_gap` must skip derived rows. The module has no notion of derived rows yet; that is an engine change.
3. **Duplicate test rule** (`detect_duplicate_tests`, `src/bilun/domain/prose_rules/common_billing_errors.py:278-345`, window at `:81`): the same code on a different claim within 7 days is flagged. It runs per patient over the patient's claim history (`src/bilun/domain/billing/focused_legacy_materializer.py:104-106`, `:130-131`). ED→ward and clinic→admission transitions are at risk.
4. **NT-proBNP:** KARDİYOLOJİ-3 fires on any L106220 line on a cardiology claim (probe: billable=False, warning). Expect it on clean heart-failure bills.
5. **Linkage:**
   - One billed lab line maps to one `lab_result_id` (`src/bilun/domain/claims/validation/lab.py:10-37`).
   - Today's `lab_clean.parquet` has no parameter column (only `SUB_CODE`). Multi-parameter tests need one.
6. **Lab-code map: fixed.**
   - `BILUN_TO_SUT_CODE` (`src/bilun/domain/constants.py:149-197`) feeds the "Lab Prices" API (`get_lab_prices`, `src/bilun/api/routes/pricing.py:193-207`).
   - Until 2026-10-15, PT and INR mapped to L106290 (PAP), aPTT to L100050 (an androgen metabolite), Prokalsitonin to L106230 (Progesteron) and Protein to L107180 (CDT).
   - Fixed in 6fe73720 (#271): they map to L106430, L101050, L106240 and L106300, and Kalsiyum and CRP to L103860 and L101850, the picks in this table. `tests/unit/domain/catalog/test_lab_code_map.py` pins each code's catalog name.
   - The generator must not reuse this map.

## Generation rules (judgment)

- **Keep values coherent:**
  - The differential sums to WBC.
  - MCV, MCH and MCHC follow from RBC, HGB and HCT; HCT ≈ 3×HGB.
  - RET% follows from RET# and the hemogram's RBC.
  - Direct bilirubin ≤ total bilirubin.
  - INR follows from PT.
  - **Creatinine follows from a target eGFR, age and sex.** Draw eGFR from the eGFR row's age band (normal) or the CKD stage, then invert CKD-EPI 2021 (formula in the creatinine row). Fixed creatinine bands ignore age: Scr 1.3 mg/dL is eGFR 71 (G2) for a 40-year-old man, not G3. The normal bands keep creatinine within its sex-specific limits at every age from 18 to 95 (checked numerically).
  - **LDL:** with TG < 400, compute Martin-Hopkins LDL from TC, HDL and TG and emit it as the derived row under L104520. With TG ≥ 400, bill L105000.
  - TSH and fT4 agree.
  - Blood glucose above about 180 gives glucosuria. SGLT2 inhibitors give glucosuria at any glucose.
- **Set `anormal_mi`** against the patient's sex-specific limits (troponin I: M 34.2, F 15.6 ng/L; CK-MB: M 6.22, F 4.88 ng/mL). Abnormal values come only from the patient's conditions; everything else is drawn from `normal_value_range`.
- **Same-date exclusions:**
  - On blood-gas dates, emit Na, K, iCa and lactate as L103900 parameters only.
  - Put ACR on a date with no serum creatinine.
  - Six panels clash with these exclusions:
    - lactate or Na/K with the blood gas: infection, icu_daily, respiratory, dka_hhs (icu_daily also has total calcium L103860);
    - creatinine with urine ACR: diabetes, ckd.
  - The panels stay as they are. **Decided by Safa, 2026-10-16: the demo data follows the SUT.** The generator emits one billed line; the other value goes under the blood-gas line or on another day, so a clean bill never carries a pair the EK-2B açıklama excludes ([review, Lab table corrections, item 7](../../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#lab-table-corrections)).
  - "Same date" is the default scope and should be a switch (answer 2 below).
- **Frequency limits:**
  - HbA1c at most once every 90 days.
  - NT-proBNP once per stay.
  - Serial troponin means 2 lines (0 h and 1–3 h).
  - ICU: icu_daily every day; icu_every_48_72h every 48–72 h.

## Review answers (2026-10-16)

Safa delegated the review; it answered the four questions of the first draft.

1. **LDL.** *Answered 2026-10-16* ([review](../../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#answers-lab-questions-datasyntheticreferencelab_reference_notesmd)).
   - Nothing restricts L105000: its açıklama is empty, and C006423 (SUT 4.2.28.A-1(a), an LDL threshold) names no method.
   - The generator emits Martin-Hopkins LDL as a derived row under L104520 when TG < 400 and bills L105000 when TG ≥ 400.
   - `lab_capture_gap` must skip derived rows.
   - Confidence: SUT kesin (no restriction); clinical güçlü kanıt (ESC/EAS 2019, EAS/EFLM 2020); practice **sahada sorulmalı** (do labs bill direct LDL routinely?).
2. **Scope of "birlikte faturalandırılmaz".** **Sahada sorulmalı** ([review](../../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#answers-lab-questions-datasyntheticreferencelab_reference_notesmd)).
   - No source defines the scope.
   - Of 1,136 açıklama rows with the phrase, 8 say "Aynı gün", 5 "Aynı seansta" and 31 "Tedavi süresince".
   - Keep same date as the default and make the scope a switch.
3. **Analyzers.** *Answered 2026-10-16*, klinik yargı ([review](../../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#answers-lab-questions-datasyntheticreferencelab_reference_notesmd)).
   - One platform. Keep troponin I (S7 uses L107360). The "same platform" note is removed; CK-MB mass is fine.
   - D-dimer in ng/mL FEU, cut-off 500, age-adjusted above 50.
   - A real Turkish lab printout would still replace the judgment ranges (field question for a biochemist).
4. **Engine bugs 1 and 6.** *Answered 2026-10-16*, verified ([review](../../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#answers-lab-questions-datasyntheticreferencelab_reference_notesmd)).
   - Fixed: hemogram (#270/#272) and the lab-code map (#271); verified on 257d1e89.
