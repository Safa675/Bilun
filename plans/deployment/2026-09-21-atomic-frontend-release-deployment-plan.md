# Atomic Frontend Releases and Production Workspace Isolation Plan

Historical (2026-10-28): the strict release lane was deleted; tag `archive/strict-lane` holds it.

> **Status:** Ready for implementation; this PR is documentation only
> **Date:** 2026-09-21
> **Incident:** `app.bilun.tech` served HTML that referenced JavaScript chunks no
> longer present on disk
> **Primary scope:** Next.js frontend deployment on the production web VPS
> **Target:** Replace in-place production builds with immutable, verified,
> reversible releases

## ELI5 summary

The running frontend and the deployment job currently share one folder. A
frontend build replaces files in that folder before the old frontend process is
restarted. For a short time, the old process asks browsers to download its old
JavaScript filenames while the folder contains only the new JavaScript files.
The browser then reports `Failed to load chunk` and the page cannot start.

The fix is to treat each frontend build like a sealed, numbered box:

1. Build the next box in a separate workshop.
2. Start and test that box on a private port.
3. Move one `current` pointer to the tested box.
4. Restart the frontend so it opens that exact box.
5. If the public checks fail, point `current` back to the previous box and
   restart again.

No command may rebuild or edit the box the live process is using.

---

## Verified incident and current failure mechanism

The 2026-09-21 investigation established all of the following:

- The active Next.js process had started at approximately 10:50 Europe/Istanbul.
- `/opt/Bilun/frontend/.next` was rebuilt in place at approximately 18:38-18:39
  without restarting that process.
- The process continued rendering its in-memory old manifest, including chunk
  names such as `2-av3zy2nw4oj.js`, while disk contained the new build's chunk
  names.
- Requests for most chunk URLs emitted by the live `/login` response returned
  HTTP 500. The journal contained missing module-factory failures from patient
  workspace modules.
- Starting a temporary Next.js process against the completed on-disk build made
  `/login` and every asset referenced by it return HTTP 200. The new build was
  valid; the live process and the files beneath it belonged to different builds.
- The backend remained healthy.

The repository configuration permits this race:

- `.github/workflows/deploy.yml` runs `npm run build` inside
  `/opt/Bilun/frontend` while the old service is still serving from that same
  directory, then restarts the service later.
- `scripts/deploy/vps-bootstrap.sh` configures `bilun-frontend.service` with
  `WorkingDirectory=/opt/Bilun/frontend` and `npx next start`.
- The deploy health check verifies `/health` and the `/login` status code, but it
  does not fetch the JavaScript and CSS URLs referenced by the returned HTML.

A dirty Git worktree was evidence that production and verification activity
shared a checkout, but it was **not** the direct cause. The same chunk mismatch
can occur in a clean checkout whenever `.next` is replaced beneath a running
process.

---

## Goal and definition of done

Deploying a frontend commit must never modify the files used by the running
frontend. A candidate must be built and asset-verified outside the live release,
activated atomically, checked through the public URL, and rolled back
automatically if activation fails.

Done means:

- A build occurs in a disposable build workspace, never in the active release.
- Every release directory is immutable after publication and identifies its Git
  SHA and Next.js build ID.
- The candidate serves `/login` and all of its referenced local JS/CSS/font
  assets before it can become current.
- Activation changes one symlink and restarts one service.
- A failed restart or public smoke test restores the previous symlink and
  verifies the restored service.
- Static assets needed by recently open browser tabs remain available across a
  bounded number of releases.
- Concurrent deploys cannot interleave.
- The existing backend/cache deployment semantics are unchanged.
- The bootstrap documentation can reproduce the same layout on a fresh VPS.

## Non-goals

- No product, patient, billing, or Drug Indication behavior changes.
- No backend release-layout migration in this PR. The backend still needs a
  separate immutable-release plan because its Python environment and DuckDB
  cache have different lifecycle requirements.
- No container/Kubernetes migration.
- No zero-downtime multi-instance frontend rollout. A short systemd restart is
  acceptable; serving mismatched assets is not.
- No change to secrets or authentication behavior.
- No automatic merge or production deployment from the plan-only PR.

---

## Required invariants

1. **The active release is read-only by convention and tooling.** Build, package,
   dependency-install, and cleanup commands must refuse to target it.
2. **A release is content-addressed by commit.** A successful release lives at a
   path containing the full Git SHA. Reusing that path with different bytes is
   forbidden.
3. **Activation is atomic.** `current` is replaced through a temporary symlink
   plus same-filesystem rename; it is never removed before its replacement is
   ready.
