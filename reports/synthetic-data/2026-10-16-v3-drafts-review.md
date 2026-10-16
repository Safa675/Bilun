# Synthetic demo v3 drafts: review on Safa's behalf (2026-10-16)

## Kısaca (Türkçe)
Safa, inceleme işini bana devretti. Üç bağımsız incelemeci `main` 257d1e89 üzerinde çalıştı: SUT/MEDULA kanıtı, klinik gerçekçilik, veri doğruluğu.

- **Hikâyeler:** hastalar, tanılar, ameliyatlar ve yatış süreleri gerçekçi. Ama dört "doğru" faturada bir hekimin ya da SGK denetçisinin reddedeceği satırlar var (S2, S5, S6, S7). Bunlar aşağıda düzeltiliyor.
- **Kodlar:** 70 kodun 66'sı doğru. Dört tanı kodu SKRS'ye göre değişiyor.
- **Bugünkü `main`:** 8 doğru faturanın hepsi 0 TL, hatalı faturalardaki hatalar yakalanıyor.
- **Resmi kaynaklardan kesin çıkan sonuçlar:**
  - aynı seans indirimlerini MEDULA kendisi hesaplıyor;
  - implantlarda KDV %10;
  - ilaçlar kullanılan adet kadar faturalanıyor;
  - refakatçide yaş şartı yok;
  - kuruş yuvarlanmıyor, kesiliyor;
  - yoğun bakım ayrı takip.
- **Yeni motor hataları:** 11 tane bulundu (aşağıda). Bunlar issue olarak açılmayı bekliyor.
- **Sahada çalışan birine sorulacak sorular:** 10 tane (aşağıda).

## Method
- **SUT/MEDULA reviewer.** Sources:
  - `data/gazette/sut_clauses.parquet` (2026-10-02 text);
  - SGK's audit guide (`fatura_inceleme_clauses.parquet`);
  - SGK *MEDULA Hastane Web Servisleri Kullanım Kılavuzu* v3.1.1, 18.09.2026 (medula.sgk.gov.tr, public PDF, read via the web);
  - Resmî Gazete for KDV rates.
- **Clinical reviewer.** Guidelines named per item: NICE, AAOS, WSES, GOLD, ATS/IDSA, ESC, EAU, EHS/AHS, WHO ICD-10 Vol. 2.
- **Data reviewer.** Every story code checked against the catalogs on its line date, ICD codes against SKRS, drugs against EK-4A and the crosswalk; proofs re-run on 257d1e89.
- **Confidence labels:**
  - *SUT kesin* / *Kılavuz kesin*: the text says it;
  - *güçlü kanıt* / *güçlü çıkarım*;
  - *klinik yargı*;
  - *sahada sorulmalı*: needs someone who works on claims or on the ward.

## Answers: story questions (`plans/data/2026-10-15-showcase-stories-draft.md`)

