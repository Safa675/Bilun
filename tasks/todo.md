## Task: Frontend Premium SaaS Aesthetic Overhaul

### Goal
Transform the BILUN frontend from "competent internal tool" to "premium SaaS" by executing the prioritized action plan from the aesthetic evaluation. Done = a staff engineer and a designer would both say "this looks like a product, not a prototype."

### Phase 1 — Quick Wins (High impact, Low risk)
- [ ] 1. Top bar polish: increase height, shrink logo, upsize nav labels, add gold underline on active tab, separate zones
- [ ] 2. Page spacing: increase `sut-app-main` top-padding, add larger gaps between major section groups
- [ ] 3. KPI sizing: promote primary KPIs to `text-2xl`, cap grids at 4 columns
- [ ] 4. Quiet table headers: drop uppercase, reduce weight to `font-medium`, use `tracking-normal`
- [ ] 5. Gold discipline: remove gold from non-action contexts (KPI values, patient IDs at rest, "clear" status badges)
- [ ] 6. Login page: add logo image, increase form shadow, add brand presence

### Phase 2 — Structural Improvements (Medium risk)
- [ ] 7. Section grouping on patient page: wrap related billing sections into grouped containers
- [ ] 8. Button primitive: create `<Button>` component to replace `.sut-btn-*` classes
- [ ] 9. Chat panel polish: add message background tints, add panel shadow when docked
- [ ] 10. Empty state redesign: replace dashed borders with icon + text pattern
- [ ] 11. Select dropdowns: replace CSS triangle hack with proper icon

### Phase 3 — Polish
- [ ] 12. Staggered reveals on all page sections
- [ ] 13. Card hover states on interactive `Surface` components
- [ ] 14. Tab content crossfade animation
- [ ] 15. Scrollbar refinement
- [ ] 16. Typography scale: 3-tier heading sizes for page / section / sub-section

### Out of Scope
- No glassmorphism, glows, gradients, backdrop-blur, or entry animations in workspaces (per lessons.md)
- No component API changes that break tests (wrap internals, don't tear open)
- No new dependencies unless absolutely necessary