4. **The old process keeps the old directory.** Because its working directory
   resolves to the old release, switching the symlink cannot replace files under
   the still-running process.
5. **A candidate is tested as a server, not merely as files on disk.** HTTP
   verification must follow the asset references from candidate HTML.
6. **A failed candidate cannot disturb current.** Failure before activation
   deletes only staging/build paths.
7. **A failed activation rolls back.** The previous symlink target is captured
   before activation and restored on any restart or public-smoke failure.
8. **Asset compatibility crosses releases.** A browser that loaded the previous
   HTML shortly before activation must still be able to fetch its hashed assets.
9. **One deploy runs at a time.** An advisory lock covers build, activation,
   verification, rollback, and retention cleanup.
10. **Health checks fail closed.** Missing or unparsable asset references, an
    unexpected redirect, a 4xx/5xx, an empty asset, or a timeout fails the gate.

---

## Target filesystem layout

Use separate source/build, live-release, shared-config, and shared-asset paths:

```text
/opt/Bilun/                              # existing source/backend checkout
/opt/bilun-frontend/
├── builds/
│   └── <workflow-run>-<sha>/            # disposable detached build workspace
├── releases/
│   └── <full-git-sha>/                  # immutable standalone frontend bundle
│       ├── server.js
│       ├── .next/
│       ├── public/
│       └── RELEASE.json                 # SHA, BUILD_ID, timestamp, checksums
├── assets/
│   └── _next/static/                    # union of retained releases' assets
├── manifests/
│   └── <full-git-sha>.assets            # paths/checksums used for safe GC
├── shared/
│   └── frontend.env -> /opt/Bilun/.env  # transitional secret/config source
├── current -> releases/<full-git-sha>/
└── deploy.lock
```

`/opt/Bilun` remains the backend checkout during this bounded change, but the
frontend service no longer runs from it. Feature experiments and verification
must use Git worktrees outside both `/opt/Bilun` and `/opt/bilun-frontend`.

The implementation should use Next.js standalone output. Because
`frontend/next.config.ts` sets `outputFileTracingRoot` to the repository root,
the assembler must normalize the generated monorepo-style standalone path into
the release root and fail if the expected `server.js`, `.next/static`, or
`public` payload is absent. The final layout must be verified from an actual
production build rather than assumed from a Next.js version example.

### Why a shared static asset store is needed

Atomic releases protect the server during deployment, but a browser can still
hold HTML from release A when the server has moved to release B. Its later
request for an A chunk would fail if only B's `.next/static` exists.

During publication, copy immutable `/_next/static` files into the shared asset
store without overwriting existing files. If the same relative path already
exists with a different checksum, fail the deploy. Caddy serves this path
directly before proxying other requests to Next.js. Asset garbage collection
removes only files unreferenced by every retained release manifest and older
than the retention grace period.

---

## Deployment transaction

### Phase 0 — Capture the current contract

- Record the active Git SHA, `readlink -f current` (once present), Next.js
  `BUILD_ID`, systemd unit contents, Caddy configuration, and current public
  health results in the deploy log.
- Add a reusable asset verifier that requests an HTML entry point, parses local
  `script[src]` and stylesheet/font `link[href]` URLs, fetches each URL with a
  timeout, and rejects non-2xx or empty responses.
- Add a regression fixture that represents the observed condition: HTML
  references an old chunk while only a new chunk exists. The verifier must fail
  it.

**Checkpoint:** The existing `/login` status-only check passes the regression
fixture while the new asset verifier fails it for the correct missing URL.

### Phase 1 — Produce a standalone immutable candidate

- Set `output: "standalone"` in `frontend/next.config.ts` while retaining the
  existing tracing root and rewrites.
- Add a release-builder script under `scripts/deploy/` that:
  - accepts an explicit full commit SHA and workflow run identifier;
  - validates both as safe path components;
  - creates a detached disposable worktree/build directory;
  - runs `npm ci` and `npm run build` there;
  - assembles standalone output, `.next/static`, and `public` into a staging
    release on the same filesystem as `releases/`;
  - writes `RELEASE.json` and the per-release asset manifest;
  - rejects an existing non-identical release;
  - removes the disposable build workspace through an absolute-path cleanup
    trap.
- Do not source or copy secrets into the release. Runtime configuration remains
  in the shared environment file.

**Checkpoint:** Starting the staged `server.js` on a private candidate port
serves `/login`, and the asset verifier confirms every referenced local asset.
The current production service and its files remain untouched throughout.

### Phase 2 — Publish and activate safely

