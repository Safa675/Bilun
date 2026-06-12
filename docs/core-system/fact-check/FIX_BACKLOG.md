# SUT Fact-Check — Fix Backlog

**Status:** Updated from Phase 1 Gate C/F findings  
**Authority:** Fix WRONG/UNSOURCED immediately per plan §14

---

## P0 — Fix first (legal / false-positive risk)

| ID | Issue | Status |
|----|-------|--------|
| **P0.2-primary** | Primary procedure = highest EK-2/C **puan** | **Done** — `session_pricing._procedure_point_score` |
| **L3.1-dup** | Clinical review, `savings_try: null`, updated `rule_source` | **Done** — `clinical_review_duplicate` flag type |
| **L3.1-dup-unknown** | No global `"unknown"` bucket | **Done** — skip dup when encounter unknown |
| **P0.4-same_incision** | Explicit `same_incision` param; skip session when `None` | **Done** — cohort passes `True` until kesi on claims |

---

## P1 — Phase 2 findings (fix wave — 2026-06-02)

| ID | Issue | Status |
|----|-------|--------|
| **P0.3-ivf** | `resolve_ivf_drug_copay_rate` 5%/10% vs §1.8.4(1) 30/25/20% | **Done** — `resolve_ivf_treatment_copay_rate` + JSON |
| **P0.3-material** | Material rate cites §1.8.3(1).a not §1.8.3(2) | **Done** — JSON `1.8.3.(2)` + `resolve_material_copay_rate` |
| **L2.1** | `rule_source` cites SUT 1.8.1; registry uses 1.8.5 | **Done** — §1.8.5(7) + EK-1/A |
| **L2.1** | No health-report gate per §1.8.5(7) | **Done** — `has_chronic_health_report`, `partial_exempt` |
| **L2.2** | Acil waiver ignores 520.021 carve-out §1.8.5(5) | **Done** — block when only `520021` on claim |
| **L2.2** | `kanun_2022_65` — no §1.8 clause in docx | **Done** — HEURISTIC, `counts_toward_exempt: false` |
| **L2.2** | Status `rule_source` strings unsourced | **Done** — §1.8.5 citations per category |
| **L3.3** | Exempt savings inherit L2 gaps | **Done** — savings gated on `exempt`; partial EK-1A note |
| **L3.3** | Material §1.8.3 rates not on claim path | **Done** — rate reference on material lines |
| **L3.5** | Bundled materials flagged as MIAT | **Done** — `bundled_separate_billing` list |
| **L3.6** | `grand_total_recoverable` sums non-exact block savings | **Done** — sum `total_recoverable_try`; gate category totals |
| **L1.3** | No unit tests for `validate_claim()` | **Done** — `test_rule_engine_validate_claim.py` |

### Sprint A (2026-06-02) — Done

| ID | Issue | Status |
|----|-------|--------|
| **P0.1** | `as_of_date` unwired in payment method + catalog | **Done** — temporal `catalog_membership`; claim dates in `claim_strategy` |
| **P0.1** | Prose-locked EK-2/C codes | **Done** — `ek2c_prose_drg_locked_seed.py` + `procedure_prose_drg_locked()` |
| **P0.1** | Jan/Jul MEDULA tercih dönemi | **OUT_OF_SCOPE** — admin preference; closed 2026-06-04 |
| **P0.2** | EK-2/B-only multi-procedure §2.2.2.A(5) | **Done** — verified 2026-06-04 |
| **L3.4-ui** | Provisional strategy badges | **Done** — catalog-as-of footnote on claim-level rows |
| **L3.2** | Heuristic drug savings / doc drift | **Done** — `savings_basis: heuristic`; UI chip + `algorithms_reference` |

### Sprint B (2026-06-02) — Done

| ID | Issue | Status |
|----|-------|--------|
| **L1.1** | Name-fuzzy only; code unused | **Done** — code→name→bundled; fuzzy → warning |
| **L1.2** | Docs 15 vs 13 rows | **Done** — docs + code match |
| **L3.5** | MIAT interval | **Done** — `miat_interval_violations` on claim history |
| **L4.2** | Chapter median DRG | **Done** — `ek2c_code` first; UI heuristic notice |
| **L4.3** | EK-2A global mean | **Done** — `lookup_ek2a_visit_price_try` |

### Sprint D (2026-06-02) — Done

| ID | Issue | Status |
|----|-------|--------|
| **L4.1×L3.1** | Lab prices without service date | **Done** — `get_all_lab_prices(visit_date=…)` per test/encounter |
| **P0.4** | Package-included + itemized uplift heuristic | **Done** — `heuristic_savings_try`, UI footnote |
| **L3.4** | Override path vs mandatory | **Done** — `overrideScopeNotice` + clearer i18n |

