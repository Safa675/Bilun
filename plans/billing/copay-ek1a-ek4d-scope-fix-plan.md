## Task: Copay exemption scope — EK-1A ≠ blanket drug waiver (§1.8.5(7) vs §1.8.5(8) / EK-4/D)

**Status:** Draft (reviewed)  
**Priority:** P0 (correctness + CI fixtures) + P1 (UI attribution)  
**Trigger:** `F-SENTETIK-HASTA-0039-104` (C83.1 günübirlik) — UI shows **EK-1A** + **EK-4D** rule chips but **₺442,76 reçete muafiyet farkı** is computed via `is_exempt` blanket on all drug lines; drugs (KADCYLA, MODIOGEN, …) are not individually listed in EK-4/D curated parquet.

**Related plans:**

- `copay-exemption-coverage.md` — composable patient/visit exemptions (patient-level `exemption_sources[]`).
- `billing_bugfixes.md` — totals split (`total_copay_savings_try` = procedure-only). **This plan supersedes** `billing_bugfixes.md` line 34 (“copay exemptions stay as-is”) for **line-level waiver application**; EK-1A matching logic in `ek1a.py` stays, but **how savings attach to lines** changes.

---

## Goal

1. **`optimize_copay_from_claims()`** applies each SUT copay waiver ground to the **service types and annex scopes** the tebliğ defines — not a single `exempt` boolean over all lines.
2. **Reçete muafiyet farkı** attributed to the correct rule (`§1.8.5(8)` yatarak/günübirlik ilaç, `§1.8.2(3)`+EK-4/D, composite visit rules, etc.).
3. **UI / billing report** shows per-line corrections for drugs when savings are asserted.
4. **CI-enforceable fixtures** — inline builder mirroring 0039-104 amounts (**required for P0 merge**, not post-merge golden).

**Out of scope (defer):**

- EK-4/D `*` broad category → ATC / antineoplastik class matching (separate plan).
- Line-level `yatarak_tedavi_ilac` flag in synthetic/HIS (until then: **claim-type proxy** for §1.8.5(8)(b) — see Resolved defaults).
- MEDULA `katilimPayindanMuaf=E` DTO simulation beyond savings attribution text.

---

## Root cause (verified)

### SUT text (`sut_clauses.parquet`)

| Clause | Scope | What is waived |
|--------|--------|----------------|
| **§1.8.5(7)** + **EK-1/A** | Kronik hastalık + sağlık raporu | **§1.8.1** on **ayaktan uzmanlık muayeneleri** for that chronic disease |
| **§1.8.5(8)** | — | **§1.8.2** not taken: tetkik/tanı ilaçları; **yatarak tedavide** ilaçlar; EK-4/D + rapor |
| **§1.8.2(3)** + **EK-4/D** | Bölüm ICD + listed drug name | §1.8.2 rates do not apply |

**EK-1/A does not waive all drug copays** because the patient has C83.

### Code bug — `claim_copay.py`

```python
# Procedure: if is_exempt → every copay_rate_applicable line
# Drug: if is_exempt → every drug line; continue (skips EK-4/D + rate_corrections)
```

**0039-104 (cache spot-check):**

| Field | Current | After P0 (expected) |
|-------|---------|---------------------|
| `visit_copay_savings_try` | 26,67 (muayene + 2 labs) | **13,21** (703720 muayene only; labs excluded) |
| `rx_copay_savings_try` | 442,76 (EK-1A blanket) | **442,76** ground = `inpatient_drug_1_8_5_8` |
| `rate_corrections` | 3 procedure, 0 drug | 1 procedure + **4 drug** rows |

Drug line amounts (billed − payable): ROLASTYM 58,70; MODIOGEN 218,43; KADCYLA 14,30; ZINCOPLEX 151,33.

---

## Architecture principles

