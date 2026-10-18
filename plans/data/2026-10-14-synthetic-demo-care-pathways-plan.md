# Synthetic demo cohort v3: care pathways instead of random draws

Date: 2026-10-14 (rev 2, after an independent review)
Status (2026-10-18): **approved 2026-10-15; P0 and P1 landed (#258, #296); P2 first step landed 2026-10-17 (#308); P3 merged (#313: fault registry, `apply_fault`, injection record, answer rows); P4 merged (#314: the showcase generator, the clean clinical tables and the plausibility checks, which are the first version of P5); P6 (the pins the swap needs) and P7-lite are done on branch `claude/synthetic-v3-p7-lite-swap` (this PR, not merged yet)** (the 8 showcase patients replace the legacy 50 in `data/synthetic/sut/`; inventory of the pins: `plans/data/2026-10-17-p6-p7-legacy-pins.md`). Safa accepted the recommended answers to Q1, Q2, Q4, Q5 and Q6 and will review the 8 showcase stories himself (Q3). **Q6 is narrowed: 8 patients now, the other 42 later.** Pathway format: `data/synthetic/pathways/README.md`. Task block in `tasks/todo.md`.
Inputs:
- the audit `reports/synthetic-data/2026-10-14-demo-cohort-audit.md`;
- its scripts in `reports/synthetic-data/2026-10-14-audit-scripts/`;
- a read-only research pass and an independent review (both 2026-10-14).

Facts carry file:line citations; anything else is labelled judgment.

## In one paragraph

Today's generator picks every procedure, drug, lab result and material at random from the whole SUT catalog. That is why a sleep-apnoea admission bills ECMO and a colectomy. The fix is a new design, not a patch. A reviewed table of care pathways says what a given diagnosis in a given setting really produces. A composer turns patients into bills priced at the rates in force on their dates. Each injected error is logged, and that log becomes the answer key. Tests in CI fail when the data stops being plausible.

## Goal

A hospital billing specialist cannot fault the demo cohort in the first ten minutes. That means:
1. Every bill is a clinically coherent episode for its patient.
2. Each bill is priced at the SUT rates in force on its service date.
3. A small share of bills carry deliberately injected errors with known causes; most bills are clean.
4. The answer key comes from the injection log, not from the generator's own sums.
5. CI fails when plausibility breaks.

## Why patching is not enough

`_pick_procedures` samples the whole EK-2B list uniformly. Its only clinical key is the ICD letter, which picks a random EK-2C package group (`scripts/synthetic/gen/procedures.py:29-43,108-131`). Other choices have no clinical key at all:
- **Exams and beds** come from name filters (`gen/orchestrate.py:90-99`), so "yatak" matches nail-bed surgery.
- **Drugs** are 1–4 random picks at invented prices (`gen/claim_lines.py:463-467`; `catalog.py:78-92`).
- **Lab values** are random (`gen/ancillary.py:44-77`).
- **Materials** attach by position (`gen/claim_lines.py:395-420`).
- **Patients** are redrawn at every visit (`gen/patients.py:136-170`).

The earlier credibility plan ruled a care-pathway simulator out of scope (`plans/data/synthetic-demo-credibility-plan.md:53`). This plan reverses that decision.

## Facts the design rests on

**1. Chapters and surgical groups**
- **Chapters:** no curated table holds SUT chapters (`scripts/sut/catalogs/price_history.py:97,100` drops the heading rows). The raw EK-2B heading rows forward-fill cleanly; the current list has 10 level-1 and 31 level-2 chapters, with 6.1–6.14 in contiguous code blocks.
- **Surgical groups:** EK-2B has no group column per code. EK-2C's `group` column ("İŞLEM GRUBU", A1–E) covers 2,198 of the 2,407 current codes from 600000 to 629999 when the code is prefixed with `P`.

**2. The engine picks the wrong anaesthesia group for most operations**
- **Two official sources disagree.** EK-2B defines the groups by puan bands in its own rows (raw 2026-07-07, rows 124–130: A1 39001+, A2 18501–39000, A3 9001–18500, B 6001–9000, C 3005–6000, D 1301–3004, E 0–1300). Those bands and EK-2C's group column agree on only 1,159 of 2,198 codes.
- **The engine's own table matches neither** (`src/bilun/domain/prose_rules/anestezi_puani.py:52-60`):
  - It agrees with the EK-2B bands on 8 of 2,407 codes and with EK-2C on 5 of 2,198.
  - It assigns no group to 1,295 codes (puan above 5,000).
- **Where this is tracked.** Safa675/Bilun#230 fixes the engine with the EK-2B bands.
- **Band dates (found in P1, 2026-10-15).** The raw EK-2B markers date the tables: the 32,561 table starts 2024-08-07 (RG 05/08/2024-32623) and the 39,001 table starts 2026-04-16 (RG 08/04/2026-33218). The engine switches on 2026-01-01 and 2026-07-07 (`anestezi_puani.py:129-139`). So the generator takes the bands and dates from `data/synthetic/reference/code_sets.yaml`, and two strict `xfail` tests pin the engine's dates until it is fixed.

**3. Beds, ICU and visits**
- **Bed and ICU codes (EK-2B):** 510010 ward, 510120 day bed (under 24 h), 510090 ICU day rate, 510121 companion, 530000 ER critical bed. ICU tiers are P552001–003 (adult) and P552006–008 (newborn).
- **Where the engine defines them.** Standard bed (`510010`) is in `prose_rules/yatak_puani.py:40`, companion (`510121`) in `prose_rules/refakatci.py:38`, and ICU day rate (`510090`) and tiers (`P552001`–`P552008`) in `prose_rules/icu_puani.py:59,65`.
- **The companion-bed rule cannot see ICU.** Its ICU list holds the literal string `"P55200x"` (`refakatci.py:41`), which never matches a real tier code. So ICU stays would wrongly get a companion-bed charge (Safa675/Bilun#236).
- **No ICU-tier detector exists.** Nothing detects ICU billed above its tier (Safa675/Bilun#242). In the TÜSEB anchor, that cause is about 81% of SGK deductions.
- **Visit codes:** 520010 consultation, 520020 ER, 520021 green area, 520030 outpatient, 520080/520090 primary care.
- **Tıp/dal merkezi visit prices are not read.** EK-2A has columns for them, but `lookup_ek2a_visit_price_try` reads only U1/A1/B and nothing calls it (`catalog.py:282-318`). `prose_rules/facility_tier.py:26-42` has no tıp/dal merkezi tier.

**4. Materials, drugs and ICD-10 data**
- **Materials:** no catalog links a material to a procedure.
  - Curated EK-3 has no procedure column; 19 of 4,928 rows mention an EK-2B code.
  - `data/gazette/prose_rules/material_pairing_uplift.json` has 12 pairs and calls itself "operational heuristics".
- **Drugs: the EK-4A columns.** It has `equivalence_group` (7,042 of 8,078 rows) and `therapeutic_group` (826), but no price, ATC or INN.
- **Drugs: price data.** The only price data in the repo is the raw EK-4C list of drugs supplied from abroad: about 415 drugs, with price and active ingredient.
- **Drugs: indications.** The indication corpus (`drug_indication_prose.json`, 939 rules; 740 with ICD codes or ranges, 470 with ranges) can seed drug-class ↔ diagnosis pairs.
- **Drugs: brand names.** It matches INN words inside brand names (`_drug_indication/matching.py:93-115`), but only 97 of 792 INNs appear in any EK-4A name. A brand→INN crosswalk is needed.
- **ICD-10:** the repo holds no ICD-10 reference (valid codes, names, sex or age edits).

**5. The app refuses any bill set without a pre-written answer for each bill, and real bills have none (Safa675/Bilun#240)**
- The loader requires the expected-outputs file (`src/bilun/domain/claims/parquet_reader.py:37-39`).
- It requires expected rows for every claim, every package-included procedure, every bundled or pre-authorised material and every drug (`claims/validation/expected_outputs.py:86-99`).
- The payable in each row must match the line (`:18-24`).
- `claims/dataset_builder.py:170` runs this in every data mode.

**6. The engine reads demo-only inputs (Safa675/Bilun#239)**
- **Optional-override showcases.** For 0002 and 0003, the billing strategy takes its package and itemised totals from `data/synthetic/demo_vignettes.json` (`billing/demo_vignette_lookup.py`; `claim_strategy.py:480-498`). Example: 0003's package total is 9,000 TL, while the catalog prices P609300 at 31,625.05.
- **Other claims** take the package total from the generator-written lines (`claim_strategy.py:93-97`).
- **Emergency detection** reads `scenario_tag` (`src/bilun/domain/prose_rules/gap_closing.py:341-345`).

**7. Dates and catalog history**
- **EK-2B and EK-2C** have 10 windows from 2020-03-11 to 2026-07-07, none in 2025. The 2026-01-31 list reprices 148 EK-2B codes; 2026-07-07 reprices none.
- **EK-3 has no curated history.** The curated table is one snapshot that already includes changes effective 2026-07-07 and 2026-09-05 (e.g. KV4001, HO1005; `scripts/sut/build_curated_catalogs.py:189`).
- **A dated EK-3 index can be built** from the raw snapshots; the audit built one from 229 of them (`reports/synthetic-data/2026-10-14-audit-scripts/materials/10_build_ek3_index.py`).
- **The rule corpus is 2026 text.**
- **The price lookups ignore `valid_to`** (`src/bilun/domain/pricing/temporal.py:80-82`). Their history has 7,127 zero-length duplicate EK-2B rows on 2026-01-31, and 17 EK-2C packages with two different puan values. Tracked in Safa675/Bilun#241 (related: #226 and #227).

**8. Test impact:** about 42 test files hold about 375 pins on synthetic IDs, tags, amounts or counts. The largest are:
- `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py` (79);
- `test_billing_actions.py` (30);
- `tests/unit/synthetic/test_vignette_golden.py` (23);
- `claims/test_loader.py` (22).

No test renders the UI with the 50 patients. The screenshot script pinned 0003, 0017 and 0029 (`frontend/scripts/capture-screens.mjs:110,520-523`). P7-lite replaced those pins by cohort roles read from `data/synthetic/cohort_registry.json`.

**9. The current generator:** 6,422 lines, of which 4,201 are in pandas files.
- **Reusable as-is:** the exporters' writers, the ID scheme, `get_ek2b_price_for_date` and `get_ek2c_price_for_date` (`src/bilun/domain/pricing/temporal.py:89-165`, after the `valid_to` fix), `claims/schema.py`, and the totals part of `gen/reconcile.py:12-43`.
- **Not reusable:** `gen/reconcile.py:44-50`, which writes the answer rows from the generator's own sums (the circular labels).

## Decisions (answered by Safa on 2026-10-15)

| Question | Decision |
|---|---|
| Q1 Service dates | 2026, February–September, with a dated EK-3 index built from the raw snapshots |
| Q2 Customer shown | One SGK-contracted private hospital (2nd–3rd level, klinik grubu member) |
| Q3 Reviewer of the 8 showcase stories | Safa |
| Q4 Drug prices and INN | Public TİTCK price list; each download named (file, source, size) and approved first |
| Q5 ICD-10 list | Public list (WHO ICD-10 or the Turkish MoH list); download approved first |
| Q6 Size | 50 patients, 100–150 bills, 8 showcase. **Revised 2026-10-18 (P7-lite): 8 patients now (the showcase), the other 42 later** |

Already done elsewhere: the price-history cleanup in fact 7 landed with #248 (0 zero-length rows, 0 duplicate windows; `_is_effective_on_or_before` now honours `valid_to`, `src/bilun/domain/pricing/temporal.py:80-92`).

### The questions as originally asked

- **Q1. Service dates.**
  - Recommendation (judgment): **2026, February–September**, with a dated EK-3 index built from the raw snapshots (fact 7). EK-2B, EK-2C and the rule text then line up, and the 2026-01-31 repricing still allows a "stale price" fault.
  - Without the EK-3 index, start service dates at 2026-09-05.
  - Keeping 2023–24 means auditing 2023 bills under 2026 rules.
- **Q2. Which customer does the demo show?**
  - Recommendation: one SGK-contracted private hospital (2nd–3rd level, a klinik grubu member). That is where inpatient and ICU stories happen and what the engine prices today.
  - A tıp/dal merkezi dataset follows once the engine reads the merkezi columns of EK-2A (fact 3).
- **Q3. Who signs off the pathways and the 8 showcase stories?** A billing specialist or a physician. This is the schedule's bottleneck.
- **Q4. Drug prices and INN.**
  - Recommendation: the public TİTCK price list, with barcode, product, active ingredient and ATC (to verify: availability and terms). EK-4C covers only about 415 imported drugs.
  - Until then, keep drug amounts out of the showcase bills.
- **Q5. ICD-10 list** for names and sex/age edits: a public source (WHO ICD-10 or the Turkish MoH list).
- **Q6. Size.** Recommendation: keep 50 patients (the demo, the docs and the screenshot script assume it) with 100–150 bills, of which 8 are showcase.
  - **Revised 2026-10-18 (P7-lite):** the app runs on the 8 showcase patients now. The other 42 patients and the remaining bills come later, with their pathways. The docs and the screenshot script no longer assume 50: the docs name the 8 showcase patients, and the screenshot script reads its roles from `data/synthetic/cohort_registry.json` and checks the backend against it.

## Design

### D1. Facility and patient state

- **One facility per dataset.** It has a tier, a provider type and a contracted status, and every bill references it.
- **Patient state is fixed.** Sex, birth date and height do not change. Chronic conditions have an onset date and persist across episodes. Episodes add acute problems that fit the patient's age and sex.
- **Age and sex mix:** includes people aged 75 and over, and an inpatient median age around 60 (judgment).

### D2. Care-pathway table (data, reviewed under Q3)

- **Location:** `data/synthetic/pathways/*.yaml`, with a schema test. The format as built (2026-10-17) is in `data/synthetic/pathways/README.md`: one file per pathway, keyed by its diagnoses, `claim_type` and `billing_mode` (not by an ICD range), with `basis` and `source` on every item and range; faults, prices and drug prices stay out.
- **Key:** (ICD range, care setting). Care settings are poliklinik, acil, günübirlik, yatış and yoğun bakım.
- **Each pathway defines:**
  - **Department and exam:** the department; the exam code for the setting; consultations.
  - **Procedures and anaesthesia:**
    - a procedure set with probabilities, from fitting chapters;
    - on itemised (hizmet başı) bills, one anaesthesia line per session, grouped by the same source as Safa675/Bilun#230 (the EK-2B bands, fact 2); multiple-surgery bands when there are several operations;
    - package (EK-2C) bills carry no separate anaesthesia line.
    - Confirm the source with a reading of the SUT text before both the engine and the generator use it; they must use the same one.
  - **Stay:** length-of-stay range; bed lines, with 510120 only under 24 hours; ICU days with tier lines.
  - **Clinical content:**
    - a lab panel: routine tests (blood count and biochemistry on admission) plus condition tests (HbA1c, creatinine…), with unit and reference range per test;
    - drug classes (INN) turned into EK-4A brands (Q4), with route and regimen by dosage form;
    - materials per procedure from a reviewed compatibility table;
    - the documents the Documents tab expects.
- **First set:** about 20 pathways, the 8 showcase stories first.
- **Sources:** SUT text and clinical review. Pairs taken from `material_pairing_uplift.json` are marked heuristic.

### D3. Bill composer

- **Line dates:** stays get dated lines: bed per day, daily visits, labs on admission and as the pathway says, drugs per day.
- **Package vs itemised:** EK-2C package contents never appear itemised next to their package.
- **Prices:** EK-2B/EK-2C come from the as-of lookups after the P1 history cleanup; EK-3 comes from the dated index (Q1).
- **Materials:** each material attaches to the operation line that used it.
- **Totals:** reuse the totals part of `gen/reconcile.py`.
- **Engineering:** written in Polars (AGENTS.md §9).

### D4. Fault injection with known causes

- **Fault registry.** `vignettes.py` becomes a fault registry. Each fault records:
  - the SUT section and the engine rule it should trigger;
  - the injection operation;
  - the expected detection;
  - the TL effect.
- **Rates (judgment).** Faults touch about 1–3% of billed TL across the cohort, anchored to the 1.72% deduction rate, and sit mostly on showcase and regression patients. Most bills are clean.
- **Mix of causes.** It follows the anchor where the engine can detect the cause.
- **ICU tiering is the exception.** No detector exists for it (fact 3, Safa675/Bilun#242). Either the engine gains one first, or the demo says plainly that it does not cover it.
- **Cohort registry for tests.** The generator writes `data/synthetic/cohort_registry.json` in the same run as the parquet files: file hashes, counts, named roles (e.g. `default_landing`, `multi_bill_patient`) and the fault rows of the injection log. Tests read it through `tests/fixtures/synthetic_cohort.py` instead of hard-coding patient ids, tags or amounts, and `empty_parameter_set_mark = "fail_at_collect"` stops an empty cohort from passing silently (see the test-pin appendix).
- **The injection log is the answer key.** The loader rule (fact 5, Safa675/Bilun#240) changes, so that answer rows are required only for injected faults and checked against the injected effect. This changes production code in `src/bilun/domain/claims/validation/`, needs its own tests, and needs a decision on what real data requires.
- **No fake codes or prices.** No sentinel prices; every code and name comes from its catalog as of the service date (lesson of `plans/data/2026-08-22-purge-fake-demo-claim-lines-plan.md`).

### D5. Plausibility tests in CI

- **Form.** Pytest tests that CI already runs (`.github/workflows/ci.yml:58-62`), ported from `reports/synthetic-data/2026-10-14-audit-scripts/`. Each check has a mutation test that seeds the defect and proves the check fails (lesson 2026-10-07).
- **What they check:**
  - **Patient:** sex and age gates (Q5).
  - **Clinical fit:** diagnosis ↔ procedure (pathway membership); department ↔ chapter; setting ↔ surgical group.
  - **Stay lines:** bed quantity equals length of stay; anaesthesia exactly when there is an operation on an itemised bill; material ↔ operation.
  - **Prices and codes:** non-injected lines at the in-force price; every code valid on its date.
  - **Labels:** each denial reason equals its injected fault.
  - **Totals.**
  - **Clinical content:** lab units and ranges per test; drug route by dosage form.

### D6. Engine work this depends on (tracked as issues, not part of this plan)

- **Filed (first batch):** Safa675/Bilun#230 (anaesthesia), #231 (stent clause), #232 (double counting), #233 (bed-day gap) and #234 (the "patients with actions" KPI).
- **Filed (second batch):**
  - Safa675/Bilun#236: companion-bed rule's `"P55200x"` (fact 3), and that it charges every stay at 2026 rates without checking billed 510121 (`refakatci.py:41,176-184`);
  - Safa675/Bilun#237: `temporal_anomaly.py:55-58` treating 50/51 codes as surgery and missing 60xxxx–62xxxx;
  - Safa675/Bilun#238: duplicate `material_code` deduplication skipping additional lines (`claim_materials.py:165-185`, `material_bundling.py:401-404`, `specialty_materials.py:205-208`);
  - Safa675/Bilun#239: demo-only inputs (`demo_vignettes.json` and `scenario_tag`, fact 6);
  - Safa675/Bilun#240: the loader requiring answer rows and payable columns in `real_claims` mode (fact 5);
  - Safa675/Bilun#241: price-history `valid_to` handling, open-ended repealed codes and duplicate 2026-01-31 rows (fact 7);
  - Safa675/Bilun#242: ICU tier (`yoğun bakım basamaklandırması`) overbilling detector under SUT §2.4.4.H (fact 3).
- **Order:** #230–#234 and #236–#241 must land before P7, or the new cohort shows the engine's errors on clean data; #242 is needed if ICU tiering is included in the fault registry (D4).

## Phases

### P0 — Decisions and baselines
- [ ] Q1–Q6 answered.
- [ ] The engine output on today's cohort is recorded as a baseline (`reports/synthetic-data/2026-10-14-audit-scripts/engine_output/`).
- [x] The test files are classified (`plans/data/2026-10-15-synthetic-v3-test-pins.md`): 25 files with about 280 load-bearing pins need work in P6; 54 tests failed under ID, tag or seed changes alone.

### P1 — Reference data
- [ ] Chapter table from the raw EK-2B headings.
- [ ] Group table under the confirmed source (D2).
- [ ] Code sets for anaesthesia, bed, ICU and visits.
- [ ] Dated EK-3 index (Q1).
- [ ] Price-history cleanup (fact 7) with tests.
- [ ] Lab reference table.
- [ ] ICD-10 list (Q5), drug crosswalk and prices (Q4).
- [ ] Every table has a schema test and a provenance note.

### P2 — Pathways
- [x] The 8 showcase pathways, written (2026-10-17). Each expands with its own pins to the golden clean bill of its story; two independent reviews found and fixed the defects. The 77 `judgment` items wait for a clinician (Q3): `reports/synthetic-data/2026-10-17-pathways-judgment-list.md`.
- [ ] The rest of the first 20.

### P3 — Fault registry and answer key
- [x] Fault registry (`data/synthetic/faults/fault_registry.yaml`, 8 faults, 26+ check ids), `apply_fault`, the injection record (`FaultInjectionRecord`, `make_record`) and the answer rows (`build_expected_rule_outputs`), 2026-10-17; merged in #313. Design: `plans/data/2026-10-17-p3-fault-registry-design.md`. Each mutation is proven against the faulty bills of `stories.py` (`tests/fixtures/pathways/golden_faulty/`). The file `data/synthetic/cohort_registry.json` that carries the records is written by the generator (P4, #314).
- [x] The loader change: not needed. PR #246 (issue #240) already makes the answer rows optional and checks only the rows present.
- Open for P6: three readers depend on the v2 shape of `expected_rule_outputs` (see `data/synthetic/faults/README.md`, "What P6 must change").
- This comes **before** the showcase bills, because they carry injected faults.

### P4 — Generator v3 (Polars)
Merged in #314 for the 8 showcase encounters (`scripts/synthetic/cohort/`).
- [ ] Facility and patient state, bill composer and pickers. (The composer exists for the 8 showcase encounters; facility and patient state and the pickers wait for the other 42 patients.)
- [x] Showcase bills built from recipes through the same composer, not as hard-coded bills. (`data/synthetic/cohort/showcase_recipes.yaml`; `python -m scripts.synthetic.cohort.build` writes the 9 claims tables, the 3 clean tables and `cohort_registry.json`; two builds are byte-identical.)
- [x] Remove the per-patient branches (`gen/patients.py:211-298`) and `gen/specs.py`. (P7-lite deleted the whole legacy generator `scripts/synthetic/gen/` with its exporters.)
- [x] Seed every random source. (The v3 builder has no unseeded source: lab values come from a deterministic SHA-256 draw and rebuilds are byte-identical. The unseeded `sag_sol` code (`gen/claim_lines.py:5,40`) goes with the legacy generator in P7-lite.)

### P5 — Plausibility tests in CI
- [x] The D5 tests with mutation tests, first version (#314): `plausibility.py` (25 claims-table ids), `plausibility_clean.py` (12 clean-table ids) and `plausibility_all.py` (one entry point). The 8 clean twins trip nothing; the faulty bills trip a pinned set.
- [ ] Open: hardening of the E2 checks (materials, prices, money, labels; the reviewer's 57-case proposal kills 48 of the 58 surviving mutants), and the lab and prescription realism items (they wait for the clinical review, #309).

### P6 — Tests
- [x] Re-point or replace the pins classified in P0, in the same PR as the regeneration, so CI never sits red between them. (Done on the P7-lite branch: the pins of `plans/data/2026-10-17-p6-p7-legacy-pins.md` are migrated, 21 Python test files (1 deleted, 20 rewritten on the registry roles or on self-made fixtures) and the three live-app scripts; the per-file table is in `tasks/todo.md`. It supersedes the 2026-10-15 inventory.)

### P7 — Regenerate and verify (after the D6 engine fixes)
P7-lite (done on branch `claude/synthetic-v3-p7-lite-swap`, this PR): the 8 showcase patients replace the legacy 50 in `data/synthetic/sut/`, the legacy generator, validator and workbooks are deleted, and the registry is `data/synthetic/cohort_registry.json`. The other 42 patients wait.
- [ ] Regenerate the cohort and rebuild the cache. (The 8 showcase patients: done in P7-lite. The other 42: later.)
- [x] Run the engine and compare its findings with the injection log, for the 8 showcase stories (#314, `scripts/synthetic/cohort/engine_proof.py`: every fault is found with its proven amount and the clean twins show nothing; S8 is the one documented divergence, issue #311 item 6). Precision and recall over the full cohort wait for the other 42.
- [ ] Re-run the audit scripts: every FATAL row reads 0.
- [ ] A human reviews the 8 showcase bills in the UI. (A first pass is done: S1 and S7 by hand and the engine's output for all 8 stories in-process, listed in `tasks/todo.md` (S3, S4 and S8 have no row that explains their money). Safa's review is still open.)
- [ ] Update staging through the wrapper after merge (Safa's call).

## Milestone order (judgment)

1. P0, P1 and the 8 showcase pathways of P2.
2. P3.
3. P4 and P5 for the showcase patients: the default landing and the showcase pages become credible first.
4. The remaining pathways, P4 for everyone, P6 and P7.
5. The cohort-wide dashboard stays wrong until step 4 and the D6 fixes are done. Say so in demos meanwhile.

## Effort (estimate from the research pass; judgment)

| Part | Working days |
|---|---|
| Reference data, incl. the EK-3 index and the history cleanup | 2–4 |
| Pathways and review | 4–6 |
| Patient and facility state | 1 |
| Composer | 3–4 |
| Pickers | 3–4 |
| Faults and loader | 2–3 |
| Showcase and regression recipes | 2–3 |
| CI tests | 2–3 |
| Test re-pointing | 3–4 |
| **Total** | **about 22–32** (D6 engine fixes not included) |

## Definition of done

- The audit scripts report 0 on every FATAL check (audit sections 1–8).
- The engine's findings on the cohort equal the injection log: every injected fault is detected or listed as a known gap, and every finding maps to an injected fault.
- Billed-at-risk never exceeds billed, per line, per patient and for the cohort.
- CI runs the plausibility tests, and each has a passing mutation test.
- Safa (or the Q3 reviewer) signs off the 8 showcase bills in the UI.

## Out of scope

- The engine fixes themselves (D6).
- Removing the real ILAY data (`plans/security/2026-10-14-remove-ilay-real-data-plan.md`).
  - Its Phase 1 should land first. Today the exporter overwrites files without clearing `claims/`, because the ILAY folder sits inside it (`scripts/synthetic/exporters.py:354-358`).
- Real claims data.
- UI redesign.

## Risks

- **Clinical review (Q3) is the bottleneck.** Without it the pathways are one person's judgment.
- **The anaesthesia source must be settled once (D2).** If the engine and the generator use different sources, the engine flags clean bills.
- **Drug prices depend on an external list (Q4).**
- **The loader change touches production code.** Decide its behaviour for real data in the same PR.
- **Test churn is large** (about 375 pins).
