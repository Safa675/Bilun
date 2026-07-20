# Plan: Finans Pricing Audit — hospital price vs SUT list price (as-of-date)

**Status:** Draft for review — 2026-07-16
**Branch:** `finans-coder` (Phases 1-5 committed)
**Predecessor:** Phases 1-5 crosswalk (867/924 codes resolved, 93.8% coverage)
**Current state:** finans rows now carry resolvable SUT codes but no motor has run on them yet.

---

## Task: Compare the hospital's billed price (`KDVSIZ_FIYAT`) against the SUT EK-2B list price *as of the service date* (`TARIH`), for all 2,257 resolved EK-2B rows. Flag over/under-charges. Validate the crosswalk as a side effect.

### Goal
One script + one report. Answer: "did the hospital bill the right SUT rate on the right date, and where did they diverge?" No claim-loader integration, no motor runs — pure catalog lookup + comparison.

---

## Context — verified facts (2026-07-16)

### The comparison is valid and meaningful
- **EK-2B prices resolve cleanly** via `lookup_procedure_code(code, visit_date=TARIH)` — returns `price_try` for all 133 distinct resolved codes.
- **Temporal pricing is mandatory and works.** SUT prices change with each tebliğ. ALT: 1.15 TRY (2019) → 7.2 TRY (2026), a 6.3× increase. Poliklinik muayene: 17→71 TRY. A non-temporal comparison would flag every old bill as mispriced. The `visit_date` overload returns the correct as-of-date price.
- **TARIH is 100% covered** (7,480/7,480 rows, 2019-01-11 → 2026-05-05).
- **133 distinct EK-2B codes** across 2,257 rows are auditable. The other 5,223 rows are drugs (no retail TRY in our catalog), materials (EK-3 ceiling pricing — different mechanism), excluded (hotel/bundled), or unresolved.

