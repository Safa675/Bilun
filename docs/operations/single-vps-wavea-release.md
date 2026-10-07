# Single-VPS Wave A release

This is the operator interface for the existing Bilun backend/frontend pair on
loopback **8001/3000**. It constructs the candidate from a pinned main commit and
keeps the old pair recoverable. It does not merge code, provision a server, create
credentials, rotate secrets, upgrade dependencies in the live environment, or
guess production paths.

## One interface

Run these from a complete checkout of the **same exact commit** selected below,
using the existing Python environment with the repository dependencies:

```sh
PYTHONDONTWRITEBYTECODE=1 /absolute/existing/python -m scripts.deploy.paired_release prepare --manifest /private/release/machine.json
PYTHONDONTWRITEBYTECODE=1 /absolute/existing/python -m scripts.deploy.paired_release status --manifest /private/release/machine.json
PYTHONDONTWRITEBYTECODE=1 /absolute/existing/python -m scripts.deploy.paired_release activate --manifest /private/release/machine.json
PYTHONDONTWRITEBYTECODE=1 /absolute/existing/python -m scripts.deploy.paired_release rollback --manifest /private/release/machine.json
```

`prepare` performs the actual frontend/cache builds, verification, private
rehearsal and signing, then prepares the paired transaction. Operators do not
assemble a collection of verifier reports by hand. `status` is read-only.
`activate` is the separate, consequential serving switch. `rollback` recovers
the original pair; recovery does not require the candidate's CI to stay green.

All release operations share the configured machine lock. Keep every release's
private directory and the shared owner/lock records; do not remove them to work
around a blocked or interrupted transaction.

## Prerequisites

- The target is a full immutable 40-character SHA available in the configured
  existing Git repository. GitHub must report this exact SHA as current `main`
  with a successful `CI` push run. A PR check or an old green main run is not
  sufficient. Preparation repeats this check after builds; activation checks it
  again before maintenance. Preparation does not fetch missing Git objects:
  after verifying the existing `origin` is the intended repository, the operator
  must first run `git -C /absolute/existing/git-repository fetch origin main`
  when necessary, then provide the exact fetched main SHA and its successful run
- The running pair is healthy and its real process working directories,
  configuration, frontend `current` symlink and selected cache match the
  explicit inventory. Tracked source/configuration changed after process start
  blocks preparation
- Linux/systemd, Git, existing Python/Node/npm, `strace`, `unshare` and `ip` are
  installed. Namespace creation and service/proxy control require the existing
  operator privileges. This command does not grant privileges or install tools
- Both systemd services are the existing `bilun-backend.service` and
  `bilun-frontend.service`. The paired driver accepts only its reviewed
  single-site Caddy layout, currently the exact `OLD_CADDYFILE` in
  `scripts/deploy/prepare_wavea_routes.py`. An imported or otherwise different
  proxy configuration requires a separate reviewed migration. Both explicit
  systemd drop-in parent directories must already exist; preparation does not
  provision them
- The old standalone frontend is already compiled to proxy to port 8001. Its
  backend is accepted in exactly one of two forms. Either it has the retained
  `.venv/bin/python` expected by the recovery launcher (unchanged behavior), or
  it has no `.venv` entry of any kind, not even an empty directory, in the live
  runtime or its snapshot and runs from a shared interpreter such as a venv
  outside the checkout (every runtime this tool builds from a git worktree has
  this layout). The second form is ready only if the issuer proves the captured
  identity: the private `live-after-snapshot.json` record loads, the whole
  declared `dependency_roots` closure re-pins from disk, every pin and the root
  list equal `preparation-pins.json`, the closure lies outside both runtime
  copies, and the recorded launcher, argv, terminal executable, environment and
  runtime digest equal the serving old process. Anything less keeps the
  `backend snapshot lacks runnable Python environment` blocker. Rollback of the
  paired release restarts the original services, so the shared interpreter must
  stay unchanged. The old two-port route chain still needs a `.venv` in the old
  backend copy and is not supported for the second form: `observe_old_pair` and
  `prepare_wavea_route_manifest` refuse it before any maintenance, and
  `rehearse_wavea_pair` starts its replay from `backend/.venv`. Both old and
  candidate Python/Node runtimes must remain available and accessible to the
  existing service identity
- The signing key already exists as an independent private file containing at
  least 32 bytes. Existing candidate authentication comes from separate private,
  NUL-delimited environment files. The backend must contain the existing
  purpose-bound developer identity accepted by `candidate_environments`; this
  workflow creates no user, developer role, password, token or signing key
