# SUT algorithm fact-check (reference)

**Status:** Audit program closed 2026-06. Fix waves P0–P1 complete; P2 corpus tail owned by billing plans.  
**Plan:** [`plans/billing/algorithm-sut-fact-check-plan.md`](../../plans/billing/algorithm-sut-fact-check-plan.md)

Evidence-backed verdicts for 28 reimbursement algorithms vs `sut_clauses.parquet`, prose JSON, annex catalogs, and MEDULA overlap.

## Layout

```
docs/core-system/fact-check/
├── README.md              ← this file
├── MASTER.md              ← rollup (28/28 verdicts)
├── FIX_BACKLOG.md         ← fix history; open P2 → billing plans
├── baseline_metrics.json  ← coverage snapshot (regenerate via scripts/sut/rebuild_baseline_metrics.py)
├── algorithms/            ← one report per unit (Gates A–F)
└── evidence/clauses/      ← audit citation CSVs (§1.8, §2.2 section dumps)

docs/medula/medula_overlap_gaps.md

data/gazette/prose_manifests/   ← encode manifests (runtime + scripts)
data/gazette/prose_corpus/      ← Gate B corpus exports (regenerable)
```

## Two “evidence” locations

| Path | Purpose |
|------|---------|
| `docs/core-system/fact-check/evidence/clauses/` | Frozen clause excerpts cited in audit reports |
| `data/gazette/prose_corpus/` | Regenerable §3.1–3.2 / L4.4 encoding candidates |
| `data/gazette/prose_manifests/` | Which corpus rows became `prose_rules/*.json` |

## Add a new report

1. Copy `algorithms/_TEMPLATE.md` → `algorithms/{ID}_{slug}.md`
2. Run Gates A–F from the fact-check plan
3. Export audit CSVs to `evidence/clauses/`; corpus work goes to `data/gazette/prose_corpus/`
