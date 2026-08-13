## Task: Update Antigravity Desktop App / IDE

### Goal
Check for and execute updates for the Antigravity Desktop Application (/opt/antigravity, currently v2.4.3).

### Subtasks
- [x] Inspect current Antigravity installation version (v2.4.3 at `/opt/antigravity`) and auto-updater configuration
- [ ] Check auto-updater manifest endpoint and background update status
- [ ] Trigger or verify update download and apply process for Antigravity IDE
- [ ] Restart/verify running Antigravity processes to ensure updated version is active

### Out of Scope
- Modifying project codebase files in Bilun repository
- Modifying custom skills or rules unless requested

---

## Task: IDE-style workspace shell (tabs + split + quick-open) — branch experiment/workspace-shell, PR #68

### Goal
Full design in `plans/frontend/ide-style-workspace-shell-plan.md`: editor-tab layer for multi-patient work, side-by-side comparison, Ctrl+K quick-open, with complexity guardrails. Direction + Phase 0 decisions locked with Safa 2026-08-13.

### Subtasks
- [x] Phase 0: locked 2026-08-13 — all sections tabbed; sessionStorage persistence; 6-tab + 2-pane caps; chat-right disabled during split
- [x] Phase 1: tab strip + URL list state (208 vitest, Playwright 14/14) — committed a3fdc00
- [x] Phase 2: 2-pane split for patient comparison (213 vitest, Playwright 12/12) — committed e41823b
- [x] Phase 3: Ctrl+K patient quick-open palette (213 vitest, Playwright 9/9)
- [x] Lint at pre-existing baseline (17 errors / 9 warnings) after every phase; tsc clean

### Out of Scope
- Drag-reorder/drag-split, >2 panes, tab groups, multi-window sync, mobile layouts
- Ctrl+\ split shortcut (deferred)
