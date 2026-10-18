# Clinical plausibility review of the showcase lab and prescription tables (slice C2)

Date: 2026-10-17. Scope: `lab_clean` (207 rows), `recete_clean` (19 rows) and `anadata_clean` (8 rows) of `data/synthetic/showcase/` at commit f445ea0a.
Author: a read-only Claude subagent (not a clinician). Every value quoted below was read from the committed files; statements marked "my clinical judgment" rely on knowledge, not on data.
Use: input for the clinician review (issue #309). Nothing here changed the data. The orchestrator verified two of its claims against the files: story S7 says D-dimer 920 ng/mL FEU while `lab_clean` holds 710 for patient 7; and the CRP pairs are 114 to 18 (patient 4), 119 to 14 (patient 6) and 96 to 24 (patient 2).

---

r2b clinical review, read-only (nothing written in the repo; notes in /home/safa/.cache/bilun-p4-scratch/r2b/NOTES.md). All 207 lab and 19 recete rows read; arithmetic recomputed.
Clean: differential sums = WBC; eGFR = CKD-EPI 2021 (±0.5); ABG pH/HCO3/BE/SaO2 follow Henderson-Hasselbalch, the BE formula and Severinghaus exactly; limits, units, flags = CSV (207/207); rows per billed line match.
No single value is out of physiological range. What a clinician sees: the course between two samples, and values that are too tidy.
**(a) Verdicts** (patients 5 and 8: no rows, by design)
| P | story | verdict | key rows |
|---|---|---|---|
| 1 | M34 appendicitis, POD1 | questionable (minor) | 07-15 CRP 181 mg/L, WBC 14.1; rest fine |
| 2 | M81 COPD+pneumonia | OK, polish | 03-09 ABG 7.30/58/56, HCO3 28.2, SaO2 88.7 coherent; 03-12 7.41/40.0/66 too tidy; CRP 96→24 acceptable on steroid |
| 3 | F77 decompression, POD1 | questionable | 08-19 HGB 10.8, HCT 30.0, MCHC 36.0, WBC 6.0 |
| 4 | F86 pyelonephritis | wrong on one row, else questionable | 05-13 CRP 18 (114 on 05-11, at the kinetic floor); Na 131, urea 67.5 never rechecked |
| 6 | M79 aspiration pneumonia | questionable | 06-11 CRP 14 (119 on 06-08), WBC 7.6, HCT 47.0 after 3 L saline; Rx timeline |
| 7 | F58 ER chest pain | questionable | 02-19 D-dimer 710 (story says 920); hs-TnI 4.9 then 7.2 |
**(b) Ranked objections** (my clinical judgment unless a value is quoted; Fix = state/YAML/CSV change, "pathway" = recete edit)
1. P4 05-11→05-13 CRP 114→18 (−84 %/48 h); P6 06-08→06-11 119→14 (−88 %/72 h); P2 03-09→03-12 96→24 (−75 %/72 h). CRP t½ ≈19 h gives floors 19.8 / 8.6 / 6.9 mg/L: P4 is at/below its floor (synthesis would have had to stop before the 1st sample), P6 needs it to stop within ~13 h, P2 within ~34 h (fine under steroid).
   Cause: 2nd state `viral_or_mild_inflammation` (5–40, draws 12–33) ignores the 1st value. Fix: new CSV state `bacterial_infection_resolving` = 35–65 % of the 1st CRP (P2 25–50 %) as 2nd state of patients 2, 4, 6.
2. P7 02-19 D-dimer 710 ng/mL FEU, but story S7, the pathway note and the judgment list say 920. `elderly_without_vte` (400–900, effective draw 500–800) cannot give 920, falls under the age cut-off 580 in 27 % of draws (CT then unjustified), and is mis-named for age 58.
   Fix: pin 920 or correct the text to 710; new state `above_age_cutoff_no_vte` = age×10+20 … 1200.
3. P6 recete: PK-MERZ 06-09, MADOPAR only 06-10, nothing dopaminergic on 06-08: ≥48 h without levodopa in "advanced" PD; MADOPAR 125 ×4/day = 400 mg levodopa/day (a starter dose), route "Ağızdan (Oral)" though the story gives it by NG tube.
   Fix (pathway): NG tube and levodopa from 06-08, 5×/day; route "Nazogastrik sonda" via drug_routes barcode 8699525094841.
4. P7 02-19 hs-TnI 4.9 then 7.2 ng/L (Δ+2.3, +47 %): two independent draws from 4.7–10.9 (30–70 % of the F limit 15.6); healthy women sit near 1–4 ng/L. The ESC 0/2 h rule-out the story cites needs, as I recall for this assay, 0 h <6 and Δ <2 ng/L (not verified).
   Fix: state `normal_low` F 1.5–4.5 for hs-TnI and a pair rule |Δ| ≤1.0.
5. P6 06-11 day 4: WBC 7.6 (NEU 60.5 %, LYM 32.1 %), CRP 14, with a control film next day and 3 nights left; HGB 14.9→15.3, HCT 44→47 after 3 × 1 L NaCl (expect −0.5…−1.0 g/dL).
   Fix: day-4 WBC 9–11 with NEU ~70 %, HGB 14.0–14.6, HCT 41–43.
6. P3 08-19: `postop` (HGB 8.5–11.5, draws 9.1–10.9) is a major-surgery state; 10.8 = −1.7…−2.7 g/dL from a 12.5–13.5 baseline (≈650–950 mL before dilution), a lot for a unilateral decompression. MCHC 36.0 and HCT/HGB 2.78 sit at the ceiling; WBC 6.0, LYM 32.5 % show no POD1 stress; MCV 86 and RDW 13.5 are on the low side for 77.
   Fix: `postop_minor_blood_loss` F 10.5–12.2; MCHC ≤35.5; `postop_stress` WBC 9–13, NEU 70–80 %.
7. P1 07-15 CRP 181 on POD1 of an uncomplicated appendicitis (one pre-op antibiotic dose, none after) is complicated-disease level; `bacterial_infection` 50–250 is a pneumonia range.
   Fix: new `appendicitis_postop_day1` 40–120 (`postop_day2_3` 80–200 is for POD 2–3).
8. P4 05-11: urea 67.5, Na 131, HR 104, BP 108/62 = hypovolaemia, yet no IV fluid in recete (P6 has one) and no Na/urea recheck 05-13; creatinine 1.03→1.11 (eGFR 53→48) worsens on day 3 (two independent `ckd_g3a` draws).
   Fix (pathway): add a NaCl 0.9 % line; force day-3 creatinine ≤ 1st (eGFR 53–59).
9. P2 03-12 pH 7.41, pCO2 40.0, HCO3 25.1, a healthy gas in a COPD retainer (admission HCO3 28.2); if both gases are room air the A–a gradient widens by 12.5 mmHg, against recovery.
   Fix: pCO2 2nd state `copd_baseline_hypercapnia` 45–52 (HCO3 then derives to 28–31).
10. All patients: too tidy, see (c3, c4).
**(c) Not caught by the coherence rules**
1. Red-cell indices re-drawn per sample: P2 MCV 89→93; P4 MCH 29→31 with RBC −12.0 %, HGB −5.6 %, HCT −8.9 %; P6 HCT +6.8 % vs HGB +2.7 % (MCHC 33.9→32.6). Expected: MCV/MCH/RDW/MPV ±1 %, RBC/HGB/HCT move together. Fix: patient baseline plus one dilution factor.
2. MCHC is accepted anywhere in the reference limits 32–36 (labs.py): 36.0 P3 08-19, 32.0 P4 05-11; HCT/HGB 2.78 (P3) vs 2.95–3.12 elsewhere; LYM 1.00 (P2 03-12) and BASO 0.10 (P4 05-11) sit exactly on a limit. Fix: accept MCHC 32.5–35.5.
3. Normals are the middle 40 % of the reference interval for every parameter: 112/157 normal values in the middle third; MCV 86–93, MCH 29–31, RDW 12.6–13.5, PLT 231–320, MPV 9.2–10.2: 45/45 inside 30–70 % (a population gives ~57 %). Age-blind: F86 HGB 14.4/HCT 45.0, M79–81 HGB 14.9–15.3; glucose 84–90 in four acutely ill patients.
4. Precision: HCT, MCV, MCH whole numbers in 9/9 samples (HCT 45.0 in P1, P2, P4); RBC 1 decimal (analyzers print 2); no differential % (printouts show # and %); ABG without FiO2/Cl/tHb/temperature; urine pH not in strip 0.5 steps (P4 7.0 fits by chance); urinalysis without bacteria/epithelium/casts/bilirubin/urobilinogen. P4 urine is otherwise coherent: SG 1.021, pH 7.0, protein Eser, blood Negatif↔RBC 1, LE ++↔WBC 68, nitrite Pozitif.
5. Unpaired draws: hs-TnI 0/2 h, D-dimer vs age cut-off, day-3 CRP vs 1st, P4 creatinine. Text vs data: S6 "1.1 mg/dL at 72 kg" vs 0.97 at 63 kg (Cockcroft-Gault CrCl 55.0 either way, so the amantadine logic holds). FYI coding: P2 pH 7.30/pCO2 58 (J96.x), P4 Na 131 (E87.1), P3 Hb 10.8 (D62/D64.9) carry no matching code.
**(d) Prescriptions**
- Fit diagnosis, day and route: P1 ceftriaxone 1 g + metronidazole once; P2 ceftriaxone 1 g×7, KLACID 500 mg×10, PREDNOL-L 40×5, CLEXANE×6; P3 cefazolin 2 g, paracetamol 3 g/day (light for spine surgery: no NSAID or opioid); P4 ceftriaxone 2 g/day×5; P6 ceftriaxone×7; P7 paracetamol 1 g. Whole boxes, course lengths, PK-MERZ units: already raised, not repeated.
- P6 NaCl 0.9 % 1 L/day ×3 while NPO (63 kg): no K or glucose, and Na/K/glucose/creatinine never rechecked (06-11 is CBC+CRP only) beside renally cleared amantadine. P6 MADOPAR: see (b3).
- P4 CLEXANE 40 mg and ceftriaxone 2 g/day at Cockcroft-Gault CrCl 35.9 (05-11) → 33.3 mL/min (05-13; 58 kg, 86 y): above the 30 mL/min cut-off but close; eGFR 53/48 flatters it.
- P2 PREDNOL-L 40 mg ×5 with glucose only on 03-09 (89); KLACID raises methylprednisolone exposure (CYP3A4) and adds QT risk with salbutamol; no ECG billed.
- Format: "Intravenöz" (plain I) in 12 rows vs "İntravenöz" in the 2 IM/IV rows; EQIZOLIN (pre-incision) and PREDNOL-L carry either/or "IM/IV" (use IV); doz_mg and doz_birimi NULL 19/19, siklik NULL 11/19, dozaj_ham is a count ("5 flakon", "1 kutu"): no dose or frequency can be read.
**(e) Missing companions** (observations; bills fixed)
P1 urinalysis; pre-op CBC/CRP (on the ER takip, so the file shows no pre-op value). P2 repeat ABG within hours of starting oxygen (pH 7.30, pCO2 58), glucose days 2–5, NT-proBNP/troponin (81 y, HR 108, SpO2 88 %), albumin, K/creatinine day 4, ECG (non-lab). P3 none essential. P4 Na/urea/glucose recheck, lactate or PCT, albumin, TSH/B12/Ca for delirium. P6 BMP recheck, albumin (BMI 21.3), lactate or ABG (SpO2 90 %, no oxygen line), CK. P7 PT/INR, aPTT.
**(f) Hard bounds** (outside = bug; units as in the file)
| group | hard min – max |
|---|---|
| WBC; NEU, LYM, MONO, EOS, BASO | 0.1–100; each 0–WBC, sum = WBC ±0.05 |
| RBC; HGB; HCT; HCT/HGB | 1.0–8.5; 3.0–23.0; 10–70; 2.74–3.57 (= 100/MCHC) |
| MCV; MCH; MCHC; RDW-CV; PLT; MPV | 50–130; 15–45; 28–36.5; 10–40; 2–1500; 4–16 |
| CRP; PCT; D-dimer; hs-TnI | 0–500; 0–500; 0–35000; 0–100000 |
| glucose; urea; creatinine; eGFR | 20–1500; 3–400; 0.2–25; 1–150 (= CKD-EPI ±0.5) |
| Na; K (serum and ABG); ALT, AST | 100–175; 1.5–9.0; 1–20000 |
| pH; pCO2; pO2; HCO3; BE; SaO2 | 6.60–7.80; 8–150; 15–650; 2–55; −35…+35; 30–100 (never >100.0; keep HH and Severinghaus ties) |
| lactate; iCa | 0.2–30; 0.40–2.20 |
| urine SG; pH; WBC, RBC /HPF; strips | 1.001–1.045; 4.5–9.0; 0–500; Negatif/Eser/+…++++/Pozitif |
Paired samples (same patient, ≤7 d): |ΔMCV| ≤2, |ΔMCH| ≤1, |ΔRDW| ≤0.5, |ΔMPV| ≤1.0; CRP(t) ≥ CRP(0)×0.5^(h/19); |ΔCr| ≤0.3 mg/dL and |ΔNa| ≤8 mmol/L per 48 h unless the story is AKI.
**(g) Not verified**: ESC 0/2 h thresholds and the CRP half-life are from memory (a web lookup failed to return the table). No real Turkish printout in the repo: CSV ranges are judgment; I disagree only with the MCHC window, pO2 ≥80 ignoring age, and the urea limit 48.5 not age-adjusted (notes say 55 above 60; no flag changes). No temperature or time stamps in any record (0 h/2 h troponin only by row order); lab_result_id is empty on all claim lines, so row-to-line linkage was checked by counts only. I read /home/safa/Documents/Bilun/.claude/worktrees/p4-generator/scripts/synthetic/cohort/labs.py but ran nothing from the repo (my checks are checks*.py in /home/safa/.cache/bilun-p4-scratch/r2b/, copy of this report: final_draft.md there).
