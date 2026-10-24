# src/bilun/domain/billing

Normative billing optimization engine — claim-backed algorithms + cohort aggregator.

## Purpose

Produce billing action reports from explicit inputs and exactness metadata. When
procedure, material, drug, package, or billed amount claim lines are missing,
active consumers should expose partial/unavailable status rather than guessed
recovery amounts.

## Algorithms

| # | Algorithm | Gazette Annex | Description |
|---|-----------|---------------|-------------|
| 1 | Lab Billing Optimizer | EK-2B | Hemogram (CBC) bundling — L107020 |
| 2 | Copay Savings Calculator | EK-1A, EK-4/D | Exemption savings + rate corrections on claim lines; a report over some bills is exempt on the emergency ground (SUT 1.8.5.(5)) only when every bill is an emergency bill |
| 3 | Package vs Itemized Recommender | EK-2C | Exact package vs itemized comparison when claim totals are supplied |
| 4 | Material Reimbursability Pre-Check | EK-3C-1/3C-2 | Pre-auth flags + MIAT warnings |

## Public Surface

| Function | Description |
|----------|-------------|
| `compute_patient_billing_report(...)` | Full billing report for one patient |
| `compute_all_billing_reports(cache)` | Cohort-level reports + summary |
| `compute_all_bill_billing_reports(cache)` | Per-bill reports keyed by `patient_id::claim_id` |

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

- `types.py` — Result dataclasses and exactness constants
- `block_registry.py` — Declarative metadata for billing blocks
- `claim_*.py` — Claim-backed algorithm implementations
- `patient_report.py` — Single-patient report assembly
- `lab_bill_merge.py` — Per-bill lab optimization + capture-gap merge
- `procedure_dedup.py` — Add-on vs capture-gap deduplication
- `report_totals.py` — TRY headline totals on `BillingActionReport`
- `report_exactness.py` — Block and report exactness rollup
- `recovery_summary.py` — Cohort table rows and cached JSON adapters
- `priority.py` — Patient priority tiering by SGK uplift percentile
- `cohort_summary.py` — `CohortRecoverySummary` aggregation
- `cohort_runner.py` — Parallel cohort fan-out
- `orchestrator.py` — Thin facade re-exporting public entry points

## Example

```python
from src.bilun.domain.billing import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

# The demo data are the 11 showcase patients, SENTETIK-HASTA-0001 .. SENTETIK-HASTA-0011.
dataset = load_sut_claim_dataset("data/synthetic/sut/claims")
claim_context = build_patient_claim_context("SENTETIK-HASTA-0001", dataset)

report = compute_patient_billing_report(
    "SENTETIK-HASTA-0001",
    claim_context=claim_context,
)
print(report.exactness_status, report.required_inputs_missing)
```
