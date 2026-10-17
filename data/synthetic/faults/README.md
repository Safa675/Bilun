# Fault registry (synthetic demo v3, P3)

A care pathway (`data/synthetic/pathways/<id>.yaml`) describes a clean hospital bill (`expand(pathway, pins, annotate=True)`). The **fault registry** (`data/synthetic/faults/fault_registry.yaml`) declares the controlled billing mutations that turn a clean expanded bill into a faulty bill, together with the expected engine finding and SUT provenance.

Prices, currency amounts and totals are **not** stored in the fault registry (`hygiene` forbids them); the TL effect is recorded in the cohort injection log (`data/synthetic/cohort_registry.json`) when bills are composed.

| Path | What |
|---|---|
| `data/synthetic/faults/fault_registry.yaml` | the declarative catalog of billing faults (`schema_version: 1`, `faults:` list) |
| `data/synthetic/faults/siblings/<id>.yaml` | itemized sibling pathways used by `use_sibling_pathway` |
| `scripts/synthetic/faults/schema.py` | frozen Pydantic v2 models (`FaultRegistry`, `FaultSpec`, `MutationOp`, `ExpectedFinding`) and `CHECKS` |
| `scripts/synthetic/faults/loader.py` | `load_registry(path)` and `load_registry_text(text, name)` with strict YAML and hygiene checks |
| `scripts/synthetic/faults/checks.py` | `run_all(registry, catalogs)` and CLI checker |
| `tests/unit/synthetic/test_fault_registry.py` | unit and mutation tests covering every check id in `CHECKS` |

## Format (`FaultRegistry` and `FaultSpec`)

Top-level keys:
- `schema_version`: `1`
- `faults`: non-empty list of `FaultSpec` entries.

Each `FaultSpec` carries:
- `fault_id`: unique identifier matching `^F_S[1-9][0-9]*_[A-Z][A-Z0-9_]{1,63}$` (for example `F_S2_BED_DAYS_UNDERBILLED`).
- `story`: showcase story `S1`..`S8` or `null`. Each showcase story appears at most once, and all eight stories `S1`..`S8` are covered.
- `title`: short English summary (2–400 characters).
- `target_pathway`: pathway id in `data/synthetic/pathways/<target_pathway>.yaml`.
- `mutations`: non-empty list of `MutationOp` entries from the closed six-operation grammar below.
- `expected_finding` (`ExpectedFinding`):
  - `engine_rule`: engine rule identifier (`billing_strategy`, `yatak_puani`, `anestezi_puani`, `refakatci`, `material_bundling`, `drug_indication`, `procedure_capture_gap`, `drg_unbundling`).
  - `detectors`: non-empty list of `"<repo module path>:<function name>"` strings.
  - `sut_section`: SUT section citation (for example `"2.2.2.A(1)"`).
  - `sut_clauses`: non-empty list of in-force clause ids (`C000000`) in `data/gazette/sut_clauses.parquet`.
  - `effect_kind`: `revenue_uplift`, `deduction_risk` or `compliance_error`.
  - `line_type`: `fatura`, `islem`, `malzeme` or `ilac`.
  - `target_entry_id`: `null` when `line_type` is `fatura`; required pathway line `id` otherwise.
  - `expected_status`: `eksik_faturalama` (missing/under-billed claim-level uplift) or `kismi_red` (line-level deduction or compliance error).
- `basis` and `source`: provenance using the pathway `Basis` enum (`sut`, `ek2b_aciklama`, `medula_kilavuz`, `guideline`, `judgment`) and `Source` rule (10–160 characters, no TL amounts).

## The six mutation operations (`MutationOp`)

Every operation is a mapping discriminated on `op` with `extra="forbid"`, operating on the annotated expansion `expand(pathway, pins, annotate=True)`:

1. **`use_sibling_pathway`** (`sibling_pathway_id`):
   - Meaning: replace the clean bill with `expand(sibling_pathway, same pins)`, where `sibling_pathway_id` lives at `data/synthetic/faults/siblings/<sibling_pathway_id>.yaml`.
   - Constraint: must be the only mutation in its fault (`schema.sibling_alone`).
   - Showcase use: `F_S1_PACKAGE_BILLED_ITEMIZED` swaps `appendicitis_lap_appendectomy_package` for `appendicitis_lap_appendectomy_itemized`.
2. **`truncate_line_days`** (`section: "procedures"`, `entry_id`, `keep_day_indices`):
   - Meaning: keep only the expanded rows of procedure line `entry_id` whose 0-based `day_index` is in `keep_day_indices` (a non-empty list of distinct non-negative integers).
   - Constraint: `keep_day_indices` must be valid `day_index` positions of `entry_id` in the showcase expansion and strictly fewer than all rows of that line (`fault.keep_day_indices`).
   - Showcase use: `F_S2_BED_DAYS_UNDERBILLED` keeps `[0, 1, 2, 3]` of the 7 `bed` rows.
