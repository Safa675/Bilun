# Frontend Rebuild — Premium Identity Aligned to BILUN Investor Deck

## Goal

Replace the current "AI startup template" frontend with a quiet, dense, content-first design system that matches the investor deck `BILUN_EN.pptx`: navy + antique gold + cream + white, Fraunces serif display, Inter body, italic-gold accents on key words and headline amounts.

**Zero backend/data-logic changes.** Pure presentation rebuild.

## Why this rebuild

Current frontend reads as "AI slop" because:

1. **Emerald monoculture.** `#10B981` is the brand color, success color, hover color, page background tint, status chip color, and chart accent simultaneously. Premium SaaS reserves one color for one role.
2. **Stylesheet sediment.** Three parallel design systems coexist:
   - `frontend/src/app/globals.css` (1,406 lines) with `.frost-*`, `.glass-*`, `.app-*`, `.metric-*`
   - `frontend/src/app/styles/sut-premium.css` (775 lines) with `.sut-premium-*`, `.sut-landing-*`, `.sut-panel-*`
   - `frontend/src/app/styles/sut-how-modal.css` (~393 lines)
3. **"Premium" prefix in class names.** Real premium products never label themselves premium.
4. **Marketing inside the product.** Landing hero with four mint-tinted icon feature cards, hero copy "Restore the SUT shell around exact claim-line rule work".
5. **Dated chrome.** Glassmorphism (`backdrop-filter: blur`), radial gradient backgrounds, accent-tinted glow shadows, `pulseGlow`/`borderGlow`/`regime-glow` animations, hover lift.
6. **Self-explanatory copy** repeated inside working panels.
7. **Plus Jakarta Sans referenced in CSS but never loaded** via `next/font` — users see system-ui fallback.

## Design contract (locked)

### Palette (extracted from `BILUN_EN.pptx` `ppt/theme/theme1.xml` + slide XML usage counts)

| Token | Hex | Role |
|---|---|---|
| `--text-primary` | `#1A2638` | All H1–H3, primary body, table headers (deck usage: 98) |
| `--text-secondary` | `#3A4456` | Body text alt, subheadings (deck usage: 59) |
| `--text-muted` | `#8590A4` | Captions, muted labels, axis text (deck usage: 75) |
| `--text-disabled` | `#98A0AC` | Disabled, placeholder |
| `--text-inverse` | `#FFFFFF` | Text on navy/gold surfaces |
| `--surface-base` | `#FFFFFF` | Page background |
| `--surface-soft` | `#E5E2DA` | Cards, panels, table wrappers (deck cream) |
| `--surface-tint` | `#EFEAD8` | Chip fills, soft accents (lighter cream) |
| `--surface-overlay` | `rgba(26, 38, 56, 0.06)` | Hover/pressed tint |
| `--border-subtle` | `#E5E2DA` | Default border on cream surfaces |
| `--border-default` | `rgba(201, 178, 126, 0.20)` | Default border on white surfaces |
| `--border-strong` | `rgba(26, 38, 56, 0.13)` | Emphasis border |
| `--gold` | `#9C7A3E` | **The only action/focus/highlight color** (deck usage: 46) |
| `--gold-hover` | `#8B6A33` | Hover darken |
| `--gold-pressed` | `#735628` | Pressed darken |
| `--gold-light` | `#C9B27E` | Hover fill, gold border accent |
| `--gold-subtle` | `#EFEAD8` | Gold fill at low intensity |
| `--success` | `#2F6E4E` | Muted forest, never emerald, never confused with gold |
| `--warning` | `#B45309` | Status only |
| `--danger` | `#B91C1C` | Status only |
| `--info` | `#1A2638` | Info = primary text (no extra hue) |

### Typography

