# Care pathways: the `judgment` items for the clinician reviewer (Q3)

Date: 2026-10-17. Pathways: `data/synthetic/pathways/` (plan `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`, phase P2). The list below was extracted from those files by a one-off script; if a pathway changes, edit this list by hand.

## Kısaca (Türkçe)
8 tarifte kaynağa dayanmayan 77 "judgment" kalemi var. Bunlar yazarın (yapay zekânın) kendi tahminidir: hasta yaşı ve cinsiyeti, yatış gece sayısı, ilaç kürü süresi, eşlik eden hastalıkların sıklığı ve hikâyede bulunan ama bir kılavuza bağlanmamış bazı tahlil, görüntüleme ve ilaç kalemleri. Hikâyelerin kendisi (hangi işlem, hangi ilaç) 2026-10-16 incelemesinden geçti; bu liste yalnızca genellemeleri ve kaynaksız kalemleri gösterir. Bir hekim ya da faturalama uzmanı her satır için "uygun" ya da "şuna çevir" demeli; cevaplar tarif dosyalarına işlenir. Bu işin tamamı kritik yol değildir: tarifler bu liste olmadan da çalışır, ama demo verisi "klinisyen onaylı" denilemez.

## What this is
Every item below has `basis: judgment` in its pathway file: nothing citable (no SUT clause, no EK-2B açıklama, no Kılavuz page, no named guideline) decides it. Each line says what the pathway uses and what it is anchored on. Please answer per line: fine, or change to X. Pins that reproduce the reviewed showcase stories are not judgments; the ranges around them are.

## Items (77)

### S1 — `appendicitis_lap_appendectomy_package`

- [ ] **Patient sexes**: M, F. Appendicitis occurs in both sexes and K35.9 has no sex gate; story S1 is a man. Clinician to confirm.
- [ ] **Patient age**: 18–70. Story S1 patient is 34. Adults only: children go to paediatric surgery. The upper bound is the author's judgment.
- [ ] **Nights of stay**: 1–4. Story S1 has 2 nights. Group C package window is 8 days (C000704), so up to 7 nights stay inside the package.

### S2 — `copd_exacerbation_pneumonia_ward`

- [ ] **Patient sexes**: M, F. COPD and pneumonia occur in both sexes and J44.0 has no sex gate; story S2 is a man. Clinician to confirm.
- [ ] **Patient age**: 55–90. Story S2 patient is 81. Both bounds are the author's judgment of who is admitted with this picture.
- [ ] **Nights of stay**: 4–9. Story S2 has 6 nights. Min 4 because the day-5 chest X-ray is fixed (admit+4); max is the author's judgment.
- [ ] **Diagnosis I10**: optional. Story S2 lists I10 as a comorbidity; the story gives no source.
- [ ] **Diagnosis I10: how often**: probability 0.6. Story S2 patient has hypertension. How often it comes with this picture is the author's judgment. Clinician to confirm.
- [ ] **procedure `chemistry_admission`**: L102890 + L104780 + L107420 + L100300 + L101280 on admit. lab_reference_notes.md panel admission_routine (judgment) without Na/K, which the blood gas L103900 excludes.
- [ ] **procedure `cbc_crp`**: L107020 + L101850 on admit, admit+3. lab_reference_notes.md panels admission_routine and respiratory (judgment); story S2 bills both on day 1 and day 4.
- [ ] **procedure `procalcitonin`**: L106240 on admit. lab_reference_notes.md panels infection and respiratory (judgment); story S2 bills it on day 1 only.
- [ ] **procedure `blood_culture`**: 906020 on admit, quantity 2. Review 2026-10-16 (S2): two blood-culture sets; no guideline named. Clinician to confirm.
- [ ] **procedure `sputum_culture`**: 905675 on admit. Story S2 orders a sputum culture on day 1; no guideline named.
- [ ] **procedure `chest_xray`**: 801720 on admit, admit+4. Story S2: an admission film and a control film on day 5; no guideline named.
- [ ] **drug `ceftriaxone`: course days**: 5–7. Story S2 bills 7 vials of 1 g, read as 1 g a day for 7 days (ATS/IDSA 2019 regimen). The range is the author's judgment.
- [ ] **drug `ipratropium_salbutamol`**: IPRAVENT, quantity 1 (box). Story S2 bills one whole box (20 nebules) for the stay, so unit box; no guideline named.
- [ ] **drug `enoxaparin`**: CLEXANE, 1 per night (syringe). Review 2026-10-16 (S2): thromboprophylaxis where guidelines expect it, 40 mg a day; guideline not named.

