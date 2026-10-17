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
| `tests/fixtures/pathways/golden/S1.json` … `S8.json` | the clean bills of the showcase stories, exported from `stories.py` by another script (`golden_faulty/` holds the faulty bills) |

## Read a pathway top to bottom

Open `copd_exacerbation_pneumonia_ward.yaml` next to this text.

1. **Identity and setting.** `id`, `title`, `claim_type` (`yatis` or `acil`), `billing_mode` (`package` = EK-2C, `itemized` = EK-2B hizmet başı), `department` (the header name and the default EK-2A branch of every line).
2. **`window`** (optional). The service window of the pathway. Default: the `window` of `code_sets.yaml`, 2026-02-01 to 2026-09-30. A pathway may narrow it, never widen it, and a narrowed window carries `start`, `end` and a `source`: one sentence, 160 characters at most, that says why. **Every code must be in force on every day of the window.** S2 ends on 2026-08-28: KLACID 500 MG IV leaves EK-4A on 2026-08-29. EK-4A rows are half-open, `[valid_from, valid_until)`, so `valid_until` is the first day a drug is not in force and the checks use the day before it (as the engine does).
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

Every expression must land inside the stay for the shortest, the longest and the pinned stay (`days.in_stay`), so pick `nights.min` with the fixed offsets in mind. A `bed` line must cover exactly `admit..discharge` and a `companion` line exactly `admit..discharge-1` at those three stays (`stay.coverage`), so the lines grow with the nights.

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
| `anaesthesia` | the 14 codes of `code_sets.yaml` | needs `group` and `operations` (below) |
| `exam` | EK-2B chapter 2 | |
| `lab` | EK-2B chapters 9 and 10 | `items:` lists a panel (several codes, same days, quantity and branch); every `L` code must be in `lab_reference.csv` |
| `imaging` | EK-2B chapter 8 | |
| `procedure` | EK-2B chapters 3, 4, 5 and 7 | |

`specialty` is an EK-2A branch code; a line without one gets the department's. Name a branch only where it differs (anaesthesia 3100, radiology 3300, neurology 1300). A **package pathway has package lines and linked materials only**: bed, companion, exams, labs, imaging, anaesthesia and drugs are inside the package (SUT 2.2.2.B-1(1), C000685 to C000699). The longest stay must end inside the package window of its group (A 15 days, B 10, C 8, D 5, E 3, counted from the package day; C000702 to C000706).

### Anaesthesia

One line per session, `kind: anaesthesia`, with `operations: [<operation line ids>]` and `group: B`. The group is derived from the puan of the operation (the sum for several operations) with the `surgical_group_bands` of `code_sets.yaml`; it must hold **on every day of the window**, and the band tables switch on 2026-04-16, so an operation near a band edge needs a window that starts after the switch. The code must be the group's code (`single` for one operation, `multiple_operations` for several).

### Materials

`id`, EK-3/F-1 `code` and `name` (site and description joined by ` | `, as the catalog lists them), `material_type` (`implant` or `consumable`), `qty`, `day`, `linked_to` (the package or operation line that used it) and `flags` (`titubb_registered`, `uts_registered`). Only EK-3/F-1 is checked so far.

### Session roles

