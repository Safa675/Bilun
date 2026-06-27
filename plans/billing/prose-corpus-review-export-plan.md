## Task: Prose corpus human review — HTML audit export (superseded)

### Goal
~~Regenerable HTML sidecars from `prose_corpus/*.csv` for Gate B human audit.~~

### Decision (2026-06-26, revised)
**HTML dropped.** Human clause audit moves to **Rule Database** (in-app): section rollup → individual
hüküm drill-down with coverage status, primary rule, encoding flags. Offline CSV/HTML sprint queue
is no longer the primary review surface.

### Subtasks
- [x] Prototype `scripts/sut/export_prose_review_bundle.py` (kept for ad-hoc exports only)
- [x] Decision: HTML primary → **reversed**
- [ ] **Moved to** `plans/frontend/rule-database-improvement-plan.md` (full phased plan)

### Out of scope
- Production Gate B encode workflow in corpus CSV
- Hosted HTML review server
- XLSX as default export

### Review
2026-06-26: HTML prototype useful for one-off L1.4/L4.33 sprints; ongoing audit belongs in Rule Database.
