# SUT exact claim loader

`src.bilun.domain.claims` loads billing-native claim Parquets and exposes exact
line-derived aggregates. In demo mode, those files are the committed synthetic
claim Parquets under `data/synthetic/sut/claims/`: the 15 patients (28 bills) of the v3
showcase cohort, built by `python -m scripts.synthetic.cohort.build` (layout and
registry: `data/synthetic/README.md`).

## Module map

| Module | Responsibility |
|--------|----------------|
| `loader.py` | Public entry point, in-process LRU cache |
| `parquet_reader.py` | Read and schema-check Parquet tables |
| `schema.py` | `ParquetTableSpec` registry; shared with synthetic validation |
| `dataset.py` | `ClaimTables`, `SUTClaimDataset` |
| `dataset_builder.py` | Parse rows, validate links, build indexes |
| `parsing/primitives.py` | Cell coercion (`parse_text`, `parse_money`, dates) |
| `parsing/row_parsers.py` | Map `RowDict` rows to typed models |
| `validation/` | FK, date, lab, expected-output checks |
| `totals.py` | Per-claim and per-patient exact totals |
| `types.py` | `RowDict` alias for raw Parquet rows |
| `config.py` | `BILUN_DATA_MODE`, path guards, provenance |
| `models.py` | Typed row and aggregate dataclasses |

## Inputs

Required Parquet tables (see `schema.REQUIRED_CLAIM_TABLES`):

- `claim_headers.parquet`
- `claim_diagnoses.parquet`
- `procedure_claim_lines.parquet`
- `material_claim_lines.parquet`
- `drug_claim_lines.parquet`
- `expected_rule_outputs.parquet`

Optional tables (see `schema.OPTIONAL_CLAIM_TABLES`):

- `patient_copay_profiles.parquet` (its optional column `has_chronic_health_report`
  is true, false, or null/absent for not known; only true lets the EK-1/A exemption
  waive the outpatient copay, SUT §1.8.5(7))
- `performed_procedure_lines.parquet`
- `medula_rejection_events.parquet`

The loader mirrors the synthetic dataset integrity rules for claim columns,
foreign keys, prescription traceability, expected rule outputs, and total
reconciliation. Optional lab-result linkage columns are validated when present;
lab aggregates are derived from explicit procedure lines with
`procedure_category="laboratuvar"`.

The cohort tests (`tests/unit/synthetic/test_cohort_tables.py`) check the generated
tables against `build_synthetic_claim_validation_columns()` from `schema.py`, so
the loader's required columns and the generated tables stay aligned.

## Public entry point

```python
from src.bilun.domain.claims import load_sut_claim_dataset

dataset = load_sut_claim_dataset()
totals = dataset.patient_totals["SENTETIK-HASTA-0001"]
```

For tests or fixture reloads, clear the in-process cache:

```python
from src.bilun.domain.claims import clear_sut_claim_dataset_cache

clear_sut_claim_dataset_cache()
# or
load_sut_claim_dataset.cache_clear()
```

Build a dataset from in-memory rows (for unit tests):

```python
from src.bilun.domain.claims import SUTClaimDataset, read_claim_tables

tables = read_claim_tables()
dataset = SUTClaimDataset.from_rows(
    claim_headers=tables.headers,
    diagnoses=tables.diagnoses,
    procedure_lines=tables.procedures,
    material_lines=tables.materials,
    drug_lines=tables.drugs,
    expected_outputs=tables.expected_outputs,
)
```

Totals are calculated only from explicit procedure, material, and drug claim
lines. The exact claim-loader contract intentionally does not expose legacy
approximation fields such as `cost_min`, `cost_max`, or `cost_mid`.

## Data modes and migration contract

`BILUN_DATA_MODE=synthetic_demo` (legacy `SUT_DATA_MODE` still accepted) uses:

```bash
BILUN_CLAIMS_DIR=data/synthetic/sut/claims
BILUN_CLEAN_DIR=data/synthetic/sut/clean
```

Synthetic demo claims are rule-exact for the generated procedure, material, and
drug claim lines, but they are not real billing outcomes. Keep product, API, and
docs copy visibly labeled as synthetic demo claim data.

Future `BILUN_DATA_MODE=real_claims` should point `BILUN_CLAIMS_DIR` at a validated
hospital claim export and `BILUN_CLEAN_DIR` at the matching clean clinical feed.
The real adapter must map hospital rows into the same `ClaimHeader`,
`ProcedureClaimLine`, `MaterialClaimLine`, and `DrugClaimLine` contract so rule
modules continue to consume `SUTClaimDataset` without source-specific branches.
In `real_claims` mode, `expected_rule_outputs.parquet`, `expected_total_billed_try`,
`expected_total_payable_try`, `expected_payable_try`, `discount_tier_expected`,
`unit_price_try`, and `scenario_tag` are optional; omitted line payables default to
`billed_amount_try` and omitted header totals are derived from `claim_totals`.