Operations of one session carry `session_role` on a single-day line: `primary` (exactly one per session day, and the one with the highest puan), `same_incision`, `separate_incision`. The expander turns the role into `billed_ratio` from a constant table in `expand.py`: packages 1 / 0.25 / 0.50 (SUT 2.2.2.B(3), C000670, C000671), itemized 1 / 0.30 / 0.50 (SUT 2.2.2.A(5), C000660, C000661). The +25 points for different specialties (C000662, C000674) are not applied: issue #295, marked `pending`.

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
| `schema.*` | an unknown or missing field (including `basis`, `source`, and the `source` of a window), a bad enum or value, a bad day expression, min above max, a probability outside [0, 1], a duplicate id, a dangling reference, an undefined anchor, a malformed line, a wrong drug quantity form, not exactly one primary diagnosis, a stay without nights |
| `procedure.in_force`, `procedure.name`, `procedure.kind` | an EK-2B/EK-2C code missing on some day of the window; a name that is not the catalog's (whitespace-normalized); a kind that does not fit the code's chapter |
| `material.*`, `drug.in_force`, `drug.name`, `drug.inn` | the same for EK-3/F-1 and EK-4A; `inn` must be the crosswalk's `active_ingredient` |
| `drug.indication`, `drug.course` | an indication that is not a diagnosis of the pathway or is optional; a `per_night` drug that does not start on admit; a course that outlasts the stay (the shortest course at the shortest stay, and a pinned course at the pinned stay) |
| `icd.exists`, `icd.active`, `icd.leaf`, `icd.name`, `icd.sex_gate` | the SKRS table; a sex-gated code with a sex list that allows the other sex |
| `lab.in_table`, `lab.name`, `specialty.exists` | an `L` code absent from `lab_reference.csv` or named differently; an unknown EK-2A branch |
| `package.mode`, `package.window` | a package pathway with a line the package includes (or the reverse); a stay past the package window |
| `anaesthesia.group`, `anaesthesia.code`, `session.primary`, `session.order` | the puan band; the group's code; the primary operation of a session |
| `pins.*`, `days.in_stay`, `days.duplicate`, `stay.coverage` | pins outside the ranges, unknown or non-optional ids, missing pins, dates outside the window; days outside the stay or twice on one day; a bed line off `admit..discharge` or a companion line off `admit..discharge-1` |
| `source.clause_exists`, `source.sut_cites`, `window.valid` | a cited clause that does not exist or is not in force; `sut` without a citation; a window outside the default |

## Add a pathway

1. Copy the closest pathway (`appendicitis_lap_appendectomy_package.yaml` for a package, `copd_exacerbation_pneumonia_ward.yaml` for an itemized stay) to `<id>.yaml`.
2. Write the clean story only: no item the story does not have, none dropped. Generalize only the sexes, the age range, the nights, drug course days and items the story or the review treats as optional. Give every range and every item a `basis` and a `source`.
3. Run the checks (command above) until they are silent. To find a catalog name, write the code with a placeholder name (`"??"`) and copy the real name from the `procedure.name`, `material.name`, `drug.name` or `icd.name` message. A `*.in_force` message names the first day a code is missing: narrow the `window` to the days it is in force and say why in its `source`, as S2 does.
4. Write the `showcase` pins from the story and make the round trip pass: `expand(pathway)` must equal `tests/fixtures/pathways/golden/<story>.json`. Never edit the golden to fit the YAML.
5. Update the status table below.

## Expander annotations and fault siblings (P3)

