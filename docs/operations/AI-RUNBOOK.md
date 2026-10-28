# AI operations handoff

Verified on 2026-10-09 for `Safa675/Bilun`; checkout: `~/work/bilun-land`. Work sequentially, preserve branches and merge only authorized PRs with green default backend/frontend CI on their exact head SHA. No force-push; no screenshot, pixel or byte-profile gates.

## Laptop CI

Read `tools/ci/laptop_runner.py`. Existing image: `bilun-laptop-ci:20261008-runtime-complete`; labels: `self-hosted, Linux, X64, bilun-laptop-ci`. Use existing admin `gh` authentication. Credentials stay in memory/container tmpfs; never send them to the VPS.

```bash
cd ~/work/bilun-land
mkdir -p ~/.cache/bilun-land
TMPDIR="$HOME/.cache/bilun-land" python3 tools/ci/laptop_runner.py --image bilun-laptop-ci:20261008-runtime-complete --jobs 2 &
runner_pid=$!
```

`--jobs 2` serves two jobs sequentially; two terminals can serve backend/frontend concurrently. Retain each PID; repeat after quota exhaustion if checks remain queued. Finish merge/push CI. Never stop a running job.

After all jobs finish, verify `busy=false`; stop your owned supervisor only if still running:

```bash
gh api repos/Safa675/Bilun/actions/runners --jq '.runners[] | {id,name,busy}'
kill -TERM "$runner_pid"
wait "$runner_pid" || test "$?" -eq 143
docker ps -a --filter name=bilun-ci --format '{{.Names}} {{.Status}}'
docker volume ls --format '{{.Name}}'
gh api repos/Safa675/Bilun/actions/runners --jq '.total_count'
```

The script removes its container, `<runner-name>-work` volume and registration. Idle runner count must be **0**. For verified owned, stopped remnants only: `docker rm "$runner_name"`, `docker volume rm "${runner_name}-work"`, `gh api -X DELETE "repos/Safa675/Bilun/actions/runners/$runner_id"`. No global pruning.

### Automatic start

`tools/ci/laptop_watcher.py` does the start and stop above by itself. A systemd user timer runs it, and a minute after each run ends it runs again. A run lists the jobs queued for the `bilun-laptop-ci` label (runs that are `queued` or `in_progress`; a run idle for more than a day is a stale record and ignored). Only while jobs are queued, no runner with the label is online and the image exists, it runs `laptop_runner.py --jobs 1`, then looks again, at most six runners per run. An idle laptop has nothing registered. A runner that receives no job within five minutes is stopped; once a runner has a job it is left to finish, and a runner status that cannot be read never counts as "no job". It uses the existing `gh` login and only starts the reviewed image; it never builds one.

Install and update from a checkout of the reviewed commit. The units run the copy in `~/.local/share/bilun-ci`, never a working tree, so a PR branch checked out elsewhere cannot change what runs unattended:

```bash
install -D -m 0755 tools/ci/laptop_watcher.py tools/ci/laptop_runner.py -t ~/.local/share/bilun-ci && install -D -m 0644 tools/ci/systemd/bilun-ci-watcher.service tools/ci/systemd/bilun-ci-watcher.timer -t ~/.config/systemd/user
systemctl --user daemon-reload && systemctl --user enable --now bilun-ci-watcher.timer
```

Look: `systemctl --user list-timers bilun-ci-watcher.timer` and `journalctl --user -u bilun-ci-watcher -n 50`. What it would do right now: `BILUN_CI_IMAGE=bilun-laptop-ci:20261008-runtime-complete python3 ~/.local/share/bilun-ci/laptop_watcher.py --dry-run`. Stop: `systemctl --user disable --now bilun-ci-watcher.timer`. A run that is already serving keeps going until the queue is empty (at most six runners); to end it at once, stop the timer first and then `systemctl --user stop bilun-ci-watcher.service`, which also stops the job in progress (stopping only the service lets the timer start it again a minute later). The image tag lives in `tools/ci/systemd/bilun-ci-watcher.service`: change it there when the reviewed image changes and run the install commands again.

Limits: the laptop must be awake with Docker running. The `gh` login is stored in the desktop keyring, which a logged-out user does not have, so expect the timer to work only while you are logged in; `loginctl enable-linger "$USER"` would not change that unless `gh` keeps its token in `hosts.yml`. Manual `laptop_runner.py` runs stay valid: the watcher stays out of the way while a runner is online. In the seconds between the slots of a manual `--jobs N` run it may start a competing runner, which finds no job, is stopped after five minutes and makes that watcher run exit 1; that is harmless.

Known intermittent main-CI failures are network failures. For `npm ECONNRESET` setup errors: `gh run rerun "$run_id" --failed --repo Safa675/Bilun`, once only. A repeat is real. For `gh`/API connection errors, wait 30 seconds and retry up to five times. Stop a step on real test/build failure or product decisions; record the first error/question in `REPORT.md` (maximum ten lines), without tuning dependencies/workflows.

Verify the PR head still matches its green CI before the authorized merge:

```bash
gh api -X PUT "repos/Safa675/Bilun/pulls/$pr_number/merge" -f merge_method=squash -f "sha=$head_sha"
```

Then verify main contains the tested tree and finish its push workflows before cleanup. The CI workflow name must remain unchanged.

## Staging: one operator command

```bash
ssh contabo-vps 'git -C /opt/Bilun pull -q --ff-only && /opt/Bilun/scripts/staging/update.sh'   # optional SHA argument
ssh -p 8443 -L 3100:127.0.0.1:3100 root@169.58.50.165       # staging UI at http://localhost:3100
```

