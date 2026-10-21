# Care pathways (synthetic demo v3, P2)

A pathway is the reviewed description of what one diagnosis in one care setting produces on a hospital bill: the department, the stay, and every procedure, lab, drug and material with when and how many. It is data, written once. Four readers use it:

- a **human reviewer** (a physician or a billing specialist) checks that it is clinically and billing-wise right;
- the **bill composer** (P4) draws a patient, pins the ranges and turns the pathway into a clean bill;
- the **plausibility tests** (P5) compare generated bills with it;
- the **fault registry** (P3) injects exactly one fault into the clean bill.

Faults, prices, amounts and totals are **not** part of a pathway. A pathway is the clean story, generalized only where a range is natural.

| Path | What |
|---|---|
| `data/synthetic/pathways/<id>.yaml` | one pathway per file; the file name is the `id` |
| `data/synthetic/faults/siblings/<id>.yaml` | fault-sibling pathways (a sibling is a pathway without a golden in `golden/`; its own test checks it against `golden_faulty/`) |
| `scripts/synthetic/pathways/schema.py` | the pydantic models (every one forbids unknown fields), the day grammar, the pin rules, and `CHECKS`, the registry of check ids |
| `scripts/synthetic/pathways/loader.py` | `load_pathway(path)`, `load_all(directory)`; an error names the file, the field and a check id |
| `scripts/synthetic/pathways/expand.py` | `expand(pathway, pins=None, *, annotate=False)`: pins in, clean bill out (golden format, or with pathway line references when `annotate=True`); pure, no catalog, no price, no randomness |
| `scripts/synthetic/pathways/checks.py` | `Catalogs` and `run_all(pathway, catalogs)`: the pathway against the catalogs and its own logic |
| `tests/fixtures/pathways/golden/S1.json` … `S9.json`, `S10.json`, `S11.json`, `S12.json`, `S14.json`, `S22.json`, `S39.json`, `S40.json` | the clean bills of the showcase stories that `stories.py` builds, exported from it by another script (`golden_faulty/` holds the faulty bills, all but S39, a clean bill without a fault: `CLEAN_ONLY` in `stories.py`). A story has goldens exactly when `stories.py` builds it (`tests/fixtures/pathway_goldens.py`); a pathway of a later story has none and is not compared with one |

## Read a pathway top to bottom

Open `copd_exacerbation_pneumonia_ward.yaml` next to this text.

1. **Identity and setting.** `id`, `title`, `claim_type` (`yatis`, a stay, or a visit: `acil`, `poliklinik` or `gunubirlik`), `billing_mode` (`package` = EK-2C, `itemized` = EK-2B hizmet başı), `department` (the header name and the default EK-2A branch of every line). A ward stay that is admitted on the day the same patient leaves an ICU bill also sets `arrives_from_icu: true` (see "A ward stay that arrives from an ICU bill" below).
2. **`window`** (optional). The service window of the pathway. Default: the `window` of `code_sets.yaml`, 2026-02-01 to 2026-09-30. A pathway may narrow it, never widen it, and a narrowed window carries `start`, `end` and a `source`: one sentence, 160 characters at most, that says why. **Every code must be in force on every day of the window.** S2 ends on 2026-08-28: KLACID 500 MG IV leaves EK-4A on 2026-08-29. EK-4A rows are half-open, `[valid_from, valid_until)`, so `valid_until` is the first day a drug is not in force and the checks use the day before it (as the engine does).
3. **`patient`**: the sexes and the age range the pathway allows. **`nights`**: the length-of-stay range (stays only). **`op_day`**: the operation day as a day expression, if the pathway has one.
4. **`diagnoses`**: one primary, the others secondary, each with the day it is coded.
5. **`procedures`**, **`materials`**, **`drugs`**, **`performed`**: the lines of the bill.
6. **`notes`**: free text for the reviewer (for example, S1 notes that its ER visit is billed on its own acil takip). Nothing reads it.
7. **`showcase`**: the pins of the story. Expanding the pathway with them must give exactly `tests/fixtures/pathways/golden/<story>.json`.

Quote every code, name, barcode and date: YAML turns `510010` into a number and `2026-03-09` into a date, and the loader refuses both.

## Grammar

### Days

