# Synthetic demo cohort audit (2026-10-14)

**Question:** is the synthetic data the demo runs on gibberish?

**Answer:** yes, in every layer, not only the bills.

- **The generator picks clinical content at random.** Procedures, drugs, labs, materials, vitals and notes are drawn uniformly from the SUT catalogs. Nothing links them to the patient's diagnosis, department, sex, age or care setting.
- **Prices and labels are wrong too.** Prices come from the wrong year, and the "expected" answers are copied from the generator's own coin flips.
- **The engine has bugs of its own.** Running it on this data exposed product bugs that would also fire on real invoices.
- **The structure is clean.** IDs, links and header totals are all correct, so the problem is the content, not the schema.

## Scope and method

**Data audited**
- The cohort in `data/synthetic/sut/`: 50 patients and 94 bills dated 2023-01-02 to 2024-12-27.
- Line tables: 489 procedure lines, 212 drug lines, 81 material lines.
- Supporting tables: 240 diagnoses, 676 lab rows, 368 expected outputs, 10 MEDULA events.
- The generator in `scripts/synthetic/`.
- The engine's reports on this data. They were computed in-process with `load_sut_build_context(sut_data_mode="synthetic_demo")` (`src/bilun/cache/context.py:227`), the same entry point the cache builder uses. Nothing was written to the repo, the cache or any server.
- **Excluded:** `data/synthetic/sut/claims/ilay_validation/` (real ILAY-derived rows) was not opened.

**How it was checked**
- Seven independent read-only audits, one per layer. Each was scripted in Polars and re-run once.
- **†** marks a number re-measured by a second, independent script.
- Domain judgments (what is normal in SGK billing) are labelled *judgment*. Every other number is measured.
- **Catalogs:** prices and code validity were checked against the version in force on the service date. The sources are `data/gazette/curated/ek2b_catalog_history.parquet`, `ek2c_catalog_history.parquet`, `ek4a_history.parquet` and the EK-3 snapshots.

**Severity**
- **FATAL:** a hospital billing person notices it in seconds and stops trusting the demo.
- **SERIOUS:** visible on inspection.
- **MINOR:** hygiene.

## Verdict

1. **Every bill fails a basic check.**
   - 93/94 bills carry procedure prices that were not in force on the service date. 473/489 lines use the 2026 list, and only 7/483 lines with an in-force price match it. †
   - 94/94 bills put every line on a single day, including 36 inpatient stays with a median of 14 nights. †
2. **Nothing is clinically linked.**
   - **Bills:** procedures come from unrelated disciplines. 25/94 bills mix two or more SUT surgical chapters and 10/94 mix three or more. Every line carries the bill's single department stamp. †
   - **Drugs:** 101/116 disease-specific drug lines have no matching diagnosis.
   - **Materials:** 0/81 are attached to a procedure they could be used in.
   - **Labs:** results are random numbers in random units. †
   - **Patients:** 16/17 patients with more than one visit never return for the same problem.
3. **Sex and age are ignored.** 30 lines on 22/50 patients are impossible for the patient's sex or age. Examples: a radical penectomy for a 22-year-old woman, artificial insemination for a 69-year-old woman. †
4. **The "expected" answers are circular.**
   - All 368 expected outputs copy the generator's own arithmetic.
   - 90/94 bills carry "Kısmi paket içi satır reddi" (partial in-package rejection), and 66 of those 90 contain no package at all. †
   - 36/36 materials flagged "do not pay" are expected to be paid in full.
5. **The engine misfires on this data.**
   - The compliance dashboard puts 5,947,866 TL at risk against 3,738,654 TL billed (159%). †
   - Anaesthesia uplift is computed on lab tests and exams, and makes up 51.7% of the "recoverable" total. †
   - A coronary-stent clause is attached to tracheal, oesophageal and ureteral stents. †
   - These are code bugs; see "Engine bugs" below.
6. **The root cause is the generator's design, not tuning.**
   - `_pick_procedures` samples the whole EK-2B list uniformly. Its only clinical key is the ICD letter, which picks a random EK-2C package group (`scripts/synthetic/gen/procedures.py:29-43,108-131`). †
   - The credibility plan put a care-pathway simulator out of scope (`plans/data/synthetic-demo-credibility-plan.md:53`).
   - The validators check shape, not plausibility, and CI does not run them.