### S3 — `lumbar_stenosis_decompression_itemized`

- [ ] **Patient sexes**: M, F. Lumbar stenosis occurs in both sexes and M48.06 has no sex gate; story S3 is a woman. Clinician to confirm.
- [ ] **Patient age**: 55–80. Story S3 patient is 77. Stenosis surgery is mostly 55 and over. Max 80 keeps ASA 2 plausible: over 75 with ASA 3-4 the geriatric codes apply (not modelled).
- [ ] **Nights of stay**: 2–4. Story S3 has 2 nights. Min 2: one night can be under 24 h, billed as the day bed 510120 (C000648). Max 4 is the author's judgment for an elective decompression.
- [ ] **Diagnosis I10**: always in the bill. SKRS leaf code. Story S3: controlled hypertension, ASA 2 (the ASA Physical Status Classification lists well-controlled hypertension as an ASA 2 example).
- [ ] **procedure `post_op_labs`**: L107020 + L104780 on op+1. lab_reference_notes.md tests hemogram and creatinine (panels admission_routine, preop); story S3 bills both on the first post-op day only.
- [ ] **drug `paracetamol`**: PARTEMOL, 3 per night (vial). Review 2026-10-16 (S3): about 6 vials for 2 nights, read as 1 g three times a day. Scaling with the nights is the author's judgment; no guideline named.

### S4 — `pyelonephritis_dementia_delirium_ward`

- [ ] **Patient sexes**: M, F. Pyelonephritis, dementia and delirium occur in both sexes; N10, F05.1, G30.1 and I10 have no sex gate. Story S4 is a woman. Clinician to confirm.
- [ ] **Patient age**: 65–95. Story S4 patient is 86. WHO ICD-10 notes G30.1 (late onset) as 'usually after the age of 65', so 65 is the floor; the upper bound is the author's judgment.
- [ ] **Nights of stay**: 4–7. Story S4 has 5 nights. Min 4: the fixed 5-day ceftriaxone course (admit..admit+4) must end by discharge. Max 7: two nights past it, author's judgment.
- [ ] **Diagnosis I10**: optional. Story S4 lists I10 as a comorbidity; the story gives no source.
- [ ] **Diagnosis I10: how often**: probability 0.7. Story S4 patient has hypertension. How often it comes with this picture is the author's judgment (common over 80). Clinician to confirm.
- [ ] **procedure `admission_labs`**: L107020 + L101850 + L102890 + L104780 + L107420 + L106910 + L106150 + L100300 + L101280 on admit. lab_reference_notes.md panel admission_routine (judgment); story S4 bills it on day 1. No blood gas, so the Na/K exclusion does not apply.
- [ ] **procedure `urinalysis`**: L107010 on admit. lab_reference_notes.md panel infection (judgment) includes urinalysis; story S4 bills it on day 1 with the urine culture.
- [ ] **procedure `urine_culture`**: 905671 on admit. Story S4 clean bill: a urine culture on day 1; no guideline named.
- [ ] **procedure `blood_culture`**: 906020 on admit, quantity 2. Review 2026-10-16 (S4): two blood-culture sets; no guideline named. Clinician to confirm.
- [ ] **procedure `control_labs`**: L107020 + L101850 + L104780 on admit+2. Story S4 repeats hemogram, CRP and creatinine on day 3 (admit+2); a subset of panel admission_routine (judgment); no guideline named.
- [ ] **procedure `urinary_ultrasound`**: 803580 on admit. Review 2026-10-16 (S4) added the urinary-tract ultrasound on day 1; no guideline named.
- [ ] **drug `paracetamol`**: PARACEROL, quantity 1 (box). Story S4 bills a whole box of 12 vials (PARACEROL) for the stay, not vials used; the story gives no indication or guideline. Clinician to confirm.
- [ ] **drug `enoxaparin`**: CLEXANE, 1 per night (syringe). Story S4: enoxaparin 40 mg a day; review 2026-10-16: x5 for 5 nights. Guideline not named. Clinician to confirm.