- **`expand(pathway, pins=None, *, annotate=False)`**: the default (`annotate=False`) returns the golden format unchanged. With `annotate=True`, rows carry pathway line references so the fault registry can target lines by id: every procedure row adds `entry_id` (the pathway line id), `kind` (the line's kind) and `day_index` (0-based position of that row's date among the dates the line resolves to, in date order; for a lab panel with several codes every code on the same date has the same index); every material and every performed row adds `entry_id`; every drug row adds `entry_id` and `indication` (the drug's indication ICD-10 code or `null`).
- **`data/synthetic/faults/siblings/`**: a sibling is a pathway without a golden in `tests/fixtures/pathways/golden/` (so `data/synthetic/pathways/` keeps its 1-to-1 bijection with the 8 clean goldens). It obeys the same schema, hygiene and catalog checks (`run_all`), and its own test (`tests/unit/synthetic/test_fault_siblings.py`) checks that expanding it with its `showcase` pins equals `tests/fixtures/pathways/golden_faulty/<story>.json`. `appendicitis_lap_appendectomy_itemized.yaml` is S1's itemized sibling.

## Tests

```
.venv/bin/python -m pytest tests/unit/synthetic/test_pathways_schema.py tests/unit/synthetic/test_pathways_roundtrip.py tests/unit/synthetic/test_pathways_golden.py tests/unit/synthetic/test_pathways_annotate.py tests/unit/synthetic/test_fault_siblings.py -q
```

- `test_pathways_schema.py`: every real pathway loads and passes every check; the folder holds only this README and top-level `*.yaml` files (a `.yml` file or a sub-folder would never load); every check id in `CHECKS` has a mutation case that takes a real pathway, proves it clean, applies one defect and asserts that exactly the expected ids fire; further tests pin the edges of the checks (the package window, the stays tested, the window and range edges, the EK-4A last day against the engine's reader).
- `test_pathways_roundtrip.py`: per pathway file, `expand` equals the golden; a flipped optional item or course changes the bill; the bed and companion lines gain one bill line per extra night; a later admission moves every date; pins outside the ranges, or a course that outlasts the pinned stay, are refused; every golden has a pathway and every pathway a golden. A broken file fails only its own cases.
- `test_pathways_golden.py`: the clean and faulty golden files are well formed, each faulty golden differs from its clean golden, and both directories equal a fresh export of `stories.py`: the test runs `reports/synthetic-data/2026-10-15-showcase-proofs/export_clean_lines.py --check` in a subprocess (about a second), so a pathway and its golden cannot be changed together unnoticed.
- `test_pathways_annotate.py`: `expand(p) == expand(p, annotate=False)` for all 8 pathways; stripping the annotation keys from `expand(p, annotate=True)` reproduces the default expansion; every `entry_id` is a pathway line id, every included line appears, `day_index` is `0..n-1` in date order per `entry_id`, and drug rows carry `indication`.
- `test_fault_siblings.py`: every `*.yaml` in `data/synthetic/faults/siblings/` loads, passes `run_all`, and expands to `tests/fixtures/pathways/golden_faulty/<story>.json` (with in-memory mutation guards).

## Not expressible yet

- One pathway has one billing mode: an EK-2C package and itemized EK-2B lines in one bill are not expressible (SUT 2.2.2.B(3) c, ç).
- Itemized lines after the package window (long package stays) are not expressible; `package.window` refuses such a stay.
- Materials are checked against EK-3/F-1 only.
- Procedure lines have no flags (the stories set none).
- `showcase` is required and `Pins.story` is limited to `S1`..`S8`, so a pathway without a showcase story (the rest of the first 20) needs the schema relaxed; P4 must relax both.
- Newborn and ICU tiers (P55200x) are not modelled.
- A drug course that runs to discharge from a later start (S6 levodopa, through the NG tube from day 3) has no "until discharge" form: `course_days` is drawn independently of the nights, so P4 must clamp it to the days left.
- The clinical sex of a diagnosis is judgment, not data. S5's M81.09 is postmenopausal osteoporosis, so S5 says `sex: [F]`, but the ICD table's sex column covers only 97 neoplasm codes (C and D), so `icd.sex_gate` cannot see it.
- *(Resolved in P3 slice 1 — #311 items 4 & 5.)* `expand(..., annotate=True)` now attaches `entry_id`, `kind`, `day_index` and `indication` so the fault registry (P3) can tell which pathway line a row came from, and S1's itemized fault sibling lives in `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml`.
- Guarded by review only: a required item made optional and pinned in, a range widened beyond the pins, a probability, a title, a note, the id of a line nothing refers to, an edit of a `source`, a `basis` or a `pending` marker, and whether a cited clause says what its source claims.
- Stay scaling is checked for `bed` and `companion` lines only. A drug rewritten from `per_night` to a fixed `qty` that matches the showcase nights, or S2's nebulizer (`admit..discharge-1`) fixed to the showcase nights, passes every check; it is a plausibility question (P5), not a validity one.

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
