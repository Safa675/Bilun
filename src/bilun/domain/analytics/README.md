# src/bilun/domain/analytics

SUT analytics helpers for material rule review.

## Purpose

Provide analytical helpers while the active SUT product contract moves to exact
claim-line inputs. Any billing amount exposed to cache, API, or UI consumers
must come from explicit procedure, material, or drug claim lines; otherwise the
consumer should return unavailable metadata instead of a guessed number.

## Public Surface

| Function | Description |
|----------|-------------|
| `price_material_lines(...)` | Compatibility material rule helpers; active billing values must come from exact claim lines; the EK-3 list price is read on the line's `material_date`, else on `as_of` (today when the request has no date, #292) |

## Modules

- `materials.py` — material line pricing helpers

## Dependencies

- `src.bilun.domain.materials` — EK-3 specialty materials and catalog lookup