## Findings by layer

### 1. What is on one bill

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 1.1 | Operations billed by medical departments | 82 operation lines on 50/73 bills from medical departments | 0003-013 Endokrinoloji: orbitotomy. 0049-091 Gastroenteroloji: LVAD + RVAD | FATAL |
| 1.2 | No diagnosis supports the operation (*judgment*: a deliberately generous ICD-to-SUT-chapter table) | 76/104 operation lines. On 36/62 bills with operations, none matches any diagnosis | 0042-066 sleep apnoea + hypertension: VA-ECMO, total colectomy, RF ablation. 0010-024 NSTEMI: cheek-tumour excision ×2 | FATAL |
| 1.3 | Major operations in an outpatient, emergency or preventive setting | 22 group A1–B operation lines on 16/41 such bills; 7/17 day cases carry an A3 operation | 0003-014 preventive neurology visit: pineal tumour surgery †. 0050-092 preventive: total cerebral lobectomy †. 0021-035 outpatient cardiology: ascending-aorta replacement + I-131 therapy † | FATAL |
| 1.4 | The exam line is not a visit | 69/83 exam lines are not an ordinary visit code at all † | Donor exam ×7, "muayene anestezisi" ×6, infant eye exam under general anaesthesia on adults, CBRN decontamination exam on a myeloma patient. 0/5 ER bills carry the ER visit code | FATAL |
| 1.5 | Packages contain unrelated lines | 0/12 in-package lines belong to the package operation's chapter | 0045-078 skin-tumour package "includes" a distal oesophagectomy. 0038-055 shoulder diagnosis: vaginal hysterectomy package | FATAL |
| 1.6 | Bed days | Quantity equals length of stay on 1/30 bed lines. 9 "bed" lines are nail-bed revision surgery (612070, up to ×17). 6 day-bed lines on multi-night stays. Only 13/36 stays use the ward-bed code 510010; 6/36 have no bed line † | 0001-001: 612070 ×17 for a 9-night stay | FATAL |
| 1.7 | Every line on one day | 94/94 bills; at most 8 lines per bill † | 0042-066: ECMO, colectomy and ablation all on admission day of a 20-night stay | SERIOUS |
| 1.8 | No ICU anywhere | 0 ICU lines †, despite ECMO, LVAD and respiratory failure | The real-world anchor puts ICU tiering at 81% of SGK deductions (Almalı & Çetin Aslan 2022) | SERIOUS |
| 1.9 | Anaesthesia does not follow surgery | 42/43 bills with fee-for-service operations have no anaesthesia line; 7/15 bills with anaesthesia codes have no operation | 0021-035, 0050-092 | SERIOUS |
| 1.10 | Facility | 32/94 bills contradict their own tier (public tier with a private provider, and the reverse). 15/17 multi-visit patients change facility tier. No tıp merkezi or dal merkezi exists in the data | 0002-008 TEVAR at a second-level public hospital | SERIOUS |
| 1.11 | Codes billed before they existed | 6 lines | 0003-013-006: code 801778 on 2024-03-28, added in 2025 | SERIOUS |
| 1.12 | One department stamp on every line | `procedure_specialty_code` equals the bill department on 481/489 lines; the other 8 are null † | — | MINOR |
| 1.13 | Department spellings | 4 bills: `kardiyoloji`, `genel_cerrahi`, `ortopedi`, `acil_servis` † | — | MINOR |
| 1.14 | Laterality never set | `sag_sol` is null on 489/489, while 22 code names state a side | "BT, Uyluk - sağ" | MINOR |

