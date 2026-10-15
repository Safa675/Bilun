# Lab reference table (synthetic demo v3, P1)

Status: **draft for Safa's review** (2026-10-15). Table: `lab_reference.csv` in this folder. `tests/unit/synthetic/test_reference_lab_table.py` checks every code, name and price against the catalog.

- **Facts:** codes, catalog names and prices come from `data/gazette/curated/ek2b_catalog_history.parquet` and are machine-verified.
- **Judgment:** every unit, range, abnormal state and panel. They are common adult values; analyzers differ.

## Reading the CSV

- **Rows and billed lines:**
  - One row per result parameter.
  - One `ek2b_code` is one billed line.
  - Multi-parameter tests emit every parameter under that one line: hemogram 15, urinalysis 10, blood gas 7, PT 2.
  - The price repeats on each row. Never sum it across parameters.
- **Derived rows** are not billed: eGFR (CKD-EPI 2021), INR (computed from PT) and transferrin saturation (Fe/TIBC). Emit each one only with its parent test.
- **Blank reference cells** mean a one-sided limit:
  - Total cholesterol, LDL and triglycerides use decision limits.
  - HDL and eGFR have no upper limit.
  - The qualitative urinalysis strip rows are graded `Negatif/Eser/+…++++`.
- **Age-adjusted limits are in the notes column:** ESR (M age/2, F (age+10)/2), D-dimer (age×10 above 50), NT-proBNP (450 at age ≥75).
- **`abnormal_states`** has the form `state: range`. The generator picks the state that matches the patient's condition.

## Panels (judgment)

| Panel | Tests |
|---|---|
| admission_routine | hemogram, glucose, urea, creatinine(+eGFR), sodium, potassium, alt, ast, crp |
| preop | admission_routine minus crp, plus pt_inr, aptt |
| outpatient_checkup | hemogram, glucose, urea, creatinine, alt, ast, lipids×4, tsh, urinalysis, esr, crp, ferritin, vitamin_b12 |
| diabetes | glucose, poc_glucose, hba1c, creatinine, lipids×4, urinalysis, urine_acr, alt |
| dka_hhs | glucose, poc_glucose, hba1c, blood_gas, sodium, potassium, chloride, urea, creatinine, magnesium, phosphorus, urinalysis, hemogram |
| ckd | creatinine, urea, sodium, potassium, calcium, phosphorus, albumin, hemogram, ferritin, iron, tibc, urinalysis, urine_acr |
| liver_biliary | alt, ast, alp, ggt, total/direct bilirubin, albumin, lipase, pt_inr, crp, hemogram |
| acs | troponin_i (serial), ck_mb, ck, hemogram, glucose, hba1c, urea, creatinine, sodium, potassium, magnesium, lipids×4, pt_inr, aptt |
| heart_failure | nt_probnp, troponin_i, sodium, potassium, magnesium, urea, creatinine, alt, ast, albumin, hemogram, ferritin, iron, tibc, tsh |
| anticoagulation | pt_inr, aptt, hemogram, creatinine, alt, potassium, magnesium, tsh |
| vte | d_dimer, troponin_i, nt_probnp, blood_gas, hemogram, pt_inr, aptt, creatinine |
| infection | hemogram, crp, procalcitonin, esr, lactate, blood_gas, urea, creatinine, sodium, potassium, alt, ast, total_bilirubin, albumin, pt_inr, aptt, fibrinogen, d_dimer, urinalysis |
| icu_daily | 23 tests: infection minus esr/urinalysis, plus glucose, poc_glucose, chloride, calcium, magnesium, phosphorus |
| respiratory | blood_gas, hemogram, crp, procalcitonin, nt_probnp, urea, creatinine, sodium, potassium |
| anemia | hemogram, ferritin, iron, tibc, vitamin_b12 |
| thyroid | tsh, free_t4 |

## Catalog facts (verified)

- **Codes:**
  - All 45 codes are in force on each of the 242 days from 2026-02-01 to 2026-09-30, with one row per day.
  - Names do not change across the window. No price changes in it (I1).
- **Hemogram** is one line, L107020 "Tam Kan Sayımı (Hemogram)" (19.73 TL). EK-2B has no per-parameter codes. L103120 "Hematokrit (Manuel)" exists; never bill it next to a hemogram.
- **eGFR, INR and BUN have no lab code** (I2).
  - The only GFR codes are nuclear-medicine measurements (801120–801122).
  - INR comes from the PT line L106430.
  - Urea is billed as "Üre".
- **Not L-codes:** cultures, serology and blood group use numeric codes. All are in force across the window (H5) and give qualitative results, so they are kept out of the CSV:
  - blood culture 906010/906020, urine culture 905671, culture with susceptibility 906060;
  - HBsAg 907440/907450, anti-HCV 906630/906640, anti-HIV 906660/906670;
  - ABO+Rh 705130/705140.
- **EK-2B "AÇIKLAMA"** is identical in the 2026-01-31 and 2026-07-07 raw snapshots (I3):
  - L103900 Kan gazları: "Tüm parametreler dahildir". It is not billed with L101670/L101680, L103820/L103830, L103860, L104890/L104900, L106150/L106160 or L106910/L106920.
  - L100330 urine ACR is not billed with L104780, the serum creatinine.
  - L102820 HbA1c: once every 3 months.
  - L106220 NT-proBNP:
    - only when one of 7 specialties orders it (acil tıp, çocuk, göğüs hastalıkları, göğüs cerrahisi, iç hastalıkları, kardiyoloji, KVC);
    - never with BNP;
    - the Fatura İnceleme rule KARDİYOLOJİ-3 adds once per ED visit or admission.
