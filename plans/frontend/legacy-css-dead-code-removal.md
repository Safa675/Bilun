# legacy.css Dead Code Removal

## Goal

Prune ~40% of `legacy.css` (classes that are no longer referenced in any JSX/TSX file) while keeping all still-active class trees intact.

## Background

`legacy.css` is a transitional stylesheet (621 lines) created in Phase 2. It holds re-platformed rules that pages still depend on. Per `tasks/lessons.md`, the file is only deleted once all its imports are gone from JSX. That hasn't happened yet, but dead classes can be removed now.

## Dead classes — confirmed unreferenced

| Class family | Lines | Notes |
|---|---|---|
| `frost-panel`, `glass-panel`, `glass-hover`, `frost-tooltip` | ~15 | Replaced by `<Surface>` primitive |
| `sut-premium-panel`, `sut-premium-glass` | ~8 | Replaced by `<Surface>` |
| `sut-panel-card`, `sut-panel-card-soft` | ~10 | Replaced by `<Surface>` |
| `sut-premium-enter` | ~3 | Already a no-op |
| `sut-landing-*` (hero, grid, actions, card-grid, card, icon, card-title, card-body, badges) | ~70 | Landing page already reskinned |
| `sut-premium-eyebrow`, `sut-muted-label` | ~12 | Replaced by `<Eyebrow>` |
| `sut-premium-pill`, `sut-premium-pill-muted` | ~13 | Replaced by `<Chip>` |
| `sut-premium-title`, `sut-app-title`, `sut-patient-id-title` | ~15 | Replaced by Tailwind typography |
| `sut-premium-subtitle` | ~6 | Replaced by Tailwind |
| `sut-breadcrumb`, `sut-breadcrumb-link`, `sut-breadcrumb-separator`, `sut-breadcrumb-current` | ~20 | Breadcrumbs removed |
| `sut-route-search-panel`, `sut-route-search-grid`, `sut-route-search-control` | ~18 | Replaced by `<PatientSearch>` |
| `sut-icon-accent`, `sut-amount-accent`, `sut-note-muted` | ~5 | Not referenced |
| `sut-section-bar`, `sut-section-description` | ~10 | Replaced by `<Section>` primitive |
| `metric-card`, `frost-kpi-card`, `metric-label` | ~17 | Replaced by `<Stat>` primitive |
| `badge`, `badge-aaa`, `badge-aa`, `badge-a`, `badge-bbb`, `badge-bb`, `badge-bccc` | ~20 | Replaced by `<Chip>` |
| `app-filter`, `app-filter-label` | ~14 | Replaced by Tailwind |
| `app-tab-button`, `tab-active`, `tab-intro`, `tab-intro-subtitle` | ~25 | Replaced by `<Tabs>` primitive |
| `sut-premium-error`, `sut-premium-warn` | ~14 | Not referenced |
| **Total dead** | **~295 lines** | |

## Live classes — must stay

| Class family | Files using it |
|---|---|
| `sut-app-main`, `sut-app-top-bar` | `AppTopBar.tsx`, `page.tsx`, `patient/[id]/page.tsx` |
| `sut-input` | 7 section components |
| `sut-btn-primary`, `sut-btn-secondary`, `sut-btn-icon` | 3 section components |
| `sut-section-btn`, `sut-section-btn-active`, `sut-section-btn-compact` | 7 files |
| `sut-section-divider`, `sut-section-divider-label` | `ToolsSection.tsx` |
| `sut-status-chip` | `SutBillingReportSections.tsx` |
| `sut-exactness-notice` | `SutBillingReportSections.tsx` |
| `sut-filter-control`, `sut-page-jump-control` | `SUTOptimizerTab.tsx` |
| `patient-id-link` | `SUTOptimizerTab.tsx` |
| `glass`, `app-select`, `patient-search-input` | `PatientSearch.tsx`, `SUTOptimizerTab.tsx` |
| `loading-state`, `loading-spinner`, `empty-state`, `empty-state-text` | `DrgPricingSection.tsx`, `PatientSection.tsx` |

## Subtasks

- [ ] Delete all dead class blocks listed above from `frontend/src/app/styles/legacy.css`
- [ ] Update the Phase 2 contract comment at the top of legacy.css (adjust line count note)
- [ ] Run lint + typecheck (`npm run lint`, `npm run typecheck`)
- [ ] Run `npm run build` to verify no CSS references break
- [ ] Run `vitest` to ensure all tests pass
- [ ] Update `plans/frontend-rebuild.md` Phase 2 line-count reference if needed

## Out of Scope

- Deleting the `legacy.css` file entirely (imported by `globals.css`, ~15 class trees still alive)
- Removing the `@import "./styles/legacy.css"` line from `globals.css`
- Reskinning or migrating any of the 15 live class trees to Tailwind/primitives (that's Phase 5 work)
