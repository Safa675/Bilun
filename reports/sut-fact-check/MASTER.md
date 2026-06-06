# SUT Algorithm Fact-Check — Master Report

**Status:** Phase 3 complete — **28/28 reports**  
**Last updated:** 2026-06-04 (P0.1/P0.2 quick-win backlog sync)  
**Next:** L1.4 corpus CSV batches + tier wiring  
**Fix waves applied:** P0/P1 (2026-06-02), Sprint A-D (2026-06-02), Phase 1 remainder (2026-06-02), Phase 2 + L1.4 tail (2026-06-02)

---

## Executive Summary

Full fact-check of BILUN reimbursement algorithms against `sut_clauses.parquet` (8,180 clauses), prose JSON, annex catalogs, and MEDULA overlap analysis.

### Critical issues (fix first)

| Priority | Issue | Unit |
|----------|-------|------|
| **P0** | ~~Session primary / lab dup / same_incision~~ | **Fixed** Phase 5 |
| **P1** | ~~IVF copay helper WRONG (5%/10% vs §1.8.4 30/25/20%)~~ | **Fixed** P0.3 |
| **P1** | ~~EK-1A missing health-report gate §1.8.5(7)~~ | **Fixed** L2.1, L3.3 |
| **P1** | ~~Cohort `grand_total_recoverable` not exactness-gated~~ | **Fixed** L3.6 |
| **P2** | §3.1–3.2 prose bundling — partial (23 rules; 0 Gate B deferred; corpus tail) | L1.4 |

### Strengths

- §2.2 payment-method core (P0.1, L3.4) largely correct post-fix
- EK-3B-1/3B-2 pre-MEDULA validation **ADDITIVE** — keep savings
- P0.5/P0.6 catalog + tier infrastructure **COMPLIANT**
- L2.5 temporal gazette audit **COMPLIANT**
- Exactness gating pattern (L2.3, L2.4, L2.7) **honest** when claim lines missing

---

## Full Verdict Table (28 units)

| ID | Unit | Verdict | MEDULA |
|----|------|---------|--------|
| P0.1 | Payment method | PARTIAL | ADDITIVE |
| P0.2 | Session pricing | PARTIAL | PARTIAL_OVERLAP |
| P0.3 | Copay general §1.8 | PARTIAL (IVF §1.8.4 fixed) | ADDITIVE |
| P0.4 | DRG unbundling prose | PARTIAL | ADDITIVE |
| P0.5 | Facility tier | COMPLIANT | ADDITIVE |
| P0.6 | Catalog membership | COMPLIANT | ADDITIVE |
| L1.1 | EK-3B-1 bundling | PARTIAL | ADDITIVE |
| L1.2 | EK-3B-2 exclusion | PARTIAL | ADDITIVE |
| L1.3 | `validate_claim()` | PARTIAL | ADDITIVE |
| L1.4 | §3 prose bundling | **PARTIAL** (23 rules: keywords, EK-3/C, claim flags, §3.1.1(15) auth) | ADDITIVE |
| L2.1 | Copay exemption EK-1A | PARTIAL | ADDITIVE |
| L2.2 | Visit/status exemptions | PARTIAL | ADDITIVE |
| L2.3 | Surcharge EK-2G | NEEDS_CLAIM_LINES | ADDITIVE |
| L2.4 | Copay rate EK-2C-1 | NEEDS_CLAIM_LINES | ADDITIVE |
| L2.5 | Temporal price audit | COMPLIANT | ADDITIVE |
| L2.6 | DRG unbundling cohort | PARTIAL | ADDITIVE |
| L2.7 | Drug discount validation | NEEDS_CLAIM_LINES | PARTIAL_OVERLAP |
| L2.8 | Cohort aggregator | COMPLIANT | ADDITIVE |
| L3.1 | Lab optimizer | PARTIAL (dup HEURISTIC) | ADDITIVE / fixed |
| L3.2 | Drug optimizer | HEURISTIC / exact OK | ADDITIVE |
| L3.3 | Copay savings | PARTIAL | ADDITIVE |
| L3.4 | Billing strategy | PARTIAL | ADDITIVE |
| L3.5 | Material pre-check | PARTIAL (MIAT interval + bundled taxonomy fixed) | PARTIAL_OVERLAP |
| L3.6 | Billing orchestrator | PARTIAL | ADDITIVE |
| L4.1 | EK-2B FFS pricing | COMPLIANT | ADDITIVE |
| L4.2 | EK-2C DRG pricing | HEURISTIC | ADDITIVE |
| L4.3 | EK-2A outpatient | PARTIAL | ADDITIVE |
| L4.4 | Specialty materials EK-3 | PARTIAL | ADDITIVE |

---

## Verdict counts

| Verdict | Count |
|---------|------:|
| COMPLIANT | 6 |
| PARTIAL | 16 |
| HEURISTIC | 2 |
| WRONG | 0 |
| NEEDS_CLAIM_LINES | 3 |
| OUT_OF_SCOPE | 0 |