- Acquire `/opt/bilun-frontend/deploy.lock` with `flock` before any publication
  or activation step.
- Copy candidate static files into the shared store with checksum collision
  protection.
- Rename the completed staging release to `releases/<sha>` on the same
  filesystem.
- Capture the existing `current` target.
- Create `current.next` pointing to the new release, then atomically rename it
  over `current`.
- Restart `bilun-frontend.service`; do not run `npm`, `npx`, or a build command
  from the release directory.
- Poll the loopback service first, then the public URL. Verify `/login` HTML and
  every referenced asset in both places.
- Verify at least one asset URL captured from the previous release remains HTTP
  200 after activation.

**Checkpoint:** The running process's working directory resolves to the new
release SHA, new and previous retained asset URLs return 200, and the release
metadata matches the deployed commit.

### Phase 3 — Automatic rollback

- Install a trap before changing `current`.
- If symlink activation, systemd restart, loopback checks, public checks, or old
  asset compatibility checks fail:
  - atomically restore the saved previous target;
  - restart the frontend;
  - run the same loopback and public verification against the restored release;
  - preserve the failed release and logs for diagnosis, but mark it inactive;
  - exit non-zero so GitHub Actions reports a failed deployment.
- If rollback verification also fails, emit an explicit high-severity error with
  both release SHAs and the relevant journal tail. Do not claim recovery.

**Checkpoint:** An intentionally broken candidate causes a failed deployment,
but the public app is verified on the previous release and `current` points back
to it.

### Phase 4 — Move service and proxy contracts to the release layout

- Update `scripts/deploy/vps-bootstrap.sh` so the frontend unit uses:
  - `WorkingDirectory=/opt/bilun-frontend/current`;
  - the absolute Node executable and `server.js`, not `npx next start`;
  - `NODE_ENV=production`, `HOSTNAME=127.0.0.1`, and `PORT=3000`;
  - the shared runtime environment file;
  - start-limit and restart settings that do not hide a permanently broken
    release.
- Add the Caddy `/_next/static/*` file-server route backed by the shared asset
  store, ahead of the general frontend reverse proxy.
- Validate Caddy configuration before reloading it.
- Add a one-time migration command that builds and verifies the first release,
  creates `current`, updates systemd/Caddy, reloads units, and only then restarts
  the frontend.
- Make the migration idempotent: rerunning it against the same SHA must verify
  and exit cleanly rather than overwrite the release.

**Checkpoint:** A fresh VPS bootstrap and an existing-VPS migration produce the
same unit, proxy, directory, and symlink contracts.

### Phase 5 — Replace the GitHub Actions in-place build

- Refactor `.github/workflows/deploy.yml` so frontend changes invoke the release
  transaction rather than `(cd frontend && npm run build)` in `/opt/Bilun`.
- Pass the triggering CI run's exact commit SHA; do not deploy whatever branch
  happens to be checked out on the VPS.
- Keep the existing rule that deployment runs only after successful `main` CI.
- Keep backend/cache detection and deployment behavior unchanged in this phase.
- Ensure a frontend-only deployment cannot run `git checkout -f` across the
  directory used by the frontend process.
- Upload or print bounded diagnostics: release SHA, candidate port result,
  activation result, public asset count, rollback result, and final active SHA.

**Checkpoint:** Workflow logs demonstrate build -> candidate verification ->
publication -> atomic activation -> public asset verification, with no build
command executed under the active release.

### Phase 6 — Retention, guardrails, and operator documentation

- Retain at least the current and two previous releases. Keep shared assets for
  those releases plus a time grace period for stale browser tabs.
- Run retention only after a successful deployment and never delete `current`,
  the captured rollback target, staging paths owned by another lock holder, or
  any asset referenced by a retained manifest.
- Add a production sentinel/guard so deploy scripts refuse to run build or
  dependency-install commands when the resolved target is `current` or one of
  its release directories.
- Update `plans/deployment/vps-deploy-plan.md` with bootstrap, migration,
  deploy, rollback, and incident-recovery commands.
- Document that `/opt/Bilun` is not a developer workspace. Ad-hoc checks belong
  in a disposable Git worktree and must not use production ports.

**Checkpoint:** An operator can identify the active and previous SHAs, perform a
documented manual rollback, verify all referenced assets, and safely remove only
expired releases.

---

## Expected implementation surface

The implementation PR is expected to touch only deployment/build concerns:

- `frontend/next.config.ts` — standalone output.
- `scripts/deploy/` — candidate build, asset verification, activation/rollback,
  and safe retention scripts.