### S5 — `femoral_neck_fracture_cemented_hemiarthroplasty_package`

- [ ] **Patient sexes**: F. Story S5 is a woman. M81.09 is postmenopausal osteoporosis, which a man cannot carry, and a pathway cannot tie a diagnosis to a sex. Clinician to confirm.
- [ ] **Patient age**: 70–95. Story S5 patient is 84 and walked with a walker, so hemiarthroplasty fits (NICE CG124 1.6.3, as the story cites). Both bounds are the author's judgment.
- [ ] **Nights of stay**: 4–8. Story S5 has 5 nights. Min 4: operated on day 1, then three nights. Max 8 is the author's judgment; the group B package window is 10 days (C000703).
- [ ] **Diagnosis I10**: optional. Story S5 lists I10 as a comorbidity; the story gives no source.
- [ ] **Diagnosis I10: how often**: probability 0.6. Story S5 patient has hypertension. How often it comes with a hip fracture at this age is the author's judgment. Clinician to confirm.
- [ ] **Diagnosis M81.09**: optional. SKRS leaf code, site unspecified because story S5 has no DXA (review 2026-10-16 Q12). The story gives no source for the osteoporosis.
- [ ] **Diagnosis M81.09: how often**: probability 0.4. Story S5 patient has osteoporosis, no DXA on file. How often a hip fracture bill carries M81.09 is the author's judgment. Clinician to confirm.
- [ ] **material `bone_cement`**: AP3220 quantity 2. Story S5 bills two 40 g packs; the review gives AP3220 x1-2 beside the stem options (Q6a): a field question. Billed apart, C002859 (SUT 3.1.4(2)(b)).

### S6 — `aspiration_pneumonia_parkinson_ward`

