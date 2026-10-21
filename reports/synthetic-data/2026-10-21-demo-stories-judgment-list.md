# Demo stories after S8: the `judgment` items and the premises for the clinician reviewer

Date: 2026-10-21. Same format as `reports/synthetic-data/2026-10-17-pathways-judgment-list.md` (the first eight stories). Plan: `plans/data/2026-10-20-demo-coverage-first-plan.md`. Each story gets its own section when it is built; so far S9, S11 and S12 (S10 is a later bill).

## Kısaca (Türkçe)
S9 (lomber spinal stenoz; dekompresyona ek olarak aynı seansta foraminoplasti; ikinci ameliyat yüzde 25 ile faturalanmış) için tarif dosyasında kaynağa dayanmayan 9 "judgment" kalem, hasta bağlamında (yaşam bulguları, tahlil durumu) 2 kalem var. Bunlara ek olarak **bir beyin cerrahının onaylaması gereken 3 varsayım** var; bunlar dosyada "judgment" değil "sut" olarak yazılı, ama hikâyenin doğruluğu onlara bağlı: (1) dekompresyondan sonra foraminoplastinin aynı seansta ayrı bir işlem olması, (2) foraminoplastinin ayrı bir kesiden yapılmış olması (SUT %50; aynı kesiden olsaydı %30), (3) iki ameliyatın toplam puanına göre tek bir "birden fazla ameliyat" anestezi satırı. Hasta uydurmadır; hiçbir gerçek hastaya ait değildir. Bu liste olmadan da veri çalışır, ama "klinisyen onaylı" denemez.

S11 (idrar kaynaklı sepsis ve septik şok, yoğun bakım yatışı; üç ara gün paketi yarı fiyatla faturalanmış) için tarif dosyasında 10 "judgment" kalem, hasta bağlamında 2 kalem var. Bunlara ek olarak **bir yoğun bakım uzmanının onaylaması gereken 4 varsayım** var: (1) yoğun bakım günü sayısı (5 gece = 5 gün; ilk ve son gün 510090, aradaki 3 gün P552002), (2) son 510090'ın hangi güne yazıldığı (SUT "ilk gün ile çıkarıldığı gün" diyor; motor gün sayısını çıkış − yatış olarak sayıyor, çıkış günü bu faturada yok), (3) basamak ve organ desteği (2. basamak; 3. basamak belgelenmiş organ desteği ister), (4) septik şokun kodu (SKRS tablosunda R57.2 yok, plan R57.1 demişti; o hipovolemik şok). Hasta uydurmadır. Bu liste olmadan da veri çalışır, ama "klinisyen onaylı" denemez.

