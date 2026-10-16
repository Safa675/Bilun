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
| `scripts/synthetic/pathways/schema.py` | the pydantic models (every one forbids unknown fields), the day grammar, the pin rules, and `CHECKS`, the registry of check ids |
| `scripts/synthetic/pathways/loader.py` | `load_pathway(path)`, `load_all(directory)`; an error names the file, the field and a check id |
| `scripts/synthetic/pathways/expand.py` | `expand(pathway, pins=None)`: pins in, clean bill out (golden format); pure, no catalog, no price, no randomness |
| `scripts/synthetic/pathways/checks.py` | `Catalogs` and `run_all(pathway, catalogs)`: the pathway against the catalogs and its own logic |
| `tests/fixtures/pathways/golden/S1.json` … `S8.json` | the clean bills of the showcase stories, exported from `stories.py` by another script |

## Read a pathway top to bottom

Open `copd_exacerbation_pneumonia_ward.yaml` next to this text.

1. **Identity and setting.** `id`, `title`, `claim_type` (`yatis` or `acil`), `billing_mode` (`package` = EK-2C, `itemized` = EK-2B hizmet başı), `department` (the header name and the default EK-2A branch of every line).
2. **`window`** (optional). The service window of the pathway. Default: the `window` of `code_sets.yaml`, 2026-02-01 to 2026-09-30. A pathway may narrow it, never widen it. **Every code must be in force on every day of the window.** S2 ends on 2026-08-29 because KLACID 500 MG IV is in EK-4A only until then.
3. **`patient`**: the sexes and the age range the pathway allows. **`nights`**: the length-of-stay range (stays only). **`op_day`**: the operation day as a day expression, if the pathway has one.
4. **`diagnoses`**: one primary, the others secondary, each with the day it is coded.
5. **`procedures`**, **`materials`**, **`drugs`**, **`performed`**: the lines of the bill.
6. **`notes`**: free text for the reviewer (for example, S1 notes that its ER visit is billed on its own acil takip). Nothing reads it.
7. **`showcase`**: the pins of the story. Expanding the pathway with them must give exactly `tests/fixtures/pathways/golden/<story>.json`.

Quote every code, name, barcode and date: YAML turns `510010` into a number and `2026-03-09` into a date, and the loader refuses both.

## Grammar

### Days

A day is an **anchor** with optional whole days: `admit`, `op` (the operation day, only when the pathway has `op_day`), `discharge` (stays only). `admit+2` is the third day, `op+1` the day after the operation, `discharge-1` the last night. A **range** `a..b` is inclusive and makes one bill line per day. `days` takes one expression or a list: `[admit, admit+3]` is two days. Nothing else is allowed. Day 0 is `admit`; for a stay of N nights `discharge` is day N. For an ER-only (`acil`) pathway `admit` is the visit day and nothing else exists.

| Expression | N = 6 nights | Lines |
|---|---|---|
| `admit..discharge` | 9 to 15 March | 7 (a bed for every calendar day, discharge day included) |
| `admit..discharge-1` | 9 to 14 March | 6 (one per night: companion, nebulizer) |
| `admit..admit+1` | 9 and 10 March | 2 |
| `[admit, admit+3]` | 9 and 12 March | 2 |

Every expression must land inside the stay for the shortest, the longest and the pinned stay (`days.in_stay`), so pick `nights.min` with the fixed offsets in mind.

### Quantities

- A procedure, material or performed line has `qty` (default 1) **per bill line**. `qty: 16` with `days: admit..admit+1` is 16 hours on each of two days. "Per calendar day" and "per night" are day ranges, one line each.
- A **drug** is one line on the first day of its course with the whole quantity. Exactly one form:
  - `qty: 7`: a fixed number of units;
  - `per_night: 1`: units times the nights of the stay (must start on `admit`);
  - `per_day: 2` with `course_days: {min, max, basis, source}`: units a day times the course days chosen by the pins. `min == max` is a fixed duration.
- `unit` and `per_box` follow the EK-4A pack. The count is units actually used, never boxes.
- A course must end on or before the discharge day (`drug.course`). The composer draws the nights first and then the course days from `min` to the days left.

### Line kinds (`procedures[].kind`)

