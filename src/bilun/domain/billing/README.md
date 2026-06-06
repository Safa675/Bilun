# src/sut/billing

Normative billing optimization engine — 4 algorithms + cohort aggregator.

## Purpose

Produce billing action reports from explicit inputs and exactness metadata. When
procedure, material, drug, package, or billed amount claim lines are missing,
active consumers should expose partial/unavailable status rather than guessed
recovery amounts.

## Algorithms

| # | Algorithm | Gazette Annex | Description |
|---|-----------|---------------|-------------|
| 1 | Lab Billing Optimizer | EK-2B | Hemogram (CBC) bundling — L107020 |
| 2 | Copay Savings Calculator | EK-1A, EK-4/D | Exemption savings + rate corrections on claim lines |
| 3 | Package vs Itemized Recommender | EK-2C | Exact package vs itemized comparison when claim totals are supplied |
| 4 | Material Reimbursability Pre-Check | EK-3C-1/3C-2 | Pre-auth flags + MIAT warnings |

## Public Surface

| Function | Description |
|----------|-------------|
| `compute_patient_billing_report(...)` | Full billing report for one patient |
| `compute_all_billing_reports(cache)` | Cohort-level reports + summary |

## Dataclasses

| Class | Description |
|-------|-------------|
| `LabOptimization` | Lab hemogram bundling analysis |
| `CopayOptimization` | Copayment savings |
| `BillingStrategyRecommendation` | Package vs itemized |
| `MaterialPreCheck` | Material pre-check flags |
| `BillingActionReport` | Complete patient report |
| `CohortRecoverySummary` | Cohort aggregation |

## Modules

- `types.py` — All dataclasses
- `lab.py` — Algorithm 1
- `copay.py` — Algorithm 2
- `strategy.py` — Algorithm 3
- `materials.py` — Algorithm 4
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
