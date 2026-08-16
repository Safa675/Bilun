## Task: Resolve 25 Dependabot alerts — Next.js + devDep security upgrade

### Goal
Clear all 25 open Dependabot alerts in `frontend/package-lock.json` by bumping `next` (and `eslint-config-next`) from 16.1.6 → 16.2.9, plus 4 devDep/build-time packages. Verified green build, tests, and CI before pushing.

### Why this matters (from the investigation)
- All 25 alerts are npm; none touch the Python backend. ~21 clear from the `next` bump alone, 4 from devDep bumps.
- **Two CVEs genuinely apply to this codebase:**
  - `GHSA-26hh-7cqf-hhc6` (Turbopack middleware bypass, HIGH) — `src/middleware.ts` is the UI auth gate + `next.config.ts` enables Turbopack. Binding constraint forcing 16.2.6 minimum.
  - `GHSA-ggv3-7p47-pfv8` (request smuggling in rewrites) — `next.config.ts` proxies `/api/:path*` to the backend.
- Mitigating: backend independently re-checks the session token on `/api/*` (per `middleware.ts:6-7`), so a bypass exposes UI but not the data layer.
- The remaining ~18 `next` CVEs (cache poisoning, App Router XSS, CSP nonce, beforeInteractive, WebSocket SSRF, Pages Router i18n, Cache Components) are **not applicable** — none of those features are used (confirmed by grep across `frontend/src`).
- **Low-risk bump:** 16.2.x introduced zero new breaking changes (all v16 breaks landed in 16.0, already absorbed). Code is already v16-correct (async `cookies()` at `layout.tsx:54,65`, App Router only, no edge runtime, no custom server). Node floor (≥20.9) unchanged.

### Subtasks

- [ ] **Create branch** `chore/dependabot-next-security-bump` off current `main`
- [ ] **Bump `frontend/package.json`** (2 lines):
  - `"next": "16.1.6"` → `"next": "16.2.9"` (line 15)
  - `"eslint-config-next": "16.1.6"` → `"eslint-config-next": "16.2.9"` (line 28) — must move in lockstep
- [ ] **Bump devDeps in `frontend/package.json`**:
  - `vite` 8.0.10 → 8.0.16 (clears 2 alerts — both Windows-only, low priority, but free)
  - `js-yaml` 4.1.1 → 4.2.0 (clears 1)
  - `@babel/core` 7.29.0 → 7.29.6 (clears 1 — low severity)
  - `brace-expansion` (nested under typescript-eslint) and `postcss` (nested under next) will auto-resolve via the next bump / lockfile regen
- [ ] **Regenerate lockfile**: `cd frontend && npm install` to update `package-lock.json` (lockfileVersion 3)
- [ ] **Verify clean install**: `npm ci` from scratch (what CI runs)
- [ ] **Typecheck**: `npx tsc --noEmit`
- [ ] **Run tests**: `npx vitest run` (273 test files)
- [ ] **Production build**: `npm run build`
- [ ] **Lint**: `npm run lint` (eslint-config-next moved in lockstep — should be no-op)
- [ ] **Manual smoke test** (local):
  - Hit `/` unauthenticated → expect redirect to `/login` (middleware still gating post-upgrade)
  - Hit `/api/...` through the rewrite → expect backend response (smuggling fix doesn't change legitimate proxying)
- [ ] **Commit** with message documenting: which CVEs were closed, which were skipped as not-applicable (with one-line reasons per AGENTS.md §11), and the devDep hygiene bumps
- [ ] **CI check**: confirm all CI jobs green on the branch before considering merge (per AGENTS.md §10)
- [ ] **PR review gate**: after CI green, read Copilot + any human review comments; classify each as (a) real bug / (b) clarity / (c) low-value; fix (a) before merging (per AGENTS.md §11)
- [ ] **Merge** to main; deploy.yml auto-detects the lockfile change and rebuilds on the VPS

### Out of Scope
- Adding `.github/dependabot.yml` (no automated updates configured today — separate task)
- Adding `.nvmrc` / `engines` field (CI pins Node 20 at `ci.yml:51`)
- Verifying production VPS Node version (deploy.yml has no setup-node step)
- Python backend dependencies (zero alerts there)
- Any code changes to `middleware.ts`, `next.config.ts`, `layout.tsx`, or components — none needed; the upgrade is dependency-only
- Going to 16.2.10 (chose 16.2.9 = current npm `latest` tag; same fixes, fewer unknowns)

### Verification criteria (definition of done)
1. All 25 Dependabot alerts show `resolved` on GitHub after merge
2. `npm ci && tsc --noEmit && vitest run && npm run build && npm run lint` all pass locally
3. CI green on the PR (both `backend` and `frontend` jobs)
4. Bot/human PR reviews read and any (a)-class findings fixed before merge
5. Manual smoke confirms middleware redirect + API rewrite still work post-upgrade