| kind | Catalog | Notes |
|---|---|---|
| `package` | EK-2C (P-codes) | the only kind in a package pathway |
| `operation` | EK-2B chapter 6 | itemized pathways |
| `bed`, `companion` | 510010 or 510120; 510121 | |
| `anaesthesia` | the 14 codes of `code_sets.yaml` | needs `group` and `operations` (below) |
| `exam` | EK-2B chapter 2 | |
| `lab` | EK-2B chapters 9 and 10 | `items:` lists a panel (several codes, same days, quantity and branch); every `L` code must be in `lab_reference.csv` |
| `imaging` | EK-2B chapter 8 | |
| `procedure` | EK-2B chapters 3, 4, 7 | |

`specialty` is an EK-2A branch code; a line without one gets the department's. Name a branch only where it differs (anaesthesia 3100, radiology 3300, neurology 1300). A **package pathway has package lines and linked materials only**: bed, companion, exams, labs, imaging, anaesthesia and drugs are inside the package (SUT 2.2.2.B-1(1), C000685 to C000699). The longest stay must end inside the package window of its group (A 15 days, B 10, C 8, D 5, E 3, counted from the package day; C000702 to C000706).

### Anaesthesia

One line per session, `kind: anaesthesia`, with `operations: [<operation line ids>]` and `group: B`. The group is derived from the puan of the operation (the sum for several operations) with the `surgical_group_bands` of `code_sets.yaml`; it must hold **on every day of the window**, and the band tables switch on 2026-04-16, so an operation near a band edge needs a window that starts after the switch. The code must be the group's code (`single` for one operation, `multiple_operations` for several).

### Materials

`id`, EK-3/F-1 `code` and `name` (site and description joined by ` | `, as the catalog lists them), `material_type` (`implant` or `consumable`), `qty`, `day`, `linked_to` (the package or operation line that used it) and `flags` (`titubb_registered`, `uts_registered`). Only EK-3/F-1 is checked so far.

### Session roles

Operations of one session carry `session_role` on a single-day line: `primary` (exactly one per session day, and the one with the highest puan), `same_incision`, `separate_incision`. The expander turns the role into `billed_ratio` from a constant table in `expand.py`: packages 1 / 0.25 / 0.50 (SUT 2.2.2.B(3), C000670, C000671), itemized 1 / 0.30 / 0.50 (SUT 2.2.2.A(5), C000660, C000661). The +25 points for different specialties (C000662, C000674) are not applied: issue #295, marked `pending`.

### Diagnoses, drugs and indications

`icd10` must be an active SKRS **leaf** code and `name` its `name_tr`. A drug may name `indication: G20`; that diagnosis must be in the pathway (and in the pinned bill).

### Optional items and the pins

An item with `optional: {probability, basis, source}` is in the bill only when its id is in `showcase.include` (a diagnosis is identified by its ICD code). The pins are `story`, `sex`, `age`, `admit` (first day), `nights`, `include` and `course_days` (drug id to days). Every pin must lie inside the declared range (`pins.*`), and the stay inside the window.

### Provenance: `basis` and `source`

Every diagnosis, line, range and probability carries both. `source` is one short sentence (160 characters at most) that names the document, clause or guideline.

| basis | Use when | `source` must |
|---|---|---|
| `sut` | an SUT clause decides it | give a clause id (`C000685`) or an annex (`EK-2B`); every `C…` id must be an in-force clause of `data/gazette/sut_clauses.parquet` |
| `ek2b_aciklama` | the EK-2B açıklama column of the code decides it | name the code and quote the limit |
| `medula_kilavuz` | the MEDULA hospital web-service guide decides it | give the page |
| `guideline` | a named clinical guideline decides it | name it |
| `judgment` | nothing citable | say what the choice is anchored on; a clinician checks these |

Do not invent a clause id: look it up with Polars in `data/gazette/sut_clauses.parquet`.

### `pending`