1. **Ground-specific applicators** in `copay_line_waivers.py`; orchestrator merges results.
2. **`exempt` (patient-level) ≠ line waiver** — cohort/alerts keep `exempt`; savings use per-line grounds.
3. **`waives_sections` tuple** on every `exemption_sources[]` entry (P0, not P1) — applicators derive scope from sections, not hard-coded `category` strings.
4. **Per-line claim context** — lines carry `claim_id` only; resolve `ClaimHeader` via `claim_by_id` map (P0.0).
5. **Line eligibility** — procedure waivers require `copay_rate_applicable` **and** category/ground rules (matrix below).
6. **Conservative when uncertain** — missing health report → partial, no savings (existing pattern).

---

## Target behavior matrix

**Procedure line filter (all grounds):** `line.copay_rate_applicable` **and** ground-specific `procedure_category` / visit rules.

| Line type | EK-1A (§1.8.5(7)) | §1.8.5(8) yatarak ilaç | EK-4/D (§1.8.2(3)) |
|-----------|---------------------|-------------------------|---------------------|
| `muayene` (poliklinik, related specialty) | ✅ EK-1A + report | — | — |
| `muayene` (gunubirlik/yatis) | ❌ P0: no savings (ayaktan only)* | — | — |
| `laboratuvar` / `islem` / `yatak` | ❌ | — | — |
| `drug` on `yatis` / `gunubirlik` | ❌ | ✅ §1.8.5(8)(b) claim-type proxy** | ✅ if listed + report (else skipped if inpatient ground already applied) |
| `drug` on `poliklinik` / `acil` | ❌ | ❌ | ✅ if listed + report |
| `material` | ❌ | — | — |

\* Resolved default: strict exclude günübirlik muayene from EK-1A until legal review flag.  
\** Resolved default: **all drugs on `yatis`/`gunubirlik` claims** → §1.8.5(8)(b). Matches onkoloji günübirlik practice (trigger case). Proxy until `yatarak_tedavi_ilac` exists on `DrugClaimLine` / synthetic ingest.

### Procedure waivers and `claim_type`

- **Composite visit rules** (acil, koruyucu, iş kazası): read **`claim_by_id[line.claim_id].claim_type`** (and procedure codes on that claim) — visit-scoped, not patient-level-only.
- **EK-1A:** same per-line `claim.claim_type`; only `poliklinik` muayene lines qualify in P0.
- Patient-level `exemption_sources[]` supplies **evidence** (EK-1A qualifying ICD); **applicability** is still per-line + per-claim-type.

---

## Phase P0 — Applicators, metadata, tests (merge gate)

### P0.0 — Claim header index

At start of `optimize_copay_from_claims()`:

```python
claim_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in ctx.claims}
```

Pass `claim_by_id` into every applicator. Lines without a header → skip waiver with debug detail (should not happen on exact claims).

### P0.1 — `waives_sections` on compositor (minimal, now)

Add to `exemption_sources` in **`ek1a.py`**, **`visit_type.py`**, **`occupational.py`**, **`patient_status.py`** (as applicable):

| Source | `waives_sections` |
|--------|-------------------|
| `ek1a_chronic` | `("1.8.1",)` |
| `acil_servis`, `koruyucu`, `is_kazasi`, … | `("1.8.1", "1.8.2", "1.8.3")` |
| EK-4/D (inline in applicator, not compositor) | `("1.8.2",)` |
| §1.8.5(8)(b) inpatient drugs (inline) | `("1.8.2",)` |

**Single schema:** `waives_sections` only — no parallel `waives_drug_copay` flag. Applicators use:

```python
def _waives(section: str, sources: list[dict]) -> bool:
    return any(section in (s.get("waives_sections") or ()) for s in sources)
```

Composite drug waiver: `_waives("1.8.2", sources)` from visit/occupational entries.

### P0.2 — `copay_line_waivers.py`

