# src/bilun/domain/pricing

SUT gazette package-price lookup helpers.

## Purpose

Resolve EK-2B procedure and EK-2C DRG package prices from curated gazette catalogs
on a specific service date. Exact patient-level billing totals are not computed
in this package; active product payloads that need billed/payable amounts must
use explicit claim lines through `src.bilun.domain.claims` or return unavailable
metadata when those inputs are missing.

## Public Surface

| Function | Description |
|----------|-------------|
| `get_ek2b_price_for_date(code, procedure_date)` | Dated EK-2B procedure price or puan from the canonical as-of catalog |
| `get_ek2c_price_for_date(package_code, procedure_date)` | Dated EK-2C package price for a billed package code |
| `get_price_history(code, catalog)` | Full price history from curated parquet |

`temporal.py` holds the active lookup helpers.

## Modules

- `temporal.py` — dated EK-2B/EK-2C catalog lookups and history helpers
- `material_kdv.py` — EK-3 payable ceiling helpers

## Dependencies

- `src.bilun.domain.catalog` — canonical as-of gazette catalog loading
- `src.bilun.domain.claims` — exact procedure/material/drug claim-line totals

## Data Sources

- EK-2B/EK-2C history: `data/gazette/curated/ek2b_catalog_history.parquet`, `ek2c_catalog_history.parquet`
- Every EK-2B, EK-2C and EK-2Ç `price_try` is puan × 0.593 cut at the kuruş, not rounded, as SUT 2.2.(15)
  (C000544) requires (510010: 374.97 puan = 222.35 TL, #299); `src.bilun.domain.money.puan_price_try` does that
  product for the catalog builders and the engine's own puan × katsayı amounts
- EK-2Ç dental history (40xxxx codes in the EK-2B index): `ek2c_dental_catalog_history.parquet`, read like
  EK-2B by each row's valid_from / valid_to, so a repealed dental code has no price after its valid_to (#293)
- Exact synthetic claim Parquets: `data/synthetic/sut/claims/*.parquet`

## Example

```python
from datetime import date

from src.bilun.domain.pricing.temporal import get_ek2c_price_for_date
from src.bilun.domain.claims import load_sut_claim_dataset

package_price = get_ek2c_price_for_date("P613380", date(2025, 1, 15))

dataset = load_sut_claim_dataset()
totals = dataset.patient_totals["SENTETIK-HASTA-0001"]
print(totals.total_billed_try, totals.exactness_status)
```
