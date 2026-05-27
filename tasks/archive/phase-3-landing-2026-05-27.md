# Task: Phase 3 — Landing reskin

## Goal
Replace the 4-card marketing hero on `/` with a quiet, content-first "resume work" surface (brand bar + Fraunces italic-gold H1 + patient search + recent patients + recent billing reports + tertiary nav into Analytics / Optimizer / How-it-works). No data-logic changes; no backend changes; existing post-entry workspace view (`/?tab=analytics|optimizer`) is untouched (it's Phase 5).

## Specification (extracted, locked)

### Current state (audited)
- `frontend/src/app/page.tsx` has two render modes gated by `enteredWorkspace`:
  - **Pre-entry** (`enteredWorkspace=false`) → `<SutLandingHero>` (the 4-card marketing grid that the plan calls out as "AI slop").
  - **Post-entry** (`enteredWorkspace=true`, set by `?tab=` query or `localStorage["ilay-sut-workspace-entered"]==="1"`) → workspace header + tabs + Analytics/Optimizer.
- `<SutLandingHero>` renders: pills, synthetic-demo provenance, `sut-premium-title` H1 ("Restore the SUT shell around exact claim-line rule work."), subtitle, two CTAs ("Enter SUT workspace", "How it works"), and a 2×2 feature grid (`LANDING_CARDS`).
- There is **no global app header / brand bar** today. Brand is implicit (the workspace header repeats the BILUN word).
- There is **no recents persistence** — no `recentPatient*`, `PatientHistory`, or equivalent in the codebase.

### Available data (no new endpoints needed)
- `searchSutPatients(q, limit)` → search-as-you-type cohort search.
- `getHealthStatus()` → `{ status, patients, build_id, message? }`.
- `getSutPatients()` → full cohort with `patient_meta` (age/sex/comorbidities).
- Patient detail pages: `/patient/[id]` and `/patient/[id]/billing` exist and accept arbitrary IDs.

### Design decisions (locked before code)
1. **Cold open replaces the wall.** `/` (no `?tab=` query) always renders the new landing — the persisted `enteredWorkspace` flag no longer gates the landing. The flag remains in localStorage for backward compat but is no longer read on `/`. `?tab=analytics|optimizer` still routes to the workspace tabs. `useWorkspaceEntered` / `setWorkspaceEntered` calls on `/` are removed; the store action and `sutHomeShell.ts` helper stay (other code may import them and Phase 5 will clean up).
2. **AppTopBar lives on `/` only in Phase 3.** A new `<AppTopBar>` primitive is rendered above the landing hero. It contains `<BilunMark>` + `<BilunWordmark>` + a small health status dot + "How it works" link. Phase 4 lifts it into a shared shell when patient pages get rebuilt.
3. **Italic-gold serif accent rule.** The landing H1 reads `Billing rule *intelligence*` with "intelligence" in Fraunces italic gold (`var(--gold)`). All other landing text is Inter / navy / muted. One italic-gold word per page, per the design contract.
4. **Recents persistence is client-side localStorage.** New hook `useRecents(kind, limit)` reads/writes `bilun.recents.patient` and `bilun.recents.billing` (JSON arrays of `{ patientId, hospitalCode?, openedAt }`). Max 8 entries, dedupe by `patientId`, ordered newest-first. The hook is SSR-safe (returns `[]` before hydration).
5. **Tracking happens on the detail pages.** `/patient/[id]/page.tsx` and `/patient/[id]/billing/page.tsx` get a one-line `useEffect` that calls `recordRecent("patient" | "billing", patientId)` once on mount when `patientId` is non-empty. No other behavior changes on those pages.
6. **Recent panels render empty states.** First-time visitor sees `Recent patients` and `Billing reports` panels with a quiet `"No recent patients yet. Search above to start."` empty state — not the marketing wall.
7. **System health = a small chip in `AppTopBar`.** Dot color: green (`--success`) for `ready`, amber (`--warning`) for `building`, red (`--danger`) for `error`/`not_started`, muted (`--text-muted`) when unknown. Label reads `Cohort ready · 50 patients` or `Cohort building…` etc. Click does nothing in Phase 3 (Phase 6 adds the popover). Polls every 30s — same cadence as today's admin panel.
8. **Marketing copy removed.** The four `LANDING_CARDS` entries ("Exact SUT rule visibility", "Exactness-aware optimization", "Product-owned SUT assistant", "Patient-first workspace") are deleted along with `SutLandingHero.tsx`. The product no longer explains itself inside itself.
9. **`SutLandingHero.test.tsx` is replaced** with `SutWorkspaceLanding.test.tsx` that asserts the new landing renders the synthetic-demo provenance and the italic-gold accent.
10. **No reskin of the workspace header / tabs.** When `?tab=analytics` is in the URL, the page still renders the legacy workspace header (`.frost-panel.sut-premium-panel.sut-home-header`) — that's Phase 5's scope.

## Subtasks

### Round A — Recents persistence
- [ ] Create `frontend/src/lib/recents.ts` exporting `recordRecent`, `getRecents`, and a `useRecents` hook. SSR-safe. Schema: `{ patientId: string; openedAt: number }`, dedupe + sort. Storage keys `bilun.recents.patient` / `bilun.recents.billing`. Cap = 8 entries each.
- [ ] Unit test `frontend/src/lib/recents.test.ts`: dedupe, ordering, cap, SSR no-op.

### Round B — AppTopBar
- [ ] Create `frontend/src/components/shell/AppTopBar.tsx`: BilunMark (24px) + BilunWordmark + (optional, right-aligned) health chip + "How it works" link. Token-only styling. No legacy classes.
- [ ] Use the existing health polling pattern (call `getHealthStatus` once, then 30s interval). Tear down on unmount.

### Round C — Landing component
- [ ] Create `frontend/src/components/home/SutWorkspaceLanding.tsx` replacing `SutLandingHero`:
  - Hero row: eyebrow `BILUN` (gold), H1 `Billing rule <em>intelligence</em>` (italic gold on the last word), subtitle from `SUT_BRAND.heroDescription`, `<SyntheticDemoProvenance compact />`.
  - Patient search row: `<PatientSearch>` with `placeholder="Search a patient ID…"`. On select → push `/patient/{id}`.
  - Two-column "Recent" grid using `<Section>`/`<Surface>` primitives:
    - Recent patients (from `useRecents("patient")`) — patient ID, optional age/sex via cached meta if available, relative timestamp.
    - Recent billing reports (from `useRecents("billing")`) — patient ID, relative timestamp.
    - Empty state in each column.
  - Tertiary nav: three plain links / buttons → `Open SUT Analytics` (→ `/?tab=analytics`), `Open SUT Optimizer` (→ `/?tab=optimizer`), `How it works` (opens existing modal).
- [ ] Component is pure presentational + uses hooks; props: `onOpenHowItWorks`, `dataSource`, `onPatientSelect`, `onOpenTab`.

### Round D — Page integration
- [ ] Update `frontend/src/app/page.tsx`:
  - Render `<AppTopBar>` always on `/`.
  - When `?tab=` is absent → render `<SutWorkspaceLanding>` (no more workspace-entered gate).
  - When `?tab=analytics|optimizer` is present → keep the existing workspace header + tabs render path **unchanged** (Phase 5 scope).
  - Remove the `useWorkspaceEntered`/`setWorkspaceEntered`/`enterWorkspace` calls on `/`. Leave the store action defined for now; Phase 5 cleans it up.
- [ ] Update `frontend/src/app/patient/[id]/page.tsx`: one-line `useEffect(() => { recordRecent("patient", patientId); }, [patientId])`.
- [ ] Update `frontend/src/app/patient/[id]/billing/page.tsx`: same, but `recordRecent("billing", patientId)`.

### Round E — Cleanup & tests
- [ ] Delete `frontend/src/components/home/SutLandingHero.tsx`.
- [ ] Replace `SutLandingHero.test.tsx` with `SutWorkspaceLanding.test.tsx` (assert: synthetic-demo provenance present; italic-gold accent class present; recent-patients empty state copy present when localStorage is empty).
- [ ] Verify `/design-system` sandbox still references existing primitives only (no changes needed there).

### Round F — Verify
- [ ] `npm run lint`, `npx tsc --noEmit`, `npx vitest run` (must still be 46+ passing, with the new test replacing the old).
- [ ] `npx next build` clean.
- [ ] Dev server: `/`, `/?tab=analytics`, `/?tab=optimizer`, `/patient/1`, `/patient/1/billing` all 200.
- [ ] Compiled-CSS audit unchanged (no new `backdrop-filter`, no glow shadows, no emerald `#10B981`).

## Out of scope
- Reskin of `/patient/[id]` or `/patient/[id]/billing` (Phase 4).
- Reskin of the workspace header that renders when `?tab=` is present (Phase 5).
- Reskin of Analytics / Optimizer / Chat (Phase 5).
- Adding a global app shell to `layout.tsx` (deferred to Phase 4 once patient pages get rebuilt — avoids double-header glitches in Phase 3).
- Server-side recents persistence — Phase 3 is localStorage-only.
- Removing legacy `enteredWorkspace` store / `SUT_WORKSPACE_STORAGE_KEY` / `sutHomeShell.ts` — defer to Phase 5.
- Changing `SyntheticDemoProvenance` styling — Phase 6.

## Definition of Done
- `/` cold open renders the new landing — no 4-card marketing grid, no "AI slop" copy.
- The landing H1 has one italic-gold word ("intelligence") in Fraunces, on a white surface.
- The `AppTopBar` shows `[mark] BILUN ··· status chip · How it works` along the top of `/`.
- Recent patients + billing reports panels render correct data after visiting `/patient/X` and `/patient/X/billing`, persist across reloads.
- `SutLandingHero.tsx` is deleted; nothing imports it.
- `?tab=analytics`, `?tab=optimizer`, `/patient/[id]`, `/patient/[id]/billing` all still render at HTTP 200.
- Lint, types, vitest, and `next build` all clean.

---

## Review — Phase 3 complete (2026-05-27)

### What changed
| Action | File |
|---|---|
| New | `frontend/src/lib/recents.ts` — `recordRecent` + `getRecents` + `useRecents` hook (uses `useSyncExternalStore`, SSR-safe, dedupe + cap of 8) |
| New | `frontend/src/lib/recents.test.ts` — 10 cases |
| New | `frontend/src/components/shell/AppTopBar.tsx` — BilunMark + wordmark + health dot + How-it-works link |
| New | `frontend/src/components/home/SutWorkspaceLanding.tsx` — replaces SutLandingHero |
| New | `frontend/src/components/home/SutWorkspaceLanding.test.tsx` — 5 cases |
| Edit | `frontend/src/app/page.tsx` — render AppTopBar + new landing for cold open; `?tab=` gates workspace mode |
| Edit | `frontend/src/app/patient/[id]/page.tsx` — `recordRecent("patient", patientId)` on mount |
| Edit | `frontend/src/app/patient/[id]/billing/page.tsx` — `recordRecent("billing", patientId)` on mount |
| Delete | `frontend/src/components/home/SutLandingHero.tsx` (110 lines of marketing chrome) |
| Delete | `frontend/src/components/home/SutLandingHero.test.tsx` (replaced by new test) |

### Visual outcomes
- AppTopBar: `[crescent] BILUN ········· ● Cohort … · How it works` — flat white surface, subtle bottom border, no chrome.
- Hero: gold eyebrow `BILUN`, Fraunces H1 `Billing rule <em italic gold>intelligence</em>.`, navy subtitle. Confirmed in compiled HTML:
  - `<em class="font-normal italic" style="color:var(--gold)">intelligence</em>`
- Patient search front-and-center inside a `<Surface>` with "Open a patient workspace" eyebrow.
- Two `<Surface>` columns: `Recent patients` + `Recent billing reports` with quiet empty states.
- Tertiary nav inside a cream `<Surface variant="tint">`: "Or jump straight into · SUT Analytics · SUT Optimizer · How it works".
- Workspace mode (when `?tab=` is in URL) is **untouched** — Phase 5 reskins the header + tabs + Analytics/Optimizer.

### Behaviour
- `recordRecent` fires on `/patient/[id]` mount and on `/patient/[id]/billing` mount → entries appear in the landing's recent lists.
- The store is localStorage (`bilun.recents.patient`, `bilun.recents.billing`), survives reload, dedupes by patient ID, caps at 8.
- Cross-tab updates work via the native `storage` event; same-tab updates via a `bilun:recents-changed` custom event dispatched from `recordRecent`.
- The legacy `enteredWorkspace` localStorage gate is **no longer read** on `/`. The flag itself remains in storage for backward compat; Phase 5 deletes the store action and the helper.

### Verification
- `npm run lint` — clean (after fixing initial setState-in-effect lint by switching to `useSyncExternalStore`).
- `npx tsc --noEmit` — clean.
- `npx vitest run` — **60 / 60 passing** (was 46; +10 recents + 5 landing − 1 deleted hero test).
- `npx next build` — succeeds; 5 routes; static where applicable.
- Dev server probe:
  - `/` → 200
  - `/?tab=analytics` → 200
  - `/?tab=optimizer` → 200
  - `/patient/1` → 200
  - `/patient/1/billing` → 200
  - `/design-system` → 200
- Rendered HTML audit on `/`:
  - "Billing rule" present (1)
  - "intelligence" present in italic-gold em (1)
  - "Open a patient workspace" present (1)
  - "Recent patients" + "Recent billing reports" present (1 each)
  - "No recent patients yet" empty state present (1)
  - "BILUN application bar" topbar present (1)
  - Old marketing copy: 0 hits for "Restore the SUT shell", "Exact SUT rule visibility", "Exactness-aware optimization", "Product-owned SUT assistant", "Patient-first workspace", "Enter SUT workspace"

### Phase 3 → Phase 4 hand-off
The new landing exposes `SUT_BRAND.heroDescription` and `SUT_BRAND.moduleLabel` only. Phase 4 will:
1. Lift `<AppTopBar>` into `layout.tsx` (or a route group layout) so it shows on every page.
2. Rebuild `/patient/[id]` and `/patient/[id]/billing` on primitives (currently those still use `frost-panel`, `sut-premium-glass`, etc.).
3. Replace the workspace-mode header (`frost-panel sut-premium-panel sut-home-header sut-premium-enter`) — that's Phase 5.