### Phase 1 remainder (2026-06-02) — Done

| ID | Issue | Status |
|----|-------|--------|
| **P0.2** | §2.2.2.A(5), EK-2/B multi-procedure, mixed EK-2/B-primary fallback | **Done** — `session_pricing.py`; `cross_specialty` param (+25pp) |
| **L2.6** | Unused `patient_icd10_chapters` | **Done** — returned on `detect_drg_unbundling`; `n_chapters_analyzed` union |

### P0 tests (Phase 1)

- [x] `test_drg_unbundling.py` — session primary, heuristic savings, patient chapters
- [x] `test_billing_bugfixes.py` — encounter grouping (visit/date)
- [x] `test_prose_rules.py` — §2.2.2.A(5), cross-specialty

---

### Phase 2 (2026-06-02) — Done

| ID | Issue | Status |
|----|-------|--------|
| **L2.3** | No runtime EK-2G join | **Done** — `optimization/catalog_join.py`; catalog-authoritative surcharge exposure |
| **L2.4** | No runtime EK-2C-1 join | **Done** — EK-2C-1 rate + flag validation on exact lines |
| **L1.4** | §3.1 prose engine | **Partial** — **23 rules** + MEDULA additive; `validate_claim` + `prose_bundling_violations` |
| **L3.5** | MIAT interval + bundled taxonomy + partial P90 labeling | **Done** |
| **L1.4-ingest** | Synthetic material prose flag columns | **Done** — `generators.py` + `material_claim_lines.parquet` |

### L1.4 tail (2026-06-02) — Done

| ID | Issue | Status |
|----|-------|--------|
| **L1.4-kdv** | C001630, C002692 — EK-3 list KDV pricing | **Done** — `src/bilun/domain/pricing/material_kdv.py`; `kdv_price_reviews` on `precheck_materials_from_claims()` |
| **L1.4-allow** | C001823 — EK-3 explicit separate-billing allow list | **Done** — `ek3_separate_billing_allowed_codes()` catalog scan in `catalog_lookup.py` |
| **L1.4-c001635** | §3.1.1(15) separate billing not authorized unless SUT says so | **Done** — rule `3.1.1.(15).separate_billing_not_authorized` (23rd prose rule) |

## P2 — Phase 3 findings (remaining → owned by billing plans)

| ID | Issue | Owner |
|----|-------|-------|
| **L1.4** | §3.1–3.2 corpus tail (beyond Gate B p1_encode) | `plans/billing/material-bundling-prose-p2-plan.md` — corpus: `data/gazette/prose_corpus/L1.4_material_bundling_corpus_batch2.csv` |
| **L1.4-tier** | Care setting / facility tier in material prose | Same plan — wire `ClaimHeader` into `check_material_bundling_for_context` |
| **L4.4** | Specialty §3.3 prose tail | `plans/billing/specialty-materials-prose-l4.4-plan.md` |
| **L3.5** | MIAT vs MEDULA patient history | Deferred — real claim ingest (Category D) |

---

## Quick wins (2026-06-04) — Done

| ID | Issue | Status |
|----|-------|--------|
| **P0.1-tercih** | Jan/Jul MEDULA tercih dönemi | **OUT_OF_SCOPE** — administrative MEDULA preference; not §2.2 package vs itemized logic |
| **P0.1-prose-lock** | Prose-mandated EK-2/C package codes | **Done** — `ek2c_prose_drg_locked_codes.json` (51); `procedure_prose_drg_locked()` |
| **P0.2-ek2b-only** | EK-2/B-only multi-procedure sessions | **Done** — verified COMPLIANT; `test_ek2b_only_multi_procedure_uses_itemized_a5` |

---

## P2 — Document gaps

| ID | Issue | Target |
|----|-------|--------|
| L3.1-hemo | §2.2.2.B session fractions | **Done** — `lab.py` + `compute_session_point_factors` (2026-06-11) |
| ~~P0.2~~ | ~~Specialty +25 auto-detect~~ | **Done** — `session_specialty.py` (2026-06-04) |

---

## Verified COMPLIANT (no fix)

| ID | Finding |
|----|---------|
| L3.4 | No residual mandatory price-comparison fallback (post §2.2 fix) |
| L3.1-hemo | L107020 bundling core matches EK-2B |
| P0.2-blood | 705371/705430/705440 at 36% |
| L4.1 | EK-2B catalog + temporal API |
| L2.5 | Temporal EK-2B/2C audit |
| L2.8 | Cohort aggregator exactness discipline |
| P0.5, P0.6 | Facility tier + catalog membership |

---

## Completed (pre fact-check)

| ID | Issue | Status |
|----|-------|--------|
| L3.4 | Price-comparison billing strategy | Fixed strategy plan Phases 1–4; verified Phase 1 |
