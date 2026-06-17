## Task: Payment-method compliance — clean synthetic claims + legal itemized totals

**Status:** Draft (reviewed)  
**Priority:** P0 (generator) + P1 (strategy)  
**Trigger:** Historical repro `F-SENTETIK-HASTA-0038-096` (build `d5fe24b`) — `P615440` paket + `612070` (`DRG_MANDATORY`, kalem yazılmış) aynı faturada; kalem toplamı ihlalli satırı içeriyor.

### Goal

1. **Sentetik demo faturaları** paketli yatışlarda kazara §2.2.2 ödeme-yöntemi ihlali üretmesin (çoğu fatura temiz olsun).
2. **Fatura stratejisi `itemized_total_try` / `itemized_raw_try`** yalnızca *yasal kalem alternatifi* satırlarını saysın; `compliance_violation` satırları dahil edilmesin.

**Out of scope (P2, ayrı plan):** otomatik fatura ayırıcı (“bill separator”) ürün önerisi.

---

## Root cause (verified)

### Repro fixture (frozen math — not tied to live claim id)

> **Note:** `F-SENTETIK-HASTA-0038-096` is **not** in current parquets (patient 0038 now has `-099` / `-100`). Keep the amounts below as a **unit-test fixture**; pin the compliance demo to a **stable cohort patient index**, not a fixed `claim_id`.

| Kod | Kategori | Faturalanan | Beklenen | Strateji |
|-----|----------|-------------|----------|----------|
| P615440 | paket | 103.260,58 | 61.956,35 | paket toplamı |
| 612070 | yatak | 2.337,01 | 2.337,01 | **compliance_violation** (`DRG_MANDATORY`, kalem) |
| G100580 | islem | 1.848,56 | 1.848,56 | kalem alternatifine dahil |
| L116470 | laboratuvar | 107,55 | 107,55 | dahil |
| 700390 | muayene | 17,11 | 17,11 | dahil |

**Kalem toplamı bugün (yanlış):**

```text
Ham:     17,11 + 2337,01 + 107,55 + 1848,56 = 4310,23
Seans:   G100580 %100 + diğerleri %30 → 3512,26
```

612070 ihlalli olduğu halde kalem toplamına giriyor.

**After P1 (expected):**

```text
Eligible: 700390, L116470, G100580  (612070 excluded)
Ham:      17,11 + 107,55 + 1848,56 = 1973,22
Seans:    1848,56 + 554,57 + 554,57 = 2957,70
```

### Generator gap — `scripts/synthetic/generators.py`

`_pick_procedures()` (≈369–479):

- `ek2c_all_codes` yalnızca `P#####` paket kodlarını `general` havuzundan çıkarıyor.
- **Muayene, yatak, lab** havuzları filtrelenmiyor.
- `612070` EK-2B’de `yatak` havuzunda; `resolve_payment_method` → `DRG_MANDATORY` at tier 2.
- Sonuç: paket satırı olan yatışa rastgele **başka bir DRG_MANDATORY** işlem düşebiliyor.

### Strategy gap — `src/bilun/domain/billing/claim_strategy.py`

- `check_payment_method_compliance()` ihlali ayrı satır olarak yazar (`type: compliance_violation`).
- `compute_session_adjusted_itemized_total()` tüm paket-dışı, `expected_payable > 0` satırları toplar — ihlal ayrımı yok.

### Parquet vs runtime

- Claim header stores `package_candidate` as `paket_adayi_mi` in parquet; strategy runs on runtime `PatientClaimContext`.
- **Validator and generator rules key off a billed `paket` line** (`procedure_category == paket`, `billed_amount_try > 0`), not `package_candidate` alone.

---

## Architecture principles

1. **Tek ödeme-yöntemi motoru:** `prose_rules/payment_method.py` — filter, validator, and strategy all call `resolve_payment_method` / `check_payment_method_compliance` with **`care_setting`, `facility_tier`, `provider_type`, `as_of_date`**.
2. **Filter ≡ validator criterion:** exclude side procedures only when `kind == DRG_MANDATORY` for that claim’s tier and service date — **not** the whole EK-2C membership set (tier-3 `DRG_OVERRIDABLE` codes may legally be itemized).
3. **İhlal = veri hatası (demo) veya ayrı senaryo** — kalem alternatifine dahil edilmez.
4. **Bilinçli demo ihlalleri** `scenario_tag = payment_method_compliance_demo`; validator skips only those claims.

---

## Phase P0 — Synthetic generator: no accidental DRG_MANDATORY mix-ins

### P0.1 — Shared exclusion helper (tier-aware)

