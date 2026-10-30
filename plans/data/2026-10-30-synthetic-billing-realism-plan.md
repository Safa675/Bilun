# Synthetic billing realism: the practitioner review of 2026-10-30

Date: 2026-10-30
Status: **plan only.** No code, data or check was changed. Every "confirmed" below is file:line evidence read on `main` 3723c885; everything else is marked as Ahmet Bey's statement, a question, or unverified.
Branch: `claude/synthetic-billing-realism-plan` (base `main` 3723c885).
Ask (Safa, 2026-10-30): Safa reviewed the bills of three showcase patients with Ahmet Bey (billing practitioner). The same mistakes recur on every bill, so fix them where they are made: in the generator, guarded by cohort-wide checks, then the pathway contents, then check whether the engine shares the same assumptions.

## Kısaca (Türkçe)

1. **Hatalar tekrar ediyor çünkü üretici kuralında yazılı.** Dördü kodda doğrulandı: yakınma alanı ICD'den üretiliyor (`clean.py:380`); ilaç kürün ilk gününe tek satır yazılıyor (`pathways/README.md:54`); yatak çıkış günü dahil yazılıyor (`README.md:44`, 21 yatış pathway'inden 13'ü); yatıştan önce acil/poliklinik faturası zorunlu değil.
2. **En önemli bulgu motorda.** `yatak_puani.py:6-9` çıkış gününün SUT gereği faturalandığını varsayıyor ve yatak kazanç fırsatlarını buna göre hesaplıyor. Mevcut `stay.bed_coverage` kontrolü de aynısını zorunlu kılıyor. Ahmet Bey "son gün yatak girilmez" diyor. Haklıysa motor, doğru kesilmiş faturalarda olmayan bir eksik faturalama buluyor olabilir. **Bu yüzden yatak kuralı, kaynakla çözülene kadar hiçbir yerde değiştirilmiyor** (WP0).
3. **Sıra:** WP0 (Ahmet Bey'e sorular + SUT metni) paralelde başlar. Cevap beklemeyenler önce: WP1 yakınma ve tedavi notu, WP2 günlük ilaç satırı, WP3 yatıştan önce giriş faturası. Cevaba bağlı olanlar sonra: WP4 yatak günü, WP5 acil kuralları, WP6 yatış içeriği ve kontrol süresi. WP7 motor denetimi WP0'dan sonra.
4. **Her kural önce bir kohort kontrolü olarak yazılır** ve bugünkü veride kırmızı yandığı gösterilir; sonra üretici düzeltilir ve kontrol yeşile döner. Böylece aynı hata başka bir pathway'de tekrar edemez.
5. **Motor değişikliği bu planın parçası değil.** WP7 yalnız aynı varsayımı taşıyan motor kurallarını listeler, para etkisini ölçer ve issue açar; değişiklik ayrı karar.

## 1. What Ahmet Bey said (Safa's notes, grouped)

| # | Statement | Scope |
|---|---|---|
| A1 | A stay is never billed directly: the patient first comes through an `acil` or `poliklinik` visit, which is its own bill; then the stay. "Fatura 1'i 2'ye bölmek gerekiyor." | every stay |
| A2 | No bed line on the last (discharge) day. | every stay |
| A3 | Drugs are entered on every day of the stay, not only on the first. | every stay |
| A4 | `yakınma` is the patient's complaint; we write the ICD code instead, on every patient. Complaints are missing everywhere. | every bill |
| A5 | No ICD code can be entered on an `acil` bill. | every acil bill (meaning to confirm, Q4) |
| A6 | The appendicitis ER visit lacks a general surgery consultation. | acil → surgical stay |
| A7 | The ER ultrasound should be an abdominal ultrasound, not "Ultrason, genel". | patient 1 |
| A8 | Control visits inside the control period are not billed; the periods follow the operation groups (A 15, B 10, C, D, E); operations not billed as a package have no control period. | post-operative controls |
| A9 | Stays lack IV access ("Granül - damar yolu girişi", Q1), a urinary catheter, in-stay labs (bills 2 and 3) and a treatment note (`tedavi notu`). | stays |
| A10 | A consultation ("EHU", Q2) is missing. | one stay |
| A11 | Patient 3, bill 2 starts with an orthopaedic examination; "L1 L2 L3" (Q3). | patient 3 |

Patient 1 is the appendicitis patient of S1/S30 (the ER ultrasound is on 2026-07-14, S30's date). Patients 2 and 3 are as Safa labelled them in the review; their stories are to be named in WP0.

## 2. Where the generator makes them (confirmed on `main` 3723c885)

| Statement | Cause |
|---|---|
| A4 | `scripts/synthetic/cohort/clean.py:380`: `yakinma = f"Başvuru tanısı: {primary_name} ({primary_code})."` for every claim. The treatment note comes from the same `_build_narratives` (`clean.py:421`). |
| A3 | `data/synthetic/pathways/README.md:54`: "A **drug** is one line on the first day of its course with the whole quantity"; `scripts/synthetic/pathways/expand.py:82` returns `per_day * course_days` as one quantity. |
| A2 | `data/synthetic/pathways/README.md:44`: `admit..discharge` is "a bed for every calendar day, discharge day included"; 13 of the 21 `yatis` pathways bill the bed `admit..discharge` and say so in a comment. |
| A2 (check) | `scripts/synthetic/cohort/plausibility.py:95` `stay.bed_coverage`: "one bed line a day, admission..discharge". The check enforces the practice Ahmet Bey calls wrong. |
| A1 | No rule. Some stays have an ER bill before them (S30 before S1, S10 before S22, `copd_exacerbation_readmission_through_er`); nothing requires it. |
| A7 | `data/synthetic/pathways/appendicitis_er_visit_ultrasound.yaml`: 803602 "Ultrason, genel" (the source line cites a guideline, not a billing practice). |
| A5 | The same pathway codes K35.9 as the primary diagnosis of the `acil` bill. |

## 3. The engine shares at least one of these assumptions (confirmed)

- `src/bilun/domain/prose_rules/yatak_puani.py:6-9`: "inclusive LOS = (discharge - admission).days + 1 — the discharge day IS billed per the Turkish SUT convention ('standart yatak gönderilmelidir' …). Matches the existing `drg.py:225` LOS convention." The bed-day opportunity (expected charge = inclusive LOS × price) rests on it.
- If A2 is right, a correctly billed stay is missing nothing, yet the engine expects one more bed day and can report it as recoverable. **This is a possible false positive in a money-bearing rule.** Not measured yet (WP7).
- Not yet read: whether drug rules read quantities per line or per date (A3), whether any rule reads an `acil` diagnosis (A5), and how controls inside a package window are treated (A8).

## 4. Work packages

Rules for every WP: one branch and one PR from current `main`; **the check first**: write the cohort-wide check, show it fails on today's committed data (the failing claims listed in the PR), then fix the generator or pathways until it passes; regenerate with `.venv/bin/python -m scripts.synthetic.cohort.build` and prove it with `--check`; record every change in the engine-proof stories (`tests/unit/synthetic/test_cohort_engine_proof.py`) as expected and explained; full suite and the CI-image gate green.

### WP0. Questions and sources (starts now; blocks WP4, part of WP5 and WP6)

1. Find the SUT and MEDULA text on the discharge-day bed: the sentence behind "standart yatak gönderilmelidir" cited in `yatak_puani.py`, with its article number and the date it is in force. Put it next to Ahmet Bey's statement.
2. Ask Ahmet Bey (paste-ready, Turkish):
   - S1. "Granül - damar yolu girişi" ile neyi kastettiniz? Damar yolu açılması işlemi mi (hangi kod), yoksa başka bir kalem mi?
   - S2. "EHU konsültasyonu" hangi branş? Hangi hastada eksik?
   - S3. Hasta 3'te "L1 L2 L3": lomber ameliyatta her seviye ayrı satır mı olmalı, yoksa başka bir şey mi?
   - S4. "Acilde ICD girilmez": acil faturasında hiç tanı olmaz mı, yoksa kesin tanı yerine semptom (R) kodu mu girilir?
   - S5. Çıkış günü yatak: SUT/MEDULA'da "standart yatak gönderilmelidir" ifadesi var; bu çıkış gününü mü kastediyor, sizin uygulamanızda çıkış günü neden girilmiyor? Yoğun bakımdan servise devirde devir günü nasıl?
   - S6. Yatıştan önce giriş faturası: istisnalar var mı? (hastanede doğan yenidoğan, yoğun bakımdan servise devir, poliklinikten planlı yatış)
   - S7. Kontrol süresi: A 15, B 10; C, D, E kaç gün? Paketsiz (hizmet başı) ameliyattan sonraki kontrol muayenesi her zaman faturalanır mı?
3. Name patients 2 and 3 by story id; list for each statement the exact bill and line it refers to.

Exit: answers recorded with date in this file (§6) and in `reports/synthetic-data/` next to the 77-item judgment list.

### WP1. Complaints and treatment notes (no answer needed)

- New pathway field `complaint`: the patient's words for why they came (`basis`, `source` as every field), per pathway; the treatment note likewise from the pathway (what was done, in clinical language), not from codes.
- `clean.py`: `YAKINMA` from `complaint`; never the diagnosis name or code.
- Checks (clean family): `clean.complaint_not_diagnosis`: `YAKINMA` contains no ICD-10 code pattern and is not the name of any diagnosis on the claim; `clean.treatment_note_present`: every stay has a non-template treatment note.
- Acceptance: the new checks fail on all committed claims today, pass after; all 42 pathways carry a `complaint`.

### WP2. Drugs on every day (no answer needed)

- Grammar: a `per_day` drug becomes one line per day of its course (quantity `per_day` each day), from the course start; README §"lines" rewritten; `expand.py:82` and the composer changed; `qty`-form drugs (a single dose) stay one line.
- Check (claims family): `stay.drug_daily_lines`: a course drug has exactly one line on each day of its course and none outside the stay.
- Engine-proof stories that count drug lines or quantities will move; each change explained. Before merging, read every drug rule of the engine for per-line vs per-date assumptions (feeds WP7).

### WP3. A stay enters through a visit (exceptions from S6)

- Rule: every `yatis` bill has an `acil` or `poliklinik` bill of the same patient on its admission day (or the day before, for an evening ER visit admitted after midnight), except the cases Ahmet Bey names in S6. Until S6 is answered, the exceptions are the ICU→ward transfer (`urosepsis_ward_stay_after_icu_transfer`) and the newborn stays (`late_preterm_newborn_*`), marked provisional.
- Check (cross-bill): `cohort.stay_has_entry_visit`, with the failing stays listed in the PR.
- Data: an entry-visit pathway for each stay that lacks one (count measured by the check first), each with its examination, the consultation of the admitting branch (A6), and no line the stay bills again.

### WP4. The discharge-day bed (after WP0 S5 and the SUT text)

- If Ahmet Bey is right: `admit..discharge-1` for the bed in the 13 pathways, README:44 rewritten, `stay.bed_coverage` changed to "admission..discharge-1" (0-night stays: the day bed, unchanged); the ICU→ward rule re-read against the answer.
- If the SUT text supports the current rule: record the source in the pathways README and in this file, change nothing, and tell Safa what to answer Ahmet Bey.
- Either way, WP7 measures the engine side.

### WP5. ER bills (A5 after S4; A6, A7 now)

- A7: replace 803602 with the abdominal ultrasound code of EK-2B (looked up and cited, not guessed) in `appendicitis_er_visit_ultrasound` and any other ER pathway that bills a general ultrasound for an abdominal complaint.
- A6: a general surgery consultation line on an ER visit that ends in a surgical admission (the consultation code from EK-2B, cited).
- A5 after S4: the diagnosis rule of `acil` bills, and a check `fit.acil_diagnosis` that enforces the answer.

### WP6. Stay contents and the control period (A8, A9, A10, A11)

- A9: IV access (code per S1), urinary catheter where the pathway's story needs one, in-stay labs at a realistic cadence, per pathway with `basis` and `source`; no new check unless a cohort-wide rule exists (to ask: is IV access on every stay?).
- A8: check `cross.control_in_package_window`: a `poliklinik` control of the operating branch inside the package window of an EK-2C operation (A 15, B 10, C 8, D 5, E 3, the windows `yatak_puani.py` already uses; to confirm in S7) bills no examination; none for an itemized operation.
- A10, A11: per S2 and S3.

### WP7. Engine audit (after WP0; no engine change in this plan)

1. List every engine rule that counts bed days (`yatak_puani.py`, `drg.py:225`, `temporal_anomaly.py:125`, the ICU and newborn overlap rules), reads drug lines per line or per date, reads an `acil` diagnosis, or treats controls inside a package window.
2. For the bed day: measure on the committed cohort how much bed-day opportunity comes only from the discharge day (amount and claims), with today's rule and with A2's.
3. File one issue per rule whose assumption contradicts a confirmed answer, with the measured amount; the change itself is Safa's decision.

## 5. Order

WP0 starts at once and runs beside WP1, WP2, WP3 (independent of the answers). WP4, WP5 (A5 part) and WP6 wait for their answers. WP7 follows WP0 and must finish before any demo shows a bed-day amount.

Stop conditions: a check that cannot be shown failing on today's data is not merged (it would not have caught the bug); no change to the discharge-day bed anywhere (generator, check or engine) before WP0 S5 and the SUT text are recorded; no code invented for A6, A7 or A9: each comes from EK-2B with its row cited.

## 6. Answers (to fill in)

| Q | Answer | Date | Source |
|---|---|---|---|
| S1 | | | |
| S2 | | | |
| S3 | | | |
| S4 | | | |
| S5 | | | |
| S6 | | | |
| S7 | | | |
| SUT text on the discharge-day bed | | | |
