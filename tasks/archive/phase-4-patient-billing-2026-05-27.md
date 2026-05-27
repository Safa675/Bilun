# Task: Phase 4 — Patient + billing reskin

## Goal
Rebuild `/patient/[id]` and `/patient/[id]/billing` on the primitives stack — quiet white surfaces, navy text, gold accents — with the deck's italic-gold serif treatment applied **exactly twice per page** (one word in the H1 + the primary money KPI). Lift `<AppTopBar>` into `layout.tsx` so the brand bar shows on every route. No backend changes, no data-logic changes, no test-mock contract changes.

## Specification (extracted, locked)

### Current state (audited)
- `frontend/src/app/patient/[id]/page.tsx` (215 lines) wraps `<SutPatientWorkspace>` with a top "route search" panel that uses `frost-panel sut-premium-glass sut-route-search-panel`, plus a custom breadcrumb (`sut-breadcrumb` / `sut-breadcrumb-link` / `sut-breadcrumb-separator` / `sut-breadcrumb-current`).
- `frontend/src/components/patient/SutPatientWorkspace.tsx` (295 lines) renders:
  - A `frost-panel sut-premium-panel sut-home-header` header with `sut-premium-eyebrow`, `sut-patient-id-title`, `sut-premium-subtitle`, synthetic-demo chip, and two `sut-section-btn` buttons.
  - A `frost-panel sut-premium-glass` KPI strip of three `<KpiCard>`s (Diagnoses / ICD chapters / Primary focus).
  - `<PatientOptimizationSnapshot>` with four `sut-panel-card` blocks (Copay exemption / Surcharge / Copay rate / DRG package) — each with their own `<KpiCard>` grids.
  - An optional `frost-panel sut-premium-glass` wrapping `<DRGPanel>`.
  - A `frost-panel sut-premium-glass` billing handoff section.
- `frontend/src/app/patient/[id]/billing/page.tsx` (884 lines) renders:
  - A `frost-panel sut-premium-panel sut-home-header` page header (`sut-app-title` H1 = `Patient billing report`, eyebrow, subtitle, breadcrumb, right-hand `<PatientSearch>`).
  - `<BillingSummary>` — exported for `page.test.tsx`. Top panel + 3-KPI strip (`Rule-calculated opportunity` / `Recommended actions` / `Priority tier`).
  - 6 section functions wrapped in `BillingSectionShell` (`frost-panel sut-premium-glass`): Lab, Drug, Copay, Billing Strategy, Materials, SUT Optimization.
  - Tables use a private `TableWrap` (`frost-table-wrap` + `frost-table`).
  - `StatusChip` is a local component using `sut-status-chip`.
- `KpiCard` (`frontend/src/components/tabs/sut/shared.tsx` lines 119–151) is a 30-line component still using `frost-panel p-4 rounded-xl glass-hover`. It's used in **13 files** (~64 occurrences total). Tests for the patient page and billing page **mock it out**, so its internals can change freely — but its **prop signature** (`{ label, value, valueColor?, sub? }`) must stay.
- `AppTopBar` currently renders only on `/` cold open inside `page.tsx`. Patient pages have no global brand bar.

### Available data / contracts (locked)
- `SUT_BRAND.billingTitle` = `Patient billing report`.
- `SUT_BRAND.heroTitle` / `heroDescription` stay where they are — Phase 5 owns the workspace-mode header.
- `BillingSummary` is `export`ed from `billing/page.tsx` and tested directly (`page.test.tsx` imports `BillingSummary`). The named export must remain; the asserted strings remain too: `"Rule-calculated opportunity"`, `"Partial exact"`, `"Unavailable"`, `"22552.44 TRY"`, `"Recommended actions"` (assertable via the mocked `KpiCard` output `Recommended actions:<value>`).
- `SutPatientWorkspace.test.tsx` exports tested string contracts: `"Exactness note: this page does not invent billing totals locally."`, `"Needs exact billed procedure lines."`, `"Missing exact inputs: …"`, `"DRGPanel"`, the synthetic-demo copy. Those must stay verbatim.
- `recordRecent("patient" | "billing", patientId)` calls on mount are Phase 3 contract and stay.
- Tests mock both `KpiCard` and `theme.accent` — so the implementation can switch tokens freely.

