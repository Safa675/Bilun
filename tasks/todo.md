## Task: Track D — Product / audit UX (coordinate-first)

### Goal
Specialists can audit rules/gaps without needing `C*`: Hüküm shows coordinates, rule detail shows coordinate cites + snippets, gap/deferral views keyed by coordinate, 4-verb pipeline docs.

### Subtasks
- [x] Scout + lock scope (API + UI surfaces)
- [x] Hüküm list/detail: primary id = coordinate; copyable; search by coordinate + text
- [x] Rule detail: `gate_b_sources` as coordinates + text snippets
- [x] Gap / deferral review views keyed by coordinate
- [x] Docs: 4-verb README `extract → compile → derive → evaluate`
- [x] Verify demo path; mark god-plan D boxes; Review

### Out of Scope
- Track E (delete C* column)
- Track F non-drug Gate B
- Polars coverage enrich (C leftover)

### Review
- Branch / PR: `refactor/sut-pipeline-god-plan` → https://github.com/Safa675/Bilun/pull/43
- API: `get_clause` dual-read; `list_deferrals`; `list/resolve prose gate_b_sources`
- UI: Hüküm coordinate-primary + copy; Prose expand → cites; Deferrals tab
- Docs: `docs/gazette/sut-pipeline.md`
- God-plan Track D checkboxes marked