### Scope boundary (corrected after investigation — all 3 catalogs in scope)
- **EK-2B (procedures/labs/radiology): IN SCOPE.** Clean list-price comparison, date-aware. 133 codes / 2,257 rows.
- **EK-4A (drugs): IN SCOPE (partial now, full if TİTCK downloaded).** EK-4A carries `discount_tier_1..4` (the SGK rebate percentages) but NOT the retail TRY shelf price. Two audit levels:
  - **Tier audit (doable now):** verify the hospital's discount application matches the EK-4A tier for each drug. Doesn't need retail price.
  - **Retail audit (needs TİTCK list):** compare `KDVSIZ_FIYAT` vs the TİTCK retail price minus tiers. TİTCK Fiyat Listesi is public ([titck.gov.tr/dinamikmodul/70](https://www.titck.gov.tr/dinamikmodul/70)), downloadable as Excel. Defer until downloaded, or do tier-only now.
- **EK-3 (materials): IN SCOPE.** Materials carry a `FİYAT (TL)` column (ex-VAT list price, e.g. OR1000 = 283.74 TRY). The "ceiling mechanism" (`ek3_payable_ceiling_try`) just adds KDV (20%) to get the payable ceiling — it's the same billed-vs-list comparison as EK-2B, with one extra VAT step. Not structurally different (earlier claim was wrong). Audit: `KDVSIZ_FIYAT` vs `EK-3 fiyat + KDV`.

### Mülga handling (abolished codes in the 2019-2026 span)
finans spans 7 years. SUT codes are added and abolished (mülga) over time. The date-aware lookup (`_load_curated_ek2b_by_asof`) filters by `effective_date <= TARIH` and keeps the **last valid version** — so a 2021 bill gets the 2021 price, and a mülga code gets its last-valid price before abolition. The `__valid_from`/`__valid_to`/`__is_mulga` columns capture this. No special handling needed — the existing temporal lookup is correct. Flag codes where `__valid_to < TARIH` (billed after abolition — a real error the hospital made).

### What the audit validates (side effect)
If the hospital's `KDVSIZ_FIYAT` closely tracks the SUT list price for resolved codes, the crosswalk mappings are confirmed correct (a wrong code→price mapping would produce wild divergences). If a specific code shows systematic 100%+ divergence across all its rows, that's likely a **wrong crosswalk mapping** — flag it for review.

---

## Subtasks

### Phase 6.1 — Pricing audit script (all 3 catalogs)
- [ ] **6.1.1** `scripts/analysis/finans_pricing_audit.py`. Three audit paths by catalog:
  - **EK-2B:** `lookup_procedure_code(sut_code, visit_date=TARIH)` → `price_try`. Compare vs `KDVSIZ_FIYAT`.
  - **EK-3:** load the EK-3 `FİYAT (TL)` (ex-VAT) for the resolved material code, apply `ek3_payable_ceiling_try` (adds KDV). Compare vs `KDVSIZ_FIYAT`.
  - **EK-4A (tier audit):** compare the hospital's `INDIRIM_ORANI` against the EK-4A `discount_tier_*` for the resolved drug. Flag mismatches. (Retail-price audit deferred until TİTCK list downloaded.)
- [ ] **6.1.2** Use `KDVSIZ_FIYAT` (ex-VAT, pre-discount) for EK-2B/EK-3 comparisons. For EK-4A tier audit, use `INDIRIM_ORANI` (the discount rate the hospital applied).
- [ ] **6.1.3** Classify each row: `MATCH` (|delta_pct| < 5%), `OVERCHARGE` (delta_pct > 5%), `UNDERCHARGE` (delta_pct < -5%), `NO_SUT_PRICE` (lookup returned null), `MULGA_BILLED_AFTER_ABOLITION` (`__valid_to < TARIH`), `TIER_MISMATCH` (EK-4A discount tier wrong).
- [ ] **6.1.4** Aggregate: per-code, per-patient, per-year, per-catalog summaries.
- [ ] **6.1.5** Flag suspected wrong crosswalk mappings: codes where the delta is consistently >100% or <-50% across ALL rows — likely wrong codes, not wrong prices.

### Phase 6.2 — Report + verification
- [ ] **6.2.1** Emit `data/finans_pricing_audit.parquet` (row-level) + `data/finans_pricing_audit.md` (summary: match rate by catalog, top overcharges/undercharges, tier mismatches, mülga violations, suspected-wrong-mappings).
- [ ] **6.2.2** Spot-check 10 rows across catalogs (5 match, 5 divergence) — confirm real vs artifact.
- [ ] **6.2.3** Commit on `finans-coder` branch.

---

## Hard rules / guards

1. **Date-aware lookup is mandatory.** NEVER compare a 2019 bill against a 2026 price. Always pass `visit_date=TARIH`. ALT went 1.15→7.2 TRY across the span — a static comparison produces false divergences. The lookup respects `effective_date` and returns the last-valid price (handles mülga codes).
2. **Compare ex-VAT to ex-VAT (EK-2B/EK-3).** `KDVSIZ_FIYAT` (hospital, ex-VAT) vs SUT list (ex-VAT). For EK-3, add KDV via `ek3_payable_ceiling_try` to get the payable ceiling, THEN compare.
3. **Distinguish wrong-price from wrong-code.** A code with systematic extreme divergence across all rows is a crosswalk error. Flag separately — don't report it as "hospital overcharged 500%".
4. **EK-4A tier audit uses INDIRIM_ORANI, not KDVSIZ_FIYAT.** The tier audit checks whether the hospital applied the correct SGK discount percentage, not the retail price. Retail-price audit is a separate sub-task pending TİTCK download.
5. **No claim-loader integration.** Standalone audit script. Option 1 (partial parquet) is separate.

---

## Out of scope
- EK-4A **retail-price** audit (needs TİTCK Fiyat Listesi download — public, deferred). The **tier** audit IS in scope.
- Partial `real_claims` parquet emission (Option 1 — separate task).
- Motor runs on finans data (needs the parquet emission first).

---

## Definition of done

- `finans_pricing_audit.py` runs, compares 2,257 EK-2B rows against date-aware SUT prices.
- `data/finans_pricing_audit.parquet` + `.md` report emitted with match/over/under breakdown + suspected-wrong-mappings.
- 10 spot-checks documented (5 match, 5 overcharge).
- Committed on `finans-coder`.

---

## Review

_(filled in as work progresses)_
