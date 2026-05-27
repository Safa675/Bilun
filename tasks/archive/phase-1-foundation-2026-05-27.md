## Task: Frontend Rebuild — Phase 1 Foundation

### Goal
Land the navy/gold/cream design tokens, load Fraunces + Inter via `next/font`, and ship 10 component primitives + a verification sandbox route — without touching any existing page yet.

**Full spec:** [plans/frontend-rebuild.md](../plans/frontend-rebuild.md)

### Subtasks

#### 1. Font wiring
- [x] Wire **Fraunces** via `next/font/google` in `frontend/src/app/layout.tsx` with `variable: "--font-display"`, weights `400 500 700`, italic enabled
- [x] Wire **Inter** via `next/font/google` in `frontend/src/app/layout.tsx` with `variable: "--font-sans"`, weights `400 500 600 700`
- [x] Apply both font variables to `<html>` className so they cascade to the whole tree
- [x] Verified via compiled CSS: `--font-display: "Fraunces"`, `--font-sans: "Inter"` both emitted

#### 2. Design tokens
- [x] Replace the `@theme inline` block at the top of `frontend/src/app/globals.css` with the navy/gold/cream tokens from `plans/frontend-rebuild.md`
- [x] Add `--gold` / `--gold-hover` / `--gold-pressed` / `--gold-light` / `--gold-subtle`
- [x] Add `--success` / `--warning` / `--danger` / `--info` (status separate from brand)
- [x] Add `--font-display` reference for Fraunces
- [x] Remove emerald `--color-accent` / `--color-accent-dark` raw values (kept as aliases pointing at `--gold` to bridge Phase 1 → 2 without breaking legacy `.frost-*` rules)
- [x] Remove `--color-glass-border-accent` raw (aliased to `--gold-light` bridge)
- [x] Remove radial gradient backgrounds from `.sut-app-main` and `.sut-premium-shell` in `sut-premium.css`

#### 3. Layout unlock
- [x] Remove `colorScheme: "light"` lock in viewport export
- [x] Update `themeColor` from `#FAFAF9` to `#FFFFFF`
- [x] Update `frontend/src/lib/theme.ts` to expose navy + gold tokens (legacy `accent` / `accentDark` kept as deprecated aliases pointing at gold)

#### 4. Brand mark
- [x] `frontend/src/components/brand/BilunMark.tsx` — crescent SVG via mask, `currentColor`, traced from `BILUN_EN.pptx` slide 1 cover
- [x] `frontend/src/components/brand/BilunWordmark.tsx` — Fraunces wordmark, navy, optional mark

#### 5. Component primitives
- [x] `frontend/src/lib/cn.ts` — added `cn()` helper using `clsx` + `tailwind-merge` (deps already installed, never used before)
- [x] `Surface.tsx` — variants `base` / `soft` / `tint` / `inset` / `raised`
- [x] `Stat.tsx` — `display="gold"` renders value in Fraunces italic gold
- [x] `Eyebrow.tsx` — tones `muted` / `gold` / `primary`
- [x] `Section.tsx` — supports `titleAccent` for italic-gold word in H1
- [x] `DataTable.tsx` + `DataTableHeader/Row/Cell/HeaderCell/Body` — sticky header, tabular-nums
- [x] `Chip.tsx` — variants `neutral` / `success` / `warning` / `danger` / `gold` / `outline`
- [x] `Tabs.tsx` — Radix Tabs wrapper, gold underline indicator
- [x] `Toolbar.tsx` — leading / children / trailing slots
- [x] `index.ts` — barrel export

#### 6. Verification sandbox
- [x] Create `frontend/src/app/design-system/page.tsx` — a non-linked route that renders every primitive in every variant, side-by-side, on a white background  *(folders starting with `_` are private in Next 16; renamed.)*
- [x] Includes: 13-token palette swatch grid, type scale (Fraunces display + Inter body), all 10 primitives in all variants, italic-gold treatment demo, focus state demo, brand mark on light + dark

#### 7. Smoke + verify
- [x] `npm run lint` — 0 errors, 0 warnings
- [x] `npx tsc --noEmit` — 0 errors
- [x] `npx vitest run` — 19 files, **46/46 passed**
- [x] `npx next build` — production build succeeds
- [x] `next dev -p 3001` — both `/` and `/design-system` return HTTP 200
- [x] Compiled CSS verified: `--text-primary: #1a2638`, `--gold: #9c7a3e`, `--surface-soft: #e5e2da`, `--font-display: "Fraunces"`, `--font-sans: "Inter"` all present
- [x] Zero `#10B981` emerald references in compiled output (legacy alias `--color-accent` now resolves to `--gold`)

### Out of Scope (Phase 1)
- Modifying any existing page (`/`, `/patient/[id]`, `/patient/[id]/billing`, analytics, optimizer)
- Deleting `sut-premium.css` or any bespoke class (Phase 2)
- Reskinning `SutLandingHero`, `SutInlineAIPanel`, `PatientSection`, `BillingSummary` (Phases 3–5)
- Dark mode (locked off per direction)
- Backend, data, API changes

### Review

**Status:** Phase 1 complete. Foundation laid; no existing page touched.

**What was built**
- 13-token palette + typography + radius + shadow + motion tokens, sourced directly from `BILUN_EN.pptx` theme XML
- Fraunces (display) + Inter (body) loaded via `next/font/google`, exposed as CSS variables `--font-display` / `--font-sans`
- `BilunMark` (crescent SVG mask) + `BilunWordmark` (Fraunces + crescent) brand components
- 10 component primitives in `frontend/src/components/primitives/` with a `cn()` helper that uses the already-installed `clsx` + `tailwind-merge`
- Verification sandbox at `/design-system` rendering every primitive in every variant

**Verification gates passed**
- ESLint: 0 errors, 0 warnings
- TypeScript: 0 errors
- Vitest: 46/46 tests pass (every prior test green)
- Production build (`next build`): succeeds, no new routes break
- Dev server: `/` (HTTP 200) + `/design-system` (HTTP 200), no SSR errors
- Compiled CSS: navy, gold, cream, both fonts present; no emerald `#10B981`

**Known carryovers for Phase 2/4**
- Two `text-emerald-700` Tailwind utilities in `frontend/src/components/tabs/sut/PatientSection.tsx` still render native Tailwind emerald — will be swept during page reskin (out of Phase 1 scope)
- Legacy CSS class trees (`.frost-*`, `.glass-*`, `.sut-premium-*`, `.sut-panel-card`, `.sut-landing-*`) still resolve to the new tokens via alias bridge — full deletion is Phase 2
- `sut-premium.css` (775 lines) and the bulk of `globals.css` (1,406 lines) untouched outside the token block + gradient strip — Phase 2 collapse
- Existing pages (`/`, `/patient/[id]`, `/patient/[id]/billing`, analytics, optimizer) render with the new tokens but retain their old layout — Phases 3/4/5

**Sandbox URL for human review**
- `http://localhost:3001/design-system` while `next dev -p 3001` is running
- Fraunces serif + italic-gold-accent rendering, primitive variants, palette swatches all visible there

**Lessons captured**
- `tasks/lessons.md` initialized with three rules: plan-before-code (§7), premium-UI-is-quiet, verify-font-loading-don't-just-declare-CSS-variable

