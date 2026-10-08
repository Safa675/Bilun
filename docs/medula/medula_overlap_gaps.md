# MEDULA Overlap Gap Report (Phase 0)

**Generated:** 2026-06-02 (Phase 5 L1.4 / material MEDULA refresh; L1.4 tail doc sync)  
**Scope:** All 28 fact-check units from `plans/billing/algorithm-sut-fact-check-plan.md`  
**Sources:** `docs/medula/medula_capabilities.md`, `docs/medula/medula_bilun_overlap.md`, `docs/medula/material_bundling_medula_boundary.md`

---

## Executive Summary

| Classification | Count | Meaning |
|----------------|------:|---------|
| **ADDITIVE** | 26 | BILUN adds analytics/strategy MEDULA does not provide — keep |
| **MEDULA_DUPLICATE** (billing recovery) | 1 | BILUN claims recoverable TRY for a pattern MEDULA already blocks or that has no billing action |
| **PARTIAL_OVERLAP** (relabel) | 5 | Related to MEDULA but different function — relabel savings/audience, do not delete |
| **UNCERTAIN_HOLD** | 0 | Resolved: L1.1/L1.2 annex lists **ADDITIVE**; L1.4 prose **ADDITIVE** (partial legal coverage) |
| **NOT_APPLICABLE** | 0 | L1.4 engine shipped (Phase 4–5) |
| **Total** | 28 | |

**Key finding:** Only **one** unit (L3.1 duplicate tests) currently **misclaims billing recovery** against MEDULA behavior. MEDULA rejects duplicate `hizmetSunucuRefNo` (idempotency), not duplicate SUT codes on separate lines (`medula_capabilities.md` §2.2). BILUN must relabel duplicates as clinical utilization review with `savings_try: null`.

**False-positive risk (materials):** MEDULA may block some lines at Hizmet Kayıt (ICU group, no procedure, ÜTS/UBB). BILUN material flags remain **ADDITIVE** for EK-3B-1/2 and §3.1 prose — do not label recoverable TRY from prose `risk_amount` as audited SGK recovery. See `docs/medula/material_bundling_medula_boundary.md`.

---

## Classification Key

| Tag | Definition |
|-----|------------|
| **ADDITIVE** | No MEDULA web-service equivalent; BILUN's unique value |
| **MEDULA_DUPLICATE** | MEDULA already rejects or computes; BILUN should not show recoverable TRY |
| **PARTIAL_OVERLAP** | MEDULA handles submission-time calculation/validation; BILUN does pre-submission analytics or a different abstraction |
| **UNCERTAIN_HOLD** | Overlap unknown from manual; defer delete/relabel until SUT fact-check |
| **NOT_APPLICABLE** | Not implemented |

---

## Layer 0 — Prose Rule Engine

| ID | Unit | MEDULA overlap | BILUN claim today | Phase 1 action |
|----|------|----------------|-------------------|----------------|
| P0.1 | `payment_method.py` | **ADDITIVE** | §2.2 payment method resolution | Fact-check Gate C; no MEDULA strategy comparison |
| P0.2 | `session_pricing.py` | **ADDITIVE** | Session fraction / point rules | Verify against §2.2.2.B; MEDULA has no session-fraction advisor |
| P0.3 | `copay_general.py` | **PARTIAL_OVERLAP** | General copay % from §1.8 | MEDULA applies copay at invoice; BILUN encodes rates for pre-check |
| P0.4 | `drg_unbundling.py` | **ADDITIVE** | Package-included line detection | MEDULA processes submitted lines; no unbundling advisor |
| P0.5 | `facility_tier.py` | **ADDITIVE** | Tier normalization for §2.2.2(2) | Input helper; MEDULA uses `saglikTesisKodu` contract context |
| P0.6 | `catalog_membership.py` | **ADDITIVE** | EK-2B/EK-2C membership + `(*)` | MEDULA validates code existence; BILUN uses catalogs for analytics |

---

## Layer 1 — Claim Validation

