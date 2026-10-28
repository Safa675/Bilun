# Cleanup plan: deploy tooling and test bloat (2026-10-26, revised 2026-10-28)

**Status: revised draft for Safa. Nothing is deleted or started until he approves this plan.** First measured at `origin/main` on 2026-10-26; re-measured at `72f73aba` on 2026-10-28 (the numbers below are the re-measured ones).

**What changed in the revision (2026-10-28):** C2 moves up (staging does not use `scripts/deploy`, so it need not wait for C1); C3 shrinks (the copied helpers are mostly not identical); a new C6 covers the synthetic-data tests the first draft left out; C2 archives the lane under a git tag before deleting it and keeps one idea as a short note; C5 adds a weekly size report and four brief rules; the expected totals are corrected (the first draft subtracted 10.3K JSON lines from a Python-only count).

## Why

| | Lines (2026-10-28, physical) | Note |
|---|---:|---|
| `src/` (the product backend) | 71,650 | |
| `scripts/` | 59,440 | deploy 20,364, synthetic 17,043, SUT 15,329 |
| `tests/` (Python) | 161,550 | 2.25× `src/`; plus 10,313 JSON fixture lines in `tests/unit/deploy` |
| `frontend/src` | 54,718 | 16,162 of it tests |

From git history (`git log --numstat`, net lines):
- 1 Oct → 28 Oct: test lines 66.6K → 161.5K, test functions 2,462 → 6,298.
- October: +123.5K test lines against +21.1K `src` lines (about 6:1); weeks 41–44 ran at 10:1 to 18:1.
- Over the whole history 196K test lines were added and 14K deleted (7 %): nothing ever deletes a test.

Where the current test lines sit:

| Area | Lines | Note |
|---|---:|---|
| `tests/unit/domain/prose_rules` | 41,731 | 161 files; 43 per-clause drug-indication files (6,082) |
| `tests/unit/synthetic` | 31,358 | 980 tests for 17K lines of generator; 3 files = 15K lines, 443 tests |
| `tests/unit/domain/billing` | 24,785 | |
| `tests/unit/deploy` + `tests/integration/deploy` | 24,823 Python + 10,313 JSON | the strict release lane |
| `tests/unit/scripts` | 12,034 | |
| `tests/unit/api` | 8,946 | |