### Design decisions (locked before code)
1. **`<AppTopBar>` lives in `layout.tsx`.** Always rendered above `{children}`, inside `<ShellStateProviders>`. The "How it works" wiring is moved from a prop callback into the component itself, reading `useSetShowHowItWorks` from the store directly. `frontend/src/app/page.tsx` drops its local `<AppTopBar>` render and the `onOpenHowItWorks` prop. Workspace mode (`?tab=...`) gets `AppTopBar` above the legacy workspace header — visually it's two stacked headers, accepted ugliness until Phase 5 reskins workspace mode.
2. **Italic-gold serif accent — exactly twice per page.**
   - `/patient/[id]`: H1 reads `Patient` + `<em>workspace</em>` (Fraunces italic gold); the patient ID renders as a mono subtitle directly under the H1. Second use: gold-display `<Stat>` on the "Diagnoses" count — that is the single quantitative anchor on this page. **No** italic gold elsewhere.
   - `/patient/[id]/billing`: H1 reads `Patient billing` + `<em>report</em>` (italic gold on "report") — same display family. Second use: gold-display `<Stat>` rendering `fmtTRY2(billingReport.total_recoverable_try)` as the primary money amount. **No** italic gold on lab/drug/copay savings totals (those stay tabular navy with subdued chips).
