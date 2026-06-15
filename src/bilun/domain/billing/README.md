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
- `claim_lab.py` — Algorithm 1 (claim-line based)
- `copay.py` — Algorithm 2
- `strategy.py` — Algorithm 3
- `materials.py` — Algorithm 4
- `orchestrator.py` — Main entry points

## Example

```python
from src.bilun.domain.billing import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

dataset = load_sut_claim_dataset("data/synthetic/sut/claims")
claim_context = build_patient_claim_context("SENTETIK-HASTA-0001", dataset)

report = compute_patient_billing_report(
    "SENTETIK-HASTA-0001",
    claim_context=claim_context,
)
print(report.exactness_status, report.required_inputs_missing)
```