S12 (geç preterm erkek bebek, yenidoğan sarılığı; kuvöz yatışı; 6 günün yalnız son 3'ü faturalanmış) için tarif dosyasında 5 "judgment" kalem, hasta bağlamında 1 kalem var. Bunlara ek olarak **bir neonatoloğun onaylaması gereken 5 varsayım** var: (1) yatağın kuvöz (510070) olması ve her takvim gününe, çıkış günü dahil, bir satır yazılması (yenidoğan yoğun bakımı değil; o 510090 + P552006-8 olurdu), (2) kuvöz yatışında refakatçi (510121) faturalanması (annenin bebeğin yanında kalması), (3) tanılar: P07.3 + P59.9 + Z38.0 (P59.0, yani "preterm doğumla birlikte sarılık", daha özgül kod), (4) yatış gününde pediatri konsültasyonu (520010), (5) bebeğin yaşam bulguları ve bu bebek için kullanılan "makul aralık" tablosu (tansiyon, nabız, boy 30-85 cm, kilo 0,4-12 kg). Faturada tahlil, fototerapi ve ilaç satırı yok; çünkü tahlil referans aralıkları erişkine göredir, yenidoğan aralıklarını bir neonatolog vermeden tahlil eklenmedi. Hasta uydurmadır. Bu liste olmadan da veri çalışır, ama "klinisyen onaylı" denemez.

## What this is
Every item below has `basis: judgment` in its file, or is a premise of the story that a clinician should confirm even though the file cites a rule for it. Each line says what the file uses and what it rests on. Please answer per line: fine, or change to X.

## S9 — `lumbar_stenosis_decompression_foraminoplasty_itemized`

Story: a woman of 77 with lumbar spinal stenosis and controlled hypertension has an elective unilateral decompression and a minimal-invasive foraminoplasty in one session, 2 nights in a neurosurgery ward, billed itemized (hizmet başı). The fault: the second operation is billed at 25 % of its list amount; the SUT pays it at 30 % (same incision) or 50 % (separate incision), so the hospital under-bills. The clean bill pays 50 %.

### Premises the neurosurgeon confirms (cited in the file, so not `judgment`, but the story depends on them)

- [ ] **A foraminoplasty after a decompression is a separate procedure of the same session.** Codes `615931` (unilateral decompression in a narrow spinal canal) and `615995` (minimal-invasive foraminoplasty, one or both sides) are both billed on the day of surgery. Is that a normal bill, or does the foraminoplasty belong inside the decompression (and so is not billed apart)? The pathway cites C000659 and C000661 (SUT 2.2.2.A(5)). If the answer is "inside", S9 has no second operation and the story must change.
- [ ] **The foraminoplasty goes through a separate incision (50 % of its puan, C000661).** With one incision the SUT pays 30 % (C000660). The claim model has no incision field, so the engine cannot tell; the demo bills 50 % as correct and reads 25 % as too low under both readings. If the surgeon says "same incision", the clean ratio becomes 30 %, which the cohort's price check (1, 0.5 or 0.25 of the list amount) does not accept: the pathway and the check must change together.
- [ ] **One multiple-operation anaesthesia line (`550220`, group A3) for the session.** The total puan of `615931` and `615995` is above 9000, which is group A3 from 2026-04-16; a single operation is group B (`550160`). The pathway keeps both variants as optional lines and pins the multiple one. An anaesthesiologist or the neurosurgeon confirms that a decompression with a foraminoplasty is billed as one multiple-operation anaesthesia and not as two.

### Items with `basis: judgment` in the pathway

- [ ] **Patient sexes**: M, F. Lumbar stenosis occurs in both sexes and M48.06 has no sex gate; story S9 is a woman. Clinician to confirm.
- [ ] **Patient age**: 55–80. Story S9 patient is 77. Stenosis surgery is mostly 55 and over. Max 80 keeps ASA 2 plausible: over 75 with ASA 3-4 the geriatric codes apply (not modelled).
- [ ] **Nights of stay**: 2–4. Story S9 has 2 nights. Min 2: one night can be under 24 h, billed as the day bed 510120 (C000648). Max 4 is the author's judgment for an elective decompression.
- [ ] **Diagnosis I10**: always in the bill. SKRS leaf code. Story S9: controlled hypertension, ASA 2 (the ASA Physical Status Classification lists well-controlled hypertension as an ASA 2 example).
- [ ] **procedure `foraminoplasty`: how often**: probability 0.3. How often a foraminoplasty joins a decompression is the author's judgment. Clinician to confirm.
- [ ] **procedure `anaesthesia_single`: how often**: probability 0.7. The variant with the decompression alone, as story S3; pinned out when the foraminoplasty is in.
- [ ] **procedure `anaesthesia_multiple`: how often**: probability 0.3. The variant with both operations; pinned in together with the foraminoplasty.
- [ ] **procedure `post_op_hemogram`**: L107020 on op+1. lab_reference_notes.md test hemogram (panels admission_routine, preop); story S9 bills it on the first post-op day only.
- [ ] **drug `paracetamol`**: PARTEMOL, 3 per night (vial). About 6 vials for 2 nights, read as 1 g three times a day (as story S3). Scaling with the nights is the author's judgment; no guideline named.

### Clinical context of patient 9 (`data/synthetic/cohort/showcase_clinical.yaml`, `basis: judgment`)

- [ ] **Vitals at admission**: blood pressure 134/78 mmHg, pulse 72, SpO2 97 %, height 161 cm, weight 69 kg (BMI 26.6). A woman of 77 with controlled hypertension, elective admission, stable.
- [ ] **Laboratory state**: the hemogram of the first post-operative day is drawn in the state `postop` for haemoglobin (as story S3), which gives low red-cell values (RBC 3.4, HCT 31 in the committed table). Clinician to confirm that a post-operative haemoglobin below normal is expected after a two-level operation and needs no transfusion in the story.

### What the story does not claim

- No drug price: the two drugs are billed at 0 ("fiyat yok"), as in every story.
- No complication, no ICU stay, no implant. A fusion (`614040`, `614050`) or facet denervation (`614900`) is not billed with `615931` (EK-2B açıklama) and is not on the bill.

## S11 — `urosepsis_septic_shock_icu_stay`

Story: a woman of 76 (born 1950) with urosepsis (A41.9, N39.0) and septic shock is admitted to a medical intensive care unit on 2026-06-02 and moves to a ward on 2026-06-07 (5 nights). Billed itemized (hizmet başı) with the EK-2/C ICU package between the end days: `510090` on day 0 and day 4, `P552002` on days 1 to 3, no ICU line on the transfer day, day-0 laboratory (hemogram, CRP, procalcitonin, lactate), two blood-culture sets, a urine culture, a urinary-tract ultrasound. The fault: the three package days are billed at 50 % of the list price (the clean bill: 100 %). The report shows `icu_puani` 6,089.82 TL (expected 13,664.87, billed 7,575.05); the clean twin is silent. The plan card said "6,089.84" and "a 0 TL row on the clean twin": the built result is 6,089.82 (4,059.89 × 1.5 on three lines, each rounded to the cent) and no row (the engine writes a row only for a shortfall).

### Premises the intensivist confirms (cited in the file, so not `judgment`, but the story depends on them)

- [ ] **ICU days.** The engine counts the ICU days of a bill as discharge − admission (5 here) and prices them as `510090` on the first and the last day plus one package per day between. The pathway puts the last `510090` on day 4 and leaves the transfer day (2026-06-07) empty. SUT 2.4.4.H.(8) (C001243) says the first day and "the day the patient leaves intensive care" are billed per service. If the exit day itself is the last `510090` day, the bill has six dates (`510090` on days 0 and 5, four packages) and the engine, which counts five days, would read it as over-billed. Which is the practice: the last ICU night or the exit day? Does the ward bill of the same patient (a later story) bill `510010` on the transfer day?
- [ ] **`510090` on both end days.** One `510090` per end day, quantity 1. On a package day the monitoring, ventilation, nebuliser, oxygen and tracheal aspiration are inside the package (EK-2B açıklama of 510090; C001234); no separate line is on the bill.
- [ ] **Level 2 (`P552002`).** A septic-shock patient on a vasopressor: second or third level? `P552003` needs documented organ support (mechanical ventilation, renal replacement, ECMO ...); `icu_tier_overbilling` reviews a third-level day billed without it. The unit's level comes from the Ministry's registration (C001233), not from the patient. The demo facility is a private 2nd-3rd step hospital, so the +100 % uplift of a Sınıf-3 facility (EK-2/C-1) is not applied; the unit stays dark in that respect.
- [ ] **Organ support is not on the bill.** No mechanical ventilation, dialysis, central line or arterial line; none is separately billable on a package day except the operations and treatments of C001234 and C001236. Is that too thin for a septic shock? (The story does not need it; the answer decides whether a richer bill is wanted later.)

### Items with `basis: judgment` in the pathway

- [ ] **Patient sexes**: M, F. Urosepsis with shock occurs in both sexes; A41.9, R57.8, N39.0 have no sex gate. Story S11 is a woman.
- [ ] **Patient age**: 60–90. Story S11 patient is 76. The bounds are the author's judgment.
- [ ] **Nights of stay**: 3–10. Story S11 has 5 nights. Min 3: `510090`, one package day, `510090`. Max 10 is the author's judgment for a septic-shock ICU stay.
- [ ] **Diagnosis R57.8** (`ŞOK, DİĞER`) for septic shock. The SKRS table has no R57.2 (septic shock, ICD-10 WHO), and R57.1 (the plan card's code) is *hypovolemik şok*. A41.9 is the primary diagnosis (organism not named on the bill). Coder to confirm; if SKRS lists septic shock under another leaf, the pathway changes.
- [ ] **Department** `Yoğun Bakım` with the EK-2A branch `1000` (İç Hastalıkları) on every line. Is a medical ICU billed under the internal-medicine branch, or under anaesthesia and reanimation (`3100`)? Plausibility has no rule on it.
- [ ] **Day-0 laboratory**: hemogram, CRP, procalcitonin, lactate (one result set each). Surviving Sepsis Campaign hour-1 bundle (lactate, cultures) plus the infection markers of the story. No repeat lactate on day 1 or 2, no blood gas, no creatinine or urea. Clinician to confirm.
- [ ] **Two blood-culture sets (`906020`, quantity 2) and one urine culture.** As story S4; no guideline paragraph is quoted.
- [ ] **Urinary-tract ultrasound** (`803580`, radiology) on day 0 as the first source-control imaging step. No CT.
- [ ] **No drug lines.** The antibiotic and the vasopressor are left out on purpose: drug prices stay 0 in the demo and a drug line would add a drug-indication review the story does not need. A septic-shock ICU stay without a drug is thin; the intensivist says whether to add noradrenaline and a carbapenem later.

### Clinical context of patient 10 (`data/synthetic/cohort/showcase_clinical.yaml`, `basis: judgment`)

- [ ] **Vitals at ICU admission**: blood pressure 84/46 mmHg, pulse 124, SpO2 91 %, height 158 cm, weight 66 kg (BMI 26.4). Septic shock presentation (the clinical file accepts a systolic pressure from 70 mmHg up).
- [ ] **Laboratory states**: WBC `bacterial_infection` (17.3 in the committed table), CRP `sepsis` (272 mg/L), procalcitonin `septic_shock` (40.7 ng/mL), lactate `septic_shock` (7.6 mmol/L). Clinician to confirm that these values fit a patient on a package-billed ICU day 0.

### What the story does not claim

- No second facility, no Sınıf-3 uplift (`ilave_oran_reason` is `not_sinif_3`), no ward bill (the transfer to the ward is a later story, S14), no companion bed (the engine suppresses `510121` on ICU days).
- Side effects on the report, none of them the fault: checklist rows `ORTAK-17`, `ORTAK-21` (it reads the ICU package as a surgical one: engine item EI-16 of the plan) and `ORTAK-27`; a `refakatci` row of 0 TL ("suppressed for ICU stay"); a `yatak_puani` row of 0 TL whose text calls the first package days a "surgery day bundled into an EK-2/C package window" although the stay is an ICU stay (the engine reads `P552002` as a surgical package here; reported in the hand-over as an engine item, not fixed).

## S12 — `late_preterm_newborn_incubator_stay`

Story: a boy born on 2026-07-10 at about 35 weeks (P07.3, with neonatal jaundice P59.9 and the birth status Z38.0) is admitted to the neonatal ward (department `Yenidoğan`, EK-2A branch `1561` Neonatoloji) on the day of birth and stays 5 nights in an incubator, until 2026-07-15. Billed itemized (hizmet başı): the incubator `510070` on every calendar day (6 lines, the discharge day included), the companion `510121` on the 5 nights, one paediatric consultation `520010` on the admission day. The fault: only the last three incubator lines are on the bill, the first three days (07-10 to 07-12) were not keyed. The report shows `yenidogan_yatak` 1,322.94 TL (expected 6 × 440.98 = 2,645.88, billed 1,322.94); the clean twin is silent (the engine writes the row with a recoverable amount of 0.00 and the report carries no `yenidogan_yatak` money). The record amount equals the report amount (clean total 3,049.55, faulty 1,726.61). The plan card said "Kuvöz ×3 on day 0"; the built bill has one incubator line per day. The fault sits on the first days so that the last day of the stay carries an incubator line: a later ward bill that starts on the discharge day (story S15) then overlaps a newborn bed line, which is the finding that story needs. (The WP3 card said "Kuvöz on the first days only", the S12 card "the fault sits on the first days"; the second reading is the one that serves S15, and it is what is built.)

### Premises the neonatologist confirms (cited in the file, so not `judgment`, but the story depends on them)

- [ ] **The bed is the incubator on every day of the stay, the discharge day included.** EK-2B 510070 (Kuvöz) "covers yemek, yatak and vizit, is billed once a day and not with 510081"; 510081 (Kot, beşik) is the cot and is not billed for a baby who is followed beside the mother ("anne yanında izlenen bebekler"). The engine counts `discharge − admission + 1` days (6 for 5 nights). Is a late-preterm baby with jaundice in an incubator for all five nights, or in a cot after the first nights? A stay that changes from Kuvöz to Kot is allowed by the grammar and priced by the engine (each Kot day at the Kot rate).
- [ ] **A newborn ward, not newborn intensive care.** The bill has no ICU line. Newborn intensive care would be `510090` on the first and the last day with `P552006-8` between (the ICU grammar of S11), and the newborn bed motor leaves such a claim to the ICU motor. Is a late-preterm baby in an incubator for jaundice a ward stay in practice, or does the hospital bill it as intensive care?
- [ ] **The companion `510121` is billed beside an incubator.** SUT 2.6.3(2) (C001628) lets the hospital bill the companion's bed and meals with 510121; for a child under 18 no medical-need statement is asked (C001627). Is the mother billed as the companion of a baby in an incubator? The engine's companion motor expects the five nights whatever the age and the bed (a bill without the line would show a second finding, `refakatci` 370.50), so the line is on the clean and the faulty bill alike. If the neonatologist says it is not billed, the story needs a change in the engine (companion suppressed for an incubator stay) or a different bill.
- [ ] **The first three days are the ones that are missing.** The story assumes the incubator lines of the first days were not keyed (for example, the days before the baby had its own registration). Does that happen? The fault could as well sit on any three days; only the first-days placement serves the later ward bill (S15).
- [ ] **Diagnoses: `P07.3` (primary), `P59.9`, `Z38.0`.** P07.3 covers 28 to under 37 completed weeks. `P59.0` (neonatal jaundice associated with preterm delivery) is the more specific code for a preterm baby with jaundice; the plan card has `P59.9`. The engine reads any `Z38` or `P00-P96` code, or a department named yenidoğan, as the signal of a newborn episode; the choice changes no number. Coder or neonatologist to confirm which is right.

### Items with `basis: judgment` in the pathway

- [ ] **Patient sexes**: M, F. Late-preterm birth and neonatal jaundice occur in both sexes; P07.3, P59.9 and Z38.0 have no sex gate. Story S12 is a boy.
- [ ] **Patient age**: 0..0. The baby was born on the day of admission. The claim carries a birth year only, so the age is 0 years (the engine cannot see the day of birth).
- [ ] **Nights of stay**: 3–10. Story S12 has 5 nights. A late-preterm baby with jaundice stays a few days; 3 and 10 are the author's judgment.
- [ ] **Diagnosis `P59.9`** (neonatal jaundice, unspecified): see the premise on `P59.0` above.
- [ ] **Procedure `pediatric_consult`**: `520010` with the branch `1500` (Çocuk Sağlığı ve Hastalıkları) on the admission day, beside the unit's own rounds (the bed covers vizit). The plan card has the line; which branch the unit would really ask (paediatric cardiology for an echocardiogram, paediatric surgery, ophthalmology) is the author's choice. 520010 açıklama: the branch must be written.

### Clinical context of patient 11 (`data/synthetic/cohort/showcase_clinical.yaml`, `basis: judgment`)

- [ ] **Vitals at admission**: blood pressure 62/36 mmHg, pulse 148, SpO2 96 %, length 46 cm, weight 2.4 kg (BMI 11.3). A late-preterm baby of about 35 weeks on the day of birth.
- [ ] **The "plausible range" table for a baby under one year** (`VITALS_RANGES["infant"]` in `scripts/synthetic/cohort/clinical.py`, `INFANT_VITALS_BOUNDS` in `plausibility_clean.py`): systolic 40–130 mmHg, diastolic 20–90, pulse 80–220 per minute, SpO2 60–100 %, length 30–85 cm, weight 0.4–12 kg. These are hard bounds ("outside can only be a bug"), wide enough for a newborn and for an infant of 11 months; the adult table was 70–260, 40–150, 30–220, 60–100, 120–210 cm, 30–200 kg. The age decides the table (age 0 is the baby table); a child of 1 to 17 has no table yet. Neonatologist to confirm the numbers.
- [ ] **No laboratory state.** The bill has no laboratory line (see below), so patient 11 has no `labs` block.

### What the story does not claim

- No laboratory line: `lab_reference.csv` holds adult reference ranges only, and a bilirubin or hemogram of a newborn needs neonatal ranges, which only a neonatologist can supply; the age-aware laboratory bounds of the plan's slice G4b are therefore not built (nothing needs them yet). No phototherapy code, no drug (drug prices stay 0 in the demo and a drug line would add a drug-indication review), no material.
- No rooming-in (the baby beside the mother): the engine never receives that fact (`rooming_in_claim_ids` has no caller; issue EI-14 of the coverage plan), so the Kot rule "not for rooming-in babies" cannot be shown.
- No ward bill after the incubator (the next bill of this patient is story S15).
- Side effects on the report, none of them the fault: a `refakatci` row of 0 TL (370.50 expected, 370.50 billed), a `yatak_puani` row of 0 TL whose text says that all 6 days are newborn bed days and not standard-bed days (the two bed motors agree on the days), 9 informational `billing_strategy` rows ("only in EK-2/B, bill itemized"), checklist rows `ORTAK-27` and `ORTAK-29`. No copay row. Wave A: the patient evaluates 185 rule ids and matches 10 (`ORTAK-13`, `-14`, `-19`, `-22`, `-25`, `-28` and four general itemized-billing rules); all 10 were already matched by other patients, so the cohort's Wave A numbers do not move.
- The generated history sentence of the clinical table says "0 yaşında erkek hasta" (the history template knows years only, not days of life).