- A GitHub read credential is already available through
  `BILUN_GITHUB_READ_TOKEN` or the existing Git credential helper. Protected
  loopback health probes reuse the verified running backend's existing private
  environment; the operator does not export or retype that token. Do not put
  secret values in the JSON manifest
- The comparison baseline is an independent copy of the actual serving cache,
  plus its **retained original build checkout and original source directories**.
  Supply the historical five-key build configuration explicitly. Source/config
  hashes must independently reconcile to stored `build_meta`; copying inputs to
  a new path or inventing recorded metadata cannot repair a missing baseline
- Private manifest, environment, evidence and key files are mode 0600 under
  private 0700 directories. `bundle_root` is initially absent under an existing
  private directory. It must not overlap the serving runtime, repository,
  baseline sources or dependencies. Allow disk space for two old runtime/cache
  copies, an independent baseline, candidate worktree/frontend, traced cache and
  logs. No fixed resource capacity or completion time is promised

## Private machine/input manifest

The following is a **template**, not a discovered host configuration. Replace
every placeholder with verified existing paths and exact identities. Executable
leaf symlinks are permitted and their resolved target bytes are pinned. Other
input paths must be canonical and unlinked. `npm` names the existing npm CLI
JavaScript entry point, executed with the explicit `node` binary.

```json
{
  "schema_version": "bilun-single-vps-preparation-v1",
  "release_id": "wavea-operator-chosen-id",
  "target_sha": "<exact current main 40-character SHA>",
  "ci_run_id": "<successful main CI run number>",
  "repository": "/absolute/existing/git-repository",
  "bundle_root": "/private/releases/absent-release-directory",
  "baseline_checkout": "/absolute/retained-original-cache-build-checkout",
  "baseline_code_sha": "<40-character code SHA stored in old cache build_meta>",
  "baseline_claims_dir": "/absolute/retained-original-cache-build-checkout/data/synthetic/sut/claims",
  "baseline_clean_dir": "/absolute/retained-original-cache-build-checkout/data/synthetic/sut/clean",
  "baseline_build_config_environment": {
    "PIPELINE_MODE": "<exact old build environment value, or empty string>",
    "PIPELINE_SUT_MODE": "<exact old build environment value, or empty string>",
    "BILUN_DATA_MODE": "<exact old build environment value, or empty string>",
    "BILUN_CLAIMS_DIR": "<exact old build environment value, or empty string>",
    "BILUN_CLEAN_DIR": "<exact old build environment value, or empty string>"
  },
  "serving_code_sha": "<40-character SHA of actual old backend checkout>",
  "old_build_id": "<actual old active Bilun cache build ID>",
  "live_backend_runtime": "/absolute/actual-old-backend-runtime",
  "live_frontend_runtime": "/absolute/actual-old-standalone-frontend",
  "live_cache_path": "/absolute/actual-serving-cache.duckdb",
  "frontend_current": "/absolute/existing/frontend/current",
  "caddy_config": "/absolute/existing/Caddyfile",
  "backend_dropin": "/etc/systemd/system/bilun-backend.service.d/bilun-paired-release.conf",
  "frontend_dropin": "/etc/systemd/system/bilun-frontend.service.d/bilun-paired-release.conf",
  "lock_path": "/private/shared-release-state/deploy.lock",
  "candidate_backend_environment": "/private/existing/candidate-backend-env.nul",
  "candidate_frontend_environment": "/private/existing/candidate-frontend-env.nul",
  "backend_python": "/absolute/existing/venv/bin/python",
  "node": "/absolute/existing/node",
  "npm": "/absolute/existing/npm-cli.js",
  "signing_key_path": "/private/existing/signing-key",
  "dependency_roots": ["/absolute/existing/python/site-packages", "/absolute/existing/python/stdlib"],
  "external_state_paths": ["/absolute/existing/chat-budget-ledger.sqlite"],
  "data_mode": "synthetic_demo",
  "patient_id": "<existing representative patient ID>",
  "payload_workers": 2,
  "billing_workers": 2,
  "snapshot_mode": "online-read-lock"
}
```

The two worker counts are explicit integers from 1 through 8 and remain identical
across the build command, traced attestation and receipt checks. The five
baseline configuration values are those used **during the historical cache
build**, not necessarily the current service environment. New traced builds
use the verifier's fixed empty five-key environment with explicit CLI input
arguments. Different old/new configuration values are verified independently.

`dependency_roots` must enumerate the existing Python runtime roots permitted by
the trace verifier. Their complete bytes and the executable targets remain
bound through activation. Do not point these at the whole filesystem.

