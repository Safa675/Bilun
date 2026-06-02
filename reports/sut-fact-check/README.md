# SUT Algorithm Fact-Check Reports

Engineering artifacts for the algorithm fact-check program (`plans/billing/algorithm-sut-fact-check-plan.md`).

## Structure

```
reports/sut-fact-check/
├── README.md                 ← this file
├── MASTER.md                 ← rollup (Phase 4)
├── FIX_BACKLOG.md            ← prioritized fixes (Phase 4)
├── WORKSTREAMS.md            ← parallel assignment (Phase 0)
├── baseline_metrics.json     ← coverage + MEDULA snapshot (Phase 0)
├── medula_overlap_gaps.md    ← MEDULA vs BILUN classification (Phase 0)
├── algorithms/
│   ├── _TEMPLATE.md          ← per-algorithm report template
│   └── {ID}_{slug}.md        ← one report per unit (Phases 1–3)
└── evidence/
    ├── clauses/              ← exported clause CSVs by section prefix
    └── diffs/                ← optional decision-table snapshots
```

## Status

| Phase | Status | Deliverables |
|-------|--------|--------------|
| 0 | **Complete** | baseline_metrics, medula_overlap_gaps, directory tree, workstreams |
| 1 | **Complete** | 7 P0 reports |
| 2 | **Complete** | 12 P1 reports (L1.1–L1.2, L2.1–L2.2, L2.7, L3.2–L3.3, L3.5, P0.3, P0.5–P0.6, L4.2) |
| 2b | **Complete** | Phase 5 P0 code fixes (session primary, lab dup, same_incision) |
| 3 | **Complete** | 9 reports: L2.3–L2.5, L2.8, L3.6, L4.3–L4.4, L1.3, L1.4 gap |
| 4 | **Complete** | MASTER.md full rollup (28/28) |
| Fix | Pending | P1/P2 waves from FIX_BACKLOG.md |
| 3 | Pending | P2/P3 algorithms |
| 4 | Pending | MASTER.md, FIX_BACKLOG.md |
| 5 | Pending | Fix wave |

## How to add a report

1. Copy `algorithms/_TEMPLATE.md` → `algorithms/{ID}_{slug}.md`
2. Run Gates A–F from the plan
3. Link evidence files under `evidence/clauses/` when exported
