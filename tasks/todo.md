## Task: L3.4 session itemized + prose_drg_locked catalog

### Goal
Wire §2.2.2.B session factors into strategy itemized totals; move prose DRG lock to EK-2C catalog seed.

### Subtasks
- [x] `compute_session_adjusted_itemized_total()` + `claim_strategy` fields
- [x] `ek2c_prose_drg_locked_codes.json` (51 codes) + `procedure_prose_drg_locked()`
- [x] `payment_method.py` uses catalog flag
- [x] Tests: session adjusted, prose locked mandatory, claim strategy suite

### Out of Scope
- DuckDB `build_cache.py --activate` (run when billing cache refresh needed)

### Review
- EK-2C rebuilt: `ek2c_catalog_history.parquet` — 26,412 rows, **51** `prose_drg_locked=True` on latest slice (matches seed).
- Seed refresh: `python scripts/sut/catalogs/ek2c_prose_drg_locked_seed.py`
