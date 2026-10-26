# src/sut/optimization

Rule engines for exact or explicitly unavailable SUT revenue optimization features.

## Purpose

Apply gazette annex rules only when the required explicit inputs are present.
Diagnoses may provide clinical context, but procedure, material, drug, package,
and billed amount decisions must come from exact claim lines. Features without
those inputs should surface missing-input metadata rather than guessed values.

## Features

| # | Feature | Gazette Annex | Active status |
|---|---------|---------------|---------------|
| 1 | Copayment Exemptions | EK-1A | Gazette rule check from explicit diagnosis input; the emergency visit ground (SUT 1.8.5.(5)) is claim-scoped: it exempts the emergency bill, and the patient only when every bill is an emergency bill; EK-1/A is read on the claim's date (`CopayExemptionInput.service_date`: a bill's own date, a patient's latest bill; today only without claims, #292); a bill report re-reads its patient's input on the bill's date (`bill_copay_exemption_input`) |
| 2 | Surcharge Eligibility | EK-2G | Gazette rule check; billed exposure requires exact procedure claim lines |
| 3 | Copay Rate Eligibility | EK-2C-1 | Gazette rule check; billed exposure requires exact procedure claim lines; the ICU day packages (P552001-3, P552006-8) are not read: their EK-2C-1 rate is the Sınıf-3 uplift of SUT 2.2.(20), applied by the ICU motor |
| 4 | Temporal Price Validation | EK-2B/2C history | Exact only when procedure code and date are supplied |
| 5 | DRG Unbundling Detection | EK-2B/2C | Unavailable for active billing until package and itemized claim lines are wired |

## Public Surface

| Function | Description |
|----------|-------------|
| `check_copay_exemptions(...)` | Check ICD-10 against EK-1A chronic disease exemptions |
| `analyze_surcharge_exposure(...)` | EK-2G no-surcharge rule eligibility; billed exposure requires exact procedure claim lines |
| `analyze_copay_rate_exposure(...)` | EK-2C-1 mandated copay rate eligibility; billed exposure requires exact procedure claim lines |
| `audit_temporal_prices()` | System-level price change audit (cached) |
| `detect_drg_unbundling(...)` | Compatibility helper; active billing must remain unavailable without exact package and itemized claim lines |
| `compute_optimization_summary(...)` | Cohort-level rule summary that must preserve exact/unavailable status |

## Modules

- `shared.py` — Helpers, `_icd10_in_range`, diagnosis extraction
- `copay_exemptions.py` — Feature 1
- `surcharge.py` — Feature 2
- `copay_rates.py` — Feature 3
- `temporal.py` — Feature 4
- `unbundling.py` — Feature 5
- `aggregator.py` — `compute_optimization_summary`

## Example

```python
from src.sut.optimization import check_copay_exemptions, compute_optimization_summary

# Single patient exemption check
result = check_copay_exemptions(["I10", "E11.9"])
if result["exempt"]:
    print(f"Exempt for: {result['qualifying_diagnoses']}")

# Cohort-level summary
summary = compute_optimization_summary(ana_df, patient_ids)
print(summary["copay_exemptions"]["exemption_rate"])
```