A day is an **anchor** with optional whole days: `admit`, `op` (the operation day, only when the pathway has `op_day`), `discharge` (stays only). `admit+2` is the third day, `op+1` the day after the operation, `discharge-1` the last night. A **range** `a..b` is inclusive and makes one bill line per day. `days` takes one expression or a list: `[admit, admit+3]` is two days. Nothing else is allowed. Day 0 is `admit`; for a stay of N nights `discharge` is day N. For a pathway without a stay (a visit: `acil`, `poliklinik` or `gunubirlik`) `admit` is the visit day and nothing else exists.

| Expression | N = 6 nights | Lines |
|---|---|---|
| `admit..discharge` | 9 to 15 March | 7 (a bed for every calendar day, discharge day included) |
| `admit..discharge-1` | 9 to 14 March | 6 (one per night: companion, nebulizer) |
| `admit..admit+1` | 9 and 10 March | 2 |
| `[admit, admit+3]` | 9 and 12 March | 2 |

Every expression must land inside the stay for the shortest, the longest and the pinned stay (`days.in_stay`), so pick `nights.min` with the fixed offsets in mind. A `bed` line must cover exactly `admit..discharge` and a `companion` line exactly `admit..discharge-1` at those three stays (`stay.coverage`), so the lines grow with the nights (a pathway with `arrives_from_icu` has its bed from `admit+1`, see "A ward stay that arrives from an ICU bill").

### Quantities

- A procedure or material line has `qty` (default 1) **per bill line**. `qty: 16` with `days: admit..admit+1` is 16 hours on each of two days. "Per calendar day" and "per night" are day ranges, one line each. A performed line has no quantity: it is one log entry.
- A **drug** is one line on the first day of its course with the whole quantity. Exactly one form:
  - `qty: 7`: a fixed number of units;
  - `per_night: 1`: units times the nights of the stay (must start on `admit`);
  - `per_day: 2` with `course_days: {min, max, basis, source}`: units a day times the course days chosen by the pins. `min == max` is a fixed duration.
- `unit` and `per_box` follow the EK-4A pack. The count is the units used (the review, Q7: drugs are billed by units used, fractions allowed), with two exceptions where the story bills a whole box with `unit: box`: the ipratropium/salbutamol nebules of S2 (one box of 20) and the paracetamol of S4. Their `source` says so; they are the stories' choice, not a rule.
- A course must end on or before the discharge day (`drug.course`): the shortest course must fit the shortest stay, and `expand` refuses pins whose course outlasts the pinned stay. The composer draws the nights first and then the course days from `min` to the days left.

### Line kinds (`procedures[].kind`)

| kind | Catalog | Notes |
|---|---|---|
| `package` | EK-2C (P-codes) | the only kind in a package pathway |
| `operation` | EK-2B chapter 6 | itemized pathways |
| `bed`, `companion` | 510010 or 510120; 510121 | |
| `newborn_bed` | the incubator 510070 or the cot 510081 (EK-2B chapter 1) | a newborn stay (below); itemized pathways only |
| `icu_day`, `icu_package` | 510090 (EK-2B chapter 1); an EK-2C ICU package P552001-3 or P552006-8 | an intensive-care stay (below); itemized pathways only |
| `anaesthesia` | the 14 codes of `code_sets.yaml` | needs `group` and `operations` (below) |
| `exam` | EK-2B chapter 2 | |
| `lab` | EK-2B chapters 9 and 10 | `items:` lists a panel (several codes, same days, quantity and branch); every `L` code must be in `lab_reference.csv` |
| `imaging` | EK-2B chapter 8 | |
| `procedure` | EK-2B chapters 3, 4, 5 and 7 | |

`specialty` is an EK-2A branch code; a line without one gets the department's. Name a branch only where it differs (anaesthesia 3100, radiology 3300, neurology 1300). A **package pathway has package lines and linked materials only**: bed, companion, exams, labs, imaging, anaesthesia and drugs are inside the package (SUT 2.2.2.B-1(1), C000685 to C000699). The longest stay must end inside the package window of its group (A 15 days, B 10, C 8, D 5, E 3, counted from the package day; C000702 to C000706).

### Intensive care (`icu_day`, `icu_package`)

