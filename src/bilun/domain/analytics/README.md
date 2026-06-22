# src/bilun/domain/analytics

SUT analytics helpers for DRG episode cost modeling and material rule review.

## Purpose

Provide analytical helpers while the active SUT product contract moves to exact
claim-line inputs. Any billing amount exposed to cache, API, or UI consumers
must come from explicit procedure, material, or drug claim lines; otherwise the
consumer should return unavailable metadata instead of a guessed number.

## Public Surface

| Function | Description |
|----------|-------------|
| `compute_drg_summary(...)` | Claim-exact DRG episode helper. Builds one episode per inpatient `ClaimHeader`, uses real admission/discharge dates for LOS, and prices from billed `paket` lines or the dated EK-2C catalog entry for the billed package code. No ICD-chapter median heuristics. |

## Removed / non-active contracts

- Legacy gap analysis is not part of the active analytics surface.
- Patient approximation-driven DRG totals are not active product behavior;
  exact totals must come from `src.bilun.domain.claims`.
- ICD-chapter median DRG pricing (`pricing.drg`) was removed; use billed package
  codes with `get_ek2c_price_for_date` instead.

## Dataclasses

| Class | Description |
|-------|-------------|
| `DRGEpisode` | Single DRG care episode, aligned to one inpatient claim |
| `DRGSummary` | Patient-level DRG summary |

## Modules

- `drg.py` — `DRGEpisode`, `DRGSummary`, `compute_drg_summary`
- `materials.py` — compatibility material rule helpers; active billing values must come from exact claim lines

## Dependencies

- `src.bilun.domain.claims` — exact claim-line totals and claim headers for active billing consumers
- `src.bilun.domain.pricing.temporal` — dated EK-2C catalog price lookups for billed package codes
- `src.bilun.domain.prose_rules.catalog_membership` — EK-2C group metadata for billed package codes

## Example

```python
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.analytics import compute_drg_summary

dataset = load_sut_claim_dataset()
drg = compute_drg_summary(
    "SENTETIK-HASTA-0001",
    None,  # ana_df is deprecated and ignored
    claim_dataset=dataset,
)
print(drg.pricing_status, drg.episodes[0].drg_package_price)
```
