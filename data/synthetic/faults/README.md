# Fault registry (synthetic demo v3, P3)

A care pathway (`data/synthetic/pathways/<id>.yaml`) describes a clean hospital bill (`expand(pathway, pins, annotate=True)`). The **fault registry** (`data/synthetic/faults/fault_registry.yaml`) declares the controlled billing mutations that turn a clean expanded bill into a faulty bill, together with the expected engine finding and SUT provenance.

Prices, currency amounts and totals are **not** stored in the fault registry (`hygiene` forbids them); the TL effect is recorded in the cohort injection log (`data/synthetic/cohort_registry.json`) when bills are composed.

| Path | What |
|---|---|
| `data/synthetic/faults/fault_registry.yaml` | the declarative catalog of billing faults (`schema_version: 1`, `faults:` list) |
| `data/synthetic/faults/siblings/<id>.yaml` | itemized sibling pathways used by `use_sibling_pathway` |
| `scripts/synthetic/faults/schema.py` | frozen Pydantic v2 models (`FaultRegistry`, `FaultSpec`, `MutationOp`, `ExpectedFinding`) and `CHECKS` |
| `scripts/synthetic/faults/loader.py` | `load_registry(path)`, `load_registry_text(text, name)` and `load_siblings(directory)` |
| `scripts/synthetic/faults/checks.py` | `run_all(registry, catalogs)` and CLI checker |
| `scripts/synthetic/faults/mutate.py` | `FaultApplyError`, `apply_fault(fault, pathway, pins=None, *, siblings=None, annotate=False)` and `fault_window(fault, pathway, siblings=None)` |
| `scripts/synthetic/faults/records.py` | `FaultInjectionRecord` and `make_record(...)` |
| `scripts/synthetic/faults/answer_key.py` | `build_expected_rule_outputs(records)` producing the 13-column `ExpectedRuleOutput` rows |
| `tests/unit/synthetic/test_fault_registry.py` | unit and mutation tests covering every check id in `CHECKS` |
| `tests/unit/synthetic/test_fault_mutations.py` | unit and mutation tests for `apply_fault` and `fault_window` against `tests/fixtures/pathways/golden_faulty/` |
| `tests/unit/synthetic/test_fault_answer_key.py` | unit tests for `FaultInjectionRecord`, `make_record`, `build_expected_rule_outputs` and `validate_expected_outputs` |

## Format (`FaultRegistry` and `FaultSpec`)

Top-level keys:
- `schema_version`: `1`
- `faults`: non-empty list of `FaultSpec` entries.

Each `FaultSpec` carries:
- `fault_id`: unique identifier matching `^F_S[1-9][0-9]*_[A-Z][A-Z0-9_]{1,63}$` (for example `F_S2_BED_DAYS_UNDERBILLED`).
- `story`: a showcase story, `S` and a number from 1 up (`S1`..`S8` are the first cohort, `S9`, `S11`, `S12` and later are the stories added since; S10 is a later bill), or `null`. Each story appears at most once. The first eight stories `S1`..`S8` must be covered (`SHOWCASE_STORIES`); a later story is optional.
- `title`: short English summary (2–400 characters).
- `target_pathway`: pathway id in `data/synthetic/pathways/<target_pathway>.yaml`.
- `mutations`: non-empty list of `MutationOp` entries from the closed six-operation grammar below.
- `expected_finding` (`ExpectedFinding`):
  - `engine_rule`: engine rule identifier (`billing_strategy`, `yatak_puani`, `anestezi_puani`, `refakatci`, `material_bundling`, `drug_indication`, `procedure_capture_gap`, `drg_unbundling`, `session_uplift`, `icu_puani`, `yenidogan_yatak`).
  - `detectors`: non-empty list of `"<repo module path>:<function name>"` strings.
  - `sut_section`: SUT section citation (for example `"2.2.2.A(1)"`).
  - `sut_clauses`: non-empty list of in-force clause ids (`C000000`) in `data/gazette/sut_clauses.parquet`.
  - `effect_kind`: `revenue_uplift`, `deduction_risk` or `compliance_error`.
  - `line_type`: `fatura`, `islem`, `malzeme` or `ilac`.
  - `target_entry_id`: `null` when `line_type` is `fatura`; required pathway line `id` otherwise.
  - `expected_status`: `eksik_faturalama` (missing/under-billed claim-level uplift) or `kismi_red` (line-level deduction or compliance error).
  - `evidence_entry_ids`: optional list of pathway line `id`s in `procedures` or `performed` that serve as evidence of the finding (default `[]`; on S7, `["ct_angiography_pacs"]`).
  - `finding_ids`: optional list of the engine's own finding/rule identifiers emitted on the faulty bill (default `[]`; S5 `["3.1.1.(2).titubb_uts_incomplete"]`, S6 `["indication_mismatch", "4.2.36.amantadine_sulfate_report"]`, S8 `["2.2.2.B.a"]`, S9 `["2.2.2.A.(5)"]`, S11 `["icu_puani_510090_p55200x"]`, S12 `["yenidogan_yatak_510070"]`).
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
   - Showcase use: `F_S8_SECOND_PACKAGE_FULL_RATE` sets `billed_ratio: "1.0000"` on `hernia_package`; `F_S9_SECOND_OPERATION_UNDERBILLED` sets `billed_ratio: "0.2500"` on `foraminoplasty` (the clean bill pays it at 0.5000, a separate incision); `F_S11_ICU_PACKAGE_DAYS_UNDERBILLED` sets `billed_ratio: "0.5000"` on the three-day `icu_package` line (the target is a line of kind `icu_package`, which takes a ratio without a `session_role`; `fault.billed_ratio_target`).