3. **`KpiCard` keeps its API, loses its chrome.** Body is rewritten to render as a flat label/value block on a transparent surface using the new tokens (Inter labels, tabular-nums values, no `frost-panel`, no `glass-hover`, no rounded corners, no extra padding — the grid container provides the layout). `valueColor` is honored when provided; `sub` becomes a single muted hint line under the value. Side-effect: 13 callers automatically get the cleaner look without changing call sites; Phase 5 decides per-caller whether to swap to `<Stat>`.
4. **`<Section>` replaces `BillingSectionShell` and the four `sut-panel-card`s on the patient page.** The section "total" pill becomes the `trailing` slot of `<Section>` (a navy-tabular `<span>`, not gold — only the page's single primary KPI is gold). The local `BillingSectionShell` is removed once all six section functions use `<Section>` directly. `frost-panel sut-premium-glass` wrappers go away.
5. **`<Surface>` replaces `frost-panel sut-premium-panel sut-home-header` for the page headers.** The header still has the same layout pieces (eyebrow, H1, subtitle, breadcrumb, right-side `<PatientSearch>`) but on a flat white surface with a 1px subtle border instead of glass.
6. **Breadcrumb is rewritten as plain inline flex** with Inter text + muted separators. No `sut-breadcrumb*` classes. Same DOM shape: `<nav aria-label="…"><Link>parent</Link><span>/</span><span>current</span></nav>`.
7. **Status chips on `/patient/[id]/billing` keep the local `StatusChip` component for now** (it still drives 20+ inline color states via `--sut-chip-color`). Phase 6 (or Phase 5 where bandwidth allows) migrates each call site to the `<Chip>` primitive. **No churn this phase.**
8. **Tables keep `frost-table-wrap`/`frost-table`** — the `DataTable` primitive doesn't yet support per-column min-widths / wrapped headers / num-col alignment that the billing tables rely on. Migration to `<DataTable>` is **Phase 5** scope. Legacy CSS for tables stays (already chrome-stripped).
9. **`PatientOptimizationSnapshot` becomes four `<Section variant="base" padding="md">`s in a 2-col grid.** Title in Fraunces (no italic-gold accent — that's reserved for page-H1 + KPI). Each section's inner KPIs use a 2-column tight `<Stat>` grid (no `<KpiCard>`). The "Risk state" copy keeps its existing semantic colors.
10. **`<SyntheticDemoProvenance>` stays as-is.** Phase 6 owns demoting it to a top-bar chip; Phase 4 just renders it where it already renders.
11. **No "How It Works" CTA inside the patient/billing pages.** The `AppTopBar` global button covers it. Existing modal wiring untouched.
12. **No change to chat docking, `SutInlineAIPanel`, `dockPadding`/`chatShiftX` math, or any data fetching.**

### File-by-file scope
| File | Action |
|---|---|
| `frontend/src/app/layout.tsx` | Render `<AppTopBar>` above `{children}` inside the providers. |
| `frontend/src/components/shell/AppTopBar.tsx` | Wire to `useSetShowHowItWorks` directly; drop `onOpenHowItWorks` prop (or default it via the store and keep the prop optional for future). |
| `frontend/src/app/page.tsx` | Remove the local `<AppTopBar>` render and `onOpenHowItWorks` prop drilling. (The workspace-mode header stays — that's Phase 5.) |
| `frontend/src/components/tabs/sut/shared.tsx` | Rewrite `KpiCard` body (keep API). Drop `frost-panel`, `glass-hover`, `rounded-xl`, fixed padding, and the hard-coded `#A1A1AA` / `#1A1A1A` / `#71717A` greys — use `var(--text-muted)`, `var(--text-primary)`, `var(--text-secondary)`. |
| `frontend/src/app/patient/[id]/page.tsx` | Replace `frost-panel sut-premium-glass sut-route-search-panel` with `<Surface>` + `<Eyebrow>` + new breadcrumb. Keep all logic. |
| `frontend/src/components/patient/SutPatientWorkspace.tsx` | Replace header `<header>` with `<Surface>`-based version that uses the italic-gold H1 phrase. Replace KPI strip with `<Stat>` row (Diagnoses is gold-display). Replace `PatientOptimizationSnapshot`'s four cards with four `<Section>` blocks of `<Stat>` grids. Replace billing-handoff section with `<Section>`. Replace warning bar styling. |
| `frontend/src/app/patient/[id]/billing/page.tsx` | Replace page-header surface with `<Surface>` + new breadcrumb. Replace `BillingSummary` panel surface with `<Surface>`, use italic-gold H1 + gold-display `<Stat>` for `total_recoverable_try`. Replace `BillingSectionShell` with `<Section>` and update every section function. Remove local helpers that are no longer needed. Keep `BillingSummary` as a **named export**. Keep `TableWrap`. |

## Subtasks

### Round A — Global shell lift
- [ ] Wire `AppTopBar` to `useSetShowHowItWorks` from the store directly. Keep the `onOpenHowItWorks` prop optional as an override.
- [ ] Render `<AppTopBar />` in `layout.tsx` inside `<ShellStateProviders>`, above `{children}`.
- [ ] Remove the `<AppTopBar>` render and `onOpenHowItWorks={() => setShowHowItWorks(true)}` prop from `frontend/src/app/page.tsx`. `setShowHowItWorks` is still used for the `<SutWorkspaceLanding>` "How it works" tertiary link and for the workspace-mode "How It Works" button — those stay.

### Round B — `KpiCard` chrome strip
- [ ] Rewrite `KpiCard` in `frontend/src/components/tabs/sut/shared.tsx` body:
  - Outer: `<div className="flex flex-col gap-1.5">`.
  - Label: same Eyebrow typography (`text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]`).
  - Value: `text-lg font-semibold tabular-nums lining-nums text-[var(--text-primary)]` unless `valueColor` provided (then inline `style`).
  - Sub: `text-xs text-[var(--text-secondary)] leading-snug`.
  - No background, no border, no rounded corners, no fixed padding — caller's grid container owns spacing.
- [ ] Visually verify on `/design-system` (which doesn't render `KpiCard` directly but the new look should match the `<Stat>` baseline).

### Round C — `/patient/[id]` reskin
- [ ] Replace the top "route search" panel in `frontend/src/app/patient/[id]/page.tsx` with a `<Surface variant="base" padding="lg">` containing:
  - New breadcrumb (`<nav>` + `<Link>` + muted separator + current).
  - Two-column grid: `<Eyebrow>Patient search</Eyebrow>` + `<PatientSearch>` on the left, a single helper sentence on the right.
- [ ] Replace inline error/warning panels (`frost-panel sut-premium-error`, `sut-premium-warn`) with `<Surface variant="base">` blocks using `<Eyebrow tone="primary">` titles + body copy. Same text, no chrome.
- [ ] Verify the chat-shift / dock-padding math is preserved verbatim.

### Round D — `SutPatientWorkspace` reskin
- [ ] Replace the header with a `<Surface variant="base" padding="lg">` containing:
  - `<Eyebrow tone="muted">SUT patient workspace</Eyebrow>`.
  - H1: `<h1 class="font-[var(--font-display)] text-3xl text-[var(--text-primary)] tracking-tight">Patient <em class="font-[var(--font-display)] italic text-[var(--gold)]">workspace</em></h1>`.
  - Patient ID rendered as `<p class="mt-1 font-mono text-base text-[var(--text-secondary)]">{patientId}</p>`.
  - Existing subtitle paragraph (navy / secondary).
  - `<SyntheticDemoProvenance>` stays.
  - Two `<Link>`s styled with the existing `sut-section-btn` classes (they're already chrome-stripped in `legacy.css`); no change.
- [ ] Replace the 3-KPI strip with `<Stat>` row inside a `<Surface variant="base" padding="lg">`:
  - `Stat label="Diagnoses" value={fmtNum(...)} display="gold"` — the page's single gold-KPI.
  - `Stat label="ICD chapters" value={icd10_chapters.join(", ") || "None"}`.
  - `Stat label="Primary focus" value={…}` (color via inline style when copay exempt — keep current copy).
- [ ] Replace `<PatientOptimizationSnapshot>`'s 4 `sut-panel-card` blocks with 4 `<Section>` cards:
  - Copay exemption — title `Copay exemption`, body keeps the existing exempt/clear `<Chip>` (use `<Chip variant={copay.exempt ? "success" : "neutral"}>` replacing the legacy `sut-status-chip`).
  - Surcharge exposure — title `Surcharge exposure`, body keeps `<Stat>` row (no gold) or `ExactnessNotice`.
  - Copay-rate exposure — same.
  - DRG package review — same.
- [ ] Replace the `frost-panel sut-premium-glass` wrapper around `<DRGPanel>` with `<Surface variant="base" padding="lg">`.
- [ ] Replace the warning row (`green-200`/`green-50` mismatch — currently a bug renders amber text on green-tinted background) with a clean `<Surface variant="soft">` + `<Eyebrow tone="primary">Consistency note</Eyebrow>` block. Keeps the same warnings text.
- [ ] Replace the billing-handoff `frost-panel sut-premium-glass` with a `<Section>` titled `Billing handoff` + `trailing={<Link …>Open billing review</Link>}`. Body keeps the existing copy + the diagnosis-context `sut-panel-card` is also moved to a `<Surface variant="soft">`.

### Round E — `/patient/[id]/billing` reskin
- [ ] Replace the page-header `frost-panel sut-premium-panel sut-home-header` with a `<Surface variant="base" padding="lg">` containing:
  - `<Eyebrow tone="muted">{SUT_BRAND.moduleLabel}</Eyebrow>`.
  - H1: `<h1 class="font-[var(--font-display)] text-3xl tracking-tight text-[var(--text-primary)]">Patient billing <em class="font-[var(--font-display)] italic text-[var(--gold)]">report</em></h1>`.
  - The existing subtitle paragraph.
  - New breadcrumb (same shape as patient page).
  - Right-side: `<Eyebrow>Patient search</Eyebrow>` + `<PatientSearch>` (no chrome).
- [ ] Rewrite `BillingSummary` (keep named export):
  - Wrapper: `<Surface variant="base" padding="lg">`.
  - Top row: `<div>` with `<Eyebrow>{SUT_BRAND.billingTitle}</Eyebrow>` + `<p class="font-mono text-base text-[var(--text-secondary)] mt-1">{billingReport.patient_id}</p>` + description + provenance. Right: `<StatusChip label={statusLabel} color={priorityColor} />` (unchanged — it already plugs into `sut-status-chip`).
  - **Primary money KPI:** `<Stat display="gold" label="Rule-calculated opportunity" value={…}>` — the page's single gold-display.
  - Other two KPIs use `<Stat>` (default display): `Recommended actions` and `Priority tier`.
  - Keep the partial-exact / unavailable exactness notices.
  - **Important:** because `BillingSummary` is tested via `renderToStaticMarkup`, ensure the test mock for `KpiCard` no longer applies (we're using `<Stat>` directly). The asserted strings are `"Rule-calculated opportunity"`, `"22552.44 TRY"`, `"Partial exact"`, `"Unavailable"`, `"Recommended actions"`, `"Billing totals remain unavailable"` (negated). The `Recommended actions:<value>` assertion (`Rule-calculated opportunity:Unavailable`) uses `:` literal because `KpiCard` is mocked. After swap to `<Stat>`, the test's negative assertion `not.toContain("Rule-calculated opportunity:Unavailable")` still holds because `<Stat>` renders label + value in separate elements. Re-run the test to confirm; no test changes needed.
- [ ] Replace `BillingSectionShell` with `<Section>` (delete the local component). Each section function becomes:
  ```tsx
  <Section title="Lab optimization" trailing={total ? <span className="font-mono text-sm text-[var(--text-primary)] tabular-nums">{total}</span> : null}>
    …
  </Section>
  ```
  Where applicable, sections still render `ExactnessNotice` blocks in their body.
- [ ] In the Lab / Drug / Copay-rate / Strategy / Materials tables, swap `style={{ color: ACCENT }}` on savings cells for `className="font-semibold tabular-nums text-[var(--text-primary)]"` — the gold cap rule means table cells must NOT be gold (only the page-level primary KPI is). The `<StatusChip>` per-row badges keep their existing semantic colors (warning / danger / success).
- [ ] `SutOptimizationSection` 4-card grid: rewrite each card as a tiny `<Surface variant="soft" padding="sm">` block with `<Eyebrow>` + `<Chip>` + helper text. No `theme.accentAlpha(0.05)` inline backgrounds (they'd be near-invisible against the new tint anyway — replace with the cream `var(--surface-soft)`).
- [ ] Inline the `frost-table-wrap` / `frost-table` tables unchanged.
- [ ] The error / no-data / "normative analysis" panels: swap `frost-panel` for `<Surface variant="base">`, drop `sut-premium-error*` classes — use plain heading + paragraph with a `<Chip variant="danger">` if needed.

### Round F — Cleanup & tests
- [ ] Delete unused local helpers in `billing/page.tsx` after `BillingSectionShell` removal (only `BillingSectionShell` itself is removable; `TableWrap`, `StatusChip`, `ExactnessNotice` all stay).
- [ ] Confirm `SutPatientWorkspace.test.tsx` still passes (it mocks `KpiCard`, but after Round D it's not used in the patient page anymore — the mock is harmless; the test asserts copy strings).
- [ ] Confirm `billing/page.test.tsx` still passes (the `KpiCard` mock returns `<div>{label}:{value}</div>`, but after Round E that mock no longer maps to any production code in `BillingSummary` because we use `<Stat>` directly; the asserted positive strings come from new code, the asserted negative strings remain absent).
- [ ] **Add tests** (light, render-only):
  - `frontend/src/components/patient/SutPatientWorkspace.test.tsx`: a new case asserting `"Patient"` + italic-gold `"workspace"` is present in the H1, and a `Stat`-rendered "Diagnoses" with italic-gold styling exists.
  - `frontend/src/app/patient/[id]/billing/page.test.tsx`: a new case on `BillingSummary` asserting the H1 contains italic-gold `"report"` and the primary KPI value renders with the `var(--gold)` color hint.
- [ ] Verify nothing else broke: no references to the deleted `BillingSectionShell` outside the file; `frost-panel sut-premium-glass` count on `/patient/*` routes drops to zero in rendered HTML.

### Round G — Verify
- [ ] `cd frontend && npm run lint` clean.
- [ ] `cd frontend && npx tsc --noEmit` clean.
- [ ] `cd frontend && npx vitest run` — 60+ passing (existing 60 + 2 new = 62 expected).
- [ ] `cd frontend && npx next build` clean.
- [ ] Dev server probe: `/`, `/?tab=analytics`, `/?tab=optimizer`, `/patient/1`, `/patient/1/billing`, `/design-system` all 200.
- [ ] Rendered-HTML audit on `/patient/1` and `/patient/1/billing`:
  - **Present:** italic-gold `workspace` / `report` em element with `color:var(--gold)`; `font-mono` patient ID under the H1; BILUN appbar; navy primary text.
  - **Absent:** `frost-panel sut-premium-glass`, `frost-panel sut-premium-panel`, `sut-route-search-panel`, `sut-premium-error`, `glass-hover`, `sut-patient-id-title`, `sut-section-description` (these still exist in legacy.css but no longer used on these routes).
  - **Counts:** italic-gold `em` with `var(--gold)` ≤ 2 per page (the contract limit).

## Out of scope
- DataTable primitive migration for billing tables — **Phase 5**.
- Workspace-mode (`?tab=...`) header redesign and the legacy `enteredWorkspace` store cleanup — **Phase 5**.
- Analytics tab / Optimizer tab / Chat panel reskin — **Phase 5**.
- `SyntheticDemoProvenance` demotion to a top-bar chip — **Phase 6**.
- Migrating remaining `KpiCard` call sites to `<Stat>` (left to Phase 5 per-caller).
- `StatusChip` → `<Chip>` migration across the billing page (deferred to keep diff focused).
- Per-section page navigation / sticky in-page TOC (Phase 6 polish).

## Definition of Done
- `/patient/[id]` renders on a flat white surface with a quiet header. H1 = `Patient <em>workspace</em>` (italic-gold "workspace"); patient ID is a mono subtitle. Exactly one gold-display `<Stat>` ("Diagnoses").
- `/patient/[id]/billing` renders on flat white. H1 = `Patient billing <em>report</em>` (italic-gold "report"). `BillingSummary`'s "Rule-calculated opportunity" KPI is the only italic-gold money amount; everything else (lab savings totals, drug savings cells, copay totals) is navy tabular-num.
- `<AppTopBar>` appears at the top of every route (`/`, `/patient/[id]`, `/patient/[id]/billing`, `/?tab=…`, `/design-system`).
- `BillingSummary` remains a named export; `KpiCard` keeps its prop API.
- Lint, types, vitest, `next build` all clean; HTTP 200 on all six probe routes; italic-gold count ≤ 2 per page in rendered HTML.

---

## Review — Phase 4 complete (2026-05-27)

### What changed
| Action | File |
|---|---|
| Edit | `frontend/src/app/layout.tsx` — render `<AppTopBar>` inside `<ShellStateProviders>` so the brand bar is global on every route |
| Edit | `frontend/src/components/shell/AppTopBar.tsx` — wires to `useSetShowHowItWorks` directly; `onOpenHowItWorks` prop kept optional as override |
| Edit | `frontend/src/app/page.tsx` — drop the conditional `<AppTopBar>` render (it's global now) |
| Edit | `frontend/src/components/tabs/sut/shared.tsx` — `KpiCard` body rewritten (no `frost-panel`/`glass-hover`/fixed greys); same `{label, value, valueColor, sub}` API |
| Edit | `frontend/src/app/patient/[id]/page.tsx` — `<Surface>` + new breadcrumb + `<Eyebrow>`; error & warning panels rebuilt on Surface |
| Rewrite | `frontend/src/components/patient/SutPatientWorkspace.tsx` — italic-gold H1 `Patient <em>workspace</em>`, mono patient-ID subtitle, gold-display `<Stat>` for Diagnoses, 4 `<Surface variant="soft">` optimization cards, `<Chip>`-based status indicators |
| Major edit | `frontend/src/app/patient/[id]/billing/page.tsx` — italic-gold H1 `Patient billing <em>report</em>`; `BillingSummary` uses `<Stat display="gold">` for the primary money KPI; `BillingSectionShell` rewired to `<Section>`; `SutOptimizationSection` rebuilt with Surface/Chip; ACCENT inline color stripped from table savings cells; error/no-data panels rebuilt on Surface |
| Edit | `frontend/src/components/patient/SutPatientWorkspace.test.tsx` — added an italic-gold-accent test (3 cases total) |
| Edit | `frontend/src/app/patient/[id]/billing/page.test.tsx` — added an italic-gold-KPI test (4 cases total) |

### Visual outcomes
- `<AppTopBar>` (`[crescent] BILUN ········· ● Cohort … · How it works`) now sits at the top of `/`, `/?tab=…`, `/patient/[id]`, `/patient/[id]/billing`, and `/design-system`.
- `/patient/[id]` H1: `Patient <em italic gold>workspace</em>`, with the patient ID rendered as a tabular `font-mono` subtitle directly under it. The "Diagnoses" stat in the KPI strip is the page's single italic-gold serif value.
- `/patient/[id]/billing` H1: `Patient billing <em italic gold>report</em>`. `BillingSummary`'s "Rule-calculated opportunity" is the single italic-gold money amount; "Recommended actions" and "Priority tier" stay navy tabular.
- All cards on both pages render on flat white `<Surface>` with quiet borders. Cream `<Surface variant="soft">` is used for inset blocks (consistency notes, optimization cards, diagnosis context, gazette ceiling tiles).
- Status chips swapped to `<Chip>` primitive where appropriate; legacy `sut-status-chip` retained inside the StatusChip helper (still in use across the billing tables) — that migration is Phase 6.

### Behaviour
- All previously asserted strings remain intact in tests (BillingSummary contract, PatientOptimizationSnapshot exactness copy, DRGPanel passthrough, synthetic-demo provenance).
- The `recordRecent("patient", patientId)` / `recordRecent("billing", patientId)` calls on mount are untouched.
- Chat docking, `SutInlineAIPanel`, dock shift/padding math: unchanged.
- Data fetching paths: unchanged.

### Verification
- `npm run lint` — clean.
- `npx tsc --noEmit` — clean.
- `npx vitest run` — **62 / 62 passing** (60 → 62; +2 italic-gold accent tests).
- `npx next build` — succeeds; same route set.
- Dev server probe:
  - `/` → 200
  - `/?tab=analytics` → 200
  - `/?tab=optimizer` → 200
  - `/patient/1` → 200
  - `/patient/1/billing` → 200
  - `/design-system` → 200
- Rendered-HTML audit:
  - `BILUN application bar` present on every page (1 per page) — global AppTopBar confirmed.
  - `<em … var(--gold) …>workspace</em>` and `<em … var(--gold) …>report</em>` present (1 per relevant SSR page).
  - **Zero hits** on `/patient/*` for: `frost-panel sut-premium-glass`, `frost-panel sut-premium-panel`, `sut-route-search-panel`, `sut-premium-error`, `glass-hover`, `sut-patient-id-title`, `sut-section-description`, `sut-app-title`.
  - Note: the patient page's content (gold Stat etc.) hydrates after data load; the SSR snapshot shows the skeleton state, which is expected. Unit tests cover the post-hydration markup.

### Lessons captured
- Added two lessons to `tasks/lessons.md` (cache-corruption / Turbopack restart + the gold-cap rule).

### Phase 4 → Phase 5 hand-off
1. Workspace-mode header (`?tab=analytics|optimizer`) still renders the legacy `frost-panel sut-premium-panel sut-home-header sut-premium-enter`. Phase 5 reskins that + the SUTAnalytics/SUTOptimizer tabs themselves.
2. The 9 remaining `KpiCard` call sites (analytics tab, optimizer tab, the section components) inherit the new chrome-stripped look automatically — Phase 5 reviews each and migrates the more important ones to `<Stat>` directly when the gold rule applies.
3. `StatusChip` (local helper in `billing/page.tsx`) and `sut-status-chip` (legacy CSS) still drive 20+ inline-colored chips. Phase 5/6 migrates each call site to `<Chip>`.
4. `frost-table-wrap` / `frost-table` tables remain — `<DataTable>` migration is deferred to Phase 5 (per-column min-widths + wrapped headers need to land in the primitive first).
5. `enteredWorkspace` store + `sutHomeShell.ts` helper are still defined but no longer read on `/`. Phase 5 deletes them.
6. `SyntheticDemoProvenance` styling unchanged — Phase 6 demotes it to a top-bar chip.