| Slot | Family | Weights | Where |
|---|---|---|---|
| Display + emphasis | **Fraunces** (variable, optical sizes, true italic) | 400, 500, 700 | H1 of each page (one word in italic gold), KPI headline money amounts |
| Body / UI | **Inter** | 400, 500, 600, 700 | Everything else |
| Numeric | Inter + `tabular-nums lining-nums` | — | Every money/count cell |

**Italic-gold serif accent rule:** maximum two uses per screen:
1. One word per H1 in Fraunces italic gold
2. The primary KPI money amount in Fraunces italic gold

Everywhere else: Inter, navy.

### Brand mark

Crescent moon shape from `BILUN_EN.pptx` slide 1 (upper-right of cover slide), navy `#1A2638` on white, paired with "BILUN" wordmark in Fraunces regular weight, navy.

### Surfaces

- Page background: pure white `#FFFFFF`
- Cards, panels, table wrappers: cream `#E5E2DA`
- Soft chips/fills: light cream `#EFEAD8`
- No glassmorphism, no `backdrop-filter`, no radial gradient backgrounds, no glow shadows

### Shadow + radius

```
--shadow-1  0 1px 0 rgba(26, 38, 56, 0.04)
--shadow-2  0 4px 12px rgba(26, 38, 56, 0.06)

--r-xs  4px
--r-sm  6px
--r-md  8px
--r-lg  12px
```

No accent-tinted shadows. No 32px hero radius.

### Motion

```
--ease  cubic-bezier(0.2, 0.8, 0.2, 1)
--dur   120ms
```

Applied to hover and focus only. Zero entry animations in workspace panels. The skip-link transition stays.

### Status semantics separate from brand

Status chips, badges, and alert backgrounds use `--success` / `--warning` / `--danger` only. Gold never indicates status. Navy never indicates status (it is text/structure).

## What gets deleted

- All `.frost-*`, `.glass-*`, `.sut-premium-*`, `.sut-panel-card`, `.sut-landing-*` class trees
- All radial gradient backgrounds (`.sut-app-main`, `.sut-premium-shell`)
- All accent-tinted shadows and `pulseGlow` / `borderGlow` / `regime-glow` / `dashboardEnter` / `sutPremiumEnter` / `skeletonSweep` keyframe animations
- Hover lift (`transform: translateY(-3px)`)
- `frontend/src/app/styles/sut-premium.css` (entire file)
- The 4-card marketing hero grid in `SutLandingHero`
- The amber full-row synthetic-data banner (demoted to a small top-bar chip)
- The green "Module label: BILUN" pill
- `colorScheme: "light"` lock in `layout.tsx` (replaced with explicit `light` theme color only, no lock)
- The `Plus Jakarta Sans` reference in `--font-sans` (replaced with Inter via `next/font/google`)

## Component primitives (Phase 1 deliverables)

| Primitive | Replaces | Notes |
|---|---|---|
| `Surface` | `.frost-panel`, `.glass-panel`, `.sut-premium-panel`, `.sut-panel-card` | Variants: `base` (white + border), `soft` (cream), `inset` (no border) |
| `Stat` | `.metric-card`, `.frost-kpi-card`, `KpiCard` shared component | Left-aligned, tabular-nums, optional Fraunces italic gold for headline money |
| `Eyebrow` | `.sut-muted-label`, `.sut-premium-eyebrow`, `.metric-label`, `.tab-intro-subtitle` | One uppercase microcopy primitive |
| `Section` | Ad-hoc panel wrappers inside `billing/page.tsx`, `PatientSection`, etc. | Title + optional total + body slot |
| `DataTable` | `.frost-table-wrap`, `.glass-table-wrap` | Sticky header, no row-zebra, denser padding |
| `Chip` | `.sut-status-chip`, `.badge-*` | One shape, semantic color tokens |
| `Tabs` | `.app-tab-button`, `.sut-home-nav-tab`, `.sut-section-btn` | Wraps Radix Tabs |
| `Toolbar` | Bespoke filter+search+paginate layouts | Search + filter + paginate |
| `BilunMark` | (new) | Crescent SVG, navy on white |
| `BilunWordmark` | The green "BILUN" pill | Fraunces wordmark, navy |