3. **`drop_entry`** (`section`: `"procedures" | "materials" | "drugs" | "performed"`, `entry_id`):
   - Meaning: remove every expanded row belonging to pathway line `entry_id` in `section`.
   - Showcase use: `F_S3_ANAESTHESIA_LINE_MISSING` drops `anaesthesia`; `F_S4_COMPANION_NOT_BILLED` drops `companion`; `F_S7_ER_CT_ANGIO_UNBILLED` drops `ct_angiography` from `procedures` while keeping `ct_angiography_pacs` in `performed`.
4. **`set_flag`** (`section`: `"materials" | "drugs"`, `entry_id`, `flag`, `value`):
   - Meaning: set `flags[flag] = value` on every expanded row of `entry_id` in `section`.
   - Constraint: `flag` must be a field of `MaterialFlags` (`titubb_registered`, `uts_registered`) or `DrugFlags` (`drug_specialty_board_report_present`, `prescriber_specialty`, `drug_inpatient_supply`) and `value` must match the field's type (`fault.flag`).
   - Showcase use: `F_S5_IMPLANT_UTS_INCOMPLETE` sets `uts_registered: false` on `femoral_stem`.
5. **`drop_diagnosis`** (`icd10`, `breaks_indication: bool = false`):
   - Meaning: remove secondary diagnosis `icd10` from `diagnoses` (never the primary diagnosis).
   - Constraint: `icd10` must be a secondary diagnosis of the target pathway (`fault.drop_diagnosis`), and `breaks_indication` must be `true` if and only if a kept drug in the pathway names `icd10` as its `indication` (`fault.breaks_indication`).
   - Showcase use: `F_S6_DRUG_INDICATION_NOT_CODED` drops `G20` with `breaks_indication: true` (breaking `pk_merz`).
6. **`set_billed_ratio`** (`entry_id`, `billed_ratio` matching `^\d\.\d{4}$`):
   - Meaning: set `billed_ratio` on every expanded row of procedure line `entry_id`.
   - Constraint: `entry_id` must be a procedure line with a `session_role` (`fault.billed_ratio_target`).
   - Showcase use: `F_S8_SECOND_PACKAGE_FULL_RATE` sets `billed_ratio: "1.0000"` on `hernia_package`.

## Checks (`scripts/synthetic/faults/checks.py`)

Run the checks from the repository root:

```bash
.venv/bin/python -m scripts.synthetic.faults.checks
```

| Check | What it verifies |
|---|---|
| `yaml.invalid`, `hygiene.forbidden_key`, `hygiene.anon_text`, `hygiene.price_text`, `hygiene.id_like_number` | strict YAML syntax (no duplicate keys); no key containing `price`, `amount`, `total` or `package_candidate`; no `ANON` identifier, non-zero currency amount (`TL`, `TRY`, `₺`) or 11-digit number in any key, value or comment |
| `schema.unknown_field`, `schema.missing_field`, `schema.bad_enum`, `schema.bad_value`, `schema.sibling_alone`, `schema.target_entry_shape` | Pydantic model validation, `extra="forbid"`, distinct `keep_day_indices`, `use_sibling_pathway` alone in `mutations`, and `target_entry_id` null iff `line_type == "fatura"` |
| `fault.target_pathway`, `fault.entry_id`, `fault.keep_day_indices`, `fault.flag`, `fault.drop_diagnosis`, `fault.breaks_indication`, `fault.billed_ratio_target`, `fault.target_entry_id` | target/sibling pathway existence and clean load; `entry_id` in stated section; valid strict-subset `keep_day_indices` on `expand(..., annotate=True)`; valid flag name and value type on `MaterialFlags`/`DrugFlags`; secondary diagnosis on `drop_diagnosis` and indication linkage; `session_role` on `set_billed_ratio`; `target_entry_id` present in effective pathway |
| `fault.sut_clauses`, `fault.source_cites`, `fault.detectors` | every `C000000` clause in `sut_clauses` and `source` is in force in `data/gazette/sut_clauses.parquet`; `basis: sut` cites a clause or `EK-` annex; every detector `"<module>:<func>"` exists on disk and contains `def <func>` |
| `fault.duplicate_id`, `fault.duplicate_story`, `fault.story_coverage`, `fault.op_coverage` | unique `fault_id`; each showcase story `S1`..`S8` at most once and all 8 covered; all 6 mutation operations used at least once |

## Add a fault

1. Verify the target pathway in `data/synthetic/pathways/<target_pathway>.yaml` and inspect its annotated expansion (`expand(load_pathway(path), annotate=True)`) to confirm `entry_id`, `day_index`, `session_role` and `indication` values.
2. Add a `FaultSpec` entry to `data/synthetic/faults/fault_registry.yaml` using one or more of the six `MutationOp` operations, citing the in-force SUT clause ids in `expected_finding.sut_clauses` and `source` (at most 160 characters, no currency amounts).
3. Run `.venv/bin/python -m scripts.synthetic.faults.checks` and `.venv/bin/python -m pytest tests/unit/synthetic/test_fault_registry.py -q` until green.
