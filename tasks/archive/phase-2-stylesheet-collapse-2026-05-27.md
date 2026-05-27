# Task: Phase 2 — Stylesheet Collapse

## Goal
Strip dated chrome (glassmorphism, glows, gradient backgrounds, hover lifts, enter-animations) from the global stylesheets and shrink `globals.css` to a tight token/base file, without breaking any existing page. All currently-used legacy classes are re-platformed onto the new navy/gold/cream tokens in a single transitional `legacy.css` that Phases 3–5 will burn down.

## Evidence-Based Inventory
Audit completed against `frontend/src` (excluding the design-system sandbox + the CSS files themselves):

- **CSS lines today**: `globals.css` 1463 + `sut-premium.css` 768 + `sut-how-modal.css` 403 = **2634 lines**
- **Distinct CSS classes defined**: 270
- **Dead classes (0 TSX refs)**: 105 → delete outright
- **Live classes (≥1 TSX ref)**: 165 → re-platform onto tokens, no chrome
- **Modal CSS** (`sut-how-modal.css`, 403 lines) is isolated to one component, scheduled for Phase 5 — leave untouched in Phase 2

## Subtasks

### Round A — Delete dead chrome rules from globals.css
- [ ] Delete `.app-shell`, `.app-header`, `.app-brand*`, `.app-tabs`, `.app-footer`, `.app-how-button` (~140 lines — unused)
- [ ] Delete `.tab-panel-animate`, `.tab-active`, `.tab-switch-*`, `.stagger-*`, `.dashboard-enter`, `@keyframes dashboardEnter`, `@keyframes pulseGlow`, `@keyframes borderGlow`, `@keyframes regimeGlow` (~150 lines)
- [ ] Delete `.regime-glow`, `.metric-pulse-glow-red`, `.metric-cue*`, `.metric-label-with-info` (~80 lines)
- [ ] Delete `.info-tooltip`, `.info-trigger`, `.info-popover*` (~75 lines)
- [ ] Delete `.chart-legend*`, `.pie-panel-*`, `.section-label-with-info`, `.section-heading-accent`, `.section-separator` (~70 lines)
- [ ] Delete `.explorer-filter-*` block (~150 lines — all unused)
- [ ] Delete `.nli-toolbar*`, `.nli-load-more` (~50 lines)
- [ ] Delete `.glass-light`, `.glass-strong`, `.glass-panel`, `.glass-hover`, `.glass-table*` (collapse into `.frost-*` aliases or drop)
- [ ] Delete `.tab-intro-frost`, `.tab-intro-header-row`, `.tab-intro-title`, `.tab-content-inner`, `.bg-overlay`
- [ ] Delete `.skeleton-pulse-{1,2,3}`, `.sut-link-btn`, `.sut-tab-summary`, `.frost-canvas`, `.sut-chat-panel-{left,right}`, `.sut-premium-kpi-strip`, `.sut-premium-shell`, `.sut-premium-success`, `.patient-hero-grid`, `.focus-ringable`, `.breadcrumb-bar`, `.kpi-grid`, `.metric-value`

### Round B — Strip chrome from live classes (no glassmorphism, no glow, no lift)
- [ ] `.frost-panel` / `.frost-table-wrap` / `.frost-table` / `.frost-tooltip` / `.frost-kpi-card`: remove `backdrop-filter`, remove `box-shadow` (replace with `--shadow-1`), remove `:hover { transform: translateY(...) }`, remove inset accent glow. Keep border + surface only.
- [ ] `.sut-premium-panel` / `.sut-premium-glass` / `.sut-premium-pill*` / `.sut-premium-error*` / `.sut-premium-subtitle` / `.sut-premium-eyebrow` / `.sut-premium-title` / `.sut-premium-warn`: token-only restyle (navy text, gold border on accent variants, no blur, no glow)
- [ ] `.sut-premium-enter`: replace animation with `opacity: 1` (no-op) — keeps the class harmless until Phase 3 removes it from JSX
- [ ] `.sut-section-btn` / `.sut-section-btn-active` / `.sut-section-btn-compact`: flat navy-on-cream, gold underline for active
- [ ] `.sut-input` / `.sut-btn-primary` / `.sut-btn-secondary` / `.sut-btn-icon`: token-based, no glow shadow
- [ ] `.sut-chat-*` (25 classes, 1 component): rewrite as a single quiet card block — no blur, no gradient
- [ ] `.sut-home-*` / `.sut-landing-*` / `.sut-hero-badges`: flat surfaces (landing-card hover lift removed; Phase 3 redesigns this section anyway)
- [ ] `.sut-breadcrumb*` / `.sut-status-chip` / `.sut-amount-accent` / `.sut-icon-accent` / `.sut-note-muted`: token restyle
- [ ] `.sut-route-search*` / `.sut-page-jump-control` / `.sut-filter-control` / `.sut-exactness-notice` / `.sut-synthetic-provenance*`: token restyle
- [ ] `.sut-app-main` / `.sut-app-title` / `.sut-patient-id-title` / `.sut-home-header` / `.sut-section-bar` / `.sut-section-description` / `.sut-section-divider*` / `.sut-muted-label`: token restyle
- [ ] `.sut-panel-card` / `.sut-panel-card-soft`: flat surface cards
- [ ] `.badge` + `.badge-{aaa,aa,a,bbb,bb,bccc}`, `.metric-card`, `.metric-label`, `.patient-id-link`, `.empty-state*`, `.loading-state*`, `.loading-spinner`, `.app-main` (kept) / `.app-select` / `.app-filter*` / `.app-tab-button` / `.tab-intro` / `.tab-intro-subtitle` / `.skeleton*`: token restyle, no glow
- [ ] Recharts overrides (`.recharts-*`): keep, retune grid/text to use `--color-grid` + `--color-text-muted`