- [ ] **Patient sexes**: M, F. Parkinson's disease and aspiration pneumonia occur in both sexes; G20 and J69.0 have no sex gate. Story S6 is a man. Clinician to confirm.
- [ ] **Patient age**: 60–90. Story S6 patient is 79. Advanced Parkinson's disease with aspiration pneumonia is a disease of old age; both bounds are the author's judgment.
- [ ] **Nights of stay**: 4–9. Story S6 has 6 nights. Min 4 because the day-5 control chest X-ray is fixed (admit+4); max is the author's judgment.
- [ ] **Diagnosis I10**: optional. Story S6 lists I10 as a comorbidity; the story gives no source.
- [ ] **Diagnosis I10: how often**: probability 0.6. Story S6 patient has hypertension. How often it comes with this picture is the author's judgment. Clinician to confirm.
- [ ] **procedure `neurology_consult`**: 520010 on admit. Story S6: neurology consultation on day 1; the amantadine specialist report is the neurologist's (C006824). 520010 açıklama: write the branch.
- [ ] **procedure `ecg`**: 530100 on admit. Review 2026-10-16 (S6): a baseline ECG for the QT interval before IV amantadine; no guideline named.
- [ ] **procedure `chemistry_admission`**: L102890 + L104780 + L107420 + L106910 + L106150 + L100300 + L101280 on admit. lab_reference_notes.md panel admission_routine (judgment) without hemogram and CRP, which cbc_crp bills. No blood gas is billed, so Na and K stay.
- [ ] **procedure `cbc_crp`**: L107020 + L101850 on admit, admit+3. lab_reference_notes.md panels admission_routine and infection (judgment); story S6 bills both on day 1 and day 4.
- [ ] **procedure `blood_culture`**: 906020 on admit. Story S6 bills one blood-culture set on day 1; no guideline named. 906020 açıklama: not with 906010, which is not billed.
- [ ] **procedure `chest_xray`**: 801720 on admit, admit+4. Story S6: an admission film on day 1 and a control film on day 5; no guideline named.
- [ ] **procedure `ng_tube`**: 530340 on admit+2. Review 2026-10-16 (S6): nasogastric tube on day 3, levodopa through it. 530340 açıklama: at most one a day; one line here.
- [ ] **drug `sodium_chloride`**: NEOFLEKS, 1 per day (bag). Review 2026-10-16 (S6): IV NaCl 0.9 %, 1000 ml a day on days 1-3 while nil by mouth; no guideline named.
- [ ] **drug `sodium_chloride`: course days**: 3–3. Story S6: 1000 ml a day on days 1-3 while nil by mouth; the course ends on the fixed NG-tube day (admit+2), so min = max.
- [ ] **drug `ceftriaxone`: course days**: 5–7. Story S6 bills 7 vials of 1 g, read as 1 g a day for 7 days. ATS/IDSA 2019: at least 5 days, until clinically stable. The upper bound is the author's judgment.
- [ ] **drug `enoxaparin`**: CLEXANE, 1 per night (syringe). Story S6: enoxaparin 40 mg a day; review 2026-10-16: 6 syringes. One syringe per night of stay; guideline not named.
- [ ] **drug `pk_merz`: course days**: 2–4. Story S6 gives days 2-4, one 500 ml bottle a day, while oral levodopa is impossible. The range is the author's judgment; a neurologist confirms.
- [ ] **drug `levodopa_benserazide`**: MADOPAR, 4 per day (tablet). Review 2026-10-16 (S6): levodopa through the NG tube from day 3. Story S6 bills 20 tablets over days 3-7, 4 a day; no guideline named.
- [ ] **drug `levodopa_benserazide`: course days**: 3–8. Story S6: levodopa through the NG tube on days 3-7, 20 tablets (4 a day). The course length (3 to 8 days) is the author's judgment, bounded by the stay.

### S7 — `pleuritic_chest_pain_er_pulmonary_embolism_ruled_out`

- [ ] **Patient sexes**: M, F. Pleuritic chest pain and dyspnoea occur in both sexes; R07.1 and R06.0 have no sex gate. Story S7 is a woman. Clinician to confirm.
- [ ] **Patient age**: 18–80. Story S7 patient is 58. Adults only; 80 is the author's judgment. The story's D-dimer 920 is above the age-adjusted cut-off at every age in range.
- [ ] **procedure `ecg`**: 530100 on admit. Story S7: a 12-lead ECG at presentation with chest pain (530100 açıklama: 12 derivasyonlu); no guideline named.
- [ ] **procedure `blood_routine`**: L107020 + L104780 + L102890 + L106910 + L106150 on admit. Story S7: CBC, creatinine, glucose, sodium, potassium; lab_reference_notes.md panels vte and admission_routine (judgment).
- [ ] **procedure `d_dimer`**: L102090 on admit. Story S7: D-dimer 920 ng/mL FEU, above the age-adjusted cut-off of 580 (age x 10 above 50, lab_reference_notes.md); it leads to the CT.
- [ ] **procedure `chest_xray`**: 801720 on admit. Story S7: a PA chest film for pleuritic pain and dyspnoea; no guideline named.
- [ ] **drug `paracetamol_iv`**: PARTEMOL, quantity 1 (vial). Review 2026-10-16 (S7): paracetamol, 1 vial; taken as analgesia for the pleuritic pain. No guideline named.
- [ ] **performed line `ecg_emr`**: 530100 (emr) on admit. Story S7: the EMR log shows the ECG; the bill carries it too.
- [ ] **performed line `iv_line_emr`**: 530080 (emr) on admit. Story S7: the EMR log shows the IV line; the bill carries it too.
- [ ] **performed line `chest_xray_emr`**: 801720 (emr) on admit. Story S7: the EMR log shows the chest X-ray; the bill carries it too.
- [ ] **performed line `ct_angiography_pacs`**: R101450 (pacs) on admit. Story S7: the PACS log shows the CT angiography; the bill carries it too.