| ID | Unit | MEDULA overlap | BILUN claim today | Phase 1 action |
|----|------|----------------|-------------------|----------------|
| L1.1 | EK-3B-1 bundling | **ADDITIVE** | Pre-submission bundling violations + savings | Manual: ICU/procedure rules only — **not** EK-3B-1 by name |
| L1.2 | EK-3B-2 exclusion | **ADDITIVE** | Non-reimbursable material flags | Manual: ÜTS/UBB DTO — **not** EK-3B-2 by name |
| L1.3 | `validate_claim()` orchestrator | **ADDITIVE** | L1.1 + L1.2 + L1.4 prose third pass | Pre-MEDULA dry-run; MEDULA still validates DTO |
| L1.4 | §3 prose material bundling | **ADDITIVE** | 23-rule partial engine + `prose_bundling_violations`; KDV reviews + EK-3 allow-list | **Not** MEDULA_DUPLICATE — prose not in manual; risk flags only |

---

## Layer 2 — Cohort Optimization

| ID | Unit | MEDULA overlap | BILUN claim today | Phase 1 action |
|----|------|----------------|-------------------|----------------|
| L2.1 | Copay exemption EK-1A | **ADDITIVE** | Proactive ICD-10 exemption scan | MEDULA: `katilimPayindanMuaf` at admission; BILUN discovers from history |
| L2.2 | Visit/status/occupational exemptions | **PARTIAL_OVERLAP** | Hand-coded visit-type waivers | MEDULA applies provision/treatment type at submission |
| L2.3 | Surcharge exposure EK-2G | **ADDITIVE** | Cohort surcharge violation analytics | MEDULA: `ilaveUcrettenMuaf` per line; no cohort exposure dashboard |
| L2.4 | Copay rate EK-2C-1 | **PARTIAL_OVERLAP** | Rate mismatch validation | MEDULA computes payable; BILUN compares billed vs expected at scale |
| L2.5 | Temporal price audit | **ADDITIVE** | Historical EK-2B/2C amendment deltas | MEDULA: `guncelSutKodlari` current prices only |
| L2.6 | DRG unbundling (cohort) | **ADDITIVE** | Package-included + strategy risk by chapter | No MEDULA cohort unbundling advisor |
| L2.7 | Drug discount validation | **PARTIAL_OVERLAP** | Tier mismatch detection | MEDULA applies EK-4A tiers; BILUN validates systematic errors |
| L2.8 | Cohort aggregator | **ADDITIVE** | Meta — rolls up L2 features | No MEDULA equivalent |

---

## Layer 3 — Per-Patient Billing

| ID | Unit | MEDULA overlap | BILUN claim today | Phase 1 action |
|----|------|----------------|-------------------|----------------|
| L3.1 | Lab — hemogram bundling | **ADDITIVE** | CBC sub-components → L107020 savings | MEDULA validates individual codes; no hemogram bundling algorithm in manual |
| L3.1 | Lab — duplicate tests | **MEDULA_DUPLICATE** (billing) / **ADDITIVE** (clinical) | `rule_source`: "EK-2B duplicate test rules"; non-zero TRY savings | **Relabel:** clinical review, `savings_try: null`. MEDULA only rejects duplicate `hizmetSunucuRefNo` |
| L3.2 | Drug — generic substitution | **ADDITIVE** | Cheaper EK-4A equivalent recommendation | MEDULA applies tier to submitted drug; no substitution advisor |
| L3.2 | Drug — passivation | **PARTIAL_OVERLAP** | Compliance alert for passivated drugs | MEDULA `IlacAra` active/passive; rejects at submission — BILUN is advance warning (no false TRY if alert-only) |
| L3.3 | Copay savings | **ADDITIVE** | Recoverable copay when EK-1A exempt | Different timing vs MEDULA invoice copay |
| L3.4 | Billing strategy | **ADDITIVE** | §2.2 payment method recommendation | MEDULA computes payment for submitted strategy; no comparison |
| L3.5 | Material pre-check | **PARTIAL_OVERLAP** | EK-3C-1/2 + MIAT + **prose_bundling_violations** + **kdv_price_reviews** + ceilings | MEDULA: ICU-group + ÜTS; BILUN adds annex + prose + KDV ceiling pre-check |
| L3.6 | Billing orchestrator | **ADDITIVE** | Exactness gating + cohort priority | No MEDULA equivalent |

---

