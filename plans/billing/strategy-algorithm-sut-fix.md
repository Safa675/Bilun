## Task: Fix billing strategy algorithm per actual SUT §2.2 rules

**Status:** Phases 1–6 + L3.4 session/prose tails **complete** (2026-06-02); Phase 7 ops verify only  
**Fact-check:** L3.4 — archived **PARTIAL** verdict; live in `fact_check_audit.py` / Rule Database (**PARTIAL**, core §2.2 fix shipped)

### Goal
Replace the remaining "pick whichever pays more" logic in billing strategy with the SUT-mandated payment-method decision tree (§2.2.2 inpatient, §2.2.1.B-1 outpatient). Recommendations must always be **legally compliant first**; savings are **corrective** (wrong method today) or **optional** (tier-3 override only).

### Root cause (resolved)
Historically `claim_strategy.py` fell back to price comparison when mandated methods were mixed. **Fixed:** mandatory paths use `PaymentMethodKind`; price compare applies **only** to `DRG_OVERRIDABLE` (§2.2.2(2)).

**SUT anchors (from `sut_clauses.parquet` / prose pipeline):**

| Section | Rule |
|---------|------|
| §2.2.2(1) | In EK-2/C → tanıya dayalı (package/DRG). Not in EK-2/C → hizmet başına (itemized). |
| §2.2.2(2) | Third-tier hospitals may bill **non-(\*)** EK-2/C procedures from EK-2/B instead — optional override, not universal. |
| §2.2.2(2) proviso | Procedures prose-mandated to EK-2/C are always package regardless of (\*) or tier. |
| §2.2.1.B-1(a/b) | Outpatient second/third tier: same EK-2/C vs EK-2/B split. |

**Current code state:**

| Item | Status |
|------|--------|
| `prose_rules/payment_method.py` + `PaymentMethodKind` | ✅ |
| EK-2C `has_star` in curated catalog + `procedure_has_star()` | ✅ |
| `prose_rules/facility_tier.py` + `ClaimHeader.facility_tier` | ✅ |
| `claim_strategy.py` — mandatory / corrective savings / override only | ✅ |
| Per-line `check_payment_method_compliance()` | ✅ |
| `recommendation_kind`, `sut_section_id`, `payment_method_kind` on recommendations | ✅ |
| Session fractions in itemized strategy totals | ✅ `compute_session_adjusted_itemized_total` |
| `prose_drg_locked` on EK-2C catalog | ✅ seed + `procedure_prose_drg_locked()` |

### Architecture principle
**Single engine:** extend `src/bilun/domain/prose_rules/` — do **not** add parallel `get_payment_method()` in `catalog.py`. All outputs carry `ProseRuleTrace` → standardized as `sut_section_id`.

**Delegate, don't duplicate:** session point checks (§2.2.2.B) stay in `prose_rules/drg_unbundling.py`; strategy focuses on payment-method selection and claim-level totals.

---

### Decision taxonomy

```text
PaymentMethodKind:
  DRG_MANDATORY    — must bill package (EK-2/C, or prose-locked EK-2/C)
  DRG_OVERRIDABLE  — tier-3 + non-star + in both lists → may choose higher legal option
  ITEMIZED         — EK-2/B only (or not in EK-2/C)
  NOT_IN_SUT       — not in EK-2/B or EK-2/C

RecommendationKind:
  mandatory_compliance  — only one legal method; savings = corrective if currently wrong
  optional_override     — tier-3 §2.2.2(2); savings = max(legal options) - min
```

### Savings semantics (mandatory)

| Kind | Current billing | Recommendation | `savings_try` |
|------|-----------------|----------------|---------------|
| DRG_MANDATORY | itemized | package | `max(0, drg - itemized)` |
| DRG_MANDATORY | package (correct) | package | `0` |
| ITEMIZED | package | itemized | `max(0, itemized - drg)` |
| ITEMIZED | itemized (correct) | itemized | `0` |
| DRG_OVERRIDABLE | either | higher-paying **legal** option | `max - min` |
| NOT_IN_SUT | — | skip | — |

**Never** recommend a non-compliant method because it pays more.

---

### Subtasks

#### Phase 1 — Data: EK-2C `has_star` column (blocker)
- [x] `scripts/sut/catalogs/price_history.py` (or EK-2C curator): extract `has_star: bool` from raw EK-2C xlsx column `*`
- [x] Rebuild `data/gazette/curated/ek2c_catalog_history.parquet` with `has_star`
- [x] `prose_rules/catalog_membership.py`: `get_ek2c_entry()` / `procedure_has_star()`
- [x] §2.2.2(2) override rule in `data/gazette/prose_rules/payment_method_2_2.json`
- [x] `tests/unit/scripts/test_extract_ek2c.py` — star count > 0

#### Phase 2 — Tier normalization (use existing `facility_tier`)
- [x] `prose_rules/facility_tier.py`: `normalize_facility_tier()` → `TierContext` (basamak 2|3, `is_university_eah`)
- [x] Map synthetic values: `3_basamak` → 3; `2_basamak_kamu` / `2_3_basamak_ozel` → 2
- [x] No new claim model fields — `ClaimHeader.facility_tier` via `claims/loader.py`
- [x] University / eğitim-arastırma provider types wired

