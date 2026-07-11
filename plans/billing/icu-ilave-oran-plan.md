# ICU İlave Oran (+100%) — Sınıf-3 Facility Surcharge

**Status:** Approved-for-implementation plan (Phase 2 of `icu_puani` motor).
**Branch:** `yatak-puani` (current).
**Spec source:** This plan supersedes the original user-supplied spec; the user asked for evaluation + fixes, which produced the corrected decisions below.
**Related:** `tasks/todo.md` (§ICU İlave Oran), `plans/refactor/rule-encoding-gap-closure-roadmap.md`.

---

## 1. Goal

Extend `src/bilun/domain/prose_rules/icu_puani.py` to apply the EK-2/C-1 **ilave oran** (+100%, in-force) to the **intermediate ICU package days** (P55200x) when the facility resolves to **3rd basamak** (Sınıf-3). The uplift multiplies the intermediate puan by 2.0 (1 + 100/100). The `510090` day-rate is **not** uplifted — it is EK-2B hizmet-başı, absent from EK-2/C-1.

This closes the Phase-2 TODO at `icu_puani.py:28-31`.

---

## 2. Regulatory basis (verified)

| Claim | Evidence | Verdict |
|---|---|---|
| ICU ilave oran applies at **3rd-basamak** facilities | İstanbul Tabip Odası SUT finance briefing: *"SUT eki EK-2/C-1 listesinde yer alan ilave oran uygulanacak işlemlerin **3. basamak sağlık hizmeti sunucularınca** yapılması halinde"* | Gate = any 3rd-basamak facility (incl. non-university özel) → use `is_third_tier`, **not** `is_university_eah` |
| In-force oran = **100** for all 6 ICU codes | `data/gazette/curated/ek2c1_copay_rates.parquet`: `P552001/2/3/6/7/8` all `copay_rate_pct=100.0`. The 6 ICU codes are the only 100% entries in the 465-row catalog. Verified as of 2026-01-31. | oran=100. The docstring's "+60% or +100%" was historical (rates revised upward repeatedly — KHGM tebliğ: *"oranlar 10 puan artırılmıştır"*); +60% is stale. |
| `510090` is NOT in EK-2/C-1 | 0 rows in parquet for `510090`. | 510090 is never uplifted. |

