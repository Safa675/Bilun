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

---

## Task: Commit & push Finans Coder pipeline removal

### Goal
Commit the working-tree changes (removal of the Finans Coder / coding-resolver pipeline + agent-doc updates) and push to `origin/fix/fi-checklist-relevance-dayanak` with green CI.

### Subtasks
- [x] Delete leftover `tests/unit/scripts/test_finans_cleanup.py` — imports deleted `analyze_finans_data` → pytest collection error (breaks full-suite CI)
- [x] Update `agents/reimbursement/run_checks.sh` — drop step 1 (`verification_loop.py` deleted)
- [x] Update `agents/reimbursement/system-prompt.md` "This runs:" list — remove `verification_loop.py`
- [x] Verify: full `pytest -q` green + `ruff check src/ scripts/` clean
- [x] Commit 1: `chore: remove Finans Coder coding pipeline` (deletions + agent docs + test cleanup + lessons)
- [x] Commit 2: `fix(data): update L1.8 copay-exemption manifest effective_date` (2026-07-25 → 2026-08-01)
- [x] Push; confirm no pre-existing failing CI on branch (AGENTS.md §10)

### Out of Scope
- Re-enabling any Finans Coder functionality
- Deleting historical plan docs that reference the removed pipeline (`plans/data/2026-07-16-finans-cleanup-and-coder-plan.md`, `plans/tooling/employee-agents-plan.md`, etc.)
- `tasks/lessons.md` historical entries mentioning removed scripts
