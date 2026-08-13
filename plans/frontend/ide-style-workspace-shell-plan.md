# IDE-Style Workspace Shell — Tabs + Split View for Multi-Patient Work

> Status: APPROVED DIRECTION — Phase 0 decisions locked 2026-08-13 (below);
> implementation starts on Safa's go-ahead.
> Context: decided 2026-08-13 with Safa: current shell is "too simple" for the real
> workflow (officers juggle 2-3 patient financial profiles); direction chosen =
> full IDE-style shell that solves BOTH alternating between profiles AND
> side-by-side comparison. This plan adopts the IDE's power while deliberately
> rejecting the IDE's complexity drivers (see Guardrails).

---

## Task: Give the shell an editor-tab layer and a 2-pane split

### Goal
An officer can open several patient financial profiles (and section views) as
tabs in a top strip, switch between them instantly with per-tab state
preserved, and split the workspace into two panes to compare two profiles
side by side — without the app feeling like a developer tool.

### Why now
- `/patient/[id]` is route-driven and single-view: opening a second profile
  means navigating away and losing scroll/chat context.
- The cohort list state (filters, page) is component state, not URL state —
  returning to the list resets it, which is the real cost of switching today.
- The collapsible sidebar (PR #31) already turned the left rail into an
  activity-bar-style launcher; a tab layer is the consistent next step.

### Concept mapping (IDE → billing domain)
| IDE concept        | Bilun equivalent                                              | In scope |
|--------------------|---------------------------------------------------------------|----------|
| Activity bar       | Collapsed sidebar (already shipped, PR #31)                    | done     |
| Sidebar panels     | Expanded sidebar sections (launcher only, never tabbed state)  | done     |
| Editor tabs        | Workspace tab strip: patient profiles + section views          | Phase 1  |
| Split editor       | 2-pane vertical split for side-by-side profiles                | Phase 2  |
| Command palette    | Ctrl+K patient quick-open (search by id/name)                  | Phase 3  |
| Status bar         | — rejected: no domain value, pure chrome                       | never    |

### Layout sketch

```
┌─ sidebar ─┬─ tab strip ─────────────────────────────────────────────┐
│ launcher  │ [Hastalar] [HASTA-0001 ×] [HASTA-0043 ×] [Gelir]  ⌄ +2  │
│ sections  ├───────────────────────────┬─────────────────────────────┤
│           │  pane A: active tab       │  pane B: pinned compare tab │
│           │  (patient workspace or    │  (second patient workspace) │
│           │   section view)           │                             │
│           ├───────────────────────────┴─────────────────────────────┤
│           │  chat copilot (existing dock: center / right)           │
└───────────┴─────────────────────────────────────────────────────────┘
```

- Tab strip sits above the workspace, below the top edge; visible only when
  ≥1 tab is open (home list alone does not force a tab).
- Split is vertical, max 2 panes. Pane B is entered via a per-tab action
  ("Yan yana aç" / "Open side by side") and via a pane-header button.
- Chat dock keeps its current behavior; when split is active the chat is
  center-docked under both panes (right-docking + split is out of scope v1).

### State model
- New zustand store `workspaceStore` (mirrors `navigationStore` pattern,
  exposed via context like `navigationContext.tsx`):
  - `tabs: [{ id, kind: "patient" | "section", ref (patientId or tabId), title }]`
  - `activeTabId`, `paneBTabId: string | null` (null = no split)
  - actions: openTab, closeTab, activateTab, splitWith(tabId), closeSplit
- Cap: 6 tabs; opening a 7th closes the least-recently-active non-pinned tab
  (overflow dropdown lists all, so nothing is ever "lost").
- Persistence: `sessionStorage` (survives F5 / crash; clears on browser
  close). Rationale: officers losing open charts to an accidental refresh is
  the exact complaint we're fixing; full localStorage persistence deferred.
- URL stays the source of truth for the ACTIVE view (deep links work):
  `/patient/[id]` activates-or-creates that tab. Pane B is store-only v1.
- Per-tab preserved state: scroll position + chat context keyed by tab id
  (component state lifted into a per-tab cache; v1 = keep-alive of the two
  visible panes + scroll restore, not full virtualization of all tabs).

### Complexity guardrails (the actual answer to "IDE = too complex")
What makes IDEs feel complex is unbounded chrome and keyboard-only paths —
not tabs. Therefore:
1. Every capability has a visible button; shortcuts are additive, never
   required (Ctrl+K palette also reachable from a search field).
2. Bounded surfaces: 6-tab cap, 2-pane cap, no drag-reorder / drag-split v1.
3. Tabs behave like browser tabs (× to close, click to activate) — a metaphor
   every officer already knows; no IDE-specific gestures.
4. Sidebar remains the only global navigation; tabs are "open documents".
5. Small screens (< md): tab strip collapses to a dropdown; split disabled
   (officers are on desktop, but the app must not break on a laptop).
6. All new strings through the existing i18n pipeline (en + tr).

### Subtasks

#### Phase 0 — Decisions to lock with Safa (before code)
- [x] Tab scope: ALL sections open as tabs (sidebar = launcher, tabs = open
      documents). Locked 2026-08-13.
- [x] sessionStorage persistence + 6-tab cap (LRU close, overflow dropdown)
      + 2-pane cap. Locked 2026-08-13.
- [x] Right-docked chat disabled while split is active (v1). Locked 2026-08-13.

#### Phase 1 — URL state + tab strip (implemented 2026-08-13, pending review)
- [x] Cohort list state: filters were ALREADY URL-driven (`useCohortFilter`);
      added the table page (`p` param, `PatientInvoiceTable`) and preserved it
      across section switches (`buildSutHomeHref` preserve list).
- [x] `workspaceStore` + `workspaceContext` wiring in `providers.tsx`
      (sessionStorage persistence via store subscription).
- [x] Tab strip (`WorkspaceTabStrip`, client-only via `WorkspaceTabStripMount`
      + `dynamic ssr:false` — server cannot see sessionStorage): render,
      activate, close, overflow dropdown, 6-tab cap.
- [x] Route integration (`WorkspaceRouteSync`): URL is the source of truth;
      each tab also remembers its last query string so list state (filters +
      page) survives tab switches.
- [x] i18n (en/tr `shell.workspaceTabs`); 13 new vitest cases (208 total);
      Playwright matrix 14/14 (open/switch/close/LRU cap/overflow/F5 restore).

#### Phase 2 — 2-pane split (implemented 2026-08-13, pending review)
- [x] Split action (Columns2 button) on patient tabs incl. overflow entries;
      pane B renders `SutPatientPageContent` (page extracted to a prop-driven
      component with `embedded` mode) — store-only, not in URL.
- [x] Pane header with swap + close split; activating pane B's tab moves it to
      pane A and clears the split.
- [x] Right-docked chat disabled while split active (dock buttons hidden,
      forced back to center). v1 scoping: panes share window scroll and pane B
      has no chat panel (synced scroll aids comparison).
- [x] Layout verified with sidebar var: Playwright 12/12 (split open/swap/
      close/refresh-restore × collapsed/expanded sidebar, no overlap).
- [ ] Keyboard additive Ctrl+\ for split (deferred; palette gets Ctrl+K).

#### Phase 3 — Quick-open palette (implemented 2026-08-13, pending review)
- [x] Ctrl+K (and Cmd+K) + visible Search trigger in the tab strip; debounced
      search over `/api/patients/search`; arrow-key navigation; Enter opens the
      patient as a tab; Escape/backdrop closes.
- [x] Playwright 9/9 (open/focus/search/Enter/trigger/Escape/arrow-nav).

### Out of Scope (v1)
- Drag-to-reorder tabs, drag-and-drop splitting, >2 panes, tab groups.
- Right-docked chat while split is active.
- Full localStorage persistence, multi-window sync.
- Mobile layouts (desktop-first product; < md gets the degraded dropdown).

### Definition of done
- Officer can: open 3 profiles from the list, switch with zero reload flicker,
  F5 and find them restored, split two side by side, and close everything
  back to the plain list — using only visible buttons.
- `npx tsc --noEmit`, `vitest run`, lint at baseline; Playwright layout matrix
  green; en/tr complete.
