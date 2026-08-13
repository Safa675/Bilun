## Task: Ready or Not launch script in home dir

### Goal
Create `/home/safa/ready_or_not.sh` (Steam App 1144200) and get the game running. Diagnosis: game is NOT installed — only Steam library (`~/.steam/debian-installation`) has apps 1493710/4183110, no `appmanifest_1144200.acf` anywhere; `steam -applaunch` on an uninstalled title silently does nothing.

### Subtasks
- [x] Write install-aware launcher: parses `libraryfolders.vdf`, launches via `steam -applaunch` if manifest present, else opens `steam://install/1144200`
- [x] `chmod +x` and run it
- [x] Verify: Steam console log shows `ExecCommandLine`/`ExecuteSteamURL: steam://install/1144200` at 21:13:10 → install dialog delivered to running client
- [x] Report disk space requirement (~90 GB) and next steps

### Resolution (2026-08-13)
- "No licenses" error: account `safaksz` has NO license for app 1144200 — 0 hits in `config.vdf` license cache, and no `LaunchApp [AppID 1144200]` entry ever in Steam logs. Steam correctly refuses.
- Build is a RUNE repack, not official: `Engine/Binaries/ThirdParty/Steamworks/Steamv153/Win64/steam_api64.rne` (renamed original DLL — RUNE signature), no `steam_api64.dll` beside the exe, uniform 2026-08-04 extraction timestamps. It "worked with Steam in the past" by running OUTSIDE Steam's license check via its patched Steamworks layer — Steam itself never launched it.
- Earlier claim "official Steam build (signed installscript.vdf)" was WRONG: preserved depot files don't prove an uncracked build; decisive signals are the Steamworks layer + account license.
- BLOCKED on user decision: (a) buy on Steam (~$29, frequent sales) → adoption of the genuine 49 GB paks then works and Steam repairs the cracked files; (b) log into an account that owns it. Setting up the cracked build's launch is not something I will do.
- Game folder left in place at `Documents/steamapps/common/Ready or Not`; launcher script `/home/safa/ready_or_not.sh` stays (works once a license exists).

### Out of Scope
- Actually downloading/installing the ~90 GB game (needs user interaction + disk space)
- Proton configuration tuning

### Review (2026-08-13)
- Root cause of "game didn't start": Ready or Not (1144200) was never installed — only library (`~/.steam/debian-installation/steamapps`) contains apps 1493710/4183110; `steam -applaunch` on an uninstalled title silently does nothing.
- Script `/home/safa/ready_or_not.sh` is install-aware: parses `libraryfolders.vdf` for `appmanifest_1144200.acf`; launches if present, otherwise opens Steam install dialog. Verified via `console_log.txt` that the `steam://install/1144200` URL was dispatched to the running client.
- Blocker to flag to user: only 65 GB free on `/` (nvme0n1p2), game needs ~90 GB → free space or another drive required before Install can complete. Script was written outside the workspace, hence the one-time full-access escalation.
- Once installed, re-running the script will launch the game directly.

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
- Committed + pushed to PR #31 as `7b2b61f` after Safa's local review (2026-08-13).

---

## Task: IDE-style workspace shell (tabs + 2-pane split)

### Goal
Full design in `plans/frontend/ide-style-workspace-shell-plan.md`: editor-tab layer for multi-patient work + side-by-side comparison, with complexity guardrails. Direction locked with Safa 2026-08-13 (full IDE-style shell; solves both alternating and comparison).

### Subtasks
- [x] Phase 0: locked 2026-08-13 — all sections tabbed; sessionStorage persistence; 6-tab + 2-pane caps; chat-right disabled during split
- [x] Phase 1: implemented + verified 2026-08-13 (208 vitest, lint at baseline, Playwright 14/14); pending Safa's local review + commit/branch decision
- [x] Phase 2: implemented + verified 2026-08-13 (213 vitest, lint at baseline, Playwright 12/12)
- [ ] Phase 3: Ctrl+K patient quick-open palette

### Out of Scope
- Drag-reorder/drag-split, >2 panes, tab groups, multi-window sync, mobile layouts
