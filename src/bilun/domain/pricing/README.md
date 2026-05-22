# src/sut/pricing

SUT gazette package-price lookup helpers.

## Purpose

Resolve EK-2C DRG package prices from curated gazette catalogs. Exact
patient-level billing totals are not computed in this package; active product
payloads that need billed/payable amounts must use explicit claim lines through
`src.sut.claims` or return unavailable metadata when those inputs are missing.

## Public Surface

| Function | Description |
|----------|-------------|
| `get_drg_package_price(icd10_chapter)` | Legacy current EK-2C median lookup for an ICD-10 chapter; not an exact patient billing total |
| `get_drg_package_price_for_date(icd10_chapter, procedure_date)` | Dated EK-2C lookup that returns `None` when no eligible package exists for the requested date |

## Compatibility-only legacy helpers

Older cohort/patient approximation helpers may still be importable while the
dead legacy removal plan is executed. They are not active cache, API, UI, or
claim-total contracts and must not be used as fallbacks for missing exact
procedure, material, or drug claim lines.

## Private Symbols (preserved for backward compatibility)

| Symbol | Description |
|--------|-------------|
| `_DRG_PRICE_CAP_FACTOR` | Max ratio of package price to itemized cost (3.0) |
| `_get_ek2c_group_median_prices()` | Module-level cache for group medians |
| `_get_ek2c_chapter_median_prices()` | Module-level cache for chapter medians |
| `_ICD10_CHAPTER_KEYWORDS` | Turkish clinical keywords for DRG matching |

## Modules

- `drg.py` — DRG package pricing, dated EK-2C medians, ICD-10 keyword filtering
- `keywords.py` — `_ICD10_CHAPTER_KEYWORDS` dictionary
- legacy cohort/patient modules — compatibility imports only; not active exact billing surfaces

## Dependencies

- `src.sut.claims` — exact procedure/material/drug claim-line totals for active patient billing values

## Data Sources

- EK-2C parquet: `data/gazette/curated/ek2c_catalog_history.parquet`
- Exact synthetic claim Parquets: `data/synthetic/sut/claims/*.parquet`

## Example

```python
from datetime import date

from src.sut.claims import load_sut_claim_dataset
from src.sut.pricing import get_drg_package_price_for_date

package_price = get_drg_package_price_for_date("I", date(2025, 1, 15))

dataset = load_sut_claim_dataset()
totals = dataset.patient_totals["SENTETIK-HASTA-001"]
print(totals.total_billed_try, totals.exactness_status)
```