**Sources:**
- [İstanbul Tabip Odası — Sağlığın Finansmanı (PDF)](https://www.istabip.org.tr/site_icerik/2023/ekim/sagliginfinansmaniweb.pdf)
- [KHGM — SGK SUT Değişiklik Tebliği](https://khgmfinansalanalizdb.saglik.gov.tr/TR-82746/sosyal-guvenlik-kurumu-saglik-uygulama-tebliginde-degisiklik-yapilmasina-dair-teblig.html)
- [Lexpera — tebliğ (P552001/2/3 cited)](https://www.lexpera.com.tr/resmi-gazete/metin/sosyal-guvenlik-kurumu-saglik-uygulama-tebliginde-degisiklik-yapilmasina-dair-teblig-30469-1-2)

---

## 3. Verified facts from the codebase (file:line)

### 3.1 Tier API — `src/bilun/domain/prose_rules/facility_tier.py`
- `tier_context_from_claim` at `:129-134` — thin wrapper around `normalize_facility_tier`. **Zero production callers** (only a unit test). Do NOT use.
- `normalize_facility_tier(facility_tier, provider_type=...) -> TierContext` at `:89` — the convention used by every production motor (`care_setting_review.py:140`, `payment_method.py:191`). **Use this.**
- `TierContext` (`@dataclass(frozen=True)`, `:66-86`):
  - `.resolved` (property, `:75-77`) = `not used_default and basamak is not None`
  - `.is_third_tier` (property, `:79-81`) = `basamak == 3`
  - `.basamak` (`:71`) = `Literal[2, 3] | None`
  - `.is_university_eah` (`:72`) — available but **not used** by this plan (Q1 resolved in favor of the broader `is_third_tier`)
- Resolvable tier literals that map to `basamak=3`: `3_basamak`, `3_basamak_resmi`, `egitim_arastirma`, `universite_devlet`, `universite_vakif` (`facility_tier.py:34-37`).
- `"devlet"` resolves to `basamak=None` / `used_default=True` (proven `test_facility_tier.py:57-60`).

### 3.2 Catalog API — `src/bilun/domain/catalog.py`
- `get_ek2c1_copay_rates() -> dict[str, dict[str, Any]]` at `:374-380`. Returns `{procedure_code: {"procedure_name": str, "copay_rate_pct": float}}`.
- Keys are **P-prefixed**: `"P552001"` … `"P552008"` (from `loaders/legacy.py:84-92`, reading the raw `procedure_code` column).
- Cached via module-global `_ek2c1_cache` (process-local, no TTL).
- **Value is a dict, NOT a float.** Must extract `float(row.get("copay_rate_pct", 0.0))`. The only existing caller does exactly this (`catalog_join.py:53`).

### 3.3 Existing motor — `src/bilun/domain/prose_rules/icu_puani.py`
- Internal var `intermediate_code` is **bare digits** (`"552003"`) — `_DEFAULT_INTERMEDIATE_CODE` at `:65`, `_claim_icu_package_code` returns stripped at `:128-133`.
- Opportunity-dict field `intermediate_package` is **P-prefixed** (`"P552003"`) — built at `:273`.
- `intermediate_puan` / `intermediate_price_try` resolved via `get_ek2c_entry(package_code)` (EK-2C entry catalog, `:102-116`) — **not** via EK-2C-1. The EK-2C-1 copay-rate path is the new wiring.
- Tier is **never read** by the current motor (grep-clean). This is net-new coupling.

### 3.4 Downstream contract (the hard external surface)
- Wrapper `claim_icu_puani.py:57-69` reads **none** of the inner opportunity fields; passes list opaquely into `IcuPuaniReview`.
- `IcuPuaniReview.confirmed_icu_try` (`billing/types.py:425-434`) sums `total_try` (fallback `recoverable_uplift_try`) gated by `included_in_sgk_total`. **This is the only numeric production read path.** It feeds `total_icu_puani` cohort counter and `sgk_uplift_try`.
- `detail`, `intermediate_puan`, `total_puan`, `intermediate_package`, `day_rate_puan` have **zero production consumers** — only unit tests read them. Rewriting `detail` and renaming/restructuring internal fields is safe.
- The `_OPPORTUNITY_TYPE` string `"icu_puani_yogun_bakim"` is never matched anywhere — also safe.

### 3.5 Tests — `tests/unit/domain/prose_rules/test_icu_puani.py`
- `_make_claim_header` factory hardcodes `facility_tier="devlet"` at `:37` → currently resolves to unresolved tier.
- 11 existing tests; none assert on tier or any ilave-oran field.
- Tests assert on `total_puan`, `total_try`, `intermediate_package`, `intermediate_days`, `rule_id`, `sut_section_id`, `included_in_sgk_total`, `recoverable_uplift_try`, `same_day_stay`, `first_day_code`, `last_day_code`, `icu_days`.

---

## 4. Implementation

### 4.1 `src/bilun/domain/prose_rules/icu_puani.py`

**Imports** (add to existing import block at `:41-48`):
```python
from src.bilun.domain.catalog import get_ek2c1_copay_rates
from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier
```

**New helper** (place after `_intermediate_package_price_try`, ~`:117`):
```python
def _resolve_ilave_oran(claim: ClaimHeader, intermediate_code: str) -> tuple[float, str]:
    """EK-2/C-1 ilave oran (%) for ICU intermediate days, gated on facility tier.

    Returns (oran_pct, reason). oran_pct is 0.0 when no uplift applies.

    Gate (SUT §2.2.(20) + EK-2/C-1): the +100% uplift applies only when the
    procedure is performed by a 3rd-basamak (Sınıf-3) facility. We resolve the
    facility tier from the claim header; if the tier is unresolved or not
    3rd-basamak, no uplift is applied (honest skip, not a default-apply).
    """
    tier = normalize_facility_tier(
        claim.facility_tier, provider_type=claim.provider_type
    )
    if not tier.resolved:
        return 0.0, "tier_unresolved"
    if not tier.is_third_tier:
        return 0.0, "not_sinif_3"
    row = get_ek2c1_copay_rates().get(f"P{intermediate_code}")
    if not row:
        return 0.0, "no_ek2c1_entry"
    oran = float(row.get("copay_rate_pct", 0.0))
    return oran, "sinif_3_uplift_applied"
```

Note: `f"P{intermediate_code}"` is load-bearing — catalog keys are P-prefixed. Using bare `intermediate_code` would silently miss (B2). `float(row.get("copay_rate_pct", 0.0))` is load-bearing — the value is a dict, not a float (B1).

**Detector changes** — in `detect_icu_puani_opportunities`, after `intermediate_code` is selected (`:224-226`) and before the puan totals (`:234`):
```python
intermediate_puan_base = _intermediate_package_puan(intermediate_code)
intermediate_price_try_base = _intermediate_package_price_try(intermediate_code)
day_rate_price_try = _day_rate_price_try()

# EK-2/C-1 ilave oran: +100% for Sınıf-3 facilities, intermediate days only.
ilave_oran_pct, ilave_oran_reason = _resolve_ilave_oran(claim, intermediate_code)
ilave_oran_eligible = ilave_oran_pct > 0
uplift_mult = 1 + ilave_oran_pct / 100
intermediate_puan = intermediate_puan_base * uplift_mult      # keeps existing key name
intermediate_price_try = intermediate_price_try_base * uplift_mult
```
Then the existing `total_puan` / `total_try` blocks (`:234-241`) work unchanged because they consume `intermediate_puan` / `intermediate_price_try`.

**Opportunity dict** — extend (`:265-287`) with:
```python
"ilave_oran_pct": ilave_oran_pct,
"ilave_oran_eligible": ilave_oran_eligible,
"ilave_oran_reason": ilave_oran_reason,
"intermediate_puan_base": intermediate_puan_base,
"intermediate_puan_uplifted": intermediate_puan,
```
Keep the existing `"intermediate_puan"` key = `intermediate_puan_base` (do **not** repoint it to the uplifted value) so any test that reads `intermediate_puan` continues to mean "base puan". (Currently no production consumer reads `intermediate_puan`, but preserving the existing semantics costs nothing and is safer.)

**Detail string** (`:256-263`) — replace the stale "Phase 2 TODO" suffix with the uplift status:
```python
if ilave_oran_eligible:
    uplift_note = (
        f"EK-2/C-1 ilave oran +{ilave_oran_pct:.0f}% applied to intermediate "
        f"days (Sınıf-3 facility)."
    )
else:
    uplift_note = (
        f"No EK-2/C-1 ilave oran ({ilave_oran_reason})."
    )
detail = " ".join(["ICU dual-charge (§2.4.4.H):", *charge_lines, uplift_note])
```

**Docstring** — delete the Phase-2 TODO block at `:28-31`. Update the module docstring header comment at `:2-4` ("Phase 1: base puan only…") to reflect that the uplift is now implemented.

### 4.2 `tests/unit/domain/prose_rules/test_icu_puani.py`

**Fixture change** — `_make_claim_header` (`:37`): `facility_tier="devlet"` → `facility_tier="3_basamak"`. This makes the 9 existing detector tests exercise the resolved-Sınıf-3 path (uplift applies).

**Existing-test re-assertions** — the 3 multi-day detector tests (`test_3day_icu_stay_dual_charge`, and any other test with `intermediate_days > 0`) currently assert `total_puan`/`total_try` computed with base intermediate puan. Under `"3_basamak"`, the intermediate term doubles. Recompute and update those assertions. Single-day and 2-day stays (0 intermediate days) are unaffected — verify but no change expected.

**New tests** (3):
1. `test_ilave_oran_applied_sinif_3` — explicit `"3_basamak"`, 3-day stay. Assert: `ilave_oran_pct == 100.0`, `ilave_oran_eligible is True`, `ilave_oran_reason == "sinif_3_uplift_applied"`, `intermediate_puan_uplifted == intermediate_puan_base * 2`, `total_puan` reflects uplift, `total_try` reflects uplift.
2. `test_no_uplift_2nd_basamak` — `"2_basamak_kamu"`, 3-day stay. Assert: `ilave_oran_pct == 0.0`, `ilave_oran_eligible is False`, `ilave_oran_reason == "not_sinif_3"`, `total_puan` == base (no uplift), `total_try` == base.
3. `test_no_uplift_unresolved_tier` — `"devlet"`, 3-day stay. Assert: `ilave_oran_pct == 0.0`, `ilave_oran_reason == "tier_unresolved"`, totals == base. (This restores the coverage the old default fixture gave away.)

---

## 5. Verification

- `pytest tests/unit/domain/prose_rules/test_icu_puani.py -v` — all 11 + 3 new pass.
- `pytest tests/unit/domain/billing/` — `test_claim_integration.py` and `test_orchestrator_grand_total.py` read only `confirmed_icu_try` (scalar from `total_try`); verify they still pass (the uplift legitimately increases `total_try` for Sınıf-3 claims — if these tests construct Sınıf-3 ICU claims, their asserted totals may need updating; check first).
- Grep for any other test that constructs an ICU claim via `_make_claim_header` and asserts on a total — update if tier is now resolved where it wasn't.
- Causation check (per lessons.md 2026-06-30): if any pre-existing test fails after the change, `git stash` the changed files and re-run to classify as pre-existing vs. caused.

---

## 6. Out of scope

- **e-nabız +60 TL/day** (§2.4.4.H.(10)) — needs a data-submission signal not on `ClaimHeader`.
- **§2.2.2.B.(5) +30% star-rule disabling** — no other motor touches P55200x today (grep-clean), so no double-count risk. Document as an inline TODO in the motor.
- **Exact EK-2/A-1 facility classification** (U1/U2/A1/A2 codes) — `TierContext.is_third_tier` is the available proxy from `ClaimHeader`.
- **Historical +60% rate reconciliation** — stale, dropped deliberately; documented in §2.
- **Frontend/UI** — backend-only task. The IA-v2 plan covers display.

---

## 7. Risk register

| Risk | Mitigation |
|---|---|
| Silent no-op if catalog key format mismatches | B2 fix: `f"P{intermediate_code}"`. Test `test_ilave_oran_applied_sinif_3` would catch a miss (asserts `oran == 100`). |
| `TypeError` if oran treated as dict | B1 fix: extract `.get("copay_rate_pct", 0.0)` + `float(...)`. |
| Existing tests silently change behavior (now Sınıf-3) | S6 fixture change is deliberate; re-assert the 3 multi-day tests. Single/2-day tests unaffected (0 intermediate). |
| `confirmed_icu_try` inflates for Sınıf-3 claims in integration tests | §5 verification checks `test_claim_integration.py`; update asserted totals if it constructs Sınıf-3 ICU claims. |
| Over-applying to non-university 3rd-basamak özel | Q1 resolved: regulation explicitly says "3. basamak sağlık hizmeti sunucularınca" — over-application is correct, not a bug. |