SUT 2.4.4.H (C001234, C001243): the first ICU day and the day the patient leaves are billed per service with the EK-2B day rate 510090 (`icu_day`), the days between from EK-2C with an ICU package (`icu_package`; one tier per stay). The engine counts the ICU days of a bill as `discharge - admission` (`icu_puani.py`), so the ICU lines are the bed lines of the bill and cover `admit..discharge-1` once each; the discharge day is the transfer day and carries no ICU line. With nights N the 510090 lines sit on days 0 and N-1 and the package lines on days 1..N-2, which the days `[admit, discharge-1]` and `admit+1..discharge-2` give at every stay (`icu.day_pattern`, `stay.coverage`; `nights.min` is 3). A ward `bed` line beside ICU lines is a defect (the engine would count the whole stay as ICU days). An ICU package is no surgical package: an itemized pathway may hold it (`package.mode`), a package pathway may not hold an ICU line, and the package window and its EK-2C group do not apply (an ICU package has no group; `package.window`). `procedure.kind` ties `icu_day` to 510090 and `icu_package` to the ICU packages of `code_sets.yaml`. A fault may set a `billed_ratio` on an `icu_package` line (`fault.billed_ratio_target`). The clean S11 pathway is `urosepsis_septic_shock_icu_stay.yaml`.

### Newborn bed (`newborn_bed`)

EK-2B 510070 (Kuvöz) and 510081 (Kot, beşik) cover yemek, yatak and vizit, once a day, never together and never beside 510010 (`yenidogan_yatak.py`, `claim_yatak_newborn_overlap.py`): the ward bed and the two newborn beds are alternatives for one patient-day. The engine counts the newborn bed days as `discharge - admission + 1`, the discharge day included, like the ward bed. So the `bed` and `newborn_bed` lines of a newborn stay together cover `admit..discharge` once each (`stay.coverage`): an incubator on every day (S12), or the incubator on the first days and the ward bed on the rest. A stay with an ICU line has no newborn bed line (a newborn intensive-care stay is 510090 with P552006-8, `icu_day` and `icu_package`, and the newborn motor leaves ICU claims to the ICU motor). A newborn bed line in a package bill is inside the package (`package.mode`). `procedure.kind` ties `newborn_bed` to 510070 and 510081 and `bed` to 510010 and 510120. The newborn is age 0 (`patient.age`: `min: 0`); the vital signs of such a bill follow the infant ranges (`scripts/synthetic/cohort/clinical.py`, `plausibility_clean.py`), and the engine reads the episode as a newborn's from a Z38 or P00-P96 diagnosis or a department named yenidoğan. The clean S12 pathway is `late_preterm_newborn_incubator_stay.yaml`.

### A ward stay that arrives from an ICU bill (`arrives_from_icu`)

A patient who leaves intensive care for the ward has two bills: the ICU bill, whose last day is the transfer day, and the ward bill, which is admitted on that day. EK-2B 510090 covers yemek, yatak and vizit, so the ICU bill pays that day's bed; a ward bed on it too is double billing (`yatak_icu_overlap.py`: the Wave A rule `yatak_icu_overlap_510010`), and the standard-bed motor takes the day out of the ward bill's expected bed days. A pathway of that ward bill sets `arrives_from_icu: true`: its `bed` line covers `admit+1..discharge` (not `admit..discharge`; `stay.coverage` tests it at every stay), the companion still covers every night `admit..discharge-1`, and the pathway has no ICU or newborn bed line of its own (`stay.coverage`). The flag needs a stay (`schema.stay_shape`). The cohort check of the tables knows the same day (`stay.bed_coverage`): a stay that begins on the day an ICU stay of the same patient ends needs no bed line for it and takes none. The faulty sibling is the same pathway without the flag, with a bed for every calendar day. The clean S14 pathway is `urosepsis_ward_stay_after_icu_transfer.yaml`.

### A visit (`poliklinik`, `gunubirlik`, `acil`)

