# src/sut/billing

Normative billing optimization engine — 5 algorithms + cohort aggregator.

## Purpose

Produce billing action reports from explicit inputs and exactness metadata. When
procedure, material, drug, package, or billed amount claim lines are missing,
active consumers should expose partial/unavailable status rather than guessed
recovery amounts.

## Algorithms

| # | Algorithm | Gazette Annex | Description |
|---|-----------|---------------|-------------|
| 1 | Lab Billing Optimizer | Gazette prices | Hemogram bundling + duplicate detection |
| 2 | Drug Cost Optimizer | EK-4A | Generic substitution + passivation detection |
| 3 | Copay Savings Calculator | EK-1A | Exemption savings + rate corrections |
| 4 | Package vs Itemized Recommender | EK-2C | Exact package vs itemized comparison when claim totals are supplied |
| 5 | Material Reimbursability Pre-Check | EK-3C-1/3C-2 | Pre-auth flags + MIAT warnings |

## Public Surface

| Function | Description |
|----------|-------------|
| `compute_patient_billing_report(...)` | Full billing report for one patient |
| `compute_all_billing_reports(cache)` | Cohort-level reports + summary |

## Dataclasses

| Class | Description |
|-------|-------------|
| `LabOptimization` | Lab billing analysis |
| `DrugOptimization` | Drug cost optimization |
| `CopayOptimization` | Copayment savings |
| `BillingStrategyRecommendation` | Package vs itemized |
| `MaterialPreCheck` | Material pre-check flags |
| `BillingActionReport` | Complete patient report |
| `CohortRecoverySummary` | Cohort aggregation |

## Modules

- `types.py` — All dataclasses
- `lab.py` — Algorithm 1
- `drug.py` — Algorithm 2
- `copay.py` — Algorithm 3
- `strategy.py` — Algorithm 4
- `materials.py` — Algorithm 5
- `orchestrator.py` — Main entry points

## Example

```python
from src.sut.billing import compute_patient_billing_report

report = compute_patient_billing_report(
    "P1",
    patient_lab_tests=["Hemoglobin", "Glucose"],
    patient_drug_names=["Aspirin"],
    chapters={"I", "E"},
)
print(report.exactness_status, report.required_inputs_missing)
```
