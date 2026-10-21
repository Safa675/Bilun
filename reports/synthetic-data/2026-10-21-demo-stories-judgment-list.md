# Demo stories after S8: the `judgment` items and the premises for the clinician reviewer

Date: 2026-10-21. Same format as `reports/synthetic-data/2026-10-17-pathways-judgment-list.md` (the first eight stories). Plan: `plans/data/2026-10-20-demo-coverage-first-plan.md`. Each story gets its own section when it is built; so far only S9.

## Kısaca (Türkçe)
S9 (lomber spinal stenoz; dekompresyona ek olarak aynı seansta foraminoplasti; ikinci ameliyat yüzde 25 ile faturalanmış) için tarif dosyasında kaynağa dayanmayan 9 "judgment" kalem, hasta bağlamında (yaşam bulguları, tahlil durumu) 2 kalem var. Bunlara ek olarak **bir beyin cerrahının onaylaması gereken 3 varsayım** var; bunlar dosyada "judgment" değil "sut" olarak yazılı, ama hikâyenin doğruluğu onlara bağlı: (1) dekompresyondan sonra foraminoplastinin aynı seansta ayrı bir işlem olması, (2) foraminoplastinin ayrı bir kesiden yapılmış olması (SUT %50; aynı kesiden olsaydı %30), (3) iki ameliyatın toplam puanına göre tek bir "birden fazla ameliyat" anestezi satırı. Hasta uydurmadır; hiçbir gerçek hastaya ait değildir. Bu liste olmadan da veri çalışır, ama "klinisyen onaylı" denemez.

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