## Layer 4 — Pricing & Catalog

| ID | Unit | MEDULA overlap | BILUN claim today | Phase 1 action |
|----|------|----------------|-------------------|----------------|
| L4.1 | EK-2B FFS pricing | **ADDITIVE** | Temporal gazette lookup for analytics | MEDULA real-time `guncelSutKodlari` |
| L4.2 | EK-2C DRG pricing | **ADDITIVE** | Package price lookup | Same |
| L4.3 | EK-2A outpatient | **ADDITIVE** | Visit pricing lookup | Same |
| L4.4 | Specialty materials EK-3 | **ADDITIVE** | Branch specialty ceiling analytics | MEDULA facility-type markups differ |

---

## MEDULA Evidence Citations

### Duplicate / idempotency (L3.1)

From `docs/medula/medula_capabilities.md` §2.2:

| Rule | Outcome |
|------|---------|
| Provider ref number uniqueness (`hizmetSunucuRefNo`) | Reject (duplicate) |
| Adet max 1 per procedure line; repeats → separate records | Not same-code rejection |

BILUN duplicate detection groups by encounter (visit_id / date), not ref number — **different signal** from MEDULA idempotency.

### Copay / exemption (L2.1, L3.3)

- MEDULA: copay at invoice; exemption flag at admission (`katilimPayindanMuaf`).
- BILUN: proactive ICD-10 EK-1A scan — **additive**, not duplicate enforcement.

### Materials (L1.1, L1.2, L1.4, L3.5) — Phase 5 resolution

Full boundary doc: [`docs/medula/material_bundling_medula_boundary.md`](../../docs/medula/material_bundling_medula_boundary.md).

| MEDULA (documented) | BILUN | Verdict |
|---------------------|-------|---------|
| ICU A/B/C group required for materials | No ICU-group gate | MEDULA-only blocking |
| No procedure in takip → no material | `procedure_pairing_required` (EK-3/C) | **PARTIAL_OVERLAP** (intent) |
| UBB/ÜTS / barcode DTO | `titubb_uts_incomplete`, barcode keyword | **PARTIAL_OVERLAP** |
| *(not in manual)* | EK-3B-1, EK-3B-2, §3.1 prose (**23 rules**) | **ADDITIVE** |
| EK-3 list price + KDV (§3.1.1(10)) | `material_kdv.py` → `kdv_price_reviews` (C002748) | **ADDITIVE** (pre-submission ceiling analytics) |
| EK-3 explicit separate-billing allow list | `ek3_separate_billing_allowed_codes()` (C001823) | **ADDITIVE** |

**L1.4:** `material_bundling_prose` is **implemented** with `prose_coverage_tier: partial`. **0** Gate B deferred clauses (tail closed 2026-06-02). Coverage matrix: 733 §3.1-classified clauses → registry `implemented` (legal corpus tail still open). Do **not** count prose violations or KDV review deltas as MEDULA-guaranteed savings.

---

## Action Items for Phase 1

| Priority | ID | Action |
|----------|-----|--------|
| P0 | L3.1-dup | Set `MEDULA_DUPLICATE` for billing recovery; clinical review label; null savings |
| P1 | L3.2-passivation | Confirm alert-only (no TRY) in Gate C |
| P1 | L2.2, L2.4, L2.7, L3.5, P0.3 | PARTIAL_OVERLAP — document audience (pre-MEDULA vs submission) |
| Done | L1.1, L1.2, L1.4 | **ADDITIVE** — see `material_bundling_medula_boundary.md` |
| P2 | Category D (overlap doc) | ICU-group + `barkodSutEslesmeSorgu` integration — optional |

---

## Counts for Baseline (`baseline_metrics.json`)

```json
{
  "additive_review": 26,
  "medula_duplicate_billing_recovery": 1,
  "partial_overlap_relabel": 5,
  "uncertain_hold": 0,
  "not_applicable": 0,
  "total_units": 28,
  "phase_5_note": "L1.4 prose ADDITIVE; L3.5 partial includes prose precheck"
}
```

Note: L3.1 is counted once in `medula_duplicate_billing_recovery` (duplicate sub-feature only). Hemogram sub-feature is ADDITIVE within the same L3.1 report.
