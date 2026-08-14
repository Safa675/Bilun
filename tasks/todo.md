## Task: Fix Sidebar & Tab Strip Intertwining + Resolve PR Conflicts

### Goal
Fix the layout bug where the fixed sidebar and sticky workspace tab strip overlap/intertwine due to CSS variable reset in `AppSidebar.tsx`, resolve merge conflicts with `main`, and verify full frontend and backend test suites pass.

### Subtasks
- [x] Resolve git merge conflicts with `main` in `WorkspaceTabStrip.tsx` and `tasks/todo.md`
- [x] Fix `AppSidebar.tsx` layout effect: prevent cleanup from resetting `--shell-sidebar-width` to `0px` when the shell is active
- [x] Ensure `WorkspaceTabStrip` and page layout have robust, bulletproof sidebar offsets across all screen widths and collapsed states
- [x] Verify `npm run typecheck` (`tsc --noEmit`) passes with 0 errors
- [x] Verify `npm test` (`vitest`) passes with 100% test pass rate (232/232 passed)
- [x] Verify `npm run build` succeeds cleanly in 2.4s
- [x] Verify backend checks and parity pass with 0 errors
- [x] Commit and push changes to `experiment/workspace-shell` to update PR #72

### Review
- Merged latest `main` into `experiment/workspace-shell` and cleanly resolved conflicts in `WorkspaceTabStrip.tsx`.
- Fixed the layout intertwining bug in `AppSidebar.tsx`:
  - Removed destructive `return () => root.style.setProperty("--shell-sidebar-width", "0px")` cleanup on re-renders.
  - Synchronously initialized `--shell-sidebar-width` on mount matching localStorage collapsed state before paint.
- All verification passed:
  - TypeScript: 0 errors
  - Vitest: 44/44 test files, 232/232 tests passed
  - Production build: Next.js 16.2 compiled in 2.4s with 0 errors
  - Backend: Ruff lint, rule compilation (137 artifacts), and manifest parity check (0 issues) passed cleanly.

### Out of Scope
- Complete redesign of the navigation shell.