```python
def waiver_ek1a_muayene(line, claim, ek1a_evidence) -> WaiverResult | None
def waiver_inpatient_drug(line, claim) -> WaiverResult | None           # §1.8.5(8)(b)
def waiver_ek4d_drug(line, claim, diagnoses, has_health_report) -> WaiverResult | None
def waiver_composite_procedure(line, claim, sources) -> WaiverResult | None
def waiver_composite_drug(line, claim, sources) -> WaiverResult | None
```

`WaiverResult`: `component_try`, `exemption_ground`, `sut_section_id`, `rule_id`, `annex`, `detail`, plus fields for `rate_corrections` row.

### P0.3 — EK-1A procedure applicator

- Require: `copay_rate_applicable`, `procedure_category == "muayene"`, `claim.claim_type == "poliklinik"`, EK-1A evidence + `has_chronic_health_report is True`.
- **Not** labs/islem/yatak even if `copay_rate_applicable`.

### P0.4 — Drug applicator order (per line)

1. `waiver_composite_drug` if `_waives("1.8.2", sources)`.
2. `waiver_inpatient_drug` if `claim.claim_type in ("yatis", "gunubirlik")`.
3. `waiver_ek4d_drug` — **always evaluate**; append `rate_corrections` on match (proves `continue` removal).
4. Else no waiver.

**Remove:** `if is_exempt: rx_savings += component; continue`.

### P0.5 — Procedure applicator order (per line)

1. `waiver_composite_procedure` if `_waives("1.8.1", sources)` — uses **line’s claim** `claim_type` + visit rule constraints (e.g. acil 520021 exclusion).
2. `waiver_ek1a_muayene` if EK-1A source present.
3. Else no waiver.

### P0.6 — Totals + serialization

| Field | Definition |
|-------|------------|
| `visit_copay_savings_try` | Sum procedure waivers |
| `rx_copay_savings_try` | Sum drug waivers |
| `patient_copay_waived_total_try` | visit + rx |
| `total_copay_savings_try` | visit only (legacy) |
| `rx_copay_savings_by_ground` | `dict[str, float]` — **required** |

**API / cache path (must update in P0):**

```
CopayOptimization (types.py)
  → patient_report.py / orchestrator
  → cache payloads (billing_reports JSON)
  → GET /api/billing-report/{patient_id} (+ bill-scoped)
  → frontend/src/lib/domains/sut.ts (CopayOptimization type)
  → SutBillingReportSections.tsx
```

### P0.7 — Tests (**merge gate**)

**File:** `tests/unit/domain/billing/test_claim_copay_scope.py`

| Test | Assert |
|------|--------|
| `test_sentetik_0039_104_equivalent` | Inline `PatientClaimContext` builder with frozen amounts above; `visit_copay_savings_try == 13.21`; `rx == 442.76`; 1 proc + 4 drug `rate_corrections`; drug rows have `exemption_ground == "inpatient_drug_1_8_5_8"` |
| `test_ek1a_excludes_labs` | EK-1A + lab line → no visit savings |
| `test_exempt_true_ek4d_poliklinik_drug` | `exempt=True` (EK-1A patient) + poliklinik + Morfozinamid + A16 → EK-4/D row emitted, `rx` from ek4d ground |
| `test_gunubirlik_drugs_inpatient_ground` | 4 drugs on gunubirlik → inpatient ground, not ek1a |

Keep `tests/unit/domain/drugs/test_ek4d_exempt.py` green.

**No dependency on live `data/synthetic/` claim id** — amounts from cache spot-check (Jun 2026).

### P0 acceptance (CI)

- [ ] All `test_claim_copay_scope.py` tests pass.
- [ ] `test_ek4d_exempt.py` unchanged behavior for `exempt=False`.
- [ ] `rx_copay_savings_by_ground` present in API JSON for billing-report endpoint.
- [ ] No drug savings attributed to `ek1a_chronic` ground.

---

## Phase P1 — UI attribution (claim-scoped vs patient-scoped)

### P1.1 — Billing copay section (claim / report scoped)

