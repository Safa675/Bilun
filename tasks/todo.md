## Task: Dependabot Next 16.2.12 + sharp/brace overrides

### Goal
Clear the 11 open Dependabot alerts by bumping `next`/`eslint-config-next` to 16.2.12 and forcing `sharp` ≥0.35.3 and `brace-expansion` 1.1.16 via npm overrides. CI green; PR open.

### Subtasks
- [x] Branch `chore/dependabot-next-16.2.12` from `origin/main`
- [x] Bump `next` + `eslint-config-next` → `16.2.12` in `frontend/package.json`
- [x] Add/extend `overrides`: `sharp` ^0.35.3, `brace-expansion@1` 1.1.16 + `brace-expansion@5` 5.0.8 (keep `postcss`)
- [x] Regenerate lockfile with `npm install` in `frontend/`
- [x] Verify: lockfile versions + `tsc --noEmit` + `vitest run` (197) + `npm run build` (Next 16.2.12)
- [ ] Commit, push, open PR

### Out of Scope
- Reviving stale `chore/dependabot-next-security-bump` (16.2.9)
- Python deps / Dependabot config
- Code changes to middleware/rewrites
- eslint@10 major (needed to silence residual npm-audit brace/minimatch noise beyond Dependabot #26)

### Review
- next 16.2.12 + eslint-config-next 16.2.12 clear Dependabot #28–#36
- sharp override 0.35.3 clears #27 (Next still optionally pins ^0.34.5)
- brace-expansion@1 → 1.1.16 clears #26; @5 → 5.0.8 keeps typescript-eslint on a patched 5.x
- tsc + 197 vitest + production build green locally