`yatis` is the only claim type with a stay. `acil` (an ER visit), `poliklinik` (an outpatient application) and `gunubirlik` (a day case) are visits: the pathway has no `nights`, `admit` is the one day of every line (`days: admit`), the header has no admission and no discharge date (`claim_start_date` equals `claim_end_date`), the anchor `discharge` does not exist, and a `per_night` drug or `arrives_from_icu` is a defect (`schema.stay_shape`, `schema.anchor_undefined`; the message names the claim type). The checks test a visit once, at no nights (`_stay_cases`). A visit of a patient who has other bills is a bill of its own: its date is the recipe's pin (`pins.admit`), and the cross-bill rules read the patient's other bills. The first `poliklinik` pathways are the control and the second visit after the stay of S4 (`pyelonephritis_dementia_post_discharge_control.yaml`, `pyelonephritis_dementia_second_visit_ultrasound.yaml`); the second visit's faulty sibling also bills the examination 520030 (`pyelonephritis_dementia_second_visit_exam_billed.yaml`). A bill whose fault depends on its date in relation to another bill (a second visit to a branch within 10 days) differs from its clean twin by a line, not by a date: a sibling is expanded with the same pins, so the twin has the same day, header and diagnoses (the exam fee of such a visit is not payable, SUT C000573). The first `acil` pathway after S7 is the ER visit of patient 12 (`gi_bleed_melena_er_visit.yaml`, S10), whose faulty sibling also bills the manual haematocrit L103120 beside the hemogram (`gi_bleed_melena_er_visit_manual_hct_billed.yaml`); the admission two days later is a stay of its own (`gi_bleed_admission_colonoscopy.yaml`, S22). The `gunubirlik` type is grammar only until a day-case story uses it (S20); the cohort check of the tables does not yet judge its dates.

### Anaesthesia

One line per session, `kind: anaesthesia`, with `operations: [<operation line ids>]` and `group: B`. The group is derived from the puan of the operation (the sum for several operations) with the `surgical_group_bands` of `code_sets.yaml`; it must hold **on every day of the window**, and the band tables switch on 2026-04-16, so an operation near a band edge needs a window that starts after the switch. The code must be the group's code (`single` for one operation, `multiple_operations` for several).

### Materials

`id`, EK-3/F-1 `code` and `name` (site and description joined by ` | `, as the catalog lists them), `material_type` (`implant` or `consumable`), `qty`, `day`, `linked_to` (the package or operation line that used it) and `flags` (`titubb_registered`, `uts_registered`). Only EK-3/F-1 is checked so far.

### Session roles

Operations of one session carry `session_role` on a single-day line: `primary` (exactly one per session day, and the one with the highest puan), `same_incision`, `separate_incision`. A line of kind `procedure` may carry a role too when its code is in EK-2B chapter 7 (group 7, the medical procedures such as the endoscopies: `procedure.kind` refuses a role on any other procedure): S22 bills the colonoscopy `701450` as `primary` and the polypectomy through it, `701460`, as `separate_incision` (half of its puan; the two have the same puan, so either may lead). The expander turns the role into `billed_ratio` from a constant table in `expand.py`: packages 1 / 0.25 / 0.50 (SUT 2.2.2.B(3), C000670, C000671), itemized 1 / 0.30 / 0.50 (SUT 2.2.2.A(5), C000660, C000661). The +25 points for different specialties (C000662, C000674) are not applied: issue #295, marked `pending`.

### Diagnoses, drugs and indications

`icd10` must be an active SKRS **leaf** code and `name` its `name_tr`. A drug may name `indication: G20`; that diagnosis must be in the pathway and must not be optional, so the drug can never be billed without it (`drug.indication`).

### Optional items and the pins

An item with `optional: {probability, basis, source}` is in the bill only when its id is in `showcase.include` (a diagnosis is identified by its ICD code). The pins are `story`, `sex`, `age`, `admit` (first day), `nights`, `include` and `course_days` (drug id to days). Every pin must lie inside the declared range (`pins.*`), and the stay inside the window.

### Provenance: `basis` and `source`

Every diagnosis, line, range and probability carries both. A narrowed `window` carries a `source` only, no `basis`: its reason is a catalog fact. `source` is one short sentence (160 characters at most) that names the document, clause or guideline.

| basis | Use when | `source` should |
|---|---|---|
| `sut` | an SUT clause decides it | give a clause id (`C000685`) or an annex (`EK-2B`); every `C…` id must be an in-force clause of `data/gazette/sut_clauses.parquet` |
| `ek2b_aciklama` | the EK-2B açıklama column of the code decides it | name the code and quote the limit |
| `medula_kilavuz` | the MEDULA hospital web-service guide decides it | give the page |
| `guideline` | a named clinical guideline decides it | name it |
| `judgment` | nothing citable | say what the choice is anchored on; a clinician checks these |