### 2. The patient over time

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 2.1 | Items impossible for the patient's sex or age | 30 lines on 22/50 patients and 26/94 bills | Radical penectomy for a 22-year-old woman †. Penile fracture repair for a 16-year-old girl †. Myomectomy for a 42-year-old man †. Vaginal cream and breast-milk expression for a 66-year-old man †. Congenital heart catheterisation "for under-2s" for a 43-year-old man †. Artificial insemination for a 69-year-old woman †. A child's above-knee prosthesis for a 65-year-old (Tier A 0038) † | FATAL |
| 2.2 | Visits are unrelated draws | 16/17 multi-visit patients never repeat a primary-diagnosis category; 8/17 share no code across visits; 10/17 see three or more departments | 0003 (default landing): meniscus → sleep apnoea (preventive) → obesity (emergency) → respiratory failure (outpatient) → hypothyroidism | FATAL |
| 2.3 | Height and weight redrawn at every visit | Height varies by more than 10 cm in 15/17 multi-visit patients † | 0003: 155–185 cm and 52–116 kg † | FATAL when seen |
| 2.4 | Clinical notes are placeholders | 94/94 read "`<department> sentetik yakınma - epizot N`", with 34 distinct texts per column † | "Gogus Hastaliklari sentetik yakınma - epizot 1" on a leukaemia admission | FATAL when opened. The audit found no UI component that shows them; not checked for the chatbot |
| 2.5 | The diagnosis tables disagree | The header's primary diagnosis differs from the diagnosis table on 6/94 bills, including Tier A 0002 (M23.2 vs K63.5). On 0038 the leukaemia code C92.0 is missing from the diagnosis table | The engine reads the diagnosis table, so its rules see the wrong diagnosis | FATAL (Tier A) |
| 2.6 | Diagnoses implausible for the age (*judgment*) | 21 instances on 9 patients | 0045, an 18-year-old woman: hypertensive heart failure with bypass-graft status, myeloma, colon cancer | SERIOUS |
| 2.7 | Department does not fit the diagnosis (*judgment*) | 6 episodes | AML admitted to chest diseases (Tier A 0038). Lung, colon and breast cancer in haematology | SERIOUS |
| 2.8 | Breast cancer only in men | 3/3 C50 episodes are male † | 0008, 0019, 0028 | SERIOUS |
| 2.9 | Chronic flags | The hypertension flag means one reading above 140/90 (94/94). Flags flip within a patient: hypertension 15/17, diabetes 9/17 | 0036, the copay-exemption diabetes demo, has its diabetes flag False | SERIOUS |
| 2.10 | Diseases appear and vanish | Diabetes missing on 19 later visits of 8 patients; cancer missing on 11 later visits of 4 patients | 0045: myeloma, then colon cancer | SERIOUS |
| 2.11 | Diagnosis dates mean nothing | Every diagnosis date equals the visit date (94/94); chronic codes are re-dated at each visit | — | SERIOUS |
| 2.12 | Vitals are uniform random numbers | SpO2 flat between 90 and 99; women 180 cm or taller on 13/49 visits; no height difference between sexes | — | SERIOUS |
| 2.13 | Acute problems in the wrong setting (*judgment*) | 12 acute primary diagnoses billed as outpatient | Acute respiratory failure as poliklinik (Tier A 0003); stroke as occupational disease; sleep apnoea with a 20-day stay | SERIOUS |
| 2.14 | Coding-convention errors (*judgment*) | G63.2 (diabetic polyneuropathy) without a diabetes code on 4/5 | Tier A 0002, 0003 | SERIOUS |
| 2.15 | Overlapping visits | Outpatient visit during an inpatient stay | Tier A 0038 | SERIOUS |
| 2.16 | Age mix (*judgment*) | Ages 16–74, nobody 75 or older; inpatient median age 51.5 | — | MINOR |
| 2.17 | Copay profiles (*judgment*) | `yesil_kart` on 3 patients; Yeşil Kart was folded into GSS in 2012 | — | MINOR |