Why it happened:
1. Nothing limits test volume, and nothing deletes a test.
2. Proof culture: "fail closed" reviewers fail a change for any concern, so agents add tests and evidence; a reviewer can add a requirement but never remove one.
3. Work-package rules (tests first, 15+ mutation tests, pinned numbers). The orchestrator's own WP1–WP37 added 19.4K test lines for 4.1K code lines (about 5:1).
4. Every test file builds its own bills: 34 helper names are re-defined in 4+ files (7,425 lines; `_claim` alone in 77 files), and 357 of the 388 copies differ from each other.
5. One test module per SUT clause group, each with the same template tests.
6. The strict release lane (21 Sep – 9 Oct): a real incident (frontend rebuilt in place, chunk 404) was answered with bank-grade release gates for a product with synthetic data and no customers; 22 deploy fix PRs in 17 days, one release shipped (5c89ed53, 8 Oct), paused 9 Oct (#200).

What it costs: main CI median 12–16 min in October (5–7 min in July–September), plus up to 14 min queue on the laptop runners; the full suite takes ~18 min on 4 VPS workers; a 1-kuruş price fix (#369) had to touch 91 files. Since #200 the 3,150 strict-lane tests are deselected from default CI, so deleting them shrinks the repo far more than it shortens CI; CI time is measured separately (see "Every package").

## Decisions for Safa (recommended option first)

- **D1. The strict release lane is finished.** Before deletion its last commit is tagged `archive/strict-lane` and the tag is pushed (one command brings it back); then its tooling is deleted. Alternative: keep it.
- **D2. Wave A on real data:** one environment flag `BILUN_WAVEA_ENABLED` replaces the signed-receipt activation. It is on in `synthetic_demo` mode, as today, and off for real data until you turn it on. Alternative: always on.
- **D3. Staging update:** one short script; the VPS fetches `main` itself with its existing read-only deploy key, so no more bundles from the laptop. Alternative: keep the laptop bundle and only slim the wrapper.
- **D4. The old frozen pair** (5c89ed53, ports 8001/3000, no traffic since Caddy sends app.bilun.tech to staging): left running for now. Retiring it is a later step.
- **D5. Off-limits files:** approving this plan allows edits to exactly these, which agents normally may not touch: `.github/workflows/strict-release.yml`, `.github/workflows/deploy.yml`, `.github/workflows/ci.yml` (one path), the `docs/operations/` files named in C2, and `data/synthetic/demo_vignettes.json`.

## Packages (one PR each, in this order)

**C5. Test budget and brief rules (rules, no code). First.**
- One regression test per defect, plus one per new branch the fix adds. Extend an existing test before adding a file.
- New test lines at most 2× the code lines they cover; more needs one sentence of reason in the PR.
- Use the shared builders (C3) and the catalog-price oracle (WP41); never hand-type a catalog price.
- No mutation-testing ritual; at most 6 mutation tests, and only on request for money-critical logic.
- No full-suite run inside a package; the PR's CI is the full gate.
- A change that makes a test obsolete deletes it in the same PR.
- Every brief states the stakes in one sentence ("pre-revenue, synthetic data; a failure breaks the demo for minutes") and does not call the demo "production".
- Every brief carries a size budget (lines and PRs); going over it means stop and ask, not finish.
- "Fail closed" review only for money-computing logic; every other review also answers "is this proportionate, and what can be deleted?".
- A weekly size report (a small script, read-only): lines added per area and the test/code ratio for the week, so a 6:1 month is seen in its first week.
- Lives in a short `docs/testing-policy.md`, the work-package brief template and the heartbeat protocol.

**C2. Delete the strict lane.**
- Tag first (D1). Then delete `scripts/deploy/` (51 files, 20,364 lines), `tests/unit/deploy/` (62 files, 33,774 lines: 23,461 Python + 10,313 JSON) and `tests/integration/deploy/` (2 files, 1,362 lines).
- Delete `.github/workflows/strict-release.yml` and `deploy.yml` (113 lines). The latter is "Release Hold": after every green main CI it only prints "Production release held", and it holds a laptop runner for 3–28 minutes.
- In the app:
  - `src/bilun/api/wavea_activation.py`'s receipt machinery (325 lines) and the `scripts.deploy` imports in `src/bilun/api/startup.py` become D2's flag.
  - `src/bilun/api/routes/wavea_gate.py` reads the flag.
  - `tests/unit/api/test_product_release_imports.py` goes; the activation tests in `tests/unit/api/test_claim_compliance_pipeline.py` move to the flag. `release_identity` is product code and stays.
- Keep `verify_public_assets.py`: move it to `scripts/ci/`, because the CI frontend job and `scripts/ci_local.sh` use it.
- Checked 2026-10-28: the staging build (`build-release.sh`) calls only `scripts/bilun/build_cache.py`, nothing in `scripts/deploy`; the frozen pair runs from its own bundle under `/root`, not from the repo. So C2 does not wait for C1.
- Docs: `docs/operations/RELEASE-LANES.md`, `single-vps-wavea-release.md`, `AI-RUNBOOK.md` and `public-billing-access.md` describe the current staging update and lose the lane. The deployment plans in `plans/deployment/` get a "historical" line. Delete `data/synthetic/demo_vignettes.json` if nothing reads it.
- Keep one idea as a half-page note in `docs/`: before a release, run it on the same bills and list every patient whose totals move (today's "S1–S8 byte-identical" check); worth a ~100-line script once real customers exist.
- Expected: about −56K lines (−55.9K measured).

**C1. Short staging script (adds; deletes nothing in the repo).**
- `scripts/staging/update.sh`, about 60 lines: check that main's CI is green (`gh`), then run the VPS half (over `ssh contabo-vps` from the laptop, or directly when it runs on the VPS).
- The VPS half does what `build-release.sh` and the wrapper do today: fetch the commit; build into a new release folder (Python env, frontend build, cache rebuild); switch `current`; restart the two staging units; wait for health (60 tries); keep the last 3 releases.
- Kept guards: CI green; staging health; the old pair still runs from its 5c89ed53 folder, healthy and unrestarted.
- Proof: deploy current main with it once, with the same health answers, and app.bilun.tech shows the same patients and totals. Then the heartbeat's step S switches to it.
- The laptop wrapper (553 lines, outside the repo) and the VPS `cleanup-wrapper.py` (286 lines) are retired after that.

**C4. One table-driven module for the per-clause drug-indication tests.**
- 43 `test_drug_indication_*` files (6,082 lines); 39 of them repeat the same template tests (rule count, manifest structure and trace, golden samples, gate-B source counts), 5,280 lines.
- They become one parametrized module over a table of clause groups; every current assertion survives as a table row.
- Expected: about −4K lines.

**C6. Synthetic-data tests (new).**
- `tests/unit/synthetic` is 31,358 lines and 980 tests for 17K lines of generator. Three files carry 15K lines and 443 tests that check the medical plausibility of the committed demo data (`test_cohort_plausibility.py` 5,710, `test_cohort_plausibility_clean.py` 4,845, `test_cohort_labs.py` 4,509).
- Step 0 (read-only, its own short report): group the 443 tests by the shape of their assertion and measure how many collapse into table rows. Stop here if the expected cut is under 5K lines.
- Then: the checks become data-driven (a table of expectations over the built cohort) where they share a shape; every assertion survives; `build --check` stays the reproducibility gate.
- These tests guard the data Ahmet Bey reviews: an assertion that cannot be kept is a stop, not a deletion.
- Expected: −8K to −12K lines (estimate until step 0 measures it).

**C3. Shared test bill builders (small).**
- `tests/builders.py` with the two most copied pieces only: `_claim` (77 files, 1,596 lines) and `_drug_line` (40 files, 1,139 lines). Each call site keeps its own defaults as explicit arguments.
- The other 32 copied helpers move to the builders only when a later PR touches that file anyway (C5 rule).
- No assertion changes; each migrated file passes and fails the same tests as before.
- Expected: about −2K lines.

## Order, checks, stop conditions

- **Order:** C5 (rules only), C2, C1, C4, C6 (step 0 first), C3. C2 and C1 touch different files and may run in parallel.
- **Where it runs:** headless on the VPS (Safa, 2026-10-28), as in VPS batches 1–3: the VPS implements, a verification step checks, the PR's CI is the full gate. What has to move to the VPS first is listed in the 2026-10-28 handover, not here.
- **Every package:** the S1–S8 and all-bill report dumps byte-identical, coverage "no change", the full CI green, and staging updated afterwards. Before/after numbers: tests, lines, and CI minutes, with `pytest --durations=30` before C2 and after C6 so the CI gain is measured, not assumed.
- **Stop and ask:**
  - any bill report or demo output moves;
  - C1's script fails to bring staging to the same health;
  - something outside this list imports `scripts.deploy`;
  - a test in C3, C4 or C6 cannot keep its assertion;
  - a package goes over its size budget.
- **Not touched:** Caddy, the old frozen pair and its `/root` folders, the `raw data` and `ilay` folders, and what the engine reports.

## Expected result

About −70K to −74K lines: C2 −56K, C4 −4K, C6 −8K to −12K, C3 −2K. Python test lines go from 161.5K to about 120K, about 1.7× `src/`, falling further under C5. Scripts go from 59.4K to about 39K. No staging ritual, and no runner time spent on Release Hold. The CI gain is reported from the measured durations.