### S8 — `cholelithiasis_umbilical_hernia_two_packages`

- [ ] **Patient sexes**: M, F. K80.2 and K42.9 have no sex gate. Gallstones are more frequent in women but occur in men; story S8 is a woman. Clinician to confirm.
- [ ] **Patient age**: 18–75. Story S8 patient is 47. Adults only: children go to paediatric surgery. The upper bound is the author's judgment for an elective case without comorbidity.
- [ ] **Nights of stay**: 1–3. Story S8 has 1 night. Max 3 is the author's judgment (slow recovery after laparoscopic surgery); the group C window of 8 days (C000704) would allow 7 nights.

## Questions that wait for a field expert (marked `pending` in the pathways)
- **#297 Q2** (companion lines of S2, S3, S4, S6): whether the discharge day counts in `refakatciGunSayisi`. The pathways bill one 510121 line per night.
- **#297 Q4** (S2 blood gas): whether "birlikte faturalandırılmaz" applies to the same date only or to the whole stay. The pathway bills no Na/K beside the blood gas.
- Not marked, still open in the review: whether auditors challenge a port-site hernia repair (S8), the stem and cement count for the hip (S5), R07.1 against Z03.5 as principal on an acil takip (S7), the neurologist's view of IV amantadine beside NG levodopa (S6).

## Observations raised by the agents who wrote the pathways (the stories are unchanged)
1. **S4 paracetamol is a whole box** of 12 vials, while the review corrected S1, S3 and S7 to vials used.
2. **S4 antibiotic course**: the story's 5-day IV ceftriaxone stands alone; EAU gives 7–10 days in all (at least 2 weeks for men), so a 6–7-night stay shows no antibiotic after day 5.
3. **S4 enoxaparin 40 mg** is billed with no renal function stated.
4. **S6 levodopa** runs from day 3 but the format cannot tie its end to discharge; the composer must clamp it. PK-MERZ overlaps NG levodopa on days 3–4 (the open neurologist question).
5. **S6 antibiotics**: ceftriaxone without a macrolide; the ATS/IDSA 2019 inpatient regimen adds one (possibly left out for QT). Full-dose amantadine is clean at CrCl above 50 only, and the age range reaches 90.
6. **S6 blood cultures**: one set, while the review raised S2 and S4 to two.
7. **S7**: whether hospitals send two troponin lines or one line with quantity 2 is not verified; the story gives no indication for the paracetamol.
8. **S8**: the review says MEDULA's `ayniFarkliKesi` code 1 marks the second operation; the claim model has no such field, so the pathway holds only the session role and the expander derives the 25 % ratio. Same incision (25 %) against separate incision (50 %) is a surgeon's call.
9. **S3**: the minimum stay is 2 nights because a stay under 24 hours is billed as the day bed 510120, which the format cannot express. The anaesthesia code does not depend on age and ASA in the format; the age cap and a note carry that.
10. **S5**: women only, because M81.09 (postmenopausal osteoporosis) cannot be tied to a sex in the format. The catalog name of the head AP1880 embeds amendment text; if the extractor ever strips it, the name check fails here.
11. **S1**: its showcase fault (a coder keys the EK-2B code and the stay goes itemized) needs an itemized sibling pathway for the same operation; that is phase P3 work.