The checks enforce two things about a `source`, and only these. `source.clause_exists`: every `C…` id in any `source` (of any basis, and the window's) must be an in-force clause of `sut_clauses.parquet`. `source.sut_cites`: a `sut` source must give a clause id or an `EK-` annex. What the other bases ask (a quoted limit, a page, a guideline name, what a judgment is anchored on) is checked by review only, and so is whether a cited clause says what the source claims. Do not invent a clause id: look it up with Polars in `data/gazette/sut_clauses.parquet`.

### `pending`

`pending: "#297 Q2"` marks a line that waits for an answer from a field expert (#297 Q2 companion days: whether the discharge day counts; Q4 scope of "birlikte faturalandırılmaz": the blood-gas / Na-K exclusion on the same date only; Q5 direct LDL; #295 the +25 points per session or per line). Use it only where the question applies.

## What the checks say

Run them on one file or all: `.venv/bin/python -m scripts.synthetic.pathways.checks [file ...]`. A message names the field (`procedures[bed]`) and, for a name or window problem, the catalog's own value, so copy the right name from the message. Each id has a mutation test in `tests/unit/synthetic/test_pathways_schema.py`.

| Check | What it finds |
|---|---|
| `yaml.invalid`, `hygiene.forbidden_key`, `hygiene.anon_text`, `hygiene.price_text`, `hygiene.id_like_number`, `schema.id_mismatch` | bad YAML or a repeated key; a key containing price, amount, total or package_candidate (any case); in any key, string or comment, text that looks like an ANON identifier (`ANON_7`, `anon-7`, `ANON 7`, any case), a non-zero currency amount (`12 TL`, `12 TRY`, `12 ₺`, `₺12`; "0 TL" passes) or an isolated 11-digit number (barcodes have 13); a file name that is not `<id>.yaml` |
| `schema.*` | an unknown or missing field (including `basis`, `source`, and the `source` of a window), a bad enum or value, a bad day expression, min above max, a probability outside [0, 1], a duplicate id, a dangling reference, an undefined anchor, a malformed line, a wrong drug quantity form, not exactly one primary diagnosis, a stay without nights, nights on a visit, a visit that arrives from an ICU, `discharge` on a visit |
| `procedure.in_force`, `procedure.name`, `procedure.kind` | an EK-2B/EK-2C code missing on some day of the window; a name that is not the catalog's (whitespace-normalized); a kind that does not fit the code's chapter (an ICU kind on a code that is not an ICU day or package, a `newborn_bed` on a code that is not the incubator or the cot) |
| `material.*`, `drug.in_force`, `drug.name`, `drug.inn` | the same for EK-3/F-1 and EK-4A; `inn` must be the crosswalk's `active_ingredient` |
| `drug.indication`, `drug.course` | an indication that is not a diagnosis of the pathway or is optional; a `per_night` drug that does not start on admit; a course that outlasts the stay (the shortest course at the shortest stay, and a pinned course at the pinned stay) |
| `icd.exists`, `icd.active`, `icd.leaf`, `icd.name`, `icd.sex_gate` | the SKRS table; a sex-gated code with a sex list that allows the other sex |
| `lab.in_table`, `lab.name`, `specialty.exists` | an `L` code absent from `lab_reference.csv` or named differently; an unknown EK-2A branch |
| `package.mode`, `package.window` | a package pathway with a line the package includes, an ICU line too (or the reverse; an ICU package is no surgical package); a stay past the package window (an ICU package has no window) |
| `icu.day_pattern` | an ICU stay whose 510090 lines are not on the first and the last ICU day, whose package lines are not on every day between, or that mixes package tiers |
| `anaesthesia.group`, `anaesthesia.code`, `session.primary`, `session.order` | the puan band; the group's code; the primary operation of a session |
| `pins.*`, `days.in_stay`, `days.duplicate`, `stay.coverage` | pins outside the ranges, unknown or non-optional ids, missing pins, dates outside the window; days outside the stay or twice on one day; a bed line off `admit..discharge` (off `admit+1..discharge` on a stay that arrives from an ICU bill, which also has no ICU or newborn line) or a companion line off `admit..discharge-1`; on a newborn stay, the ward and newborn bed lines together not on every day of `admit..discharge` exactly once; on an ICU stay, ICU lines off `admit..discharge-1`, on the discharge day, twice on a day, or a ward or newborn bed beside them |
| `source.clause_exists`, `source.sut_cites`, `window.valid` | a cited clause that does not exist or is not in force; `sut` without a citation; a window outside the default |

## Add a pathway

1. Copy the closest pathway (`appendicitis_lap_appendectomy_package.yaml` for a package, `copd_exacerbation_pneumonia_ward.yaml` for an itemized stay) to `<id>.yaml`.
2. Write the clean story only: no item the story does not have, none dropped. Generalize only the sexes, the age range, the nights, drug course days and items the story or the review treats as optional. Give every range and every item a `basis` and a `source`.
3. Run the checks (command above) until they are silent. To find a catalog name, write the code with a placeholder name (`"??"`) and copy the real name from the `procedure.name`, `material.name`, `drug.name` or `icd.name` message. A `*.in_force` message names the first day a code is missing: narrow the `window` to the days it is in force and say why in its `source`, as S2 does.
4. Write the `showcase` pins from the story and make the round trip pass: `expand(pathway)` must equal `tests/fixtures/pathways/golden/<story>.json`. Never edit the golden to fit the YAML.
5. Update the status table below.

## Expander annotations and fault siblings (P3)

- **`expand(pathway, pins=None, *, annotate=False)`**: the default (`annotate=False`) returns the golden format unchanged. With `annotate=True`, rows carry pathway line references so the fault registry can target lines by id: every procedure row adds `entry_id` (the pathway line id), `kind` (the line's kind) and `day_index` (0-based position of that row's date among the dates the line resolves to, in date order; for a lab panel with several codes every code on the same date has the same index); every material and every performed row adds `entry_id`; every drug row adds `entry_id` and `indication` (the drug's indication ICD-10 code or `null`).
- **`data/synthetic/faults/siblings/`**: a sibling is a pathway without a golden in `tests/fixtures/pathways/golden/` (so every pathway of a story that `stories.py` builds keeps its 1-to-1 pairing with its clean golden). It obeys the same schema, hygiene and catalog checks (`run_all`), and its own test (`tests/unit/synthetic/test_fault_siblings.py`) checks that expanding it with its `showcase` pins equals `tests/fixtures/pathways/golden_faulty/<story>.json`. `appendicitis_lap_appendectomy_itemized.yaml` is S1's itemized sibling.

## Tests

```
.venv/bin/python -m pytest tests/unit/synthetic/test_pathways_schema.py tests/unit/synthetic/test_pathways_roundtrip.py tests/unit/synthetic/test_pathways_golden.py tests/unit/synthetic/test_pathways_annotate.py tests/unit/synthetic/test_fault_siblings.py -q
```

- `test_pathways_schema.py`: every real pathway loads and passes every check; the folder holds only this README and top-level `*.yaml` files (a `.yml` file or a sub-folder would never load); every check id in `CHECKS` has a mutation case that takes a real pathway, proves it clean, applies one defect and asserts that exactly the expected ids fire; further tests pin the edges of the checks (the package window, the stays tested, the window and range edges, the EK-4A last day against the engine's reader).
- `test_pathways_roundtrip.py`: per pathway file, `expand` equals the golden; a flipped optional item or course changes the bill; the bed and companion lines gain one bill line per extra night; a later admission moves every date; pins outside the ranges, or a course that outlasts the pinned stay, are refused; every golden has a pathway and every pathway of a story that `stories.py` builds has its golden (a pathway of a later story needs none). A broken file fails only its own cases.
- `test_pathways_golden.py`: the clean and faulty golden files are well formed, each faulty golden differs from its clean golden, and both directories equal a fresh export of `stories.py`: the test runs `reports/synthetic-data/2026-10-15-showcase-proofs/export_clean_lines.py --check` in a subprocess (about a second), so a pathway and its golden cannot be changed together unnoticed.
- `test_pathways_annotate.py`: `expand(p) == expand(p, annotate=False)` for every pathway; stripping the annotation keys from `expand(p, annotate=True)` reproduces the default expansion; every `entry_id` is a pathway line id, every included line appears, `day_index` is `0..n-1` in date order per `entry_id`, and drug rows carry `indication`.
- `test_fault_siblings.py`: every `*.yaml` in `data/synthetic/faults/siblings/` loads, passes `run_all`, and expands to `tests/fixtures/pathways/golden_faulty/<story>.json` (with in-memory mutation guards).

## Not expressible yet

- One pathway has one billing mode: an EK-2C package and itemized EK-2B lines in one bill are not expressible (SUT 2.2.2.B(3) c, ç).
- Itemized lines after the package window (long package stays) are not expressible; `package.window` refuses such a stay.
- Materials are checked against EK-3/F-1 only.
- Procedure lines have no flags (the stories set none).
- `showcase` is required, so a pathway without a showcase story (the rest of the first 20) needs the schema relaxed. `Pins.story` is `S` and a number from 1 up (it was limited to `S1`..`S8` until the ninth story).
- Newborn intensive-care tiers (P552006-8) are modelled as ICU packages (`icu_package`), not as a newborn stay; rooming-in (a baby beside the mother, for whom 510081 is not billed) cannot be shown, because the engine's `rooming_in_claim_ids` has no caller (issue EI-14 of the coverage plan).
- A drug course that runs to discharge from a later start (S6 levodopa, through the NG tube from day 3) has no "until discharge" form: `course_days` is drawn independently of the nights, so P4 must clamp it to the days left.
- The clinical sex of a diagnosis is judgment, not data. S5's M81.09 is postmenopausal osteoporosis, so S5 says `sex: [F]`, but the ICD table's sex column covers only 97 neoplasm codes (C and D), so `icd.sex_gate` cannot see it.
- *(Resolved in P3 slice 1 — #311 items 4 & 5.)* `expand(..., annotate=True)` now attaches `entry_id`, `kind`, `day_index` and `indication` so the fault registry (P3) can tell which pathway line a row came from, and S1's itemized fault sibling lives in `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml`.
- Guarded by review only: a required item made optional and pinned in, a range widened beyond the pins, a probability, a title, a note, the id of a line nothing refers to, an edit of a `source`, a `basis` or a `pending` marker, and whether a cited clause says what its source claims.
- Stay scaling is checked for `bed`, `newborn_bed` and `companion` lines only. A drug rewritten from `per_night` to a fixed `qty` that matches the showcase nights, or S2's nebulizer (`admit..discharge-1`) fixed to the showcase nights, passes every check; it is a plausibility question (P5), not a validity one.

## Status

| Story | Pathway | State |
|---|---|---|
| S1 | `appendicitis_lap_appendectomy_package` | done |
| S2 | `copd_exacerbation_pneumonia_ward` | done |
| S3 | `lumbar_stenosis_decompression_itemized` | done |
| S4 | `pyelonephritis_dementia_delirium_ward` | done |
| S5 | `femoral_neck_fracture_cemented_hemiarthroplasty_package` | done |
| S6 | `aspiration_pneumonia_parkinson_ward` | done |
| S7 | `pleuritic_chest_pain_er_pulmonary_embolism_ruled_out` | done |
| S8 | `cholelithiasis_umbilical_hernia_two_packages` | done |
| S9 | `lumbar_stenosis_decompression_foraminoplasty_itemized` | done (2026-10-21; sibling of S3 with an optional second operation) |
| S11 | `urosepsis_septic_shock_icu_stay` | done (2026-10-21; the ICU grammar) |
| S12 | `late_preterm_newborn_incubator_stay` | done (2026-10-21; the newborn grammar) |
| S10 | `gi_bleed_melena_er_visit` | done (2026-10-21; an `acil` visit; sibling `gi_bleed_melena_er_visit_manual_hct_billed`, the manual haematocrit beside the hemogram) |
| S14 | `urosepsis_ward_stay_after_icu_transfer` | done (2026-10-21; a ward stay that arrives from an ICU bill) |
| S22 | `gi_bleed_admission_colonoscopy` | done (2026-10-21; the admission after the ER visit of S10; a colonoscopy session with a chapter-7 add-on, the polypectomy at 50 %) |
| S39 | `pyelonephritis_dementia_post_discharge_control` | done (2026-10-21; the first `poliklinik` pathway, a clean bill) |
| S40 | `pyelonephritis_dementia_second_visit_ultrasound` | done (2026-10-21; a second visit to the same branch within 10 days; sibling `pyelonephritis_dementia_second_visit_exam_billed`) |