`scripts/staging/update.sh` runs on the VPS as root and fetches `main` itself with the VPS's read-only deploy key (no bundle from the laptop). It refuses a commit that is not on `main` or has no green CI run, waits while a CI job runs (it holds the CI watcher's lock, so a build never runs beside a 10 GB CI container), builds into a new `/opt/bilun-staging/releases/<sha>-<stamp>` with that release's own `scripts/staging/build.sh` under `MemoryMax=8G`, and stops the build if available RAM falls below 4 GiB. The cache is rebuilt only when the evaluator, data or dependencies changed. It then switches `current`, restarts only `bilun-staging-backend.service` and `bilun-staging-frontend.service`, waits for health on `8101` and `/login` on `3100` (60 tries), and restores the previous release if they do not come up. The old frozen pair (8001/3000) must keep its MainPIDs and health. The last 3 releases and their caches are kept. Same-SHA runs are no-ops. Keep live, Caddy, UFW, Tailscale, OS packages and keys untouched.

## Local SUT package ingest

The hosted SUT Monitor cannot ingest (the workflow is disabled and hosted runners refuse jobs), so a new consolidated SUT package is ingested by hand. Run the scripts in the reviewed image with the lock environment, so the generated parquet comes from the same pandas, polars and pyarrow that CI uses. First time only: `docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home --entrypoint bash -v "$VENV":/venv -v "$PWD":/work:ro -w /work bilun-laptop-ci:20261008-runtime-complete -c 'python -m venv /venv && /venv/bin/pip install -q --no-index --find-links=/opt/wheels --require-hashes -r requirements-ci.lock'`, with `$VENV` an empty folder outside the repo. Then run each script below as `docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home -e LANG=C.UTF-8 -e PYTHONUTF8=1 -e PYTHONPATH=/work/src:/work -v "$VENV":/venv:ro -v "$PWD":/work -v "$SCRATCH":/scratch -w /work --entrypoint /venv/bin/python bilun-laptop-ci:20261008-runtime-complete <script and arguments>` (`$SCRATCH` is any folder outside the repo). Work in a worktree off `origin/main`.

1. `scripts/sut/sut_fetch.py "<announcement URL>" <YYYY-MM-DD>`: one download; it refuses a file that differs from one already committed. Check that `git status` shows no changed tracked file and, for a package already pinned in `ingest_state.json`, that the inventory's `zip_sha256` equals the pinned one.
2. Copy `data/gazette/sut_clauses.parquet` to `$SCRATCH/sut_clauses_old.parquet` (the old side of the clause diff).
3. `scripts/sut/convert_xlsx_to_parquet.py --input-dir "/work/raw data/<YYYY.MM.DD>-…" --defer-state`: converts the current workbooks; MÜLGA (repealed) lists are skipped by design. Compare every rewritten raw partition with `HEAD` ignoring `__source_file` and `__ingested_at`: most differ in provenance only, the rest are the amendments to review.
4. `scripts/sut/build_curated_catalogs.py --overwrite`: while the EK-4A list carries marker-dated rows it exits 1 from the EK-4A snapshot spec only (`ek4a_drugs.parquet` stays); any other `FAIL` line, or a `SKIP … incompatible headers` line for a workbook that carries data, stops the ingest.
5. `scripts/sut/sut_ingest_state.py --input-dir … --inventory …/.sut_package_inventory.json --prepare-corpus`: `data/gazette/sut_clauses.parquet` must not change. If it does, restore it (`git checkout -- data/gazette/sut_clauses.parquet`) and stop: a corpus change forces coverage closure.
6. `scripts/sut/sut_clause_diff.py /scratch/sut_clauses_old.parquet data/gazette/sut_clauses.parquet --new-date <date>` (add `--legacy-input-fingerprints data/gazette/deltas/<date>_clause_diff_inputs.json` when that file exists), then `scripts/sut/sut_delta.py <last_ingested_date> <date>` (add `--legacy-input-fingerprints data/gazette/deltas/<date>_delta_inputs.json` when that file exists).
7. Write the report (`reports/sut-ingest/`) before the last step, and copy `component_receipts` from `data/gazette/ingest_state.json` into it: completion removes them.
8. The same `sut_ingest_state.py` call without `--prepare-corpus` completes the ingest (`completion_scope: complete`). Then run the CI commands and commit the raw package files and the generated data separately.

Limits of the reports: `sut_delta.py` slices the current curated files by date, so an amendment inside a list version whose file-level date did not change shows as 0 changes; the raw-level comparison in step 3 is the review delta. `scripts/sut/catalogs/price_history.py::extract_ek2b` no longer drops rows whose code cell carries an amendment marker: since #226 it strips the marker as EK-2C does.

## Release lanes and pin traps

- **Staging only, synthetic data only** (`BILUN_DATA_MODE=synthetic_demo`). This runbook grants no production deployment permission. Before non-synthetic data, real claims or money enters the product, Safa decides the release path; a real-claims launch path is added deliberately. See [RELEASE-LANES.md](RELEASE-LANES.md).
- The strict release lane was deleted on 2026-10-28; the git tag `archive/strict-lane` holds it.
- `data/gazette/sut_coverage_evidence.json:file_sha256` pins `pyproject.toml` and other dependencies, including pytest metadata bytes. Put markers/default collection policy in `tests/conftest.py`; never silently refresh evidence hashes for green CI.