| Q | Answer | Evidence | Confidence |
|---|---|---|---|
| 1 Bed days | One 510010 per calendar day, discharge day included (9→15 = 7). Under 24 h: 510120. | Kılavuz p.62 (bed records for every day in the stay range), p.168 (yatisBitisTarihi = taburcu tarihi); El Kitabı "Taburcu olduğu son günde standart yatak gönderilmelidir"; C000648 | güçlü çıkarım |
| 1b Companion days | MEDULA takes refakatciGunSayisi as entered by the hospital from the refakatçi belgesi. The engine's night formula (`refakatci.py`) has no source. | Kılavuz p.264 | Kılavuz kesin; the count convention needs the field |
| 2 Package window | Answered 2026-10-16; implemented in #285. Days before the operation on the same takip are inside the package. | C000685 | SUT kesin |
| 3 S1 realism | No document says a normal ward takip rejects EK-2B 610131. The realistic fault is a coder keying 610131 in the HBYS, which Bilun catches before submission. The outcome is "≈4.086 TL lost or rejected". | Kılavuz p.84, p.156; C000672, C000710 | sahada sorulmalı |
| 4 Session reductions | **MEDULA computes them.** The hospital sends, per operation, a session/incision code (`ayniFarkliKesi` 1–5) and no reduced amount. MEDULA returns each line's amount; a wrong code is cut at audit. So the incision is known in real data. | Kılavuz p.190 (AmeliyatveGirisimBilgisiDVO has no price field), p.280; F000027 | Kılavuz kesin |
| 5 S8 incision | Same incision (25 %): the umbilical camera port goes through the hernia defect. 50 % only with a separate skin incision. | Gundogdu 2023 (PMC10565757); C000670 | klinik yargı |
| 6a S5 implant | **Cemented** hemiarthroplasty at 84. Stem AP2000 or AP1980, cement AP3220 ×1–2 (cement is billed outside the package, C002859), existing head AP1880. | NICE CG124 1.6.4; AAOS 2021; WHiTE 5 (NEJM 2022) | güçlü kanıt |
| 6b KDV | KDV is sent per material line at the facility's declared rate. Implants: **10 %** since 10.07.2023 (8 % from 01.04.2022); the engine uses 20 %. | C002886, C002748; Kılavuz p.243, p.126; KDV (II) sayılı liste sıra 22; CK 7346 (RG 07.07.2023) | SUT/Kılavuz kesin; rate kesin |
| 7 Drug boxes | Billed by **units used**; fractions allowed. S6: 3 bottles at box price ÷ 2. | Kılavuz p.21–22 | Kılavuz kesin |
| 8 R-codes | R07.1 is a correct principal diagnosis when no diagnosis is made. The engine's blocklist (N7) is a defect. | WHO ICD-10 Vol. 2 (2019) §4.5; TİG guide 2019 | güçlü kanıt |
| 9 Companion | A doctor's medical-necessity decision plus the hospital's refakatçi belgesi. No age condition. Never on day cases, ICU days or inside an EK-2C window. | C001628, C001629, C000650, C000698; age rules only C000737 (non-contracted/travel) | SUT kesin |
| 10 Rounding | **Truncate**: 510010 = 222,35, not 222,36. The catalog rounds half-up; 3,664 of 7,144 EK-2B rows in force on 2026-07-20 are 1 kuruş high. | C000544 (§2.2(15)) | SUT kesin; what MEDULA displays: sahada sorulmalı |
| 11 ICU | Its own takip (type Y), linked or not to the ward takip. The engine's separate-claim model holds; link the claims for the transfer day, package window and companion. | Kılavuz p.83, p.156 | Kılavuz kesin |
| 12 ICD-10 | Use SKRS leaf codes: K35.9 (S1), M48.06 (S3), S72.00 (S5), M81.09 (S5, no DXA in the story). No engine output changes. | `icd10_tr.parquet` | verified |
| 13 Noise | Every clean bill is 0 TL on 257d1e89. N7 is the only open item (see engine defects). | proofs re-run | verified |

## Answers: lab questions (`data/synthetic/reference/lab_reference_notes.md`)