- **Package bills:** on EK-2C package bills, lab tests are inside the package price (SUT 2.2.2.B-1(1)(ğ)). The window counts from the procedure date: A 15, B 10, C 8, D 5 and E 3 days (2.2.2.B-1(3)).

## Candidate codes: the pick and why

| Test | Picked | Alternatives | Reason |
|---|---|---|---|
| CRP | L101850 | L101840 latex, L106680 hsCRP | Quantitative mg/L. Latex and quantitative CRP are mutually exclusive. EK-2B orders hsCRP only when CRP is below the cut-off. |
| HbA1c | L102820 | L102830 HPLC, L102840 electrophoresis | EK-2B limits those two to diabetic patients at 3rd-level providers. |
| Troponin | L107360 I | L107370 T | Choose one per facility (analyzer). Troponin I shows the sex-specific limits. |
| CK-MB | L104770 mass | L104760 activity | Runs on the same immunoassay platform as troponin. |
| Natriuretic peptide | L106220 NT-proBNP | L101320 BNP | Same price and mutually exclusive. The Fatura İnceleme rule names NT-proBNP. |
| D-dimer | L102090 quantitative | L102080 qualitative | Mutually exclusive. The quantitative test allows the age-adjusted cut-off. |
| Calcium | L103860 total | L103820/L103830 ionized | Routine. Ionized calcium comes with the blood gas. |
| Urinalysis | L107010 | L103560 strip, L103570 microscopy | Mutually exclusive with both. |
| Blood gas | L103900 | L103910 with co-oximetry | Co-oximetry is needed only for CO poisoning or MetHb. |
| Lactate | L104890 plasma | L104900 blood; inside L103900 | Standalone only on days without a blood gas. |
| Ferritin / Na / K | serum codes | "(Kan)" variants | The serum and "(Kan)" codes are pairwise exclusive. |
| LDL | L105000 (direct) | none | It is the only LDL code (see check 1). |

## Engine behaviour the new cohort will hit (verified by probes)

1. **False hemogram-unbundling finding.**
   - `src/bilun/domain/billing/claim_lab.py:28-37` matches CBC lines by name keywords from `constants.py:228-244`. "Glike hemoglobin (Hb A1c)" contains "hemoglobin".
   - So a clean claim with L107020 and L102820 on the same date is flagged (`:80-83`).
   - Probe: 26.34 TL of "savings" were reported on a clean bill.
2. **Lab capture gap** (`prose_rules/lab_capture_gap.py:74-136`): any L-code that has results but no billed line on the claim is reported as unbilled.
   - Derived rows must therefore carry the parent's code.
   - Labs in an EK-2C package period, ACR on a creatinine date, and Na/K/Ca/lactate on a blood-gas date will show false gaps if their results are emitted under their own codes.
3. **Duplicate test rule** (`prose_rules/common_billing_errors.py:81`, `:284-351`): the same L-code on a different claim of the same patient within 7 days is flagged. ED→ward and clinic→admission transitions are at risk.
4. **NT-proBNP:** KARDİYOLOJİ-3 fires on any L106220 line on a cardiology claim (probe: billable=False, warning). Expect it on clean heart-failure bills.
5. **Linkage:**
   - One billed lab line maps to one `lab_result_id` (`claims/validation/lab.py:10-37`).
   - Today's `lab_clean.parquet` has no parameter column (only `SUB_CODE`). Multi-parameter tests need one.
6. **Wrong codes in `BILUN_TO_SUT_CODE`** (`src/bilun/domain/constants.py:148-196`):
   - PT and INR map to L106290 (PAP).
   - aPTT maps to L100050 (an androgen metabolite).
   - Prokalsitonin maps to L106230 (Progesteron).
   - Protein maps to L107180 (CDT).
   - The "Lab Prices" API and UI show those prices (`api/routes/pricing.py:189-203`). The generator must not reuse this map.

## Generation rules (judgment)

- **Keep values coherent:**
  - The differential sums to WBC.
  - MCV, MCH and MCHC follow from RBC, HGB and HCT; HCT ≈ 3×HGB.
  - Direct bilirubin ≤ total bilirubin.
  - INR follows from PT, and eGFR from creatinine, age and sex.
  - TC ≈ LDL + HDL + TG/5.
  - TSH and fT4 agree.
  - Blood glucose above about 180 gives glucosuria. SGLT2 inhibitors give glucosuria at any glucose.
- **Set `anormal_mi`** against the patient's sex-specific limits. Abnormal values come only from the patient's conditions; everything else is drawn from `normal_value_range`.
- **Same-date exclusions:**
  - On blood-gas dates, emit Na, K, iCa and lactate as L103900 parameters only.
  - Put ACR on a date with no serum creatinine.
- **Frequency limits:**
  - HbA1c at most once every 90 days.
  - NT-proBNP once per stay.
  - Serial troponin means 2 lines.

## For Safa to check

1. **LDL.** Either bill L105000 (direct) on every lipid panel, or emit no LDL and only compute it (Friedewald) when needed. An emitted but unbilled LDL is flagged as a gap.
2. **Scope of "birlikte faturalandırılmaz".** I assumed it means the same date, not the whole claim. This decides how ICU, DKA and sepsis days handle the blood gas next to serum Na/K/Ca/lactate, and ACR next to creatinine.
3. **Analyzer choices.** Troponin I or T, CK-MB mass, and whether the facility prints D-dimer in ng/mL or µg/mL FEU. The ranges are judgment. A real Turkish lab printout would replace them.
4. **Engine bugs 1 and 6 above.** File them as issues and fix them before P7, or the clean cohort shows false findings and the UI shows wrong lab prices.