---

## Layer summary

| Layer | Key takeaway |
|-------|----------------|
| **P0 Prose** | Payment method OK; session A(5)/specialty fixed; copay IVF §1.8.4 fixed |
| **L1 Validation** | EK-3B lists + **23-rule** §3 prose + KDV/allow-list tail + synthetic claim-field columns; MEDULA additive; corpus tail open |
| **L2 Cohort** | Exemptions partial; exactness honest; temporal audit solid |
| **L3 Billing** | Strategy OK; lab dup fixed; drug heuristic; **L3.5 MIAT interval**; orchestrator cohort totals |
| **L4 Pricing** | EK-2B/C catalogs good; EK-2A mean heuristic; DRG chapter medians |

---

## MEDULA overlap (final)

| Tag | Count |
|-----|------:|
| ADDITIVE | 26 |
| PARTIAL_OVERLAP | 5 |
| MEDULA_DUPLICATE (billing) | 1 (L3.1 dup — clinical relabel only) |
| UNCERTAIN_HOLD | 0 |
| NOT_APPLICABLE | 0 |

Detail: `medula_overlap_gaps.md`, materials: `docs/medula/material_bundling_medula_boundary.md`

---

## Registry drift (update after fixes)

| rule_id | Registry | Fact-check |
|---------|----------|------------|
| `payment_method_*` | implemented | partial |
| `drg_unbundling` | implemented | partial |
| `copay_exemption_ek1a` | implemented | partial |
| `material_bundling_prose` | implemented | partial clause coverage (23 rules; 0 Gate B deferred; MEDULA additive) |
| `copay_rate_ek2c1` | needs_claim_lines | confirmed |
| `surcharge_ek2g` | needs_claim_lines | confirmed |

---

## Post-Fix Summary (2026-06-03 sync)

All 28 algorithm reports now include post-fix status lines and Post-Fix Updates sections documenting what was fixed and when. Key fix categories:

| Category | Reports affected | What was fixed |
|----------|-----------------|----------------|
| **WRONG → FIXED** | P0.2, P0.3, L2.1, L3.1 | Primary selection, IVF copay, rule_source citations, unknown bucket |
| **PARTIAL → FIXED** | P0.1, P0.4, L1.1, L1.2, L1.3, L2.2, L2.3, L2.4, L2.5, L2.6, L3.3, L3.4, L3.5, L3.6, L4.1, L4.2, L4.3 | Temporal wiring, code matching, unit tests, exemption gates, MIAT interval, per-visit pricing, cohort gating |
| **HEURISTIC → LABELED** | P0.4, L3.2 | heuristic_savings_try + UI footnote; savings_basis: heuristic |
| **COMPLIANT (verified)** | P0.5, P0.6, L2.5, L2.8, L4.1-core | No fixes needed; confirmed post-audit |
| **Ongoing (P2)** | L1.4, L4.4 | Corpus tail + tier wiring; 84/84 traced, more corpus to encode |

**Remaining open items (P2):**
- L1.4: §3.1–3.2 corpus tail (hundreds of clauses), facility tier wiring, real ETL flag derivation
- L3.5: MIAT vs MEDULA patient history (Category D)
- L4.4: §3.1–3.2 prose bundling enforcement beyond EK-3B-1

**Closed (2026-06-04 quick wins):** P0.1 prose-locked EK-2/C seed (51 codes); P0.1 Jan/Jul MEDULA tercih dönemi **OUT_OF_SCOPE**; P0.2 EK-2/B-only multi-procedure sessions (verified COMPLIANT); P0.2 specialty +25 auto-detect (`session_specialty.py` + claim strategy).

## Phase completion

| Phase | Status |
|-------|--------|
| 0 Setup | ✅ |
| 1 P0 reports | ✅ |
| 2 P1 reports | ✅ |
| 3 P2/P3 reports | ✅ |
| 5 P0 code fixes | ✅ |
| Post-fix report sync | ✅ (2026-06-03) |
| 4 Synthesis | ✅ (this document) |
| Material P2 Phase 5 MEDULA | ✅ |
| L1.4 Phase 6 synthetic prose flags | ✅ |
| L1.4 tail (KDV, allow-list, C001635 §3.1.1(15)) | ✅ |
| L3.5 MIAT interval + partial-mode labeling | ✅ |
| Fix waves | ✅ P0/P1 + L1.4 partial engine (corpus tail + tier wiring open) |

---

## Report index

All reports: `reports/sut-fact-check/algorithms/`

Phase 3 rollup: `PHASE3_VERDICT_TABLE.md`

---

## Links

- [Fact-check plan](../../plans/billing/algorithm-sut-fact-check-plan.md)
- [Fix backlog](./FIX_BACKLOG.md)
- [MEDULA overlap](./medula_overlap_gaps.md)
- [Material vs MEDULA boundary](../../docs/medula/material_bundling_medula_boundary.md)
