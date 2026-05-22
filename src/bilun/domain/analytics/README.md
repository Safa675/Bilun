# src/sut/analytics

SUT analytics helpers for DRG and material rule review.

## Purpose

Provide analytical helpers while the active SUT product contract moves to exact
claim-line inputs. Any billing amount exposed to cache, API, or UI consumers
must come from explicit procedure, material, or drug claim lines; otherwise the
consumer should return unavailable metadata instead of a guessed number.

## Public Surface

| Function | Description |
|----------|-------------|
| `compute_drg_summary(...)` | Compatibility DRG episode helper; not an active exact billing contract until rewritten to claim-line inputs |

## Removed / non-active contracts

- Legacy gap analysis is not part of the active analytics surface.
- Patient approximation-driven DRG totals are not active product behavior;
  exact totals must come from `src.sut.claims`.

## Dataclasses

| Class | Description |
|-------|-------------|
| `DRGEpisode` | Single DRG care episode |
| `DRGSummary` | Patient-level DRG summary |

## Modules

- `drg.py` — `DRGEpisode`, `DRGSummary`, `compute_drg_summary`
- `materials.py` — compatibility material rule helpers; active billing values must come from exact claim lines
- `shared.py` — `_select_patient_rows` helper

## Dependencies

- `src.sut.claims` — exact claim-line totals for active billing consumers
- `src.sut.materials` — Material lookup functions

## Example

```python
from src.sut.claims import load_sut_claim_dataset

dataset = load_sut_claim_dataset()
totals = dataset.patient_totals["SENTETIK-HASTA-001"]
print(totals.total_expected_payable_try, totals.source)
```