### Round C — Reorganize files
- [ ] Move all Round-B re-platformed rules into a new `frontend/src/app/styles/legacy.css` (clearly labeled "transitional — burned down in Phases 3–5")
- [ ] Delete `frontend/src/app/styles/sut-premium.css` entirely
- [ ] Reduce `globals.css` to ≤200 lines: `@import "tailwindcss"`, `@import "./styles/legacy.css"`, the `@theme inline { }` token block, `*` reset, `html/body`, scrollbar, focus-visible default, base typography, Recharts overrides, skeleton shimmer
- [ ] Keep `sut-how-modal.css` untouched (Phase 5 scope)

### Round D — Verify
- [ ] `npm run lint` clean
- [ ] `npx tsc --noEmit` clean
- [ ] `npx vitest run` — 46/46 pass
- [ ] `npx next build` succeeds
- [ ] `curl http://localhost:3001/` returns 200 with new tokens, no emerald `#10B981`, no `backdrop-filter`, no `pulseGlow`/`borderGlow`/`regimeGlow` keyframes in compiled CSS
- [ ] `curl http://localhost:3001/design-system` still renders all primitives
- [ ] Spot-check `/`, `/patient/1/billing`, and analytics tabs render without console errors

## Out of Scope
- No JSX edits to `SutLandingHero`, `PatientSection`, `BillingPage`, `SutChatPanel`, etc. — those are Phases 3–5.
- No reskin of `sut-how-modal.css` — Phase 5.
- No new primitives added beyond what already exists.
- No design-token changes beyond what Phase 1 established.
- No deletion of class names that are still referenced in JSX (those move to `legacy.css`; their rules become flat/quiet).

## Definition of Done
- `sut-premium.css` is deleted.
- `globals.css` is ≤200 lines.
- All 105 dead classes are gone.
- No `backdrop-filter`, no `transform: translateY` on `:hover`, no accent-tinted glow shadows, no `pulseGlow`/`borderGlow`/`regimeGlow`/`dashboardEnter`/`sutPremiumEnter` keyframes anywhere in `frontend/src/app/styles/` or `globals.css`.
- All existing pages still build, type-check, lint, and render at HTTP 200.

---

## Review — Phase 2 complete (2026-05-27)

### Line counts
| File | Before | After | Δ |
|---|---:|---:|---:|
| `frontend/src/app/globals.css` | 1463 | **158** | −89% |
| `frontend/src/app/styles/sut-premium.css` | 768 | **0 (deleted)** | −100% |
| `frontend/src/app/styles/legacy.css` | — | **971 (new, transitional)** | +971 |
| `frontend/src/app/styles/sut-how-modal.css` | 403 | 403 | 0 (Phase 5 scope) |
| **Total** | **2634** | **1532** | **−42%** |