## Phase plan

### Phase 1 — Foundation (complete)

Tokens + fonts + primitives + verification sandbox at `/design-system`. No existing page changes. Lint, type-check, vitest (46/46), and `next build` all green.

### Phase 2 — Stylesheet collapse ✅ COMPLETE (2026-05-27)

- 105 dead classes deleted outright (audit-driven).
- `sut-premium.css` deleted; `globals.css` reduced 1463 → 158 lines.
- Live legacy classes re-platformed onto navy/gold/cream tokens in a new transitional `frontend/src/app/styles/legacy.css` (971 lines, scheduled to burn down across Phases 3–5).
- Removed everywhere: `backdrop-filter`, accent-tinted glow shadows, `translateY(-1/-3px)` hover lifts, `pulseGlow`/`borderGlow`/`regimeGlow`/`dashboardEnter`/`sutPremiumEnter` keyframes, gradient panel backgrounds.
- Verified: lint clean, `tsc --noEmit` clean, 46/46 vitest, `next build` succeeds, `/`, `/design-system`, `/patient/1`, `/patient/1/billing` all 200.

### Original Phase 2 spec (kept for reference)

Delete `sut-premium.css`, reduce `globals.css` to ≤200 lines (tokens + base + reset). Migrate every bespoke class usage to primitives + Tailwind utilities.

### Phase 3 — Landing / home reskin ✅ COMPLETE (2026-05-27)

- Deleted `SutLandingHero` + its 4 marketing cards.
- Added `AppTopBar` (BilunMark + wordmark + health chip + How-it-works) on `/`.
- New `SutWorkspaceLanding` with italic-gold serif H1 (`Billing rule <em>intelligence</em>`), patient search, recent patients + recent billing reports lists, tertiary nav row.
- Added `recents.ts` (localStorage, `useSyncExternalStore`-backed, dedupe + cap 8) + 10 tests.
- Patient detail + billing pages now call `recordRecent(...)` on mount.
- `?tab=analytics|optimizer` still routes to the legacy workspace view (Phase 5 reskin scope).
- Verified: lint, `tsc --noEmit`, 60 / 60 vitest, `next build` succeed; `/`, `/?tab=…`, `/patient/1`, `/patient/1/billing`, `/design-system` all 200.

### Phase 4 — Patient + billing reskin ✅ (2026-05-27)

`/patient/[id]` and `/patient/[id]/billing` rebuilt on primitives. Tighter KPI strip with `Stat`. Italic-gold serif treatment applied to one H1 word and primary money amount.

- `<AppTopBar>` lifted into `layout.tsx` — global brand bar on every route.
- `KpiCard` chrome stripped (kept API; 13 callers auto-upgrade to the new look).
- `SutPatientWorkspace`: H1 `Patient <em>workspace</em>` + mono patient-ID subtitle; gold-display `<Stat>` on "Diagnoses"; 4 optimization cards on cream `<Surface variant="soft">`; legacy `frost-panel sut-premium-glass` wrappers eliminated.
- `BillingSummary` (still a named export): H1 `Patient billing <em>report</em>` + gold-display `<Stat>` for `total_recoverable_try`. Other KPIs/section totals stay navy tabular (max-2-gold rule enforced).
- `BillingSectionShell` rewritten as `<Section>` wrapper — every section function picks up the new look without touching its body.
- All inline `color: ACCENT` on table savings cells swapped to navy tabular. `SutOptimizationSection`'s 4-card grid rebuilt with `<Surface variant="soft">` + `<Chip>`.
- Verified: lint, `tsc --noEmit`, 62 / 62 vitest, `next build` succeed; all 6 routes return 200; rendered-HTML audit confirms zero `frost-panel sut-premium-glass`, `frost-panel sut-premium-panel`, `sut-route-search-panel`, `sut-premium-error`, `glass-hover`, `sut-patient-id-title` on `/patient/*`.