For a distribution Python installation with an external regular-file link (for
example, `/usr/lib/python3.13/sitecustomize.py` pointing directly to
`/etc/python3.13/sitecustomize.py`), explicitly select
`"schema_version": "bilun-single-vps-preparation-v2"` and include the canonical
target **file** as a separate `dependency_roots` entry alongside the Python
directories. No new manifest fields are required. Merely declaring the target's
parent directory does not authorize the link. V2 pins both its literal link text
and resolved target, plus the target's bytes and mode, and inventories that file
independently. The dependency roles are retained in the hash-bound
`bilun-preparation-pins-v2` contract and replayed on repeated preparation and
the paired release's existing preflight, candidate start and listener checks.
Undeclared targets, external directory links, dangling/cyclic links and linked
intermediate target paths remain rejected. Source, cache and runtime inventory
rules and signed startup receipts are unchanged. V1 manifests and pin contracts
retain their original strict behavior; they do not gain this exception.

For an external **file-link chain**, select
`"schema_version": "bilun-single-vps-preparation-v3"`. It uses the same fields,
but `dependency_roots` may also explicitly name leaf symlinks whose parent is
canonical and contains no directory symlinks. Every intermediate link in a
chain leaving a dependency root must be listed separately, and so must the
canonical final regular file. A source link already inside an inventoried
dependency directory need not also be listed as a leaf; listing it is allowed.
Declaring another directory never grants permission for its file-link leaves.

For example, the observed Ubuntu layout is:

```text
/usr/lib/python3.13/config-3.13-x86_64-linux-gnu/libpython3.13.so
  -> ../../x86_64-linux-gnu/libpython3.13.so.1
/usr/lib/x86_64-linux-gnu/libpython3.13.so.1
  -> libpython3.13.so.1.0
/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0  (regular file)
```

Alongside the stdlib and venv directories, explicitly list the `.so.1` link and
the `.so.1.0` file, plus `/etc/python3.13/sitecustomize.py` for the direct
sitecustomize link. V3 pins every hop's absolute path, literal text, link mode
and normalized next path, and the final file's bytes/full mode. Each declared
leaf link and final file also receives an independent pin. Replay uses only
the roles in the hash-bound `bilun-preparation-pins-v3` contract. Cycles, more
than eight link hops, undeclared hops/targets, directory-link components
(including those hidden by `..`) and external directory targets fail closed.
Purely root-contained links retain their ordinary inventory behavior; this
does not grant new directory-link permissions. V1 and V2 remain unchanged and
continue rejecting external multi-hop links. Do not alter distribution links
or replace these declarations with broad filesystem roots.

`external_state_paths` pins canonical locations, filesystem identity, permissions
and ownership of known live mutable state. Mutable ledger contents may continue
to change; these ledgers are never copied, reset or replaced. A configured
`BILUN_PUBLIC_CHAT_BUDGET_DB` must be unchanged between old and candidate backend
environments and explicitly listed, even if the list would otherwise be empty.
An absent ledger is not created by preparation.

## Snapshot modes and interruption

`online-read-lock` is the default. Preparation requires a successful DuckDB
read-only connection to the live cache and no WAL sidecar. It verifies stable
file identity and exact copied bytes and validates the independent clone.
It never copies around a denied writer lock. An ordinary `load-only` process
can hold a writable DuckDB connection even while idle; that host configuration
therefore fails the online snapshot gate without stopping services. Do not
assume a different startup policy guarantees online copying without checking
the actual lock behavior.

Selecting `"snapshot_mode": "brief-maintenance"` is explicit permission for an
additional preparation-time interruption. After copying unchanged runtimes and
configuration, the operation durably records its recovery intent, stops the old
frontend/backend, takes the database-supported snapshot, and starts and checks
the **same old pair before any candidate build begins**. No candidate cache,
source, frontend pointer or configuration is selected in this phase. A normal
shutdown may checkpoint the old database; the selected build and restored pair
must still match. Unsupported WAL/recovery conditions fail and restore the old
services instead of bypassing snapshot verification. During this interruption
the existing public proxy may return service errors; the Caddy configuration
is not switched by the snapshot operation.

If interrupted during this small snapshot transaction, `status` reports
`recovery_needed` without restarting anything. Explicit `prepare` retry or
`rollback` restores the old services from the self-contained journal, without
requiring candidate files, an available signer, or green CI. After recovery,
choose a fresh absent `bundle_root` before beginning another build. Do not
delete an unfinished journal or its machine-owner record.

If the original input manifest is unavailable, the same interface can inspect
or recover directly from the retained self-contained journal:

```sh
PYTHONDONTWRITEBYTECODE=1 /absolute/existing/python -m scripts.deploy.paired_release status --snapshot-journal /private/releases/release-id/snapshot-maintenance/transaction.json
PYTHONDONTWRITEBYTECODE=1 /absolute/existing/python -m scripts.deploy.paired_release rollback --snapshot-journal /private/releases/release-id/snapshot-maintenance/transaction.json
```

## What preparation constructs and checks

1. Recheck exact main CI and running old tuple; bind immutable inputs, existing
   environments/signing key, external dependencies and mutable-state ownership
2. Preserve independent `old-snapshot` and `old-replay` runtimes/cache plus
   configuration and effective environments. The comparison `baseline.duckdb`
   keeps its actual original build identity; no metadata is rewritten
3. Create `candidate-backend` with `git worktree add --detach` at the target SHA.
   Copy explicitly pinned input files into this private worktree. Build a fresh
   standalone `candidate-frontend` with its proxy compiled for port 8001; retain
   old hashed static assets, rejecting collisions and public secret/source maps
4. Generate both source rosters and a traced candidate cache. Verify selected
   build metadata, all persisted structural rows, same-input source/config
   identities, version-aware original-five/current-v2 semantic equality and
   traced process invocation/read closure
5. In an isolated network namespace, use ports 8001/3000 sequentially for old,
   candidate and recovered old pairs. Verify compiled proxy routing, each
   patient/bill HTTP DTO against its own persisted cache, all-row cross-pair
   equivalence, auth/public-access rules, assets and full old recovery. Only
   independently attested source-path identities may be normalized
6. Freeze verifier evidence, build the sidecar, recheck live/source/external
   identities and exact main CI, and issue the candidate receipt with the
   existing key. Emit `candidate-launch.json`, the dependency/ownership pin
   contract and `paired-manifest.json`. The paired driver then prepares its
   separate durable activation journal
7. For an old backend without its own `.venv`, `prepared.json` carries
   `receipt.old_backend_interpreter.identity_sha256`. Before any maintenance or
   activation, compare it with the digest reviewed in the stage plan for the
   reviewed `dependency_roots` list. A different value means stop and re-review;
   never edit the expected value to make it match. The verifier accepts
   whatever closure was declared, so the reviewed root list and this comparison
   are the controls for a complete closure. Changing the shared interpreter
   between preparation and activation invalidates the bundle. Only the legacy
   `.venv` form omits this key

Canonical evidence lives under the bundle: `baseline-roster.json`,
`source-roster.json`, `traced-build.json`, `structural.json`, `semantic.json`,
`trace-attestation.json`, `rehearsal/`, `evidence/`, `candidate-receipt.json`,
`preparation-pins.json` and finally `prepared.json`. Private logs remain there
on failure. No successful marker is emitted for a partial build.

A successful repeat of `prepare` reuses only the bundle from the exact same
input manifest, rechecks its pins and lets the paired driver revalidate it.
A failed/partial bundle is preserved for diagnosis and is not silently resumed,
overwritten, pruned or treated as a valid release.

## Activation and rollback

Before maintenance, activation rechecks CI, signed candidate artifacts, external
dependency bytes, mutable-state ownership and the live old pair. Under the
maintenance barrier it stops both services, copies the stopped current database,
derives a final serving database retaining all supported historical builds,
pointers and mutable state, independently verifies that derivation, and signs
the **actual final serving bytes** with a versioned v2 receipt extending the
unchanged candidate v1 receipt. Unsupported tables, sequences or metadata fail
closed rather than being discarded.

It installs the coherent backend/cache/frontend pair and verifies both private
and public routing before reopening traffic. The full work is timed and
journaled; the maintenance duration depends on cache size and checks and is not
promised to be a fixed number of seconds. Dependency drift after preparation
blocks activation before the barrier whenever detected by the preflight.

Failure recovery and explicit rollback restore the old runtime/configuration,
frontend pointer and old selected build while preserving newer supported
history/mutable records. Cache bytes are never relabeled to make an earlier
signature pass. If proof or recovery fails, the journal remains blocked for
operator inspection rather than falsely reporting a healthy release.

## Verification boundary

Repository tests exercise the actual preparation/paired transaction interfaces
with fabricated commands, processes, HTTP responses, fault injection and small
real DuckDB files. They include genuine subprocess DuckDB lock behavior. This
implementation work does **not** execute a VPS build, systemd/Caddy operation,
network namespace rehearsal or deployment. The complete target checkout, real
host identity, resource availability, permissions, source roster, public probes
and exact merged-main CI remain mandatory operator-time gates.