## Applying a fault (`apply_fault`, `fault_window`), the injection record and the answer rows

### `apply_fault` and `fault_window` (`scripts/synthetic/faults/mutate.py`)

`apply_fault(fault, pathway, pins=None, *, siblings=None, annotate=False) -> dict` expands `pathway` with `annotate=True` (`pins` default to `pathway.showcase`), verifies the stay is inside the service window, applies `fault.mutations` in order on a deep copy without modifying any input, and strips the annotation keys (`entry_id`, `kind`, `day_index`, `indication`) unless `annotate=True`. `fault.target_pathway` must equal `pathway.id`.

`fault_window(fault, pathway, siblings=None) -> tuple[str, str]` returns the `(start, end)` intersection of the target pathway's service window and (when `use_sibling_pathway` is used) the sibling pathway's service window, using `Catalogs().window` for any pathway without an explicit `window`. Phase P4 places faulty encounters inside this window.

Pins outside the pathway's declared ranges (age, sex, nights, optional ids or drug course days) raise `ExpandError` (from `expand`). Pins whose stay (`admit` through discharge day) falls outside the window of the target pathway or sibling pathway raise `FaultApplyError`. Whenever a mutation precondition fails, a procedure drop/truncation leaves a material with a dangling `linked_procedure`, or an operation would change nothing, `apply_fault` raises `FaultApplyError` naming the fault and the operation:

1. **`use_sibling_pathway`**: replaces the bill with `expand(siblings[sibling_pathway_id], same pins, annotate=True)`; raises `FaultApplyError` if `siblings` lacks `sibling_pathway_id`, the stay is outside the sibling's window, or the sibling produces an identical bill.
2. **`truncate_line_days`** (section `procedures`): among rows with `entry_id`, keeps those whose `day_index` is in `keep_day_indices`; raises `FaultApplyError` if the line has no rows, if any listed index does not occur, if all rows are kept, or if a remaining material's `linked_procedure` no longer matches any kept procedure row ("dangling link").
3. **`drop_entry`**: removes every row of `section` with `entry_id`; raises `FaultApplyError` if there is none or, when `section == "procedures"`, if a remaining material's `linked_procedure` no longer matches any kept procedure row ("dangling link").
4. **`set_flag`**: sets `row["flags"][flag] = value` on every row of `section` with `entry_id`; raises `FaultApplyError` if there is none or if every such row already has that value.
5. **`drop_diagnosis`**: removes the diagnosis row with `icd10`; raises `FaultApplyError` if it is absent or is the primary diagnosis.
6. **`set_billed_ratio`**: sets `billed_ratio` on every `procedures` row with `entry_id`; raises `FaultApplyError` if there is none or if all rows already equal that ratio.

### Injection record (`scripts/synthetic/faults/records.py`)

`FaultInjectionRecord` is a frozen Pydantic v2 model (`extra="forbid"`) recording one injected fault on a claim:
- `injection_id` (`f"INJ-{claim_id}-{fault_id}"`), `fault_id`, `story` (`S<n>` or `null`), `pathway_id`, `patient_id`, `claim_id`;
- `line_type` (`fatura` / `islem` / `malzeme` / `ilac`), `line_id` (empty string `""` if and only if `line_type == "fatura"`), `line_ids` (`tuple[str, ...]` of other affected or evidence line ids, may be empty);
- `engine_rule`, `sut_section`, `effect_kind`, `expected_status`;
- `amount_try`, `billed_clean_try`, `billed_faulty_try` as decimal strings with two decimal places (`^\d+\.\d{2}$`). For `revenue_uplift` records, `amount_try` must equal `billed_clean_try - billed_faulty_try`.

`make_record(fault, *, patient_id, claim_id, line_id, line_ids=(), evidence_line_ids=(), amount_try, billed_clean_try, billed_faulty_try)` populates `engine_rule`, `sut_section`, `effect_kind`, `expected_status`, `line_type`, `story` and `pathway_id` from `fault`, builds the `line_ids` tuple from `line_ids` and `evidence_line_ids` (defaulting to `fault.expected_finding.evidence_entry_ids` when neither is provided), and validates `line_id` shape and `revenue_uplift` arithmetic.

### Answer-key rows (`scripts/synthetic/faults/answer_key.py`)