### 3. Drugs

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 3.1 | No link to diagnosis (*judgment* on the class-to-ICD table) | 101/116 disease-specific drug lines lack a matching diagnosis on the bill; 30/31 high-acuity drugs (chemotherapy, haemophilia, biologics, HIV, transplant) | 0042-066: factor VIII + daratumumab on a neurology sleep-apnoea stay †. 0042-067: ifosfamide (chemotherapy) in orthopaedics for low back pain. 0003-013: abatacept at an ER visit for obesity | FATAL |
| 3.2 | One regimen for every prescription | 212/212 read "1 kutu, oral, 7 gün, 500 mg × 2" †, including 78 injectables, 21 topicals and 6 eye drops | Dostinex 0.5 mg → 1,000 tablets per dose | FATAL |
| 3.3 | Random prices (*judgment* on real prices) | 206/212 at or below 500 TL; biologics median 108 TL | Darzalex 60.90 TL † | FATAL |
| 3.4 | "copay_rate" is the public discount | Equal to `discount_tier_expected` on 212/212 † | The SGK drug copay is a 10/20% share (SUT 1.8.2) | SERIOUS |
| 3.5 | Wrong age or sex | 6/6 paediatric-only products given to adults; 3/4 sex-restricted drugs to the wrong sex | Vaginal cream for a 66-year-old man † | SERIOUS |
| 3.6 | Not on EK-4A on the service date | 28/212 | Pomavid for 0003 billed 2023-07-17, first listed 2026-05-23 † | SERIOUS |
| 3.7 | Inputs to Bilun's own drug rules are empty | 9 clinical fields null on 212/212. 56 lines need a report under Bilun's §4.2 rules, yet there are no drug denials | MEDULA 0411 "drug report missing" (0031) points at no line | SERIOUS |
| 3.8 | Timing and setting | All drugs dated on the first day of the stay (about 2.4 lines per 14-day stay); 80 drug lines on outpatient bills, 16 of them IV infusions | — | SERIOUS |

### 4. Labs

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 4.1 | Results are noise | 676 rows = 169 tests × 4 †. The same test on the same day appears in up to 4 units, with 4 reference ranges and several organ systems. 55/168 flow-cytometry percentages exceed 100 | 0041: serum sodium 12.54 g/dL, 8.11 mg/dL, 241.86 mm/h and 2.78 mm/h, filed under microbiology, biochemistry and oncology † | FATAL |
| 4.2 | Wrong test mix | 4/169 tests are routine. No blood count, glucose, HbA1c or creatinine anywhere. 0/20 diabetic episodes have HbA1c or glucose; 0/10 renal-failure episodes have creatinine | Tuna, ant and green-pepper IgE ordered in orthopaedics; one time-point of a stimulation test billed alone | FATAL |
| 4.3 | Lab prices | 0/169 at the in-force price; billed ≠ quantity × price on 168/169 | — | SERIOUS |

### 5. Materials

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 5.1 | Attached to the wrong line | 0/81 attached to a procedure that could use them; 58/81 hang on an exam, lab or bed line †. 79/81 have no fitting procedure anywhere on the bill | Knee-revision part → total colonoscopy (Tier A 0009) †. Shoulder implant → eye exam (Tier A 0029) †. Carina stent → nail-bed revision (Tier A 0038) †. Hip prosthesis → "yeşil alan muayenesi" (green-area exam) † | FATAL |
| 5.2 | Fault flags rotated, one per line | 78 flag columns, 76 true values on 42/81 lines; 74 flags used exactly once †. 56/76 contradict the line | "Cochlear implant under 12 months" on a 43-year-old's apheresis column (Tier A 0013) †. Dental-prosthesis adhesive on a J-stent † | FATAL |
| 5.3 | Expected outputs contradict the flags | 36/36 "do not pay" flagged lines expected paid in full | 0029: MEDULA 0704 "ÜTS barcode missing" on the shoulder implant, expected paid 12,500 TL † | FATAL |
| 5.4 | The 999,999 TL "ICD kalp pili" | 1 line = 26.7% of all cohort billing † | Code OP1592 is a hydraulic knee joint (EK-3C-2, 99,960 TL) †. Real ICDs (EK-3H KR1000–KR1012) are about 49–100k TL | FATAL |
| 5.5 | Devices without the condition | 10/10 amputation prostheses (299,309 TL) with no amputation diagnosis in the cohort | Child devices on adults † | FATAL |
| 5.6 | Names are not product names | 10 arthroplasty lines named only "KALÇA" or "DİZ" †. OP1000 is named "İhale ekranı eksik sözleşmeli malzeme" but is a crutch in EK-3; OP2000 does not exist | — | FATAL |
| 5.7 | Prices from the latest list | 77/81 lines at the latest snapshot price, 0/81 at the in-force price; +62.9% over in-force | AP4060 on 2023-03-03: 31,415.64 billed vs 6,981.25 in force | SERIOUS |
| 5.8 | Bundling inverted | 23 bundled lines, none linked to a package; the only 2 linked to a package are not bundled. Prostheses denied as "package consumables" (195,441 TL) | — | SERIOUS |
| 5.9 | Pre-authorisation is a coin flip | 36/81 true; the same code gets conflicting values | GHC1220 twice on one bill, true and false | SERIOUS |
| 5.10 | Implants on day-case or outpatient bills (*judgment*) | 9/28 | 0029 shoulder implant on an outpatient bill | SERIOUS |

