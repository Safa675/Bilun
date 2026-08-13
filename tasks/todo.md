## Task: PR #31 polish — crescent logo, auto-collapse on dock-right, stale-CSS overlap fix

### Goal
On `experiment/collapsible-sidebar-shell`: (1) collapsed sidebar shows the half-moon crest from `Bilun Extras/Artwork/Logo/Nameless.png` instead of the letter "B"; (2) docking the chat right auto-collapses the sidebar; (3) eliminate the sidebar/main-content overlap, root-caused to a stale `.next` dev cache serving main-branch CSS (missing `body { padding-left: var(--shell-sidebar-width) }`).

### Subtasks
- [x] Root-cause overlap with Playwright measurements: `--shell-sidebar-width` set on `<html>` but served CSS lacked the sidebar rules (contained dead `data-sut-topbar` selectors) → stale `.next` cache
- [x] Copy `Nameless.png` → `frontend/public/brand/nameless.png`
- [x] AppSidebar: render crescent `<img>` (aspect 1236/1476) when collapsed instead of "B"
- [x] AppSidebar: auto-collapse when dock becomes `right` — reworked from a `useEffect` setState (which added a `react-hooks/set-state-in-effect` lint error) to a zustand store subscription via new `useNavigationStoreApi()`; mount-time case folded into the persisted-state read
- [x] Kill dev servers, `rm -rf frontend/.next`, restart
- [x] Re-measure with Playwright: 13/13 layout checks pass across dock center/right × collapsed/expanded; screenshots in /tmp/bilun-verify/
- [x] `npx tsc --noEmit` clean; `npx vitest run` 196/196; `npm run lint` identical to pre-change baseline (17 errors / 9 warnings, none new)

### Out of Scope
- Merging the PR or pushing (user reviews locally first)
- Re-expanding the sidebar when chat returns to center (auto-collapse only)
- pr_agent's dead-AbortController nit (separate decision)

### Review (2026-08-13)
- Overlap was NOT a source-code bug: `globals.css` already had `body { padding-left: var(--shell-sidebar-width) }` and `.sut-app-main` chat insets; the served bundle came from a stale `.next` cache. Clearing `.next` + clean restart fixed it.
- Auto-collapse semantics: docking right collapses the sidebar (including on mount if already docked); manual re-expand while docked right still works; returning to center does not auto re-expand (per plan).
- Verification stack used throwaway credentials generated via `src.bilun.api.auth.hash_password` injected through process env (process env overrides `frontend/.env.local` in Next.js), so no user secrets were read.
- Changed files: `frontend/src/components/shell/AppSidebar.tsx`, `frontend/src/stores/navigationContext.tsx` (new `useNavigationStoreApi`), `frontend/public/brand/nameless.png` (new asset). Left uncommitted for user review.