### What changed
- 105 unused legacy classes deleted outright (`.app-shell/header/footer/brand*`, `.tab-switch-*`, `.stagger-*`, `.regime-glow`, `.metric-pulse-glow-red`, `.metric-cue*`, `.info-popover*/trigger/tooltip`, `.chart-legend*`, `.pie-panel-*`, `.section-label-with-info`, `.section-heading-accent`, `.section-separator`, `.explorer-filter-*` block, `.nli-toolbar*`, `.tab-content-inner`, `.tab-intro-frost/header-row/title`, `.bg-overlay`, `.frost-canvas`, `.dashboard-enter`, `.skeleton-pulse-*`, `.sut-link-btn`, `.sut-tab-summary`, `.sut-chat-panel-{left,right}`, `.sut-premium-shell`, `.sut-premium-success`, `.sut-premium-kpi-strip`, `.patient-hero-grid`, `.kpi-grid`, `.breadcrumb-bar`, etc.).
- 165 live legacy classes re-platformed onto `--gold`/`--surface-*`/`--text-*`/`--border-*` tokens with chrome stripped.
- Removed keyframes: `pulseGlow`, `borderGlow`, `regimeGlow`, `dashboardEnter`, `sutPremiumEnter`, `tabFadeIn`, `fadeSlideUp`, `scaleIn`.
- Removed effects: every `backdrop-filter`, every `transform: translateY(-…)` hover lift, every accent-tinted glow `box-shadow`, every linear/radial gradient panel background.
- `globals.css` is now strictly: token block + base reset + scrollbar + focus-visible + skeleton + Recharts overrides. 158 lines, target was ≤200.

### Verification
- `npm run lint` — clean
- `npx tsc --noEmit` — clean
- `npx vitest run` — 19 files / **46 passing**
- `npx next build` — succeeds (5 routes prerender; bundles emit correctly)
- Dev server probe (`http://localhost:3001`):
  - `/` → HTTP 200
  - `/design-system` → HTTP 200
  - `/patient/1` → HTTP 200
  - `/patient/1/billing` → HTTP 200
  - Compiled CSS audit:
    - `--gold: #9c7a3e` defined, **81** `--gold` references
    - **0** `#10B981` (old emerald hex)
    - **0** `pulseGlow` / `borderGlow` / `regimeGlow` / `dashboardEnter` / `sutPremiumEnter`
    - **0** `translateY(-1px)` / `translateY(-3px)`
    - **2** remaining `backdrop-filter` hits — one is Tailwind's `.transition` utility *listing* it as transitionable (not applying blur), the other is `sut-how-modal.css` (intentionally kept; Phase 5 scope)
    - **1** `text-emerald-700` utility class remains, but aliased to `var(--gold-pressed)` — that's the planned alias bridge, retired in Phases 3–5 as components migrate to `text-[var(--gold-pressed)]` or primitives

### Burn-down list for Phases 3–5
The transitional `legacy.css` (971 lines) holds these class trees that pages still depend on. Each phase removes one cluster:

- **Phase 3 (landing reskin)** retires: `.sut-landing-*`, `.sut-hero-badges`, `.sut-home-header*`, `.sut-home-nav-*`, `.sut-home-info-link`, `.sut-home-tab-context`, `.sut-app-title`, `.sut-premium-title/-subtitle/-eyebrow/-pill*`
- **Phase 4 (patient/billing reskin)** retires: `.sut-breadcrumb*`, `.sut-route-search*`, `.sut-patient-id-title`, `.sut-panel-card{,-soft}`, `.sut-status-chip`, `.sut-exactness-notice`, `.sut-synthetic-provenance*`, `.sut-amount-accent`, `.sut-icon-accent`, `.sut-note-muted`, `.sut-section-bar/-description/-divider*`, `.metric-card`, `.metric-label`, `.frost-kpi-card`, `.patient-id-link`
- **Phase 5 (analytics/optimizer/chat reskin)** retires: `.sut-chat-*` (full block), `.sut-section-btn{,-active,-compact}`, `.sut-input`, `.sut-btn-*`, `.sut-filter-control`, `.sut-page-jump-control`, `.frost-panel`, `.glass{,-hover,-panel}`, `.frost-table*`, `.frost-tooltip`, `.sut-premium-panel/-glass/-enter/-error*/-warn`, `.app-tab-button`, `.app-select`, `.app-filter*`, `.tab-active`, `.tab-intro*`, `.app-main`, `.empty-state*`, `.loading-state/-spinner`, `.badge{,-aaa,...}`, `.sut-app-main`, `.sut-muted-label`
- **Phase 6 (polish)** also retires `sut-how-modal.css` after the modal is rebuilt with primitives.

### Notes
- The `legacy.css` import sits at the top of `globals.css`, which keeps the legacy bridge active until pages move off it. When the last class is retired in Phase 5/6, the `@import "./styles/legacy.css"` line in `globals.css` is removed and the file is deleted.
- Phase 2 was *strictly* CSS — zero changes to any JSX file. The visible effect is: pages look quieter (no blur, no glow, no gradient panels, no hover-lift on cards/tables, no enter animation), and any emerald accent is now gold.