- `scripts/deploy/vps-bootstrap.sh` — release-aware systemd and Caddy contracts.
- `.github/workflows/deploy.yml` — exact-SHA release transaction.
- Deployment-script tests and asset-verifier fixtures.
- `plans/deployment/vps-deploy-plan.md` — operator documentation.

If implementation requires application component, API, billing, cohort, or
patient data changes, stop and split that work into a separately justified PR.

---

## Verification matrix

| Scenario | Required result |
|---|---|
| Build while release A is live | A's HTML and every referenced asset stay 200 |
| Valid release B candidate | Candidate `/login` and all local assets are 2xx and non-empty |
| Missing candidate chunk | Activation is blocked; A remains current |
| Concurrent deploy attempt | Second deploy exits or waits without changing shared state |
| Activation of B | `current` and process working directory resolve to B |
| Browser holds A HTML after B activation | Captured A asset URLs remain 200 |
| B fails after restart | Symlink and service return to A; workflow fails |
| Rollback also fails | Workflow reports unrecovered production failure explicitly |
| Re-deploy same SHA | Idempotent verification; no release mutation |
| Existing path has different checksums | Deploy fails closed |
| Fresh bootstrap | Same release/service/proxy layout as migrated VPS |
| Backend-only commit | Existing backend/cache path runs; frontend is not rebuilt |

### Required automated checks

- Unit tests for URL extraction, same-origin filtering, redirects, empty bodies,
  timeouts, and missing assets in the verifier.
- Filesystem tests in temporary directories for atomic symlink replacement,
  collision refusal, idempotent publication, retention safety, and rollback.
- A real `npm run build` contract check that asserts the standalone release can
  start and serve all `/login` assets.
- Shell syntax checks for deploy scripts and `git diff --check`.
- `caddy validate` for the generated proxy configuration where Caddy is
  available.
- Existing backend and frontend CI remain green.

### Production rollout checks

Before migration:

- Capture the current service unit, Caddyfile, Git SHA, build ID, environment
  file path, and a list of `/login` assets.
- Confirm the previous recovery path and who can restart the service.
- Back up configuration files, not generated `.next` output.

After migration:

- Confirm `/health` is 200.
- Confirm public `/login` is 200 and every referenced asset is 200 and non-empty.
- Log in and open at least one patient workspace route.
- Confirm the service process working directory and `current` resolve to the
  same SHA.
- Confirm a pre-migration captured asset remains available during the grace
  window.
- Perform one controlled rollback drill, then reactivate the new release.

---

## Failure handling and observability

Every deployment log must make these values explicit without printing secrets:

- triggering workflow run and exact commit SHA;
- previous, candidate, and final active release paths;
- Next.js `BUILD_ID` for each checked release;
- candidate and public verification URL counts;
- systemd restart outcome and bounded journal tail on failure;
- whether rollback was attempted and whether it was verified;
- releases/assets retained or removed.

The public health check must report a deployment failure if any referenced
frontend asset fails, even when `/login` itself returns 200. A page-level 200 is
not sufficient evidence that a JavaScript application can boot.

---

## Implementation order and PR boundaries

1. **PR A — scripts and tests:** standalone artifact, verifier, release
   assembler, activation/rollback, and temp-directory tests. No VPS switch.
2. **PR B — infrastructure migration:** bootstrap/systemd/Caddy changes and the
   one-time migration procedure. Roll out with a documented rollback window.
3. **PR C — workflow cutover:** make GitHub Actions call the verified release
   transaction and remove the in-place frontend build.
4. **Follow-up plan:** move the backend and its dependency environment out of
   the mutable source checkout without changing DuckDB atomic-cache semantics.

The PRs may be combined only if the full failure-injection matrix is automated
and the migration remains independently reversible. The first production
cutover must not be mixed with product behavior changes.

## Final acceptance criteria

- [ ] No live service has `/opt/Bilun/frontend` as its working directory.
- [ ] No deployment command mutates an active frontend release.
- [ ] Candidate HTML plus all referenced assets are checked before activation.
- [ ] Public HTML plus all referenced assets are checked after activation.
- [ ] Recently retained releases' assets remain fetchable after activation.
- [ ] Failed activation automatically returns to a verified previous release.
- [ ] A deploy log identifies the exact Git SHA and Next.js build ID in service.
- [ ] Concurrent and same-SHA deployments are safe and deterministic.
- [ ] Fresh bootstrap and existing-VPS migration are both documented and tested.
- [ ] CI is green, and the deployment workflow no longer builds inside the live
      production directory.
