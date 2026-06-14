# SUT Algorithm Fact-Check — Archived Summary

**Audit program:** closed **2026-06**  
**Live source of truth:** `src/bilun/domain/sut/fact_check_audit.py` + Rule Database tab (`GET /api/rules`)  
**Original deliverables:** relocated from `docs/core-system/fact-check/` (deleted 2026-06)

---

## Verdict rollup (28 units)

| Verdict | Count |
|---------|------:|
| COMPLIANT | 5 |
| PARTIAL | 18 |
| HEURISTIC | 2 |
| NEEDS_CLAIM_LINES | 3 |
| WRONG | 0 |
| OUT_OF_SCOPE | 0 |

---

## Full verdict table

| ID | Unit | Verdict | MEDULA |
|----|------|---------|--------|
| P0.1 | Payment method | PARTIAL | ADDITIVE |
| P0.2 | Session pricing | PARTIAL | PARTIAL_OVERLAP |
| P0.3 | Copay general §1.8 | PARTIAL | ADDITIVE |
| P0.4 | DRG unbundling prose | PARTIAL | ADDITIVE |
| P0.5 | Facility tier | COMPLIANT | ADDITIVE |
| P0.6 | Catalog membership | COMPLIANT | ADDITIVE |
| L1.1 | EK-3B-1 bundling | PARTIAL | ADDITIVE |
| L1.2 | EK-3B-2 exclusion | PARTIAL | ADDITIVE |
| L1.3 | `validate_claim()` | PARTIAL | ADDITIVE |
| L1.4 | §3 prose bundling | PARTIAL | ADDITIVE |
| L2.1 | Copay exemption EK-1A | PARTIAL | ADDITIVE |
| L2.2 | Visit/status exemptions | PARTIAL | ADDITIVE |
| L2.3 | Surcharge EK-2G | NEEDS_CLAIM_LINES | ADDITIVE |
| L2.4 | Copay rate EK-2C-1 | NEEDS_CLAIM_LINES | ADDITIVE |
| L2.5 | Temporal price audit | COMPLIANT | ADDITIVE |
| L2.6 | DRG unbundling cohort | PARTIAL | ADDITIVE |
| L2.7 | Drug discount validation | NEEDS_CLAIM_LINES | PARTIAL_OVERLAP |
| L2.8 | Cohort aggregator | COMPLIANT | ADDITIVE |
| L3.1 | Lab optimizer | PARTIAL | ADDITIVE |
| L3.2 | Drug optimizer | HEURISTIC | ADDITIVE |
| L3.3 | Copay savings | PARTIAL | ADDITIVE |
| L3.4 | Billing strategy | PARTIAL | ADDITIVE |
| L3.5 | Material pre-check | PARTIAL | PARTIAL_OVERLAP |
| L3.6 | Billing orchestrator | PARTIAL | ADDITIVE |
| L4.1 | EK-2B FFS pricing | COMPLIANT | ADDITIVE |
| L4.2 | EK-2C DRG pricing | HEURISTIC | ADDITIVE |
| L4.3 | EK-2A outpatient | PARTIAL | ADDITIVE |
| L4.4 | Specialty materials EK-3 | PARTIAL | ADDITIVE |

---

## What moved where

| Former path | New home |
|-------------|----------|
| Verdict table + per-rule metadata | `src/bilun/domain/sut/fact_check_audit.py` |
| Rule Database UI banner | `frontend/.../RuleDatabaseSection.tsx` |
| API rollup | `GET /api/rules` → `fact_check` field |
| `baseline_metrics.json` | `tasks/archive/sut-fact-check-2026-06/baseline_metrics.json` |
| 28 detailed algorithm reports | **Removed** — audit closed; reopen from git history if needed |
| `evidence/clauses/*.csv` | **Removed** — clause text available via Rule Database drill-down |
| `FIX_BACKLOG.md` | **Removed** — fixes landed in code; see git log / billing plans |
| MEDULA overlap detail | `docs/medula/medula_overlap_gaps.md` |

---

## Remaining open items (P2 at audit close)

- L1.4: §3.1–3.2 prose corpus tail
- L3.5: MIAT vs MEDULA patient history
- L4.4: §3.3 specialty prose beyond current JSON coverage

Track in active billing plans under `plans/billing/`.

---

## Links

- [Original fact-check plan](../../plans/billing/algorithm-sut-fact-check-plan.md)
- [MEDULA overlap gaps](../../docs/medula/medula_overlap_gaps.md)
- [Algorithm reference](../../docs/core-system/algorithms_reference.md)