### Phase 5 — Analytics + Optimizer + Chat reskin ✅ (2026-05-27)

`SUTAnalyticsShell`, `SUTOptimizerTab`, `SutInlineAIPanel` rebuilt on primitives. `CHART_COLORS` rewired to navy/gold/cream.

- New `SutWorkspaceHeader` replaces legacy `frost-panel sut-premium-panel sut-home-header` on `/?tab=…` (italic-gold H1 + `<Tabs>` for Analytics/Optimizer).
- `SUTAnalyticsShell` subtab bar migrated to compact `<Tabs>`.
- All 15 `sut/` tab files (`PatientSection`, `ToolsSection`, 12 section modules) migrated from `frost-panel`/`frost-card` to `<Surface>`.
- `SUTOptimizerTab` (1,223 lines): all panels on `<Surface>`/`<Section>`, filter/section nav on `<Tabs>`, `PIE_COLORS` → navy/gold/warning/danger, error panels on `<Chip>`.
- `SutInlineAIPanel`: dropped `frost-panel`/`sut-premium-enter`; chat chrome stays on tokenized `sut-chat-*` rules (Phase 6 can inline to Tailwind).
- `CHART_COLORS` in `constants.ts` + `CATEGORY_COLORS` in `shared.tsx` rewired to theme tokens (no emerald).
- `ChartTooltipContent` migrated off `frost-tooltip`.
- Skeletons migrated to `<Surface>`; slate hardcodes → token classes.
- `SutHealthPanel` admin strip reskinned.
- Dead code removed: `workspaceEntered` store field/hooks, `sutHomeShell.ts` + tests.
- Verified: lint, `tsc --noEmit`, 60 / 60 vitest, `next build` succeed; all 6 routes 200; workspace HTML audit shows zero `frost-panel`, `sut-premium`, `sut-home-*`, `sut-section-bar`.

### Phase 6 — Polish + audits ✅ (2026-05-27)

Tabular-nums sweep. Focus states audit. Iconography sweep. Synthetic provenance demoted to top-bar chip everywhere. Print stylesheet aligned.

- `SyntheticDemoChip` in global `AppTopBar`; inline provenance banners removed from landing, patient workspace, billing, analytics, optimizer.
- Emerald hardcodes removed (`#6EE7B7`, `text-emerald-700`, `#059669` in `error.tsx`); money/ICD cells use navy tabular tokens.
- Last JSX `frost-panel` usages removed (`error.tsx` → `<Surface>`, `SutHowItWorksModal`).
- `frost-table` → `<DataTable>` migration completed across billing + 12 section modules.
- `SutInlineAIPanel` fully on Tailwind; `sut-chat-*` legacy block deleted (~190 lines).
- Legacy burn-down: removed `sut-home-*`, `sut-synthetic-*`, `frost-table`, `sut-chat-*` from `legacy.css` (~350 lines).
- Print rules expanded in `globals.css` (hide top-bar chrome, white background, avoid chart/table breaks).
- Verified: lint, `tsc --noEmit`, 62 / 62 vitest, `next build` succeed.

## Out of scope

- Dark mode (locked to light only per direction)
- Backend changes
- Data logic changes
- API contract changes
- Test rewrites unless a primitive change breaks an existing snapshot

## Success criteria

- All pages render with the locked palette and typography
- Zero references to emerald `#10B981` remain in source
- Zero references to `.frost-*`, `.glass-*`, `.sut-premium-*` class names remain in TSX
- `globals.css` ≤ 200 lines; `sut-premium.css` deleted
- All money/count cells use `tabular-nums`
- The italic-gold-serif accent appears on H1 + primary KPI on every page that has one
- The crescent + Fraunces wordmark is the only brand surface in the top bar
- The frontend test suite still passes (`npm test` in `frontend/`)