`build_expected_rule_outputs(records) -> list[dict]` produces one row per `FaultInjectionRecord`, sorted by `(claim_id, fault_id)`, with the 13 columns of `ExpectedRuleOutput`:
- `expected_output_id`: `f"BEK-{claim_id}-{fault_id}"` (duplicate ids raise `ValueError`)
- `scenario_tag`: `fault_id`
- `patient_id`, `claim_id`, `line_id`, `line_type`
- `rule_family`: `engine_rule`
- `expected_status`: `expected_status` (`eksik_faturalama` or `kismi_red`)
- `expected_payable_try`: always `None` (no answer is stored in a payable)
- `expected_savings_try`: `Decimal(amount_try)`
- `expected_denial_reason`: `f"{effect_kind}:{fault_id}"`
- `expected_rule_trace`: `f"{sut_section}|{engine_rule}"`
- `assertion_notes`: `f"clean={billed_clean_try} faulty={billed_faulty_try}"`

A clean claim has no `FaultInjectionRecord` and therefore zero rows in `expected_rule_outputs.parquet`. That `expected_payable_try` equals `billed_amount_try` on every submitted claim line (and `expected_total_payable_try` equals `expected_total_billed_try` on the claim header, so no runtime rule can read the answer from a pre-computed payable amount) is a rule for the cohort generator of phase P4; nothing in P3 constructs or checks submitted claim lines.

## What changed with the v3 cohort

In v2, `expected_status = "kismi_red"` meant `expected_payable_try < billed_amount_try` with a non-null payable amount on every claim and line row. In v3, `expected_rule_outputs.parquet` reuses `"kismi_red"` for line-level deductions/compliance errors with `expected_payable_try = None`, adds `"eksik_faturalama"` for claim-level missing/under-billed uplift rows (`expected_payable_try = None`), and emits zero rows for clean claims. The v3 cohort replaced the v2 Parquet files in `data/synthetic/sut/` (P7-lite). Two readers of the v2 shape, `scripts/synthetic/validate_sut_synthetic_data.py` and `scripts/synthetic/assert_tier_a_post_regen.py`, were deleted with the v2 generator. The third, `tests/unit/domain/claims/test_loader.py`, had row-count floors sized for 50 patients; it moves to the registry counts (P6/P7 pin inventory `plans/data/2026-10-17-p6-p7-legacy-pins.md`, row 11).

## Checks (`scripts/synthetic/faults/checks.py`)

Run the checks from the repository root:

```bash
.venv/bin/python -m scripts.synthetic.faults.checks
```

| Check | What it verifies |
|---|---|
| `yaml.invalid`, `hygiene.forbidden_key`, `hygiene.anon_text`, `hygiene.price_text`, `hygiene.id_like_number` | strict YAML syntax (no duplicate keys); no key containing `price`, `amount`, `total` or `package_candidate`; no `ANON` identifier, non-zero currency amount (`TL`, `TRY`, `₺`) or 11-digit number in any key, value or comment |
| `schema.unknown_field`, `schema.missing_field`, `schema.bad_enum`, `schema.bad_value`, `schema.sibling_alone`, `schema.target_entry_shape` | Pydantic model validation, `extra="forbid"`, distinct `keep_day_indices`, `use_sibling_pathway` alone in `mutations`, and `target_entry_id` null iff `line_type == "fatura"` |
| `fault.target_pathway`, `fault.entry_id`, `fault.keep_day_indices`, `fault.flag`, `fault.drop_diagnosis`, `fault.breaks_indication`, `fault.billed_ratio_target`, `fault.target_entry_id`, `fault.evidence_entry_ids`, `fault.applies` | target/sibling pathway existence and clean load; `entry_id` in stated section; valid strict-subset `keep_day_indices` on `expand(..., annotate=True)`; valid flag name and value type on `MaterialFlags`/`DrugFlags`; secondary diagnosis on `drop_diagnosis` and indication linkage; `session_role` on `set_billed_ratio`; `target_entry_id` and `evidence_entry_ids` present in effective pathway; `apply_fault` succeeds on the target pathway with its showcase pins |
| `fault.sut_clauses`, `fault.source_cites`, `fault.detectors` | every `C000000` clause in `sut_clauses` and `source` is in force in `data/gazette/sut_clauses.parquet`; `basis: sut` cites a clause or `EK-` annex; every detector `"<module>:<func>"` exists on disk and contains `def <func>` |
| `fault.duplicate_id`, `fault.duplicate_story`, `fault.story_coverage`, `fault.op_coverage` | unique `fault_id`; each story at most once and the first eight (`S1`..`S8`) covered; all 6 mutation operations used at least once |

## Add a fault

1. Verify the target pathway in `data/synthetic/pathways/<target_pathway>.yaml` and inspect its annotated expansion (`expand(load_pathway(path), annotate=True)`) to confirm `entry_id`, `day_index`, `session_role` and `indication` values.
2. Add a `FaultSpec` entry to `data/synthetic/faults/fault_registry.yaml` using one or more of the six `MutationOp` operations, citing the in-force SUT clause ids in `expected_finding.sut_clauses` and `source` (at most 160 characters, no currency amounts).
3. Run `.venv/bin/python -m scripts.synthetic.faults.checks` and `.venv/bin/python -m pytest tests/unit/synthetic/test_fault_registry.py -q` until green.

