## Task: SUT referans / normatif / encode ayrımı

**Branch:** `feat/sut-referans-normatif`  
**Plan:** `plans/billing/sut-referans-normatif-plan.md`

### Goal
Referans hükümler (başlık, tanım, RG meta) gap sayılmasın; encode borcu KPI’sı dürüst olsun.

### Subtasks — Phase R1 (active)
- [x] Branch + plan doc
- [x] Fix `_has_actionable_signal` for structural clause types (C000002)
- [x] Unit tests for chapter / prose subtitle / section_heading
- [x] Regenerate coverage parquets (`missing` 10→4)
- [x] pytest green

### Out of scope (this phase)
- UI üç rozet (R2)
- classify.py routing wave 2 (R3)
- encode interaction graph (R4)
- Gate B corpus expansion (R5)

### Review
_(pending)_
