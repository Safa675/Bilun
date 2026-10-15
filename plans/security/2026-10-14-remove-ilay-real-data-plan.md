# Remove the real ILAY data from the repo, the servers and the laptop

Date: 2026-10-14 (rev 2, after an independent review)
Status: **Phase 1 done on 2026-10-15** (branch `claude/ilay-phase1-remove-real-data`, PR pending Safa's merge). Phases 2–5 not started.

**Who runs what**
- An agent may edit the repo on a branch (Phase 1) and prepare lists.
- Safa runs every deletion, on the laptop, on the VPS or in git history, or his reviewed wrapper runs it.
- Each phase needs Safa's go. Phases 3 and 4 need their own explicit approval.

## In one paragraph

Real hospital data from ILAY sits in the Bilun repo: prescription logs with pseudonymized patient numbers, plus summaries built from them. No part of the product reads it, so removing it changes nothing in the app. It has spread to:
- every copy of the repo: GitHub, 88 folders on the laptop, the staging server and both live release folders;
- the project history.

Taking it out of today's files is easy (Phase 1). Taking it out of the history means rewriting every commit since July (Phase 4), which is disruptive and optional.

## What "done" means

| Stage | Done when |
|---|---|
| A (Phases 1, 2 and 5) | The current repo, staging and the laptop hold no copy except one approved local folder, and a CI test stops it from coming back. |
| B (Phase 3) | Live holds no copy. This happens with the next live release, and only after its source folder is cleaned (see Phase 3). |
| C (Phase 4, optional) | The history on GitHub and in every clone holds no copy. |

Every status report must say which stages are done.

## Why

**What the data is**
- **The ILAY folder.** `data/synthetic/sut/claims/ilay_validation/` holds patient-level logs from real ILAY prescriptions.
  - The writer code puts `patient_id` and `episode_id` in both violation logs (`scripts/validation/validate_drug_rules.py:118-127`, `validate_specialty_rules.py:134-143`).
  - `specialty_pairs.parquet` is most likely patient-level too: its loader outputs patient, episode and date (`scripts/validation/rx_loader.py:223-233,313-315`).
  - The two CSV files are per-rule summaries.
- **The golden set.** `data/gazette/prose_rules/golden/ilay/` (15 JSON files) holds drug, ICD-10, department and severity per real violation, without patient numbers (`scripts/validation/build_golden_dataset.py:28,64-73,160-168`).
- **The harness.** It reads its input from outside this repo (`/home/safa/Documents/ILAY-Health/data/clean/`, `rx_loader.py:28-30`) but writes its outputs into it. That contradicts its own README (`scripts/validation/README.md:81`, "never copied").

**Why it matters**
- **KVKK (judgment, not legal advice).** Health data is special-category personal data (Art. 6). Pseudonymized data stays personal data while the hospital can re-identify patients. Keeping it on GitHub is a transfer abroad (Art. 9).
- **Project rule.** No patient data in any repo.

**The product is unaffected**
- `git grep` finds no reference in `src/`, `tests/` (except one test of the golden set), `.github/`, `scripts/deploy/` or the build files.
- The app reads fixed claim file names only (`src/bilun/cache/builder.py:56-63,145`; `src/bilun/domain/claims/parquet_reader.py:69-79`).

## Where the copies are

Checked on 2026-10-14 by file name, size and git metadata only. No data content was opened.

### In the repo today

Both folders were added in `9a233212` (2026-07-20, PR #36) and never modified. 184 commits on `main` came after it.

| File | Bytes | Blob |
|---|---|---|
| `ilay_validation/violation_log.parquet` | 301,249 | `e4df7d4c` |
| `ilay_validation/specialty_pairs.parquet` | 269,085 | `a355c0f3` |
| `ilay_validation/rule_compliance.csv` | 96,535 | `358acb52` |
| `ilay_validation/specialty_rule_compliance.csv` | 52,490 | `efcdd980` |
| `ilay_validation/specialty_violation_log.parquet` | 8,123 | `8eb3d35f` |
| `golden/ilay/*.json` (15 files) | 30,998 | 15 blobs |

### In the history

- **The blobs.** 20 blobs (758,480 B) are reachable from branches and tags. 2 more older blobs (orphan commit `a03a3c14`) are reachable only from this laptop's reflog, which makes 22 in all. The list is in the scratchpad file `ilay_blobs.txt`; regenerate it with `git rev-list --all --objects -- <both folders>`.
- **Where they live on GitHub.** `main`, the tag `strict-lane-paused-98fad3f5`, and 218 old pull-request refs. PR #36 certainly contains them, and the 182 PRs after it very likely do.
- **In this checkout.** 7 of its 14 saved stashes.

### Other copies

| Where | What |
|---|---|
| Staging `/opt/bilun-staging/releases/2d083d17…`, `…/8d60a43e…` (current) | Release worktrees: files + history |
| Staging `/opt/bilun-staging/repository.git` | The bare repository the releases come from |
| Staging `/opt/bilun-staging/bundles/bilun-79f52f43….bundle` (181 MB) | Full bundle; history includes `9a233212` |
| Live `/root/bilun-release-5c89ed53-20261007-online/bundle/candidate-backend` (**running**) | Files. Its history is in `/root/bilun-release-5c89ed53-20261007-online/operator/.git` |
| Live `/root/bilun-release-499dff4c-20261004/bundle/candidate-backend` | Files. Its history is in `/root/bilun-release-499dff4c-20261004/operator/.git`. This tree is also the **baseline** the running release copied its claims folder from (its records name `baseline_claims_dir`) |
| Live records `bundle/pinned-inputs.json`, `preparation-pins.json`, `semantic.json` | List the 5 file names and their hashes (no data) |
| Live `/root/bilun-release-{53431821,67db3308}-inputs/*.bundle` (61 KB, 108 KB) | **Not checked.** The size suggests thin bundles, which exclude the blobs |
| Laptop: 88 folders named `ilay_validation` | 73 Codex task worktrees; 7 in `~/.cache/overnight-verify-deploy/`; 3 `~/.cache/ui-review-*`; 4 under `~/work/`; this checkout. Each clone also holds the history, and probably also a `golden/ilay` folder |
| Laptop full bundles | `~/work/bilun-deploy-plan/staging-ops/bilun-79f52f43….bundle`; `staging-ops/runs/update-20261009T082845-*/bilun-98fad3f5….bundle` (181 MB each); `~/Documents/Codex/overnight-2026-10-07/lanes/semantic-release/producer-observation.bundle` (170 MB) |
| Laptop temporary test copies | 4 tests copy the whole claims folder into pytest's temp folders (`/tmp/pytest-of-safa/`, the CI basetemp) |
| Checked, not a copy | Docker volume `bilun-ci-4622e8b6c508-work`: its `.git` is empty and it holds none of the blobs |
| Unknown | VPS provider backups or snapshots (check in the provider panel) |

Find the laptop copies with:
```
find /home/safa /tmp -xdev \( -name ilay_validation -o -path '*golden/ilay' \)
```

### Related real data found on the way (decide whether it joins Phase 4)

- **`reports/finans_flagged.xlsx`** (597 KB). Added in `b19f9b30`, deleted in `2735b5f9`, still in history. Its writer script describes line-level rows from the Acıbadem Finans extract, which `.gitignore:35-36` says never to commit.
- **`raw data/Interviews/*Kent Hastanesi Röportajlar.docx`.** Removed in `c25e6a98`, still in history.
- **The separate `ILAY-Health` repo** (private, on GitHub) tracks 4 docs that contain pseudonymized patient numbers. Is it in scope?
- **Side effect of this review.** A reviewer's search printed 4 such lines into this session's agent log.

## Decisions for Safa

1. **Does an ILAY data agreement say where the data may be kept?** It decides how urgent Stages B and C are.
2. **Keep the harness outputs in one local folder outside every repo, or delete them?** Recommendation: one local folder, if the agreement allows it.
3. **Remove `golden/ilay` too?** Recommendation: yes. Keep it in the local folder, and make its test skip when that folder is absent.
4. **Live (Stage B).** Recommendation: wait for the next live release, but clean its source first (Phase 3). If decision 1 requires speed, reopen the strict lane for it under `docs/operations/RELEASE-LANES.md`. Do not delete files from the running release by hand: its records pin them, and the lane's tools must not be changed while it is paused.
5. **Rewrite the history (Stage C)?** It needs:
   - an exception to the runbook's "No force-push" rule (`docs/operations/AI-RUNBOOK.md:3`);
   - temporarily lifting the push protection on `main`;
   - re-cloning every copy;
   - translating 47 commit IDs that 43 tracked files cite (reviewer's count).
   
   Recommendation: decide after decision 1. If yes, do it in the same window as the strict-lane reopen.
6. **Add `finans_flagged.xlsx`, the interviews docx and the ILAY-Health docs to this cleanup?** Recommendation: yes for the two files in this repo's history, in the same rewrite. The ILAY-Health repo needs its own small plan.

## Phases

### Phase 1 — The repo's current files (normal PR; an agent may do it on a branch)

- [x] **1.1** Safa copies both folders to the local folder from decision 2. Then, on a branch: *(done 2026-10-15 with Safa's approval: copied to `~/bilun-local/ilay-validation/` (mode 700, outside any git work tree, identical by checksum, 5 + 15 files), then removed from the branch)*
  ```
  git rm -r data/synthetic/sut/claims/ilay_validation data/gazette/prose_rules/golden/ilay
  ```
  (the second folder per decision 3).
- [x] **1.2** The harness writes to a folder named by an environment variable, outside the repo (`validate_drug_rules.py:40`, `validate_specialty_rules.py:41`, `build_golden_dataset.py:24-28`). Add `.gitignore` lines for both repo paths; `.gitignore:42-43` currently re-includes all of `data/synthetic/`. *(done: `scripts/validation/output_paths.py` reads `$BILUN_ILAY_VALIDATION_DIR`, default `~/bilun-local/ilay-validation`, and refuses paths inside the repo; `.gitignore` lists both folders)*
- [x] **1.3** ~~`tests/unit/domain/prose_rules/test_specialty_real_data.py` skips, with a reason, when the local golden folder is missing.~~ Changed with Safa's approval: the test is replaced by `test_specialty_scope_cases.py`, synthetic cases for the same three rules (only the rule ids were read from the old files), plus two strict `xfail` cases for the matching defects in Safa675/Bilun#256.
- [x] **1.4** Update the references:
  - `scripts/validation/README.md:38-40,66,121-127`; make line 81's promise true.
  - `plans/backend/specialty-scope-validation-plan.md:157,180-181,194,269,287`.
  - `plans/update/2026-08-07-track-e-phase0-audit.md:34`, which wrongly calls `rule_compliance.csv` synthetic.
- [x] **1.5** Add a CI test that fails when any tracked path contains `ilay_validation` or `golden/ilay`. Prove it with a mutation: stage a dummy file at each path and see it fail. *(done: `tests/unit/test_no_real_patient_data_paths.py`; an empty file force-staged in each folder made it fail, and it passes again after cleanup and with git missing from PATH)*
- [x] **1.6** Verify (results in the PR description):
  - `git ls-files | grep -c -E "ilay_validation|golden/ilay"` prints 0.
  - The full suite passes in the CI image.
  - A synthetic cache build gives the same report numbers before and after.
- [x] **1.7** Check CI on `main` first (rule 10), then open the PR. Merge is Safa's call. *(CI on `main` @ `1c22ee9c` green before the push)*

### Phase 2 — Staging (the reviewed wrapper; Safa runs it)

- [ ] **2.1** After the merge, Safa runs `~/work/bilun-deploy-plan/staging-ops/staging-update.sh`. The new release has neither folder.
- [ ] **2.2** The wrapper keeps two releases (`keep_releases: 2`; `cleanup-wrapper.py:177` refuses any other value). So the previous release, which still holds the files, survives until the next update. Recommended: let one more normal update retire it. The runbook allows only wrapper-proven VPS cleanup (`docs/operations/AI-RUNBOOK.md:65`), so removing it by hand would be an exception that only Safa can make and run.
- [ ] **2.3** The staging bare repository and the staging bundle keep the history. Only Stage C changes that. The wrapper cannot rebuild them, and deleting `repository.git` would cut the release worktrees off from it; the cleanup then refuses to run (`cleanup-wrapper.py:163,187,212`). Re-seeding needs a written operator procedure first (Phase 4.3).
- [ ] **2.4** Verify, read-only:
  - No staging release holds either folder.
  - Staging health is OK.
  - The live PIDs and both live health answers are unchanged.

### Phase 3 — Live (Stage B; separate approval; no hand deletion in the running release)

- [ ] **3.1** Why live cannot be cleaned by hand:
  - The running release copied its claims folder, ILAY folder included, from `baseline_claims_dir`, the previous live tree (`scripts/deploy/prepare_single_vps_release.py:803-812`). The next release would copy from its own baseline the same way.
  - The release records pin the 5 files (`pinned-inputs.json`, `preparation-pins.json`, `semantic.json`).
  - The lane's own checks use the trees' git history (`scripts/deploy/capture_release_preflight.py:452`, `prepare_single_vps_release.py:584`).
- [ ] **3.2** At the strict-lane reopen, before preparing the next live release, Safa removes the ILAY folder from the baseline claims folder that the release will copy. The strict-lane runbook decides how that baseline is chosen; follow it, no shortcut.
- [ ] **3.3** After the release, check that its `pinned-inputs.json` lists no ILAY file. Then retire the old release trees and their `operator/.git` repositories under the lane's own procedure.
- [ ] **3.4** Do not modify the lane's tools while it is paused (`docs/operations/RELEASE-LANES.md:3`).

### Phase 4 — History rewrite (Stage C; optional; separate approval; planned window)

- [ ] **4.1 Protect work first.** Run Phase 5.1 on every clone. Then:
  - Export the 14 stashes of this checkout (for example `git stash show -p stash@{n} > stash-n.patch`).
  - Commit or save the uncommitted `tasks/*.md`, the plans and the audit report.
  - Keep `~/work/bilun-staging-source-20261009` and `~/work/bilun-deploy-plan/staging-ops/`; the wrapper needs both (`staging-update.sh:6`). Keep `~/work/bilun-land`.
  - Make a full backup (a mirror clone plus these folders) and store it outside every repo.
- [ ] **4.2 Prepare the tool.** `git-filter-repo` is not installed; install it, for example with `pip install git-filter-repo`.
- [ ] **4.3 Write the operator procedure for staging.** It re-seeds `repository.git` and the bundle from the rewritten history and re-creates the release worktrees. Review it before use, because the wrapper cannot do it (see 2.3).
- [ ] **4.4 Rewrite.** On a fresh mirror clone, run:
  ```
  git filter-repo --invert-paths --path data/synthetic/sut/claims/ilay_validation/ --path data/gazette/prose_rules/golden/ilay/
  ```
  Add the paths from decision 6. Keep the old→new commit map that filter-repo writes.
- [ ] **4.5 CI first.** Run the full CI on the rewritten `main` before anything is pushed.
- [ ] **4.6 Push.** This step is Safa's and needs the runbook exception from decision 5:
  1. Lift the force-push protection on `main`.
  2. Force-push all branches and tags.
  3. Restore the protection.
  4. Ask GitHub Support to remove cached views and the 218 old pull-request refs, following GitHub's "Removing sensitive data from a repository".
- [ ] **4.7 Fix references.** Translate the commit IDs with the map: 47 IDs in 43 tracked files, including 3 strict-lane scripts and source-authority files that are pinned by hash. Re-generate those pins and check them. The live pair `5c89ed53` will not exist on GitHub until it is re-released (Phase 3).
- [ ] **4.8 Re-clone.** Re-clone the working copies listed safe in 5.1, re-seed staging with 4.3, and replace the operator bundles.
- [ ] **4.9 Verify.** On a fresh clone, `git rev-list --all --objects` shows neither folder, and none of the 22 blob IDs exists (`git cat-file -e` fails for each).

### Phase 5 — Laptop (an agent prepares the list; Safa deletes)

- [ ] **5.1** For each clone holding a copy, record:
  - `git status --ignored`;
  - `git stash list`;
  - `git log --branches --not --remotes` (works on detached HEADs, unlike `@{u}..`).
  
  Mark each clone "safe to remove" or "has unpushed work".
- [ ] **5.2** Safa removes the obsolete clones, worktrees, cache folders and pytest temp folders. Where a clone must stay, removing the folder clears only its working tree; its history goes only with Stage C and a re-clone.
- [ ] **5.3** Safa removes the three full bundles once nothing needs them: after 4.8, or right away if Stage C is not chosen and they are not needed as backups.
- [ ] **5.4** Re-run the `find`. Only the local folder from decision 2 remains.

## Verification summary

| Stage | Check |
|---|---|
| A | The CI guard passes, and its mutation test fails on a re-added file. `find` on the laptop and on staging returns only the approved local folder. The live PIDs and health answers are unchanged. |
| B | The next live release's `pinned-inputs.json` lists no ILAY file. |
| C | A fresh clone holds none of the 22 blob IDs. |

## Out of scope

- The raw ILAY source data in `~/Documents/ILAY-Health/data/clean/` (gitignored there).
- The `ILAY-Health` repo's own docs (decision 6).
- Rewriting the validation harness beyond its output paths.
- The synthetic cohort redesign (`plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`).
- Legal review (decision 1).

## Risks

- **Stage A alone looks finished but is not.** GitHub history, staging's bare repository, the bundles, live and the clones' histories still hold the data. Reports must name the stage.
- **Stage C can lose work or break releases** if it runs before 4.1–4.5. Stashes, uncommitted files, the wrapper's source folders and hash-pinned files are all at risk.