- [ ] Add `scripts/synthetic/payment_method_sampling.py` (or module under `generators.py`):
  - `is_mandatory_package_side_procedure(code, *, care_setting, facility_tier, provider_type, as_of_date) -> bool`
    - Thin wrapper: `resolve_payment_method(...).kind == DRG_MANDATORY`.
  - `filter_ek2b_pool_for_packaged_claim(df, *, care_setting, facility_tier, provider_type, as_of_date, allow_mandatory_side_procs: bool) -> DataFrame`
    - When `allow_mandatory_side_procs=False`: drop rows whose `code` maps to `DRG_MANDATORY` (per-row or vectorized precompute for pool codes).
    - When `True`: no filter (**compliance demo only**).
- [ ] **Do not** filter on full `get_ek2c_codes_as_of()` — that blocks valid tier-3 `DRG_OVERRIDABLE` synthetic scenarios.

### P0.2 — Apply filter to all procedure pools when billed package present

In `_pick_procedures()` when a `package_code` will be appended and **not** `payment_method_compliance_demo`:

- [ ] Pass claim/episode `facility_tier`, `provider_type`, `care_setting` (`yatis` / `gunubirlik`), and service date into the filter.
- [ ] Filter **`muayene`, `yatak`, `lab`, `general`** pools before `sample()`.
- [ ] Keep existing `P#####` exclusion on `general` (harmless duplicate guard).
- [ ] Do **not** filter the billed `paket` line itself.

**Note:** `612070` repro came from **yatak** pool — filtering only `general` is insufficient.

### P0.3 — Intentional compliance demo scenario

- [ ] Add `PAYMENT_METHOD_COMPLIANCE_DEMO_PATIENTS` map (mirror `DRUG_INDICATION_DEMO_PATIENTS` in `validate_sut_synthetic_data.py`):
  - `scenario_tag`: `payment_method_compliance_demo`
  - **Pin to stable cohort patient index** (e.g. patient slot `0038`), not a fixed `F-SENTETIK-HASTA-0038-096` id.
  - Builder emits:
    - One billed `paket` line (`P#####`)
    - One `DRG_MANDATORY` procedure billed as non-`paket` (e.g. `612070` as `yatak` or `islem`)
  - `allow_mandatory_side_procs=True` only on this builder path.
- [ ] At most **1–2** cohort patients carry this tag.

### P0.4 — Post-generate validator (aligned with filter)

Extend `scripts/synthetic/validate_sut_synthetic_data.py`:

- [ ] For each claim with a **billed `paket` line** (`procedure_category == paket`, `billed_amount_try > 0`):
  - Unless `scenario_tag == payment_method_compliance_demo`:
    - For each **other** procedure line, **skip** if:
      - `is_package_included == True`, or
      - `expected_payable_try == 0` (same as strategy eligibility).
    - Assert remaining lines are **not** non-compliant `DRG_MANDATORY` side procedures:
      - `procedure_category != paket` **and**
      - `resolve_payment_method(..., facility_tier from claim header, as_of_date from line/claim).kind == DRG_MANDATORY` **and**
      - billed as non-package (`procedure_category != paket`).
- [ ] Fail build with `claim_id` + offending codes.

### P0.5 — Regenerate & cache

- [ ] `python scripts/synthetic/generate_sut_synthetic_data_v2.py` (canonical regen entrypoint)
- [ ] Validator green on new parquets.
- [ ] Spot-check: untagged package claims have **0** accidental mandatory side violations.
- [ ] Rebuild analytics cache; document that claim suffixes may change if seed shifts — demo located by `scenario_tag` + patient index.

### P0 acceptance

| Check | Target |
|-------|--------|
| Untagged claims with billed paket + non-compliant `DRG_MANDATORY` side line | **0** |
| Tagged `payment_method_compliance_demo` claims | **≥ 1** |
| Tier-3 claims can still include `DRG_OVERRIDABLE` EK-2C codes as itemized sides | preserved |
| One billed `paket` line per yatış (existing invariant) | preserved |

---

## Phase P1 — Strategy: legal-only itemized totals

### P1.1 — Shared eligibility helper (export for reuse)

- [ ] Add `lines_for_legal_itemized_alternative(lines, claim) -> list[ProcedureClaimLine]` in `claim_strategy.py` (or `prose_rules/payment_method.py` if preferred single home):
  - Base filters (unchanged): `category != paket`, `not is_package_included`, `_line_itemized_payable(line) > 0`.
  - **Exclude** lines where `check_payment_method_compliance(..., billed_as_package=(category == paket)).is_compliant is False`.
  - Same `care_setting`, `facility_tier`, `provider_type`, `as_of_date` as compliance rows.

### P1.2 — Wire into claim-level strategy row

In `recommend_billing_strategy_from_claims()` for each `package_candidate` claim:

- [ ] `eligible = lines_for_legal_itemized_alternative(claim_procs, claim)`
- [ ] **`itemized_raw_try`** = sum `expected_payable_try` on `eligible` only.
- [ ] **`itemized_total_try`** = `compute_session_adjusted_itemized_total(eligible, ...)` only.
- [ ] **Both fields must move together** — do not update `itemized_total_try` without `itemized_raw_try` (API consumers compare raw vs session-adjusted).
- [ ] Metadata on recommendation row:
  - `itemized_excluded_violation_count: int`
  - `itemized_excluded_procedure_codes: list[str]` (stable sort; cap 10 in API if needed)
  - `itemized_price_methodology` unchanged (`session_adjusted`).