`pending: "#297 Q2"` marks a line that waits for an answer from a field expert (#297 Q2 companion days: whether the discharge day counts; Q4 scope of "birlikte faturalandırılmaz": the blood-gas / Na-K exclusion on the same date only; Q5 direct LDL; #295 the +25 points per session or per line). Use it only where the question applies.

## What the checks say

Run them on one file or all: `.venv/bin/python -m scripts.synthetic.pathways.checks [file ...]`. A message names the field (`procedures[bed]`) and, for a name or window problem, the catalog's own value, so copy the right name from the message. Each id has a mutation test in `tests/unit/synthetic/test_pathways_schema.py`.

| Check | What it finds |
|---|---|
| `yaml.invalid`, `hygiene.forbidden_key`, `hygiene.anon_text`, `schema.id_mismatch` | bad YAML or a repeated key; a key named price, amount, total or package_candidate; `ANON_` text; a file name that is not `<id>.yaml` |
| `schema.*` | an unknown or missing field (including `basis`, `source`), a bad enum or value, a bad day expression, min above max, a probability outside [0, 1], a duplicate id, a dangling reference, an undefined anchor, a malformed line, a wrong drug quantity form, not exactly one primary diagnosis, a stay without nights |
| `procedure.in_force`, `procedure.name`, `procedure.kind` | an EK-2B/EK-2C code missing on some day of the window; a name that is not the catalog's (whitespace-normalized); a kind that does not fit the code's chapter |
| `material.*`, `drug.in_force`, `drug.name`, `drug.inn` | the same for EK-3/F-1 and EK-4A; `inn` must be the crosswalk's `active_ingredient` |
| `drug.indication`, `drug.course` | an indication that is not a diagnosis of the bill; a course that outlasts the stay |
| `icd.exists`, `icd.active`, `icd.leaf`, `icd.name`, `icd.sex_gate` | the SKRS table; a sex-gated code with a sex list that allows the other sex |
| `lab.in_table`, `lab.name`, `specialty.exists` | an `L` code absent from `lab_reference.csv` or named differently; an unknown EK-2A branch |
| `package.mode`, `package.window` | a package pathway with a line the package includes (or the reverse); a stay past the package window |
| `anaesthesia.group`, `anaesthesia.code`, `session.primary`, `session.order` | the puan band; the group's code; the primary operation of a session |
| `pins.*`, `days.in_stay`, `days.duplicate` | pins outside the ranges, unknown or non-optional ids, missing pins, dates outside the window; days outside the stay or twice on one day |
| `source.clause_exists`, `source.sut_cites`, `window.valid` | a cited clause that does not exist or is not in force; `sut` without a citation; a window outside the default |

## Add a pathway

1. Copy the closest pathway (`appendicitis_lap_appendectomy_package.yaml` for a package, `copd_exacerbation_pneumonia_ward.yaml` for an itemized stay) to `<id>.yaml`.
2. Write the clean story only: no item the story does not have, none dropped. Generalize only the sexes, the age range, the nights, drug course days and items the story or the review treats as optional. Give every range and every item a `basis` and a `source`.
3. Run the checks (command above) until they are silent. To find a catalog name, write the code with a placeholder name (`"??"`) and copy the real name from the `procedure.name`, `material.name`, `drug.name` or `icd.name` message. A `*.in_force` message names the first day a code is missing: narrow the `window` to the days it is in force and say why in a comment, as S2 does.
4. Write the `showcase` pins from the story and make the round trip pass: `expand(pathway)` must equal `tests/fixtures/pathways/golden/<story>.json`. Never edit the golden to fit the YAML.
5. Update the status table below.

## Tests

```
.venv/bin/python -m pytest tests/unit/synthetic/test_pathways_schema.py tests/unit/synthetic/test_pathways_roundtrip.py tests/unit/synthetic/test_pathways_golden.py -q
```

- `test_pathways_schema.py`: every real pathway loads and passes every check; every check id in `CHECKS` has a mutation case that takes a real pathway, proves it clean, applies one defect and asserts that exactly the expected ids fire.
- `test_pathways_roundtrip.py`: per pathway file, `expand` equals the golden; a changed pin changes the bill; pins outside the ranges are refused; every golden has a pathway and every pathway a golden. A broken file fails only its own cases.
- `test_pathways_golden.py`: the golden files are well formed.

## Not expressible yet

- One pathway has one billing mode: an EK-2C package and itemized EK-2B lines in one bill are not expressible (SUT 2.2.2.B(3) c, ç).
- Itemized lines after the package window (long package stays) are not expressible; `package.window` refuses such a stay.
- Materials are checked against EK-3/F-1 only.
- Procedure lines have no flags (the stories set none).
- `showcase` is required, so a pathway without a showcase story (the rest of the first 20) needs the schema relaxed.
- Newborn and ICU tiers (P55200x) are not modelled.

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