### 6. Money

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 6.1 | Prices from the wrong year | 473/489 lines at the 2026 list; 7/483 at the in-force price; unit/in-force ratio 0.66–22.5×, median 1.76× †. The ratio tracks the service date: about 4.1× early 2023, 1.2× late 2024 | 0045-078-002: bed 510010 at 222.36 on 2023-02-12, when the price was 53.13 | FATAL |
| 6.2 | Line arithmetic | billed ≠ unit × quantity on 430/489 lines †. The pattern is billed = k·unit·qty·(1 + surcharge), with k ∈ {0.3, 0.55, 1} | 0001-001-001: unit 108.26, billed 64.96 | FATAL |
| 6.3 | Package-rejection label without a package | "Kısmi paket içi satır reddi" on 90/94 bills; 66/90 have no package line, code, candidate or included line †. The label is set whenever payable < billed (`gen/orchestrate.py:439`) † | 31 poliklinik, 5 acil, 3 koruyucu bills | FATAL |
| 6.4 | Gap far above reality | Billed 3,738,654 TL, payable 2,918,608 TL, gap 21.9% †, against the anchor's 1.72% / 0.13%. 80/94 bills exceed 1.72% and 23 exceed 50% | — | SERIOUS |
| 6.5 | Extra fee (ilave ücret) where not allowed (*judgment*, 5510 md. 73) | 397 lines, including 31/32 ER lines and 119/133 lines at MoH public hospitals | — | SERIOUS |
| 6.6 | Percentage copay on procedures | 236 lines at 20–60%, including lab and exam lines; 1 preventive line at 60% | 0003-014-005 (the pineal surgery) | SERIOUS |
| 6.7 | Payable above billed | 5 lines, 2 bills with negative savings † | 0005-018-001: billed 0, payable 5,000 | SERIOUS |
| 6.8 | Package bills still pay included items (*judgment*) | On 28 package bills, 12/12 bed, 39/39 lab and 22/22 visit lines are paid | — | SERIOUS |

### 7. Ground truth: expected outputs and MEDULA events

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 7.1 | Expected outputs are circular | 368/368 copy the generator's own payable and trace. All 94 bill-level "rule traces" are just the scenario tag. 477/489 procedure lines and 31/81 materials have no expected row | — | SERIOUS |
| 7.2 | MEDULA rejections on the service day | 10/10 dated the service day †, 9 of them at invoice registration (`fatura_kayit`); all 10 on university outpatient bills †. 7/8 rejected lines are still payable | 0026: provision not obtained, yet the line is payable 33,372 TL | SERIOUS |
| 7.3 | MEDULA linkage gaps | 0411 and 1102 point at no line; 1205 "service date mismatch" has no second date | — | SERIOUS |

### 8. What the product shows on this data