#### Phase 3 — Engine: tier + star aware payment method
- [x] `resolve_payment_method(procedure_code, *, care_setting, facility_tier, provider_type, as_of_date)` → `PaymentMethodResult`
- [x] Decision tree (NOT_IN_SUT → ITEMIZED → prose-locked → star → basamak 2 → basamak 3 override)
- [x] `check_payment_method_compliance()` uses `.kind`
- [x] `tests/unit/domain/prose_rules/test_payment_method_tier_star.py`

#### Phase 4 — Algorithm: fix `claim_strategy.py` (core fix)
- [x] Removed mandatory price-comparison fallback
- [x] Per-claim aggregation: `DRG_MANDATORY` > `DRG_OVERRIDABLE` > `ITEMIZED`
- [x] Unified recommendation shape (`recommendation_kind`, `payment_method_kind`, `sut_section_id`, `rule_id`, …)
- [x] Corrective savings vs current billed category
- [x] Compliance violations as `type: "compliance_violation"`
- [x] `tests/unit/domain/billing/test_claim_strategy_sut.py`

#### Phase 5 — Docs, coverage, tests
- [x] `docs/core-system/algorithms_reference.md` §3.4 — SUT-first strategy (no universal “pick cheaper”)
- [x] `tests/unit/domain/prose_rules/test_payment_method_tier_star.py`
- [x] `tests/unit/domain/billing/test_claim_strategy_sut.py`
- [x] `tests/unit/domain/test_billing_strategy_exactness.py` — `F-SENTETIK-HASTA-0003-011` mandatory package
- [ ] Re-run `scripts/sut/build_sut_coverage.py` after next catalog/prose change (optional hygiene)

#### Phase 6 — Frontend (follow-up, after backend stable)
- [x] `SutBillingReportSections.tsx` — mandatory vs override badges (`billing.strategy.badgeMandatory`, …)
- [x] `billingReportFields.ts` — `recommendation_kind`, `payment_method_kind`, savings basis
- [x] Compliant mandatory rows: savings not shown as revenue “optimization”

#### Phase 7 — Rebuild and verify
- [ ] Rebuild EK-2C curated + gazette snapshot when raw SUT files change
- [ ] `python scripts/bilun/build_cache.py --activate` after catalog rebuild
- [ ] Full test suite in `.venv` before release tag

---

### Remaining

1. **Phase 7 — operational verify** — rebuild EK-2C curated parquet with `prose_drg_locked` column when raw SUT files change; `python scripts/bilun/build_cache.py --activate`; full pytest before release.

~~2. Session-adjusted itemized totals~~ — **Done (2026-06-02):** `compute_session_adjusted_itemized_total()` in `session_pricing.py`; `claim_strategy.py` exposes `itemized_price_methodology`, `itemized_raw_try`.

~~3. v2 `prose_drg_locked` on catalog~~ — **Done (2026-06-02):** SUT-mined seed `ek2c_prose_drg_locked_codes.json` (51 codes); `procedure_prose_drg_locked()`; EK-2C extract column; `payment_method.py` uses catalog flag.

---

### Out of scope (v1)
- §2.2.1 full outpatient / EK-2/A visit fee stacking beyond payment-method kind
- §2.2.2.C complication billing
- §2.2.2.B-3 ten-day post-discharge window
- §2.2.2.B session point factors **inside strategy totals** (handled elsewhere until remaining #2)
- Prose-locked "always EK-2/C" procedure list beyond `has_star` (v2 — remaining #3)
- Real hospital master data integration beyond synthetic `facility_tier` strings

### Success criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | No mandatory claim recommendation from pure `package_total <= itemized_total` | ✅ |
| 2 | Tier-2 + EK-2/C → `DRG_MANDATORY`, `mandatory_compliance` | ✅ |
| 3 | Tier-3 + non-star + dual-listed → `DRG_OVERRIDABLE`, higher legal total | ✅ |
| 4 | Every recommendation has `sut_section_id` and `rule_id` | ✅ |
| 5 | Corrective savings only when current billing ≠ mandated | ✅ |
| 6 | `test_claim_strategy_sut.py` + tier/star tests pass | ✅ |

### Review

**Completed 2026-06-02.** Backend Phases 1–4 in `payment_method.py`, `facility_tier.py`, `claim_strategy.py`. Session-adjusted itemized totals + catalog `prose_drg_locked` (51 SUT-listed codes). Phase 5–6 tests/UI landed. Rebuild curated EK-2C for parquet column: `python scripts/sut/catalogs/ek2c_prose_drg_locked_seed.py` then `build_curated_catalogs.py --overwrite`.

**Key files:** `src/bilun/domain/billing/claim_strategy.py`, `src/bilun/domain/prose_rules/payment_method.py`, `frontend/src/lib/billingReportFields.ts`, `frontend/src/components/patient/SutBillingReportSections.tsx`.

**Verify locally:**
```bash
python -m pytest tests/unit/domain/billing/test_claim_strategy_sut.py \
  tests/unit/domain/prose_rules/test_payment_method_tier_star.py \
  tests/unit/domain/test_billing_strategy_exactness.py -q
```
