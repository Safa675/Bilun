## Task: Finans Pricing Audit — hospital price vs SUT list price (as-of-date)

### Goal
One script (`scripts/analysis/finans_pricing_audit.py`) + one report
(`data/finans_pricing_audit.{parquet,md}`). Answer: did the hospital bill the
right SUT rate on the right date, and where did it diverge? Date-aware catalog
lookup + comparison across 3 catalogs (EK-2B / EK-3 / EK-4A). No claim-loader,
no motor.

**Full plan:** `plans/data/2026-07-16-finans-pricing-audit-plan.md`

### Subtasks
- [ ] **6.0** Load finans rows + frozen crosswalk; join → resolved rows w/ catalog tag
- [ ] **6.1.1a** EK-2B path: `get_ek2b_price_for_date(sut_code, TARIH)` → compare vs `KDVSIZ_FIYAT`
- [ ] **6.1.1b** EK-3 path: `lookup_ek3_list_price_try` → `ek3_payable_ceiling_try` (KDV) → compare vs `KDVSIZ_FIYAT`
- [ ] **6.1.1c** EK-4A path: join frozen DRUG `sut_code`(=kamu_no) → ek4a; compare `INDIRIM_ORANI` vs `discount_tier_1`
- [ ] **6.1.2** Use `KDVSIZ_FIYAT` (EK-2B/EK-3 ex-VAT) and `INDIRIM_ORANI` (EK-4A tier)
- [ ] **6.1.3** Classify: MATCH/OVERCHARGE/UNDERCHARGE/NO_SUT_PRICE/MULGA_BILLED_AFTER_ABOLITION/TIER_MISMATCH (±5% threshold)
- [ ] **6.1.4** Aggregates: per-code / patient(SIRA) / year / catalog
- [ ] **6.1.5** Flag suspected wrong crosswalk mappings (systematic extreme divergence across ALL rows)
- [ ] **6.2.1** Emit `data/finans_pricing_audit.parquet` + `.md` report
- [ ] **6.2.2** Spot-check 10 rows (5 match, 5 divergence), document in report
- [ ] **6.2.3** Commit on `finans-coder`
- [ ] **6.3** Verify: script runs clean, report renders, counts match plan (7480 total, 2257 EK-2B, 133 codes)

### Key API facts (verified 2026-07-16)
- `get_ek2b_price_for_date(code, date)` → strict as-of float|None (`temporal.py:89`); enforces `effective_date <= asof`
- Mülga: history parquet has `valid_from`/`valid_to` (NO `__` prefix). `get_price_history(code)` → polars DF. Detect billed-after-abolition via `valid_to < TARIH`.
- EK-3: `lookup_ek3_list_price_try(code)` (static, not date-aware) + `ek3_payable_ceiling_try(ex_vat)` adds 20% KDV.
- EK-4A: join frozen `sut_code`==`kamu_no` to `ek4a_drugs.parquet` (254/294 join). Tier audit vs `discount_tier_1`.
- Finans: `data/finans_clean.parquet`, 7480 rows. Frozen: `data/coding/hospital_to_sut.csv`, 867 rows (all reviewed=TRUE).
- Categories → catalog: LAB/PROCEDURE/RADIOLOGY=EK-2B, MATERIAL=EK-3, DRUG=EK-4A, HOTEL=excluded.

### Plan deviations (documented, resolved)
1. `__valid_from/__valid_to/__is_mulga` don't exist on lookup result → derive from `get_price_history()` history parquet (`valid_from`/`valid_to` cols).
2. EK-4A has 4 tiers, no single selector → compare `INDIRIM_ORANI` vs `discount_tier_1` (primary SGK rebate), report closest tier.

### Out of scope
- EK-4A **retail-price** audit (needs TİTCK Fiyat Listesi — deferred; tier audit IS in scope)
- Partial `real_claims` parquet emission (separate task)
- Motor runs on finans data (needs parquet emission first)

### Definition of done
- Script runs, compares 2257 EK-2B rows (+ EK-3/EK-4A) vs date-aware SUT prices
- `data/finans_pricing_audit.{parquet,md}` emitted with match/over/under breakdown + wrong-mappings
- 10 spot-checks documented
- Committed on `finans-coder`

### Review — Completed (2026-07-16)
- **Script:** `scripts/analysis/finans_pricing_audit.py` (6294 rows, 3 catalogs).
- **Counts match plan:** 7480 total → 6294 resolved → 2257 EK-2B / 133 distinct codes ✓.
- **Crosswalk validated (side effect):** 374 EK-2B MATCH (Potasyum/Sodyum/BUN exact).
- **Key finding:** 1568 EK-2B OVERCHARGE concentrated on inpatient lab lines (same code matches SUT on outpatient, billed 50–70× on inpatient stays → panel/bundle pattern).
- **Two plan premises corrected during implementation:**
  1. `INDIRIM_ORANI` is NOT a discount rate (values >1, e.g. 41.87) → derive real discount from `1 - KDVSIZ_INDIRIMLI/KDVSIZ_FIYAT`.
  2. Each finans row is ONE unit (repeated units = separate rows) → KDVSIZ_FIYAT is per-unit, no quantity column needed.
- **⚠️ EK-3 deferred:** catalog prices implausible (KN1069=103K TRY) — data-quality bug, not script bug.
- **Outputs:** `data/finans_pricing_audit.{parquet,md}` (gitignored under `data/*`, regenerable).
- **Lint:** ruff check + format clean.
- **Two bugs caught & fixed before shipping:** (a) sign bug from referencing in-flight `delta_pct` in same `with_columns`; (b) duplicate `_classify_ek3` block.

### Lessons (for tasks/lessons.md)
- Polars `with_columns` cannot reference a column being created in the same call for the flag expression — materialize numeric cols first, derive flag in a second `with_columns`.
- Verify a column's *semantics* from its value distribution before building logic on it (`INDIRIM_ORANI` looked like a discount rate but wasn't).
- `get_ek4a_drugs()` returns `list[dict]`, not a DataFrame — wrap with `pl.from_dicts`.
