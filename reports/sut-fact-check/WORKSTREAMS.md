# Fact-Check Workstreams (Phase 0 Assignment)

**Generated:** 2026-06-02  
**Plan:** `plans/billing/algorithm-sut-fact-check-plan.md`

Parallel streams for Phases 1–3. Each stream owns report files under `algorithms/` and clause exports under `evidence/clauses/`.

---

## Phase 1 — P0 (start immediately after Phase 0)

| Stream | Owner | Units | Target reports |
|--------|-------|-------|----------------|
| **A** | subagent | P0.1, P0.2, P0.4, L3.4, L2.6 | `P0.1_payment_method.md`, `P0.2_session_pricing.md`, `P0.4_drg_unbundling.md`, `L3.4_billing_strategy.md`, `L2.6_drg_unbundling_cohort.md` |
| **B** | subagent | L3.1, L4.1 | `L3.1_lab_optimizer.md`, `L4.1_ek2b_pricing.md` |

**Exit:** 7 P0 reports + FIX_BACKLOG P0 section draft.

**Stream A clause exports:** `evidence/clauses/section_2_2*.csv`  
**Stream B clause exports:** `evidence/clauses/section_2_2_lab*.csv`, hemogram keywords

---

## Phase 2 — P1

| Stream | Owner | Units |
|--------|-------|-------|
| **C** | subagent | L3.2, L2.7, P0.3 |
| **D** | subagent | L2.1, L2.2, L3.3 |
| **E** | subagent | L1.1, L1.2, L3.5, P0.5, P0.6, L4.2 |

**Exit:** 13 reports. Resolves L1.1/L1.2 UNCERTAIN_HOLD from MEDULA report.

---

## Phase 3 — P2/P3

| Stream | Owner | Units |
|--------|-------|-------|
| **F** | main | L2.3, L2.4, L2.5, L2.8, L3.6, L4.3, L4.4, L1.3, L1.4 |

**Exit:** 9 reports (L1.4 = gap doc only).

---

## Phase 4 — Synthesis

| Owner | Deliverables |
|-------|--------------|
| main | `MASTER.md`, `FIX_BACKLOG.md`, doc drift list, frontend i18n drift list |

---

## Definition of done (per report)

- [ ] Gates A–F complete
- [ ] Verdict assigned with `section_id` or explicit "no clause"
- [ ] MEDULA overlap tag set
- [ ] Test diff (F.1) listed if non-COMPLIANT
- [ ] File path citations for code claims
