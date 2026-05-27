# Task: Phase 5 — Analytics + Optimizer + Chat reskin

## Goal
Reskin workspace mode (`/?tab=analytics|optimizer`), the Analytics/Optimizer tab bodies, and the inline chat panel on the primitives stack. Rewire chart colors to navy/gold/cream. Delete dead `enteredWorkspace` code.

## Definition of Done
- [x] Workspace header on `/?tab=…` uses `SutWorkspaceHeader` (Surface + italic-gold H1 + Tabs)
- [x] `SUTAnalyticsShell` uses compact Tabs for Patient SUT / Reference Tools
- [x] All `sut/` tab modules migrated off `frost-panel` / `frost-card`
- [x] `SUTOptimizerTab` reskinned (Surface, Section, Tabs, Chip, Stat; PIE_COLORS updated)
- [x] `SutInlineAIPanel` drops `frost-panel` / `sut-premium-enter`
- [x] `CHART_COLORS` + `CATEGORY_COLORS` use theme tokens
- [x] Skeletons + `SutHealthPanel` on Surface
- [x] Dead `workspaceEntered` / `sutHomeShell` removed
- [x] lint / tsc / vitest (60) / build / 6-route probe / HTML audit clean

---

## Review — Phase 5 complete (2026-05-27)

### What changed
| Action | File |
|---|---|
| New | `frontend/src/components/shell/SutWorkspaceHeader.tsx` |
| Edit | `frontend/src/app/page.tsx` — workspace header + fallback |
| Edit | `frontend/src/components/tabs/sut/SUTAnalyticsShell.tsx` — compact Tabs |
| Edit | `frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.tsx` — full primitive reskin |
| Edit | 15 files under `frontend/src/components/tabs/sut/` — Surface migration |
| Edit | `frontend/src/components/chat/SutInlineAIPanel.tsx` — drop frost-panel |
| Edit | `frontend/src/lib/constants.ts` — CHART_COLORS → theme tokens |
| Edit | `frontend/src/components/tabs/sut/shared.tsx` — ChartTooltipContent, CATEGORY_COLORS |
| Edit | `frontend/src/components/skeletons/SutSkeletons.tsx` — Surface wrappers |
| Edit | `frontend/src/components/admin/SutHealthPanel.tsx` — Surface + Chip |
| Delete | `frontend/src/lib/sutHomeShell.ts`, `sutHomeShell.test.ts` |
| Edit | navigation store — removed `workspaceEntered` |

### Verification
- `npm run lint` — clean
- `npx tsc --noEmit` — clean
- `npx vitest run` — **60 / 60** (−2 from deleted sutHomeShell tests)
- `npx next build` — clean
- All 6 routes → HTTP 200
- Workspace HTML audit: zero `frost-panel`, `sut-premium`, `sut-home-*` on `/?tab=analytics` and `/?tab=optimizer`

### Phase 5 → Phase 6 hand-off
1. `sut-chat-*` CSS block in `legacy.css` (~190 lines) — inline to Tailwind or a ChatPanel primitive
2. `SyntheticDemoProvenance` demotion to top-bar chip
3. `SutHowItWorksModal` still uses `frost-panel how-modal`
4. `frost-table-wrap` / `frost-table` remain in reference tools + billing (DataTable migration)
5. Orphan sections (`ExposureSection`, etc.) reskinned but still unwired — delete or wire in Phase 6
6. Tabular-nums sweep, focus audit, print stylesheet