- `rule_source` / chips derived from **this report’s** `rate_corrections` grounds and `rx_copay_savings_by_ground`.
- Show §1.8.5(8) when inpatient drug ground > 0; EK-4/D only when ek4d ground > 0; EK-1A chip on copay block only when ek1a muayene savings > 0.

### P1.2 — Patient exemption chips (cohort-scoped) — **do not conflate**

`PatientExemptionRuleSourceAttribution` / optimizer may still show **EK-1A** because the **patient** qualifies (C83 in EK-1A list). That is legally fine and distinct from **which lines** received waiver on a given claim.

Document in UI:

- **Patient / kohort:** “Bu hasta EK-1A kapsamında değerlendirilebilir.”
- **Fatura / katılım payı incelemesi:** “Bu faturada muafiyet farkı şu satır ve gerekçelerle hesaplandı.”

P2 footnote (`copay.ek1aScopeNotice`) clarifies; no requirement to hide patient-level EK-1A when claim drugs use §1.8.5(8) only.

### P1.3 — Copay table

- Column **“Muafiyet gerekçesi”** from `rate_corrections[].exemption_ground`.
- Drug rows in table when savings asserted (P0).

### P1.4 — i18n

`tr/billing.ts` + `en`: `copay.ek1aScopeNotice`, `copay.inpatientDrugWaiverNotice`, `copay.patientVsClaimExemptionNotice`, `copay.groundLabels.*`.

---

## Phase P2 — Docs & cache

- `docs/core-system/algorithms_reference.md` §3.2 — narrow EK-1A; §1.8.5(8) claim-type proxy; patient vs claim chips.
- `src/bilun/domain/billing/README.md` — same.
- `billing_bugfixes.md` — add cross-link: line-level copay superseded by this plan.
- Rebuild cache; manual spot-check 0039-104.

---

## Files to touch

| Area | Path |
|------|------|
| Orchestrator | `src/bilun/domain/billing/claim_copay.py` |
| Applicators | `src/bilun/domain/billing/copay_line_waivers.py` (new) |
| Compositor | `src/bilun/domain/optimization/copay_exemption_rules/ek1a.py`, `visit_type.py`, … |
| Types | `src/bilun/domain/billing/types.py` |
| Cache/API | `src/bilun/cache/payloads.py` (if needed), billing report routes |
| Frontend types | `frontend/src/lib/domains/sut.ts` |
| UI | `frontend/src/components/patient/SutBillingReportSections.tsx` |
| Tests | `tests/unit/domain/billing/test_claim_copay_scope.py` (**required**) |
| Docs | `docs/core-system/algorithms_reference.md`, `billing_bugfixes.md` |

---

## Implementation order

1. **P0.0–P0.6** + **`test_sentetik_0039_104_equivalent`** (merge gate).  
2. **P0 API serialization** + TypeScript types.  
3. **P1** UI / footnotes.  
4. **P2** docs + cache rebuild.

---

## Resolved defaults (was open questions)

| # | Decision |
|---|----------|
| 1 Günübirlik muayene + EK-1A | **Exclude** from EK-1A savings in P0 (ayaktan only). |
| 2 §1.8.5(8)(b) on gunubirlik | **All drugs** on `yatis`/`gunubirlik` claims — claim-type proxy until `yatarak_tedavi_ilac` line flag. Document in code comment + algorithms_reference. |
| 3 Specialty match | **Warn-only** if `procedure_specialty_code` empty; do not block muayene savings in P0. |

---

## Manual test plan

1. `pytest tests/unit/domain/billing/test_claim_copay_scope.py -q`  
2. Open `SENTETIK-HASTA-0039` → `…-104`: visit **₺13,21**; rx **₺442,76**; **4 drug rows**; ground labels not EK-1A for drugs.  
3. Patient optimizer still shows EK-1A eligibility; billing copay section shows §1.8.5(8) for drugs.  
4. Poliklinik + `exempt=True` + EK-4/D drug: table shows EK-4/D row (unit test).