### P1.3 — Align other itemized call sites

- [ ] **`claim_drg_uplift.py`** — use `lines_for_legal_itemized_alternative` before `compute_session_adjusted_itemized_total`.
- [ ] **`prose_rules/care_setting_review.py`** (optional but recommended) — same pattern; avoids inconsistent alternate totals in care-setting review.

### P1.4 — Frontend copy (optional, small)

- [ ] `frontend/src/messages/tr/billing.ts` — footnote: kalem toplamı ödeme-yöntemi ihlali satırlarını içermez.
- [ ] EN mirror in `en/billing.ts`.

### P1 regression fixture (inline builders — not live claim id)

| Field | Before | After |
|-------|--------|-------|
| `itemized_raw_try` | 4310,23 | **1973,22** |
| `itemized_total_try` | 3512,26 | **2957,70** |
| `package_total_try` | 61956,35 | unchanged |
| `compliance_violation` rows | 612070 | unchanged |

### P1 acceptance

- [ ] `test_claim_strategy_sut.py`: violating side line → excluded from **both** `itemized_raw_try` and `itemized_total_try`.
- [ ] `test_claim_strategy_sut.py`: compliant package claim → totals unchanged.
- [ ] `test_claim_strategy_sut.py`: tier-3 `DRG_OVERRIDABLE` side line on package claim → still included in itemized totals.
- [ ] Golden fixture test using frozen five-line amounts from repro table above.

---

## Phase P2 — Bill separator (deferred)

Separate plan: `claim_partition_recommendation` for incompatible mixes; no parquet mutation.

---

## Files to touch

| Area | Path |
|------|------|
| Generator | `scripts/synthetic/generators.py` (`_pick_procedures`) |
| Sampling helper | `scripts/synthetic/payment_method_sampling.py` (new) |
| Validator | `scripts/synthetic/validate_sut_synthetic_data.py` |
| Regen | `scripts/synthetic/generate_sut_synthetic_data_v2.py` |
| Strategy | `src/bilun/domain/billing/claim_strategy.py` |
| DRG uplift | `src/bilun/domain/billing/claim_drg_uplift.py` |
| Care setting (optional) | `src/bilun/domain/prose_rules/care_setting_review.py` |
| Tests | `tests/unit/domain/billing/test_claim_strategy_sut.py`, `tests/unit/scripts/test_synthetic_*` |
| Docs | `docs/core-system/algorithms_reference.md` §3.4 |
| i18n | `frontend/src/messages/tr/billing.ts`, `en/billing.ts` |

---

## Test plan (manual)

1. After regen, open cohort patient pinned for `payment_method_compliance_demo` (by tag, not `-096` suffix).
2. Untagged package inpatient claims: no random payment-method violations.
3. Tagged demo claim: violation visible; **both** kalem columns exclude violating code.
4. Tier-3 hospital claim (if present in cohort): non-star EK-2C side procedure may appear as itemized — not filtered by P0.
5. DRG kalemlendirilmiş (`billed_amount_try` sum) unchanged.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Over-filtering blocks tier-3 override demos | Filter on `DRG_MANDATORY` only, not all EK-2C members |
| Demo patient / claim ids shift on regen | Pin by patient index + `scenario_tag`; tests use inline fixture |
| Raw vs adjusted mismatch | P1.2 updates `itemized_raw_try` and `itemized_total_try` in same pass |
| Validator noise on paket-içi lines | Skip `is_package_included` and `expected_payable_try == 0` |

---

## Review log (incorporated)

| Issue | Fix in plan |
|-------|-------------|
| P0 filter vs validator: full EK-2C vs `DRG_MANDATORY` | Tier-aware `resolve_payment_method`; filter ≡ validator |
| Repro claim stale | Fixture math retained; demo pinned by patient index |
| Wrong symbol names | `_pick_procedures()`, `generate_sut_synthetic_data_v2.py` |
| `itemized_raw_try` consistency | P1.2 explicit dual update |
| P1.3 scope | `claim_drg_uplift.py` + optional `care_setting_review.py` |
| Validator included lines | Skip `is_package_included` / zero payable |
| `package_candidate` vs billed paket | Validator keys off billed paket line |

---

## Done when

- [ ] P0 validator green after `generate_sut_synthetic_data_v2.py`
- [ ] P1 unit tests green (including tier-3 override case)
- [ ] `pytest tests/unit/domain/billing/test_claim_strategy_sut.py tests/unit/scripts/ -q` passes
- [ ] No untagged billed-paket claims with non-compliant `DRG_MANDATORY` side lines