| # | Defect | Count | Examples | Sev |
|---|---|---|---|---|
| 8.1 | The same TL counted by several rules | Compliance dashboard: 5,947,866 TL at risk vs 3,738,654 TL billed † (159%). 10/50 patient pages show at-risk above billed †. 60/76 flagged material lines are hit by 2–4 rules | 0047: 61,513 at risk vs 50,636 billed †. On 0023, the 999,999 line is counted ×4 | FATAL |
| 8.2 | Anaesthesia uplift on lab tests and exams | 176/203 rows, 68.5% of anaesthesia TL; anaesthesia is 51.7% of the recoverable total † | "Anestezi E grubu" on "Ürik asit (24 saatlik idrar)"; 0003: 16,682 TL anaesthesia † | FATAL (engine bug) |
| 8.3 | A clause about a different object | 46/163 material findings, 1.45M TL, 15 of them in Tier A | Coronary-stent clause on non-coronary stents; a hearing-aid clause on a knee part (0009) | FATAL (engine bug for the stent case) |
| 8.4 | Copay "savings" from surgery lines | 78,603 of 93,255 TL | 0003's top action: a 14,508 TL "preventive copay waiver" taken from the pineal-surgery line † | FATAL (data-driven) |
| 8.5 | Bed-day "recoverable" counts beds already billed | 18,331 of 107,400 TL † | F-0001-005: 889.44 expected while 693.76 is already billed | SERIOUS (engine bug) |
| 8.6 | Recoverable above billed | 13/94 bills, 3/50 patients † | 0010: 12,605 vs 8,053 †. 0006: 5,375 vs 4,576 † | SERIOUS |
| 8.7 | Impossible bills pass silently | 44 surgical lines on outpatient/ER/preventive bills; the care-setting review fires on 2 day-case bills only. The engine's response is "must use package billing" | 0003: adrenalectomy on a poliklinik bill | SERIOUS |
| 8.8 | Composition is the opposite of the anchor | Anaesthesia 51.7% + bed days 31.6% + companion 10.1% = 93.4% of recoverable; ICU 0 † | Anchor: ICU tiering ≈ 81% of deductions | SERIOUS |
| 8.9 | The Documents tab is boilerplate | 238/255 checklist rows are 5 generic items. A pathology report is demanded on 42 bills with no biopsy; orthopaedic pre/post-op X-rays on 12 bills without orthopaedic surgery (triggered by the department name) | — | SERIOUS |
| 8.10 | "Eylemli Hastalar" (patients with actions) counts loaded patients | `n_patients = len(reports)` (`cohort_summary.py:168`), shown by `RevenueRecoverySummary.tsx:92` †. It reads 50, while 34 patients have a revenue action and 28 have recoverable > 0 | — | SERIOUS (engine bug, #234) |
| 8.11 | Two counts on one panel | 12 patients | 0003: "Riskli bulgu 5" next to "none of the 4 findings has a billed amount" | MINOR |
| 8.12 | Display text | — | Material name "OR2640"; ASCII-only Turkish; English sentences in the Turkish UI; `package_flag` as a section ID | MINOR |

## Engine bugs exposed by this data (they also fire on real invoices)

| # | Bug | Where | Effect here | Issue |
|---|---|---|---|---|
| E1 | The anaesthesia rule treats any EK-2B code with a puan as surgery: labs, exams, beds, even anaesthesia codes. Its group table matches none of EK-2B's own (raw 2026-07-07 rows 124–130: A1 39001+ … E 0–1300). It skips every procedure above 5,000 puan, never subtracts billed anaesthesia, and cites §2.4.4.A, which is ESWL | `src/bilun/domain/prose_rules/anestezi_puani.py:45,52-60,83-97,167-175` † | 176/203 rows are on non-surgical lines. 51.7% of "recoverable". The 27 surgical rows are inflated about 6.8× | Safa675/Bilun#230 |
| E2 | The coronary-stent clause matches the bare word "stent". All §3.1.4 "paid separately" (info) findings count as billed at risk. The misfire also hides other §3.1 rules | `data/gazette/prose_rules/material_bundling_prose.json:1325`; `material_bundling.py:135-142`; `cohort_compliance.py:413-415` † | 10/11 stent lines, 164,437 TL. §3.1.4 info rows at risk: 12 rows, 1.17M TL | Safa675/Bilun#231 |
| E3 | Billed at risk is summed per finding, not per line, in the backend and the frontend | `billing_actions.py:460-490`; `cohort_compliance.py:413-418`; `frontend/src/lib/workspaceViews.ts:105-119` † | 159% of billed †. Counted once per line it is 50.1%. 10/50 pages exceed billed † | Safa675/Bilun#232 |
| E4 | Bed-day "recoverable" is the full expected charge; the gap is computed but not read. The ICU sum falls back to the full charge when the gap is 0 | `yatak_puani.py:143-152` (gap computed); `types.py:419-427,447`; `billing_actions.py:321` † | 18,331 TL already billed counted as recoverable | Safa675/Bilun#233 |
| E5 | The "patients with actions" KPI counts loaded patients | `cohort_summary.py:168`; `RevenueRecoverySummary.tsx:92` † | Shows 50. Patients with a revenue action: 34; with recoverable > 0: 28 | Safa675/Bilun#234 |

**More engine problems found while drafting (no issues opened yet):**
- `temporal_anomaly.py:55-58` treats codes starting 50/51 as surgery; 51xxxx is beds.
- The companion-bed rule charges every inpatient stay without checking billed 510121 (`refakatci.py:176-184`). That is 34,308 TL, 10.1% of recoverable.
- A second line with the same material code is never checked (`claim_materials.py:165-185`).
- Emergency detection reads the synthetic `scenario_tag` (`prose_rules/gap_closing.py:341-345`).
- The billing strategy prices showcase claims 0002/0003 from `demo_vignettes.json` (`demo_vignette_lookup.py`, `claim_strategy.py:480-498`).
- The loader demands expected-output rows in every data mode (`claims/dataset_builder.py:170`), so real claims would most likely fail to load (inference).
- No detector exists for ICU billed above its tier, which is the anchor's 81% cause.

## Tier A: the eight showcase bills

| Patient | The showcase bill † | Headline action (engine) | Verdict |
|---|---|---|---|
| 0002 | Orthopaedics, meniscus (M23.2), inpatient: a single "package" line 609270 "Safra fistülleri için girişimler" (biliary fistula), 3,500 TL; the diagnosis table says K63.5 | Ig adsorption column 17,242 TL counted twice, on another bill | Nonsense |
| 0003 (default landing) | Orthopaedics, meniscus, inpatient: cheek-tumour excision ×2. The alternative package is 609300, islet-cell transplant | 14,508 TL "preventive copay waiver" from a pineal-surgery line on the patient's preventive visit; 16,682 TL anaesthesia uplift | Nonsense |
| 0006 | Cardiology, angina (I20.9), inpatient: cheek-tumour excision | 13 bed days, 2,891 TL | Nonsense |
| 0009 | Orthopaedics, disc herniation (M51.1), day case: total colonoscopy + knee and hip implants | Knee part "DİZ" with a hearing-aid clause | Nonsense |
| 0010 | Cardiology, NSTEMI (I21.4), inpatient: cheek-tumour excision ×2 + biliary-fistula "package" | Package adequacy 12,718 TL; recoverable 12,605 > billed 8,053 | Nonsense |
| 0013 | Oncology, lung cancer (C34.9), day case: biliary-fistula intervention + enterostomy closure | Apheresis column flagged as prosthesis and cochlear implant | Nonsense |
| 0029 | Orthopaedics, femoral-neck fracture (S72.0), **outpatient**: hindquarter amputation, video-EEG, oesophageal variceal ligation, eyelid reconstruction, eye exam | Shoulder implant on the eye exam; MEDULA 0704 yet paid in full | Nonsense |
| 0038 | Chest diseases, AML (C92.0), inpatient: Wood's-lamp exam, nail-bed revision as bed days, a lab line named only "L116470", BRCA1/2 sequencing, a package shown only as "P615440" at 103,261 TL | Endobronchial valve 33,760 TL counted twice | Nonsense |

## What is fine

- **Structure.** IDs and links are clean across all 12 tables: no orphans, no broken links, and patient and episode IDs agree everywhere †. Header totals equal the line sums on 94/94 bills.
- **Codes.** Every procedure code exists in EK-2B/EK-2C, and every drug code in EK-4A history. All but one material code (OP2000) exist in EK-3.
- **Dates.** Every line, lab and drug date falls inside its bill window. Every diagnosis date falls inside its claim window.
- **Patient arithmetic.** Sex is constant per patient. Age equals visit year minus birth year. BMI arithmetic is correct. `exemption_eligible` matches EK-1A.
- **Drug arithmetic.** Quantity × unit = billed, and payable = billed × (1 − discount), on 212/212 lines.
- **Engine.** Two runs were identical. There are no bed-day or companion rows on day cases. ICU and newborn blocks raise no false positives.

## Root causes in the generator (`scripts/synthetic/`)

| Symptom | Mechanism | file:line |
|---|---|---|
| Unrelated procedures on one bill | Uniform sample of the whole EK-2B list; the only clinical key is the ICD letter, which picks a random EK-2C package group | `gen/procedures.py:29-43,108-131` † |
| One department on every line | The bill's department is stamped on each line | `gen/claim_lines.py:299` † |
| Random exam and "bed" lines | Pools are name filters ("muayene", "konsültasyon", "yatak"), sampled uniformly. "yatak" also matches "Tırnak yatak revizyonu". Bed quantity is random 1–20 | `gen/orchestrate.py:90-99`; `gen/procedures.py:57-81` † |
| Sex and age ignored | Patient sex and age are written but never read when choosing items | `gen/patients.py:59,158` |
| Visits unrelated | Each visit draws a new template, diagnosis, department and vitals | `gen/patients.py:136-170` † |
| Placeholder notes | Format strings | `gen/patients.py:202-205` † |
| Prices from 2026 | The last catalog row per code is kept, not the row in force on the service date | `catalog.py:26-51` † |
| Drug prices and regimen | Uniform random price; one fixed regimen | `catalog.py:78-92`; `gen/ancillary.py:19-27` † |
| Lab noise | 4 rows per test with random value, range, unit and organ system | `gen/ancillary.py:44-77` † |
| Materials on the wrong line | Uniform catalog row; attached by index (`mat_idx % n`), so the first material lands on the exam line | `gen/claim_lines.py:395-420` † |
| Flags rotated | Flag k goes to candidate k mod N; the validator requires every flag to be true somewhere | `gen/materials_flags.py:191-204,285-289`; `validate_sut_synthetic_data.py:381-426` |
| "Kısmi paket içi satır reddi" | Set whenever payable < billed, whatever the cause | `gen/orchestrate.py:439` † |
| 999,999 "ICD" | Hard-coded demo spec on code OP1592 | `gen/specs.py:30-37` † |
| Nothing catches it | Validators check shape, IDs, demo pins and Tier A totals, not plausibility. CI runs pytest and ruff, not the validators | `.github/workflows/ci.yml:55-62` † |
| Not reproducible | `sag_sol` uses Python's unseeded `random` | `gen/claim_lines.py:5,40` |

## Corrections to statements made earlier in this session

- **"Only 16 of 94 bills stay inside one SUT chapter"** does not reproduce. Depending on the definition the figure is 7, 10, 26 or 28. Retracted.
- **"The oldest procedure price list is 2024-05-11"** was wrong. The curated EK-2B history covers 2020-03-11 onward.
- **"All prescriptions are identical"** was half right. The regimen is identical on 212/212 lines, but the lines name 208 different products.
- **"Labs are 169 tests × 4"** is confirmed.

## Coverage

| Dimension | Status |
|---|---|
| Identity against catalogs as of the service date (procedures, labs, drugs, materials) | Checked |
| Line arithmetic and header totals | Checked |
| Cross-table links | Checked, clean |
| Within one line (material ↔ procedure, drug ↔ diagnosis) | Checked |
| Within one bill (disciplines, setting, exam, bed, anaesthesia, packages) | Checked |
| Across a patient's timeline | Checked |
| Care setting and facility | Checked |
| Sex and age | Checked |
| Dates (service, catalog validity, MEDULA) | Checked |
| Money against the real-world anchor | Checked (anchor comparison is *judgment*) |
| Ground truth (expected outputs, MEDULA events) | Checked |
| What the product shows | Checked in-process; UI numbers recomputed with the frontend formulas; not clicked through in the browser |
| Chatbot answers on this data | **Not checked** |
| `sentetik_sut_v2_*.xlsx` workbooks vs the parquet files | **Not checked** |
| Whether the MEDULA codes are real (they match the repo playbook; their source is unverified) | **Not checked** |

## Reproduction

The audit scripts sit in this session's scratchpad under `audit/` (`bill_composition`, `patient_diagnosis`, `drugs_labs`, `materials`, `money_expected`, `engine_output`, `verify`). Each folder has a `run_all.sh` or `reproduce.sh`. The scratchpad lives in `/tmp` and does not survive a reboot. The scripts are the natural starting point for plausibility validators in CI.