| Q | Answer | Confidence |
|---|---|---|
| 1 LDL | Nothing restricts L105000 (empty açıklama; C006423 names no method). Generator: emit Martin-Hopkins LDL as a derived row under L104520 when TG < 400, and bill L105000 when TG ≥ 400. `lab_capture_gap` must skip derived rows. | SUT kesin (no restriction); clinical: güçlü kanıt (ESC/EAS 2019, EAS/EFLM 2020); practice: sahada sorulmalı |
| 2 "birlikte faturalandırılmaz" | No source defines its scope. Of 1,136 açıklama rows with the phrase, 8 say "Aynı gün", 5 "Aynı seansta" and 31 "Tedavi süresince". Keep same date as the default and make the scope a switch. | sahada sorulmalı |
| 3 Analyzers | One platform. Keep troponin I (S7 uses L107360) and remove the "same platform" note; CK-MB mass is fine. D-dimer in ng/mL FEU, cut-off 500, age-adjusted above 50. | klinik yargı |
| 4 Engine bugs | Fixed: hemogram (#270/#272) and the lab-code map (#271); verified on 257d1e89. | verified |

## Answers: ICD/drug questions (`data/synthetic/reference/icd10_drugs_notes.md`)

| Q | Answer |
|---|---|
| 1 ATC source | Keep the e-reçete ATC first. The engine now reads `atc_code` from this crosswalk for the C000690 blood-product carve-out (#288), so this choice changes engine output. |
| 2 Ambiguous barcodes | Leave them blank. The generator requires an ingredient, which removes SULJEL, DIDERAL, ZENALB, DELSTRIGO and KREON from its pool. |
| 3 Old barcodes | Keep the 12 rows. |
| 4 Drug pool | **Outpatient prescriptions:** the 5,959 pool. **Inpatient/ER lines:** barcodes licensed in September with an ingredient and an EK-4A row in force on the line date (7,638; includes all 6 story drugs). The strict pool drops IV solutions, antibiotics and contrast. Dropping the 48 suspended products needs a new builder column. |
| 5 ICD codes | SKRS codes only, and **leaf codes only** for diagnoses (12,817 of 14,723 active codes are leaves). Whether MEDULA rejects a parent code is unverified. |
| 6 kind | Add `kind` and `is_leaf` in the builder. |

## Story corrections (clinical and data)

| Story | Corrections |
|---|---|
| S1 | K35.9. Faulty bill: drop the 07-14 inpatient CBC/CRP (the ER drew them that day). Paracetamol ≈5 vials, not one 12-vial box. One pre-op antibiotic dose, none after (WSES 2020). |
| S2 | EK-2B açıklama caps: 530350 "Günde bir adet" → 6 lines, not 18; 530360 "Günlük en fazla 16 saat" → 32 h, not 48; L103900 excludes serum Na/K → drop them on 03-09. Together 952,28 TL was unbillable on a "clean" bill. Add a steroid (GOLD), a macrolide (ATS/IDSA 2019), enoxaparin 40 mg/day and 2 blood-culture sets. |
| S3 | M48.06. Cefazolin 2 g once (ASHP 2013). Paracetamol ≈6 vials. |
| S4 | Ceftriaxone 2 g/day (EAU). Blood culture 906020 ×2. Add 803580 urinary ultrasound. Enoxaparin ×5. |
| S5 | Cemented stem (AP2000/AP1980) + cement AP3220; S72.00, add W19; M81.09. NICE 1.6.3: state "walker outdoors" so hemiarthroplasty, not THR, is the indicated choice. **Prerequisite:** the curated EK-3F-1 file lacks the in-force cement codes AP3180–AP3250 (raw partition only). |
| S6 | Add IV fluid (NaCl 0,9 % days 1–3), NG tube 530340 and levodopa via the tube from day 3. Bill PK-Merz as 3 bottles, state CrCl and add an ECG for QT. Drop metronidazole. Enoxaparin ×6. |
| S7 | R101450 açıklama: "Kontrast ilaçlar ve sarf malzemeleri ayrıca faturalandırılmaz" → delete the OMNIPAQUE line. Paracetamol 1 vial. D-dimer above the age-adjusted cut-off (580). Troponin at 0 h and 2 h (ESC 2023). |
| S8 | State a defect under 1 cm. Same incision. With MEDULA's `ayniFarkliKesi`, the clean bill carries code 1. |

## Lab table corrections
1. CK-MB limits: use the current 99th percentiles (F < 4,88, M < 6,22 ng/mL). Remove the false "same platform as troponin" note.
2. Make the troponin abnormal states sex-specific.
3. Add Na/K/iCa rows under L103900 (iCa ≈ 1,12–1,32 mmol/L) and a sample type: most ED/DKA/ward gases are venous.
4. Derive creatinine from the target eGFR, not fixed bands, so age is included.
5. Urea: 16,6–48,5 (ages 18–60), with an age-adjusted upper limit.
6. Panels:
   - DKA: add β-hydroxybutyrate (L101560);
   - anemia: add folate (L102480) and reticulocytes (L106530);
   - CKD: add PTH (L105960);
   - infection: drop ESR;
   - ICU: PCT, D-dimer and fibrinogen every 48–72 h, not daily.
7. Same-day exclusions clash with six panels:
   - lactate or Na/K with blood gas (infection, icu_daily, respiratory, dka_hhs);
   - creatinine with urine ACR (diabetes, ckd).

   **Decided by Safa, 2026-10-16: the demo data follows the SUT.** The generator emits one billed line; the other value goes under the blood-gas line or on another day.

## Engine defects found (filed 2026-10-16)
Filed as issues, with two changes: items 6 and 7 are one issue, and the EK-3/F-1 item (10) is fixed in this PR. Numbers below are the review's item numbers.

| Review item | Issue |
|---|---|
| 1 KDV | #298 |
| 2 Rounding | #299 |
| 3 Session list price | #300 |
| 4 Companion | #301 |
| 5 Drug quantity | #302 |
| 6 + 7 EK-2B açıklama limits | #303 |
| 8 R-code principal (N7) | #304 |
| 9 Parent/leaf matcher | #305 |
| 11 Docs contradiction | #306 |
| new: 27 ICD-10-CM codes missing from SKRS in the drug rules | #307 |

The field-expert questions are #297 and #295.
1. **KDV on implants:** `material_kdv.py:7` uses 20 %. It should be the line's declared rate, defaulting to 10 % from 10.07.2023 and 8 % from 01.04.2022.
2. **Rounding:** the catalog `price_try` is rounded half-up (`scripts/sut/catalogs/price_history.py:117,153,235`); SUT §2.2(15) truncates.
3. **Session list price:** it is taken from the bill's unit price (`session_pricing.py:507-519`); it should come from the catalog, because MEDULA computes the reduction. The claim model lacks MEDULA's `ayniFarkliKesi`; adding it makes the incision known.
4. **Companion:**
   - the day count should come from the refakatçi belgesi (refakatciGunSayisi), not a night formula;
   - eligibility needs an input (doctor's order, belge); without it, emit a review, not TL;
   - suppress ICU days.
5. **Drug quantity** is an integer (`models.py:266`); MEDULA allows decimals.
6. **EK-2B açıklama frequency caps are not enforced** ("Günde bir adet", "Günlük en fazla 16 saat"): 952,28 TL on S2 went unflagged.
7. **Contrast billed next to R101450** despite its açıklama ("Kontrast ilaçlar … ayrıca faturalandırılmaz") went unflagged on S7.
8. **N7:**
   - `diagnosis_coding_quality.py:164-165` blocks every R code as principal (error);
   - its list includes US-only ICD-10-CM codes (O09, Z51.81);
   - its stated source documents are not in the repo.

   It should block an R principal only when a related definitive diagnosis is also coded.
9. **Drug-indication matcher:** a listed parent code (M08.0) does not cover a coded leaf (M08.01), in `_drug_indication/matching.py:158-178`. 9 parent codes in 7 rules give false `indication_mismatch` once diagnoses are leaf codes.
10. **Curated EK-3F-1** lacks the in-force bone-cement codes AP3180–AP3250, so cement lines may raise `material_not_in_ek3`.
11. **Docs:** `docs/medula/medula_capabilities.md:273` (blood gas only via KanBilgisiDVO) contradicts Kılavuz p.254 (result codes KGAZ01–17).

## Questions for a field expert

**SGK billing** (e.g. Ahmet Almalı; anyone with MEDULA access):
1. Does a normal ward takip accept EK-2B 610131 when the package is mandated?
2. Do hospitals count the discharge day in refakatciGunSayisi?
3. What price does MEDULA show for 510010: 222,35 or 222,36? (guncelSutKodlari, Kılavuz p.334, or any invoice.)
4. How do auditors apply "birlikte faturalandırılmaz" across different days of one takip?
5. Do labs bill direct LDL routinely?
6. The +25 points per session or per line: #295.

**Clinicians:**
1. Orthopaedist: which stem and cement, how many packs at 84, and is the cement restrictor billed?
2. ER physician and coder: R07.1 or Z03.5 as principal on an acil takip; does MEDULA reject either?
3. General surgeon: do auditors challenge an umbilical-port hernia repair as a port-site closure?
4. Neurologist: an IV PK-Merz bridge vs NG levodopa alone.
5. Biochemist: one real lab printout (analyzer, troponin type, D-dimer unit, LDL method).
