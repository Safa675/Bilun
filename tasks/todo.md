## Task: FI checklist relevance + dayanak UX

### Goal
FI documentation reminders only show when claim signals match; dayanak column shows FI/SUT **section** labels (not F000/C000); column title is “Dayanak”. Plan: `plans/billing/2026-07-29-fi-checklist-relevance-dayanak-plan.md`. Option B locked.

### Subtasks
- [x] Plan onay — Option B (kodsuz branş: sinyal yoksa gizle)
- [x] Phase 1: relevans gates + `sut_anchor` = `Fatura İnceleme {ref}` (+ tests)
- [x] Phase 2: i18n “Dayanak” / “Basis” + footnote
- [x] Phase 3: verify (0003-011 spam down; dayanak filled)

### Out of Scope
- EMR document presence
- Algorithmic FI violation changes
- A2 separate UI block
- Removing `gate_b_sources` from JSON provenance

### Review
- Option B: code-less rules need `relevance_signals`; 6 ORTAK + ORTOPEDİ-6 wired; other 15 code-less hidden until signals added
- Dayanak: `Fatura İnceleme {ref}` (+ optional `sut_section_label`); never F000/C000
- FE: TR Dayanak / EN Basis; footnote mentions FI+SUT
- Tests: 36 passed (`test_fatura_inceleme_checklist`, `test_claim_readiness`, `test_billing_actions`)
