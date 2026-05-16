# SUT exact claim loader

`src.sut.claims` loads billing-native claim Parquets and exposes exact
line-derived aggregates. In demo mode, those files are the committed synthetic
claim Parquets under `data/synthetic/sut/claims/`.

## Inputs

- `claim_headers.parquet`
- `procedure_claim_lines.parquet`
- `material_claim_lines.parquet`
- `drug_claim_lines.parquet`
- `expected_rule_outputs.parquet`

The loader mirrors the synthetic dataset integrity rules for claim columns,
foreign keys, prescription traceability, expected rule outputs, and total
reconciliation. Optional lab-result linkage columns are validated when present;
the current v1.1 claim Parquets do not carry lab-result IDs, so lab aggregates
are derived from explicit procedure lines with `procedure_category="laboratuvar"`.

## Public entry point

```python
from src.sut.claims import load_sut_claim_dataset

dataset = load_sut_claim_dataset()
totals = dataset.patient_totals["SENTETIK-HASTA-001"]
```

Totals are calculated only from explicit procedure, material, and drug claim
lines. As a non-active guard against legacy approximation contracts, the exact
claim-loader contract intentionally does not expose `cost_min`, `cost_max`, or
`cost_mid` fields.

## Data modes and migration contract

`SUT_DATA_MODE=synthetic_demo` uses:

```bash
SUT_CLAIMS_DIR=data/synthetic/sut/claims
SUT_CLEAN_DIR=data/synthetic/sut/clean
```

Synthetic demo claims are rule-exact for the generated procedure, material, and
drug claim lines, but they are not real billing outcomes. Keep product, API, and
docs copy visibly labeled as synthetic demo claim data.

Future `SUT_DATA_MODE=real_claims` should point `SUT_CLAIMS_DIR` at a validated
hospital claim export and `SUT_CLEAN_DIR` at the matching clean clinical feed.
The real adapter must map hospital rows into the same `ClaimHeader`,
`ProcedureClaimLine`, `MaterialClaimLine`, and `DrugClaimLine` contract so rule
modules continue to consume `SUTClaimDataset` without source-specific branches.
