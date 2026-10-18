# Lessons

Persistent lessons captured from corrections during work. Reviewed at the start of every session per AGENTS.md §1.

## 2026-10-18 — After a squash merge, `git log | grep <subject>` cannot find the branch's commits: decide "is the work in?" by content

**Pattern:** The brief for the newborn-detection task opened with a Step 0: `git log --oneline | grep -i "review round 3"` must show a commit, else merge the newborn-bed branch. That branch had been squash-merged as #319 in the meantime: the grep found nothing although every line of the branch was already in `origin/main` (HEAD == `origin/main`), and merging as told would have put 18 commits of identical content into the history. The test that settled it: `git diff --name-only $(git merge-base HEAD <branch>) <branch>` listed 36 files and `git diff HEAD <branch> -- <those files>` was empty.

**Rule:** Whether a branch's work is in the tree is a question about content, not about commit subjects: it is in when `git diff HEAD <branch> -- $(git diff --name-only $(git merge-base HEAD <branch>) <branch>)` is empty. A subject missing from `git log` proves nothing after a squash. A brief that says "merge branch X if its commit is missing" should say "if that diff is not empty" instead; the follow-up cards `short-stay-bed` and `bed-double-billing` of the newborn block start from the same Step 0.

## 2026-10-18 — A mutation loop restores from a byte-identical backup, never with `git checkout --` while the file has uncommitted edits

**Pattern:** To prove a new test bites, I removed one contract key at a time from `public_contracts.json` and restored the file with `git checkout -- <file>` after each mutant. The file also held my own uncommitted additions (two new keys), so the first restore silently threw them away: the second "mutant" then failed for a reason that had nothing to do with the mutation, and I read it as a kill. I noticed only because the mutation script's own assertion failed on a key that should have been there.

**Rule:** In a mutation loop, copy the file to a backup first and restore with `cp backup file` followed by a `cmp` (or work in a scratch clone, as the independent reviewer did). `git checkout --` is for committed state only. After the loop, check `git diff --stat` shows exactly your own change, and re-run the unmutated test once to see it green.

## 2026-10-18 — A motor's amount is right only against every condition its sibling motor honours: probe the sibling, don't just fix the named defects

**Pattern:** The brief for the newborn bed motor named two defects (no netting of billed lines, no ICU gate) and a double count with the standard-bed motor. Fixing those three would have shipped rows on an amount that was still wrong: while writing the plan I ran the motor on the same in-memory bills as its sibling for each condition the sibling honours, and found a third overcount nobody had listed. The standard-bed motor bundles the bed into an EK-2/C package window (10-day stay, group-B package: 0 TL); the newborn motor counted 4,409.80 TL on the same bill. The same probe showed that the department tokens flag every pediatric ward stay as a newborn Kuvöz stay (3 x 440.98 on a pneumonia claim), a detection question that rows would have made visible. None of it shows in tests of the named defects.

**Rule:** Before calling a motor's amount right, and before giving it action rows, run it and its sibling on the same in-memory bills for every condition the sibling honours (netting of billed lines, ICU and package windows, day counting, short stays, rooming-in, department and diagnosis signals) and write each difference down with the measured numbers. Fix what changes the same amount; report what is a detection question for the owner. Do this probe before the plan's decision list is final, not at the review.

## 2026-10-18 — A "mirror" of a live path on a cached path needs a parity test on the real cache shape, not a hand-made payload

**Pattern:** `patient_recovery_summary_from_payload` carried a comment ("mirror the keys of `_get_top_action_type`", audit finding #12) and one unit test with a hand-made payload. Seven of its twelve keys read `@property` amounts (`confirmed_yatak_try`, `uplift_savings_try`, `total_uplift_try`, ...) that the cache never stores: `json_ready` keeps dataclass fields only. On a payload as `cache/builder.py` writes it, S1 gave `none` (live: `strategy`) and S2 gave `none` (live: `yatak_puani`); the fix of #12 only matched the key names. A fresh cache hid it (the cohort summary is built live), so nothing failed in three months. I found it only because the task asked for a parity test and I fed it the production serializer's output instead of copying the neighbouring key pattern; the new four keys would have been dead too.

**Rule:** Before adding a key to a function that must agree with its twin, build the twin's input with the production serializer from real reports (`json.loads(json.dumps(json_ready(report)))` for the cache, the endpoint's serializer for the API; the 8 showcase bills, copay exempt and not) and assert equality of the whole result and of the intermediate values, not of one key. A hand-made payload only proves the mapping you imagined. Where the shapes differ, derive from data every shape has (the rows), not from a property only one of them carries. This repeats the 2026-09-20 lesson (live/cache contract parity): the check must run on the real round trip.

## 2026-10-18 — Measure a branch against `origin/main`, and keep dev-run leftovers out of CI-parity checks

**Pattern:** In the worktree the local `main` ref was three PRs behind `origin/main` (98861219 against 3abe33a3), so `git diff main...HEAD` showed 144 files and +43,773 lines: P3 and P4 content that is already merged. I nearly took it for the branch's size. Separately, a local `next dev` run left `frontend/.next/dev/types`, and `tsc --noEmit` failed on those generated files although CI, on a clean checkout, has none.

**Rule:** compare a branch with `origin/main` after `git fetch` (or with the PR's base), never with the local `main`. Before a CI-parity check, delete what a local run leaves behind (`frontend/.next`, `frontend/.env.local`, `.cache/`) or run the check on a clean clone, as the CI-image gate does.

## 2026-10-18 — A new billing-report field or step has seven touchpoints; the fail-closed tests found them one by one

**Pattern:** To explain the S3, S4 and S8 KPIs I added rows to `recommended_actions`. The S3/S4 half was a short collector change. The S8 half needed row data the report did not keep, so I added a report field and a step. The public-projection test (`test_public_projection_preserves_cohort_business_results_and_cached_nulls`) failed because `src/bilun/api/public_contracts.json` did not list the field; the rule-surfacing audit failed closed because the new call had no metadata, and its committed outputs and its count of 5 aggregate-only findings went stale; the engine proof failed on three JSON files because it counts every action row and `action_count`. My first design built the rows inside `finalize_report_totals`, which would have made a totals function originate findings.

**Rule:** Before adding data or a step to the billing report, list the touchpoints and do them in one pass: (1) the field in `types.py`; (2) the step in `compute_patient_billing_report` as its own named call, never inside a totals function; (3) `public_contracts.json`, section `BillingActionReport`; (4) `collect_billing_actions` and the `_finding_type` sets; (5) the surfacing-audit metadata (`EXPECTED_REPORT_CALLS`, `PATIENT_REPORT_META`, `EMISSION_OVERRIDES`) and then `python scripts/audits/build_rule_surfacing_inventory.py --write`; (6) the showcase proof JSON, regenerated with `reports/synthetic-data/2026-10-15-showcase-proofs/prove.py <stories>`, never by hand; (7) the frontend label maps (`recommendedActions.ts`, `RecommendedActionsPanel.tsx`, `messages/{en,tr}/billing.ts`). Save a baseline of all 16 showcase reports (8 stories, copay exempt and not) before the change and diff it after: only the intended `action_count` may move.

## 2026-10-18 — Do not `cat` a scratch env file to see what is in it

**Pattern:** To find out how an earlier session had run the UI, I printed `~/.cache/bilun-p4-scratch/ui_env.sh`. It holds the throwaway local test account's password hash and session secret, which then sat in this transcript. Nothing was sent anywhere, but the print was avoidable: all I needed was whether the file exists and which variables it sets.

**Rule:** For files named `*env*`, `*secret*`, `*.key`, `.env*` and for any scratch file of another session, check existence with `ls` and names with `grep -o '^export [A-Z_]*'`; load values with `set -a; . file; set +a` in a subshell and never echo them.

## 2026-10-18 — Background agents do not restart by themselves after a usage-limit stop: cap the parallel agents and checkpoint

**Pattern:** I ran four to five implementation and review agents at once, each with several mutation workers. The usage window ran out after about three hours (HTTP 429, "resets 1:50am"); the three agents then working ended as `failed`, my own turn was cut by the same limit, and nothing restarted them when the limit reset: a failed agent continues only when the orchestrator sends it a message. Safa came back hours later to find the work idle and asked why it had not resumed. Nothing was lost only because each agent saved its edits at step boundaries.

**Rule:** keep at most three agents running at once and say so before launching more; give each agent a persistent notes folder and tell it to write its progress after every step; when a usage-limit or API failure ends agents, first check the worktree (tests, ruff, `build --check`), commit what is consistent as a WIP checkpoint, then resume each agent with `SendMessage`. Tell Safa at launch that a limit stop needs a manual restart, and what it costs.

## 2026-10-18 — Test new data code on CI's polars 2.0.0 and on a 300-copy table, not only on the 8-patient showcase

**Pattern:** The cohort checks passed 10,600 tests locally on polars 1.41.2, but CI locks polars 2.0.0, and the first gate in the CI image failed one test: it compared fresh Parquet bytes with the committed file, and 2.0.0's writer stamps its own version into the footer (the data was identical). A mutation reviewer then found a second 2.0.0-only problem that no test reached: `pl.format` of two columns panics (`assertion failed: i < self.len()`) on a joined table of 15,000 rows cut down to a few findings, in the plausibility module since its first commit. Only a test on a table larger than the 8-patient showcase shows it. Three smaller notes from the agents: Polars prints a Rust-side deprecation notice for `is_in(pl.Series)` that `-W error` does not catch (pass lists); a join does not keep the order of its left side, so sort explicitly; `tests/conftest.py` rewrites `data/gazette/prose_manifests` at session start, so run containers on a clone, not on the worktree.

**Rule:** compare tables by content (schema and sorted values), never raw Parquet bytes against a committed file; build message text with `+` or `concat_str`, not `pl.format`; give every new check a scale test (the showcase copied 300 times with renamed ids must give the findings of the small table); run each slice in the CI image (`~/.cache/bilun-p4-scratch/ci_gate.sh <label>`) as soon as it is committed, not only at the end.

## 2026-10-17 — Session scratchpads are tmpfs: a reboot wipes the briefs, runners and scripts kept there

**Pattern:** The briefs, the Argon runner, my mutation script and the takeover snapshots of the P4 work lived only in the sessions' scratchpads under `/tmp/claude-1000/...`. `/tmp` is a 16 GB tmpfs. Safa rebooted at 20:05 and all of it vanished while four background agents were stopped half way. The saved JSONL transcripts under `~/.claude/projects/-home-safa-Documents-Bilun/` let me rebuild the three briefs byte-identical (Write tool inputs, sizes equal to what I had read), and stopped agents can be resumed with SendMessage because their transcripts are on disk. Without that the reviews and the E2 slice would have started from nothing.

**Rule:** Anything a later step or another agent needs again (briefs, runner scripts, verification and mutation scripts, takeover snapshots) goes to a persistent place: `~/.cache/bilun-p4-scratch/` or a tracked file in `tasks/` or `plans/`, never only into the scratchpad. Give every background agent a persistent scratch folder and tell it to save intermediate results there. After a restart, check `uptime -s` and `ls` the scratch paths before trusting them, and tell resumed agents which files are gone.

## 2026-10-17 — Interval ends differ per catalog: read the builder's convention and test the boundary day

**Pattern:** The pathway checks compared EK-4A `valid_until` with `>=`, the way they compare EK-2B/EK-2C `valid_to`. EK-4A spans are half-open, `[valid_from, valid_until)`: 272 rows end on 2026-08-29 and 295 start that day. So S2's window ended one day after KLACID 500 MG IV left the list, and no test noticed, because every mutation I wrote used a date far from the edge. An independent reviewer found it by querying the catalog. The builder's docstring (`scripts/sut/catalogs/ek4a_history.py`) and the engine's reader (`ek4a_as_of.py:152`, `valid_until > day`) both said so.

**Rule:** Before writing a validity check against a dated catalog, read how its builder and the engine's reader define the end, and write a test on the boundary day itself (the day a row ends and the day its successor starts). Do not assume one end convention for all catalogs: EK-2B/EK-2C `valid_to` is inclusive (the next row starts the day after), EK-4A `valid_until` is exclusive (the next row starts on it).

## 2026-10-16 — A status report Safa cannot follow is a failed report: Turkish, plain first

**Pattern:** While five agents ran (catalog dates, money fixes, three reviewers), I sent short English status messages packed with PR numbers, clause ids, code lists and follow-up inventories. Safa replied that he could not understand anything from the latest one, asked to switch to Turkish, and asked why one job had been running for an hour, which none of my messages had explained.

**Rule:** For Bilun engine/SUT work, report in Turkish:
- Lead with what is happening in plain words, what it means for Safa, and whether he needs to do anything.
- Then, only if needed, the details: which PR, which numbers.
- For every running job, say how long it has run, why, and when it should end.
- One decision per question, in everyday words, with my recommendation.

## 2026-10-15 — Run the artifact checks and the test suite one after the other, never at the same time

**Pattern:** For the ILAY Phase 1 branch I started the full pytest suite in the background and, at the same moment, ran `scripts/sut/compile_rules.py --check` and `scripts/sut/audit_manifest_parity.py --drug-only`. Four tests failed: manifest hash mismatches, a coverage count of 758 vs 732, and bucket ids "not in clause_traces". All four passed on unchanged `main`, on the branch when run alone, and in a second full run on its own (8,354 passed). The failures came from the concurrent scripts touching the same manifest artifacts, not from the change.

**Rule:** Run `compile_rules.py --check`, `audit_manifest_parity.py` and anything else that rebuilds or compares `data/gazette` artifacts sequentially with pytest, never in parallel. When a failure shows up, prove causation first. Run the failing tests on unchanged `main` (stash) and alone on the branch before blaming or clearing the change (see the 2026-06-30 lesson).

## 2026-10-14 — Check `~/second-brain/inbox/` and local config (`~/.gemini/config/config.json`) before answering runtime/billing questions

**Pattern:** When Safa asked whether his GCP Free Trial credit (`01D62C-CF9CBE-0ADC91`) covers `gemini-4-argon` in Antigravity and why the balance looked unchanged, I relied on a stale Sep 10 `gbrain` recall and generic Antigravity OAuth assumptions, claiming Argon in Antigravity runs on a built-in subscription quota rather than GCP Vertex AI. Two hours earlier on the same day, another session had enabled Antigravity Enterprise ADC mode (`"enableAdc": true` in `~/.gemini/config/config.json` against `golden-index-505019-r1`) and logged the setup in `~/second-brain/inbox/20261014T163857Z-safa-loq-17irx10-claude-code-acb223.md` (not yet indexed by nightly `gbrain`). Furthermore, comparing the earlier `₺12,401` credit balance with Safa's pasted `₺12,291.36` balance and querying `monitoring.googleapis.com` (`aiplatform.googleapis.com/publisher/online_serving/model_invocation_count`) proved that 143 `gemini-4-argon` calls (19.42M input / 131k output tokens) hit `golden-index-505019-r1` and deducted `₺109.64` from the Free Trial credit.

**Rule:** Before answering any question about Safa's local environment, model routing, or billing: (1) check `~/second-brain/inbox/` in addition to `gbrain recall`, because same-day `brain add` entries live in `inbox/` until the nightly filing run; (2) inspect the actual local config (`~/.gemini/config/config.json`, ADC files) and live telemetry (`monitoring.googleapis.com`) rather than assuming default consumer auth.

## 2026-10-14 — A data-realism audit is a checklist with coverage, not a list of what the samples showed

**Pattern:** Asked to evaluate the synthetic demo cohort, I merged three sampled audits (three patient pages, a price check, a few agent passes) into a verdict that read as the list of problems. Safa found a class it never measured (one bill mixing unrelated departments: VA-ECMO, colectomy and a nail-bed revision on a neurology sleep-apnoea claim), then said the evaluation still was not good enough. The gap was method, not effort: no dimension list, so whatever the samples happened to show became "the problems".

**Rule:** Before auditing a dataset's realism, write the dimension checklist first and measure each one over the whole cohort: identity against the catalogs as of the service date; arithmetic; cross-table links; coherence within one line, within one bill, across one patient's timeline; care setting and facility; sex and age; dates; money against a real-world anchor; and what the product shows on it. Report every dimension as checked (with count/denominator), clean, or not checked. Never present a sampled audit as an inventory; say what was not covered.

## 2026-10-13 — "Unchanged" needs the whole value, not a print cut at N characters

**Pattern:** Diffing two SUT packages cell by cell, I printed the changed cells cut at 400 characters, saw only a provenance marker at the end of the EK-3O row and wrote "values unchanged" in the plan, the report and a commit message. The cell had a third clause after the marker. In the same pass I described a changed bone-marrow package row as "gains a second marker" from a truncated print; the new row restored a clause the previous amendment had dropped. An independent review caught both. The data was right; my claims were not.

**Rule:** A statement that something did not change, or changed in only one way, must come from comparing the full values (equality, or a word-level diff of the whole text) and quote that output. A truncated print is for orientation only. Run the independent review before the report and the commit messages are written, not after.

## 2026-10-04 — Corpus compatibility includes every positional consumer

**Pattern:** Bounded clinical bindings and focused tests stayed valid after a corpus replacement, but old coverage, manifest traces and retrieval artifacts still joined positional C* IDs to different clause bodies. Updating a renal test literal alone would conceal the wider dependency break.

**Rule:** Before publishing a corpus replacement, inventory all ID-based derived artifacts and consumers. Compare canonical keys and full body hashes against the actual new corpus, regenerate manifests before coverage, refresh the final source evidence closure, and verify retrieval artifacts. Require negative stale-artifact/consumer checks; do not call a provisional table or a bounded-family test result complete corpus compatibility.

Format per entry:
- Date
- Mistake pattern (not just the incident)
- Rule that prevents recurrence

## 2026-09-29 — Check established demo-data scope before asking about real records

**Pattern:** During a proposal for anonymous billing access, I asked whether Bilun contains real patient/billing records before checking the existing synthetic-data setup. The user had to restate that the app has no real records.

**Rule:** Before asking a data-sensitivity clarification, inspect the project's documented/current dataset and reuse established session facts. For this Bilun setup, the user confirmed all patient and billing data is synthetic/demo. Design anonymous billing access on that basis; ask again only if new evidence indicates the data scope has changed.

## 2026-09-25 — Rule removal needs full CI parity before opening a PR

**Pattern:** I removed a registered pricing rule and its demo, then opened a PR after focused tests and selected artifact checks. I missed a stale row in the committed registry-coverage parquet and hard-coded cohort-tier counts in an unselected test; the full CI backend suite caught both.

**Rule:** Before publishing a rule-removal PR, run the exact CI test command and generated-artifact checks on the final branch, not only focused suites. Explicitly reconcile every derived registry artifact and synthetic cohort count with the removed rule, and disclose any unrun gate before calling the PR verified.

## 2026-09-25 — A review-only label does not rescue a pricing rule without SUT authority

**Pattern:** A post-service price-increase detector had no encoded SUT clause permitting repricing, yet it remained in the optimization engine after automatic rebilling was disabled. It still displayed a monetary "recoverable" amount, so the product suggested value that the service-date tariff could not support.

**Rule:** For SUT-first pricing features, require an amendment-specific effective-date or transition clause that makes the proposed amount payable on the actual service date before surfacing any recoverable amount. If that gate is absent, remove the opportunity across runtime, registry, API, UI, demos, and generated artifacts; a review-only flag or zeroed headline total is insufficient.

## 2026-09-20 — Focused green tests do not prove semantic arbitration or live/cache contract parity

**Pattern:** A first-pass implementation passed its focused suites while independent review exposed order-dependent route selection, an incomplete public legacy projection, cached/live count drift, false exactness in genuine legacy payloads, missing noncoverage states, and UI/projection contract gaps.

**Rule:** For correctness migrations, test the public boundary and the real cache round-trip in addition to private helpers. Reverse/permuted full-corpus inputs, discover corpus-derived shadowing families instead of freezing counts, validate every structured payload fail-closed, and assert that live, cached, API, cohort, and frontend representations preserve the same identity, status, severity, bounded evidence, null-money semantics, and honest uncertainty.

## 2026-09-19 — Static surfacing audits must validate source contracts and whole-file invariants

**Pattern:** A static inventory trusted a declared evaluator order without proving that its direct detector calls, source mappings, metadata maps, and emitted IDs agreed; a projection-only symbol check also missed forbidden compatibility imports elsewhere in the source file. The evaluator taxonomy then misclassified the compute-side canonical stage as internal even though it is a surfaced product stage.

**Rule:** For static runtime inventories, inspect the complete source file for forbidden symbols, resolve bare and module-qualified imported calls, and fail closed when direct detector sources, source-to-rule mappings, required metadata maps, and actual emitted IDs do not form an exact contract. Classify each entrypoint separately from its real product surface: a canonical evaluator consumed by a visible generic projector is visible at that product entrypoint, while a validation-root flat result remains hidden.

## 2026-09-19 — Temporary dependency cleanup must use a stable path after `cd`

**Pattern:** A frontend test trap tried to remove `frontend/node_modules` after the shell had changed into `frontend`, so it targeted `frontend/frontend/node_modules` and left the temporary symlink behind.

**Rule:** When a temporary resource is created before changing directories, anchor trap cleanup to the absolute worktree path (or capture the original directory) and verify absence in a separate command before reporting the gate complete.

## 2026-09-19 — Distinguish a proposed-write transport rejection from a native tool failure

**Pattern:** Read-only native Codex commands had completed successfully, but a rejection occurred before a proposed repository write became a native event. I generalized that boundary rejection into a provider/tool failure and stopped, even though the dedicated patch path had not failed.

**Rule:** When a supervisor provides transport-specific recovery instructions, preserve the exact failure boundary. If read-only native calls succeeded and repository writes are required to use `codex_apply_patch`, use that dedicated tool for every modification and stop only if the dedicated patch call itself fails or is rejected. Quote the exact patch-tool result on failure; do not relabel a pre-write rejection as a generic native/provider failure. For large generated artifacts, keep generation read-only and materialize bounded chunks through `codex_apply_patch` rather than switching to shell writers.

## 2026-09-03 — Local Next "closing by itself" is a Turbopack V8 OOM, not a closed tab or a free port

**Pattern:** The user could not open localhost and said the app kept closing. Port 3000 was empty; backend :8001 was fine. Logs showed `FATAL ERROR: ... JavaScript heap out of memory` at ~15GB after ~15–30 minutes of `next dev` (Turbopack default on Next 16). Restarting with Turbopack just died again. Treating it as a zombie/port issue (or telling them to refresh) wasted a round.

**Rule:** When the frontend vanishes while uvicorn stays up, read the Next terminal for `heap out of memory` / `Ineffective mark-compacts` BEFORE killing ports or blaming the browser. Default Turbopack `next dev` on this machine leaks until V8 hits ~half of RAM. Use `next dev --webpack` (and a 4GB `max-old-space-size` cap) for local `start.sh`. Confirm with `curl http://localhost:3000/login`, not `127.0.0.1`.

## 2026-08-29 — A loopback OpenAI shim must not treat Hermes Authorization as a Cursor key

**Pattern:** The Contabo Cursor proxy preferred any incoming `Authorization: Bearer …` over systemd `CURSOR_API_KEY`. Hermes 0.20 fills empty custom-endpoint keys with the placeholder `no-key-required` (OpenAI SDK refuses an empty string). The gateway process does not have `CURSOR_API_KEY` in `os.environ` (it is not in `OPTIONAL_ENV_VARS` / `_EXTRA_ENV_KEYS`, and the unit has no `EnvironmentFile`), so Telegram POSTs to `127.0.0.1:8765` authenticated as `Bearer no-key-required`. Cursor CreateAgent then 401s `Invalid User API Key` and Hermes surfaces HTTP 502. CLI `hermes chat --provider cursor` worked because that short-lived process load_dotenv'd the real key. Catalog GET still returned 200 because a failed catalog fetch falls back to a hardcoded model list.

**Rule:** For any OpenAI-compatible proxy in front of Cursor (or any provider that actually authenticates): (1) ignore Hermes placeholders (`no-key-required`, `no-key`, `aws-sdk`, `undefined`/`null`/`none`) and any Bearer that is not the expected key prefix (`crsr_`); always use the process env key. (2) Do not diagnose "invalid API key" from `/v1/models` 200 — prove with a chat POST and log `auth source/kind/len` (never the secret). (3) Hermes request dumps under `~/.hermes/sessions/request_dump_*` show the redacted Authorization; read those before rotating keys. (4) Do not restart `hermes-gateway` while `hermes setup` is on pts/0 — the proxy can be fixed independently.

## 2026-08-22 — The BILUN cache DuckDB keeps SUPERSEDED builds; verify the ACTIVE build_id or you'll "find" stale rows. And regenerating a stale cohort surfaces pre-existing golden/test drift — expect it, don't misattribute it.

**Pattern:** After purging the fake demo lines and rebuilding the cache, I grepped `.cache/bilun.duckdb` for `SUT-DEMO`/`DEMO-L44` and found 121 cells — concluded the rebuild had used stale data. Wrong: the cache tables (`patient_billing_report_rows`, `patient_outcome_base`, …) carry a `build_id` column and RETAIN every historical build; `build_meta` marks old ones `superseded` and `build_pointer_scopes` names the active one. My un-filtered grep matched superseded builds. Filtering `WHERE build_id='<active>'` gave 0 demo cells. Separately: the cohort had last been regenerated 2026-06-28; 318 commits later (2026-07-01 SUT amendment `5e82c31`, 163 newly-wired billing rules, a generator RNG-path change) the committed data was stale, so regenerating broke 5 goldens/tests that pinned pre-amendment values (Tier A 0003 band, test_f011, test_f015, test_0001, copay rate-patient). A pristine-HEAD regen reproduced all of them — proving the drift pre-existed and was not caused by my change.

**Rule:** (1) When verifying a BILUN cache rebuild, ALWAYS scope queries to the active build: read the active id from `build_pointer_scopes` (or `/health.active_build`) and add `WHERE build_id='<id>'`; an unscoped grep over the cache DB reports superseded history as if it were live. Row-count deltas in `build_meta` (e.g. 96→94 bill rows) are a good sanity signal that the new build reflects the new data. (2) Before regenerating a cohort whose last regen is old (`git log -- data/synthetic/sut` vs head), EXPECT golden/test drift from intervening catalog/generator/engine commits; when tests fail post-regen, first reproduce on a pristine-HEAD worktree regen to attribute cause (pre-existing drift vs your change) BEFORE editing goldens. Recalibrate drift-pinned goldens to the current deterministic values only after confirming the scenario semantics still hold; retarget spot-checks whose claim no longer exhibits the property (and say so in a comment). (3) A backend restart for cache rebuild needs `BILUN_STARTUP_POLICY=rebuild` in the ENV of the launched process and the port actually free — check both, and confirm `/health.active_build` changed to the new build id.

## 2026-08-22 — A removal plan built from generator+validator+obvious-tests misses downstream pins; and "not in catalog" needs every name form

**Pattern:** Planning the purge of 13 fake-coded synthetic claim lines, I inventoried the generator, validator, manifest/vignettes, and two billing tests — and called it done. A plan review found 5 live pins I missed: an API test file pinning per-patient violation counts, a workbook-content test asserting the demo material *names*, a vignette-golden index list, hardcoded tier counts (24/17), and a validator branch checking the MEDULA-0411 drug anchor — plus an inline drug-row injector block in orchestrate.py (I had only flagged its import), a golden JSON still pinning the fake codes, and human docs advertising the patients. I also overclaimed: "the 6 oncology drugs are not in EK-4A" was wrong for 5/6 because I searched INN names (NIVOLUMAB) while the Turkish catalog lists brand names (OPDIVO). And I wrote "Tier B / unranked" without checking that unlisted patients classify as Tier C.

**Rule:** Before planning any feature/data REMOVAL in this repo, inventory ALL six pin surfaces, not three: (1) generators (including inline injection blocks, not just imports/wiring), (2) validators (every branch keyed on the feature, e.g. `elif sonuc == "0411"`), (3) curated data + GOLDEN artifacts (`data/gazette/prose_rules/golden/*.json`), (4) ALL test layers — unit, API (`tests/unit/api/`), synthetic-golden, and hardcoded cohort-shape counts/index lists, (5) human docs (`data/synthetic/README.md`, `DEMO_COHORT.md`, `docs/gazette/*.md`), (6) exported workbooks (`.xlsx`), not just parquets. Grep for the feature's scenario tags, patient ids, codes, AND display names. Separately: before asserting "X is not in catalog", search every name form the catalog could use (INN AND brand name, Turkish-folded); one negative search is not evidence of absence. Tier/shape claims ("unranked", counts) require reading the classifier's else-branch, not guessing.

## 2026-08-16 — Maintain Bilun's native design system; eliminate AI-sloppy redundant banners and cluttered cards

**Pattern:** Generated UI components with verbose explanatory subtitles and redundant header cards ("MEDULA red kuyruğu — reaktif acil ayıklama...", chat banner placeholders, ad-hoc cards) which felt "AI sloppy" and deviated from Bilun's clean, premium, minimal aesthetic.

**Rule:** 
1. **Strictly adhere to Bilun's design tokens and primitives:** Use `Surface`, `Eyebrow`, `Stat`, `DataTable`, `Chip`, and `Button` with clean spacing (`gap-4`, `space-y-5`, `p-0`), subtle borders (`var(--border-subtle)`), tabular numerics, and muted uppercase tracking. Avoid bloated custom cards or decorative fluff.
2. **Never render redundant explanatory banners:** Omit unnecessary descriptive subtitles like "MEDULA tarafından reddedilen talepler için reaktif acil ayıklama..." or wordy workspace banners when the table/filters are self-explanatory.
3. **Respect core terminology changes:** When renaming navigational tabs (e.g., "Operasyonlar" → "Red Kuyruğu"), propagate cleanly across translations (`constants.homeTabs.operations.label`) and remove any lingering legacy headers or redundant chat prompts.

## 2026-08-15 — A lazy module-level loader that publishes its "loaded" flag BEFORE populating the cache races under ThreadPoolExecutor; a memoizing resolver then freezes the poisoned empty result forever

**Pattern:** `rules_catalog._load_coverage()` set `_coverage_loaded = True` *before* assigning `_coverage_cache`. Cohort billing reports run on a `ThreadPoolExecutor` (`cohort_runner.map_parallel`), so a worker racing the first load saw `loaded=True` with a still-`None` frame, `get_clause` returned nothing, and the new `resolve_clause_key` — decorated with `lru_cache` — cached the empty `clause_key` for the process lifetime. Symptom: unit tests green (single-threaded first call loads cleanly) but the LIVE cache rebuild emitted `clause_ref.clause_key == ""` for exactly the coordinates resolved early in each worker, while later coordinates resolved fine. Tests did not catch it because they never reproduce the concurrent first-load.

**Rule:** Any module-level lazy loader must publish its ready flag only AFTER the value is assigned, guarded by a lock — and any resolver that memoizes must NOT cache a miss/empty result. Concretely: (1) wrap the load in `threading.Lock`, assign cache then flag inside the lock; (2) keep a manual success-only memo (skip `lru_cache` when failures are possible), so a transient miss retries instead of freezing; (3) when a feature will be called from a ThreadPoolExecutor (all `cohort_runner` paths), add a concurrency regression test that resets module state (`monkeypatch` the cache/flag) and hammers the resolver from N threads asserting every call gets the real value. "Unit tests pass" is not evidence a lazy initializer is correct under the cohort runner — verify through the threaded path.

## 2026-08-14 — A scene crack that "launches but hangs" is stuck on ONLINE auth (OnlineFix/EOS), not on Wine/Proton/GPU

**Pattern:** "0xdeadcode" (OnlineFix) releases of online-only games silently HANG — not crash — while polling the crack's auth servers (`api.epicgames.dev`, `online-fix.me`). The game process shows 66 threads, ~5GB virtual but tiny resident growth, near-zero CPU, no GPU process, and no engine log (`SixDays.log`) because it never reaches UE4's log init. The prior session kept fighting Wine/Proton/Steamless/GPU, but the real blocker was the OnlineFix cloud handshake.

**Rule:** When a cracked game "launches but never shows a window", before touching Wine/Proton/GPU: (1) sniff the hang (`ss -tnp` for ESTABLISHED sockets to Cloudflare/Akamai + `WINEDEBUG=+winsock` to see `connect`/`select`/`WS2_recv` polling), (2) identify the crack layer (a `winmm.dll`/`version.dll` proxy exporting an `OnlineFix` symbol + `dlllist.txt` listing `OnlineFix64.dll`/`StubDRM64.dll` + a shrunken `EOSSDK-Win64-Shipping.dll` vs a larger `.of` original), (3) decide offline-bypass (drop the proxy DLL so the game uses the system DLL, restore the original SDK, rely on Goldberg `steam_api64.dll`). A game process at 0% GPU + polling a network socket for minutes = online-auth hang, not a rendering bug. The fix is crack-layer surgery, not driver/prefix tweaking.

## 2026-08-13 — Don't call a game build "official" from preserved depot files alone; check the Steamworks layer and the license

**Pattern:** Diagnosed `/home/safa/Documents/Ready.or.Not` as an "official Steam build" because `installscript.vdf` carried a valid Valve signature and the content paks were signed. In reality it was a RUNE repack: `steam_api64.dll` was replaced (original preserved as `steam_api64.rne`), the account had zero license hits for app 1144200 in `config.vdf`, and Steam logs showed the game was never launched via Steam (`LaunchApp [AppID 1144200]` absent). Repackers preserve depot files byte-for-byte — signed install scripts and paks prove nothing about the executable/Steamworks layer.

**Rule:** Before classifying any software folder as a genuine/official install, require multiple independent signals: (1) an install manifest (`appmanifest_*.acf`) in a registered library OR a license for the appid in `config.vdf`; (2) the Steamworks DLL (`steam_api64.dll`/`steam_api.dll`) present unrenamed next to the game executable; (3) absence of repack markers (renamed `.rne`/`.o` dlls, `crack`/`RUNE` folders, uniform extraction timestamps across all files). One preserved signed file is never enough — same multi-signal pattern as the 2026-08-07 inventory lesson.

## 2026-08-06 — pytest in this repo can MUTATE committed artifacts; verify staged content at commit time, not at first-read time

**Pattern:** Committing a user's manifest change (`effective_date: 2026-07-25 → 2026-08-01`), I read the diff at session start, then ran the full pytest suite, then committed — but a test (`test_copay_exemption_gate_b.py::test_manifest_has_encoded_clause_ids_union`) called `write_artifacts` without a `manifest_path`, so every pytest run rewrote the committed L1.8 manifest with `date.today()`. The committed value silently became 2026-08-03 while my commit message claimed 2026-08-01. The user's intended value was lost and the discrepancy was only found 3 days later when the date moved again (→ 2026-08-06). Aggravating factor: this repo's conftest ALSO writes on purpose (`reconcile_drug_manifests(write=True)` session fixture), so "pytest mutates the tree" is normal here — which makes accidental mutation easier to miss.

**Rule:** A working-tree value read at session start is NOT the value you commit. Before every commit:
1. `git diff --cached` the exact files being committed and confirm the content matches the stated intent (message and content must agree).
2. After any full pytest run, re-run `git status --short` — new modifications to committed artifacts mean a test writes outside tmp_path; that is a test bug to fix, not noise to absorb.
3. Any test calling a writer (`write_artifacts`, `reconcile_*`, `build_*` with default output paths) must pass an explicit tmp output path; audit with `grep -c write_artifacts` vs `grep -c manifest_path` per file when suspicious.
4. A date/counter field that always equals "today" in a committed artifact is a write-leak signature — compare sibling artifacts' values before believing it.

---

## 2026-08-07 — "Repo'da yok" demeden önce raw data envanterini çıkar — ingest state'e de bak

**Pattern:** Copay freshness açığını açıklarken "01/07/2026 sonrası metin repo'da hiçbir yerde yok, yeni SUT paketi gerekir" dedim. Kullanıcı paketi gösterdi: `raw data/2026.07.01-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/` (konsolide, EK klasörlü). Dahası `data/gazette/ingest_state.json` paketin 07-12'de ingest edildiğini söylüyordu — eksik olan yalnızca Branch B (docx → clause corpus) imiş. İki ayrı kanıt (klasör + state dosyası) varken yokluk iddiası yaptım.

**Rule:** Bir veri/artifact "repo'da yok" demeden önce: (1) `raw data/` + `data/` altında isim/envanter araması yap (klasör adları tarih önekli), (2) varsa ingest/state/manifest dosyalarını oku ("ingest edildi ama downstream koşmadı" yarım-başarı durumları vardır), (3) yokluk iddiasını ancak ikisi de boşsa kur. Yarım-ingest durumlarında doğru soru "paket var mı?" değil "hangi adım koştu, hangısı koşmadı?"dır.

---

## 2026-08-01 — Never include build artifacts or dependencies (.next, node_modules, lockfiles) when counting LOC

**Pattern:** When calculating LOC for the frontend, the script failed to exclude Next.js build output directories (`frontend/.next/`), resulting in reporting 497,124 lines instead of the actual ~30,615 lines of true frontend source code.

**Rule:** When calculating lines of code (LOC) or searching codebase volume, ALWAYS explicitly exclude `.next/`, `node_modules/`, `dist/`, `build/`, `.cache/`, and generated lockfiles. Report only human-authored source code (`src/`, `app/`, `components/`, etc.).

---

## 2026-07-13 → 2026-07-20 — Graphify installed but NEVER used by any agent; tool removed (126 subagents, 0 graphify calls)

**Pattern:** graphify was installed specifically to cut subagent token usage on codebase exploration — `graphify-out/graph.json` (11MB) was present and fresh, the `graphify` binary (v0.8.49) was on PATH, the `/graphify` skill was registered, and AGENTS.md had escalating rules from soft guidance up to a Hard Rule. A full audit of all agent session directories under `~/.zcode/cli/agents/` (16 sessions) showed **zero** executed `graphify query`/`path`/`explain` commands across every single one. The word "graphify" appeared 927 times in transcripts, but every occurrence was either AGENTS.md text being echoed into context (~574) or the model discussing graphify in prose — never an actual Bash command execution. The tool was fully wired, rules escalated from guidance to Hard Rule, and it produced **zero** value. Developer research confirmed this is an industry-wide pattern: AGENTS.md/CLAUDE.md instructions are hints, not enforcement, and agents default to Grep/Read because it's lower-friction.

**Rule:** Don't install agent-integration tools that depend on the agent choosing to use them. Before installing any "agents will automatically use X" tool:
1. **Verify it actually works.** Check real session logs for actual tool invocations, not just mentions. A tool mentioned 927 times with 0 executions is dead weight, not an integration.
2. **Instruction-following is a hint, not a contract.** Escalating wording (guidance → MUST → Hard Rule → critical failure) does NOT increase invocation rate. The failure isn't the wording; it's the assumption that instructions reliably control agent tool selection.
3. **Right-size the tool to the repo.** Graphify's token savings (40-70%) only materialize on large repos where Grep returns too much. At ~146K LOC with clean module boundaries, Grep + Glob + Read genuinely works. Don't pay the complexity tax for a benefit you won't see until 500K+ LOC.
4. **The costs are real even when the tool is unused.** graphify cost 255M of `.git` bloat, inotify watcher exhaustion (ENOSPC errors), context-window tax (574 echoed mentions per session), and maintenance overhead (regenerating graphs after every change). All for zero executions.

---

## 2026-07-10 — Single-shot benchmarking of a stochastic system (LLM) is noise, not data

**Pattern:** Asked to test whether `opencode run --variant {low,high,max}` affects GLM-5.2 reasoning. I ran ONE shot per variant, got a counterintuitive result ("max was fastest/shortest"), and reported it as a finding while *simultaneously* writing "1 run per variant can't separate variant effect from noise." The user correctly called this out. When I re-ran with 5 shots/variant (20 total), the trend FLIPPED: `low` was actually the fastest (20.6±2.5s) and `high`/`max` slowest (~27s) — the opposite of my 1-shot claim. My single-shot conclusion was pure sampling noise dressed up as a result.

**Rule:** LLM output latency/length/quality is a stochastic distribution, not a deterministic value. When asked whether a parameter (variant, model, temperature, provider) affects output:
1. Run **N≥5 shots per condition**, never 1. Report mean ± std, not single observations.
2. Never publish a conclusion AND a caveat that invalidates it ("here's the result, but n=1 so it's noise"). If n is too small to separate signal from noise, the honest answer is "I need more runs," not a guess.
3. A single observation that contradicts the group trend is noise by default — do not headline it.
4. Use a task that DISCRIMINATES on the dimension you're measuring (a too-easy puzzle that every variant solves correctly tells you nothing about quality differences). Pick a task where low reasoning plausibly fails and high reasoning succeeds.
5. State statistical limitations explicitly: with n=5 and high variance, call effects "suggestive," not "proven."

---

## 2026-07-06 — Multi-week epic: the gap-count drop came from STATUS HONESTY not ENCODING

**Pattern:** The rule-encoding gap-closure roadmap (Phases 0-5) was framed as "encode ~2,183 unencoded clauses to drop the gap count." After 5 phases of work, the gap count dropped 1,897 → 601 (−68.3%), but the breakdown of WHERE the drop came from was surprising:
- **Phase 1.1 (structural reclassification, 908 clauses → non_algorithmic):** 0 gap-count change. The `_is_structural_gap_excluded` function was ALREADY excluding these from gaps; Phase 1.1 only fixed the status LABEL. The gap count was already correct.
- **Phase 4.2/4.3 (copay + specialty reclassification, 279 clauses → non_algorithmic):** −279 gap-count change. These WERE gaps because they weren't structural (no `_is_structural_gap_excluded`), but they were supporting text (indication lists, report specs) whose decisional parents were already encoded. Reclassification was honest — but it was reclassification, not encoding.
- **Phase 5 (drug motor flip partial→implemented, 984 encoded clauses):** −989 gap-count change. THE LARGEST single drop. 984 of 1,162 drug_indication gaps were ALREADY ENCODED but counted as gaps because the motor was `partial` (commit `ec33851`), and partial status counts as gap unconditionally. Flipping back to `implemented` dropped them. Zero encoding work.
- **Actual encoding (Phase 4.1 + 5.3, 16+35=51 new clause linkages):** −51 gap-count change. Only ~4% of the total drop came from actual encoding.

**Rule:** When a gap-count reduction goal is set, distinguish three mechanisms and track them separately:
1. **STATUS HONESTY** (fixing coverage_status labels so the gap predicate fires correctly) — accounts for ~80% of this epic's drop. The biggest wins came from discovering that clauses were mislabeled (partial vs implemented, structural vs actionable).
2. **RECLASSIFICATION** (moving non-decisional text to non_algorithmic) — accounts for ~20%. Honest but requires per-clause text auditing to avoid hiding real regulatory content.
3. **ENCODING** (adding new rules + gate_b_sources linkages) — accounts for ~4%. The hardest, most labor-intensive work, but the smallest numerical impact because most clauses were either already encoded, honestly non-decisional, or correctly deferred.
A roadmap that promises "encode N clauses to drop the gap count by N" will misallocate effort unless it first audits which mechanism applies to each clause. Concretely: before encoding, check `has_rule_encoding` — if the clause is already encoded but still a gap, the issue is status honesty (the motor's coverage_status), not missing encoding.

---

## 2026-07-05 — "Reclassify to reduce the gap count" is dishonest when the clauses contain real regulatory text

**Pattern:** The Phase 1 plan (approved by user, sourced from Agent 3's diagnostic) proposed reclassifying ~250 "price-oracle decision-rule" clauses (in `pricing_ek2b`, `copay_rate_ek2c1`, `copay_exemption_ek1a`, `drug_discount_prose`, `surcharge_general`) to `non_algorithmic` to drop the headline `has_algorithmic_gap` count from ~1897 toward ~450. Agent 3 had labeled them "ANNEX_LOOKUP — text just references annex tables; the code motor resolves these." When I actually READ the gap clause text before reclassifying, ~248 of the ~250 contained substantive regulatory content — copay participation-fee rules ("katılım payı uygulanacak sağlık hizmetleri"), exemption criteria, surcharge logic. Only 12 of 1897 gaps were genuinely pure annex references (text like `a) Tıbbi Uygunluk Aranacak Tıbbi Malzemeler (EK-3/C-1)`). Reclassifying the other 248 would have hidden real encode-debt to make the dashboard number look better — exactly the metric-manipulation the codebase has been fighting (the recent `ec33851` "honest drug_indication partial status" commit moved in the opposite direction).

**Rule:** Before reclassifying any clause to `non_algorithmic` to reduce a gap count, READ THE ACTUAL TEXT of a representative sample. A clause is honestly `non_algorithmic` only if its text is purely navigational/structural (a heading, an amendment marker like `(Değişik: RG-...)`, or a bare annex citation with no deontic content). Concretely:
1. The diagnostic-report agent's text-classification ("ANNEX_LOOKUP", "DECISION_RULE", "REFERENCE_TEXT") is a HEURISTIC from sampling, not ground truth. Verify with a direct text read before acting on it at scale.
2. A clause whose text contains regulatory verbs (`karşılanır`, `ödenir`, `uygulanır`, `yapılır`, `alınır`, `gereken`) is NOT non_algorithmic regardless of which code motor implements it — the regulatory content exists and is unencoded as a prose rule.
3. Distinguish "status honesty" (Phase 1.1 — moving structural amendment/heading markers to `non_algorithmic`) from "gap-count reduction" (the temptation). Phase 1.1 made the status breakdown honest but did NOT move the gap count, because `_is_structural_gap_excluded` already correctly excluded those clauses from gaps. The gap count was already correct; only the status labels were misleading.
4. If a phase's value proposition is "drop the gap count by N" and inspection shows the N clauses have real regulatory text, STOP and surface the conflict. Do not execute the reclassification. The honest path is to encode them (Phase 4/5) or build the evaluator (Phase 2/3), not to relabel them out of the gap population.

---

## 2026-07-05 — Diagnostic-report baseline goes stale when commits land between report and implementation

**Pattern:** Produced a full rule-encoding diagnostic report (2,175 unencoded, 914 gaps, 19.4% gap_pct, 3,954 implemented). The user approved a multi-week roadmap using those numbers as every checkpoint target. Between the report and implementation, commit `ec33851` ("honest drug_indication partial status") landed, flipping `drug_indication_prose` from `implemented` → `partial` in `rule_registry.py:350`. This roughly doubled `has_algorithmic_gap` (914 → 1,896) and inverted the implemented/partial split (3,954/53 → 1,585/2,422), because `partial` clauses count as gaps unconditionally (`coverage.py:381-382`). I almost started coding against the stale 914 target. The catch was only because I ran a fresh baseline query on the parquet immediately before touching anything and the numbers didn't match the report.

**Rule:** A diagnostic report's headline numbers have a shelf life. Before any implementation phase begins, RE-CAPTURE the baseline metrics with a fresh read-only query against the live artifacts — do not trust numbers in a report (even one produced the same session) once commits may have landed. Concretely:
1. At phase-0 entry, run the baseline query (counts of `coverage_status`, `has_rule_encoding`, `has_algorithmic_gap`) and DIFF it against the report. If any number moved, investigate `git log -- <parquet> <relevant .py>` for intervening commits before proceeding.
2. Every phase checkpoint target must be expressed as "current value ± N" or "monotonic increase/decrease", NOT as an absolute number copied from the report. Absolute targets silently become wrong.
3. When a commit's message says "honest X status" or "reclassify", assume the headline gap metric moved — those are exactly the commits that invalidate report baselines.
4. Pay special attention to `coverage.py:381-384`: the `has_algorithmic_gap` definition makes `partial` and `implemented ∧ ¬encoded` BOTH gaps, so any `coverage_status` flip between those two states moves the gap count even when no clause's encoding changed.

---

## 2026-06-29 — Parallel subagents editing the SAME shared file (coverage.py / rule JSONs) clobber each other — orchestrator-only writes

**Pattern:** Launched 7 parallel encoding subagents. Each was told to (a) append its rules to a shared rule JSON and (b) wire its manifest into `scripts/sut/prose/coverage.py`. Because they ran concurrently, each read coverage.py from its own snapshot and wrote it back — last-writer-won destroyed the others' edits. Result: coverage.py ended with only 2 of ~8 manifest wirings; `specialty_materials_prose.json` dropped 152→78 rules (a subagent read a stale/uncommitted 49-rule base and overwrote wave2a/2b additions); cumulative encoded count collapsed 817→231. The batch scripts + manifest JSONs on disk were fine — only the SHARED aggregation files were lost.

**Rule:** Shared mutable files are orchestrator-only. Subagents produce self-contained artifacts (own `*_batch_rules.py`, own merge script, own dedicated manifest JSON) but must NOT touch shared aggregators (`coverage.py`, shared rule JSONs, shared manifests). The orchestrator runs each merge script IN SEQUENCE and applies all coverage.py wiring itself. Concretely:
1. A subagent's clause_ids go into its OWN dedicated manifest file, never a shared master.
2. Concurrent appends to a shared rule JSON race — run merges SEQUENTIALLY from the orchestrator.
3. All `coverage.py` manifest-registry additions + section-override functions are written by the orchestrator in one pass after subagents return.
4. If a subagent reports "the JSON only had N rules" where N < expected, it read stale/clobbered state — STOP and reconcile before its write propagates the loss.

---

## 2026-06-29 — Encoding subagents must be sub-section-sized, not cluster-sized (timeout tail-loss)

**Pattern:** Launched 4 parallel encoding subagents sized by SUT *cluster* — A1 §4.2 (383 clauses), A2 §2.4 (166), A3 §3.3 (132), A4 §2.6 (56). All 4 hit the 10-minute tool timeout. The small one (A4, 56 clauses) "completed" but under-encoded by 9 (47/56) — it ran out of time on the tail sub-sections. The 3 large ones produced zero files. Re-launching the same way would repeat the failure.

**Rule:** Size encoding subagents by *sub-section* (~20-60 clauses), not by top-level cluster. A single 383-clause §4.2 encode cannot finish in 10 minutes — split into ~6 sub-section batches, each its own subagent. Cap per-subagent targets at ~50-70 clauses. When a subagent times out, verify encoded-count vs target-count and specifically check the *last* sub-sections in its scope (tail-loss is the failure mode).

---

## 2026-06-25 — Regenerating synthetic data surfaces latent code bugs hidden by the old data's shape

**Pattern:** Fixing the false-positive material flags required regenerating the cohort. The new cohort's slightly different values (different rate distributions, different material assignments) exercised a code path in `compute_optimization_summary` that the OLD cohort never reached — specifically the `Decimal(str(rate_val)).quantize(...)` line at `aggregator.py:157`. That line used `Decimal` but the module never imported it (`from decimal import Decimal` was missing). The import was latent-broken since the line was written, but only the regen exposed it — and it crashed the production cache rebuild, taking the billing endpoint 503. The old data happened to never produce a rate that hit the quantize branch, so the NameError was invisible.

**Rule:** A synthetic-data regeneration is NOT just "swap the parquet" — it is a full-pipeline smoke test that can surface dormant bugs in every downstream consumer. Before declaring a regen-based fix deployed:
1. After regenerating, **rebuild the cache** (`BILUN_STARTUP_POLICY=rebuild` + restart), not just restart the backend. The cache builder processes the data through the entire compute path; a stale cache hides code bugs that the rebuild exposes.
2. A cache rebuild that silently fails (no `active_build` in `/health`) means the rebuild **errored** — check `journalctl -u bilun-backend` for the traceback. `active_build: null` with `status: ok` is a degraded state, not healthy.
3. Latent import bugs (`NameError`) hide in code paths only reached by specific data values. When a regen changes data distributions, grep for unqualified builtin/stdlib names (`Decimal`, `date`, `Decimal`) in the modules the cache builder touches.
4. The deploy workflow restarts services but does NOT rebuild the cache. If a deploy includes regenerated data, the cache rebuild must be an explicit deploy step — otherwise the frontend serves stale findings until the cache is manually rebuilt.

---

## 2026-06-24 — A synthetic row missing optional flag columns coerces the whole DataFrame column to float, breaking string-truthy validators

**Pattern:** Injecting one extra material row (a MEDULA rejection anchor) that set only the `prose_flags` dict but NOT the L4.4 `specialty_flags`. When the per-claim material dicts were assembled into a DataFrame and written to the xlsx workbook, the specialty columns were `NaN` for that one row. Because the column now mixed `True`/`False`/`NaN`, pandas/the Excel round-trip stored them as floats (`1.0`/`0.0`/`nan`) instead of object strings. The validator's `_truthy()` does `_strings(series).str.lower().isin({"true","1","evet","yes"})` — and `_strings(1.0)` → `"1.0"`, which is NOT `"1"`, so EVERY row in that column failed the truthy check. Result: 35 spurious "Expected at least one material line with X=true" errors even though the parquet (read separately) showed the flags correctly. The single incomplete row poisoned the entire column's dtype.

**Rule:** When adding a new row to a list-of-dicts that gets assembled into a DataFrame and written to a workbook/parquet, the row MUST include EVERY column the sibling rows carry — especially boolean flag columns — even if the value is just the default `False`. A missing key becomes `NaN`, and if the column mixes `NaN` with bools, the round-trip dtype flips to float, which silently breaks downstream string-based parsers. Concretely:
1. When appending a material row outside the normal builder (`_append_material_lines_for_claim`), spread BOTH `**_default_prose_material_flags()` AND `**_default_specialty_prose_flags()` — the specialty flag set is large and easy to forget.
2. If a validator reports "expected at least one row with flag X" but the parquet clearly has the flag, the bug is the WORKBOOK column dtype (NaN-induced float coercion), not the data. Read the `.xlsx` sheet, not the parquet, to diagnose.
3. Diagnose column dtype with `df[col].dtype` and `df[col].value_counts(dropna=False)` — a float dtype with `0.0`/`1.0`/`nan` is the smoking gun.
4. The post-pass coverage functions (`_ensure_specialty_flag_coverage`) cannot fix this — they set flags on existing rows but the NaN row still forces float dtype. The fix must be at row-construction time.

---

## 2026-06-22 — When a test reads a committed artifact and a sibling test rebuilds the same artifact, check both before changing a shared constant

**Pattern:** Fixing `test_phase5_manifest_traces_all_4214c_clauses` (reads committed manifest JSON, section_clause_total=828) by changing every `832` in the file to `828` — including line 116 in `test_build_phase5_manifest_partition_is_disjoint`, which rebuilds the manifest live from `sut_clauses.parquet` (which has 832 clauses). The committed manifest JSON is stale (828) relative to the current `sut_clauses.parquet` (832). The two tests exercise different sources, so they legitimately expect different counts. Blindly replacing all occurrences broke the rebuild-based test.

**Rule:** When a test file has one test reading a committed JSON/parquet and another test rebuilding the same artifact from a source parquet, the committed artifact may be stale. Before changing a shared numeric assertion:
1. Identify which tests read the committed artifact vs which rebuild from source — grep for the fixture/`build_*` call.
2. Only update assertions in the tests that read the committed artifact.
3. The rebuild test's count reflects the current source data and should be left alone (it was passing for a reason).
4. Flag the committed-artifact staleness (828 committed vs 832 source) as a separate data-rebuild task, don't paper over it by lowering the rebuild assertion.

---

## 2026-06-19 — Don't advise on a subsystem's data dependencies without reading the compute path

**Pattern:** When asked "do I need to rebuild the cache after the SUT replace?", I correctly identified the stale-process issue but hedged the *correctness* answer with "the rebuild may not visibly change much because claim lines carry their own billed_amount." That hedge was unverified speculation — I hadn't yet traced whether the DRG compute path actually reads EK-2C. When I finally did trace it (`src/bilun/domain/analytics/drg.py:196 get_ek2c_price_for_date`), it confirmed DRG pricing DOES depend directly on the rebuilt EK-2C catalog. So the cache rebuild IS a correctness requirement, not optional — my hedge downplayed a real staleness bug (later confirmed as audit finding B-C2/B-C7: no staleness detection mechanism exists). The backend audit (3 parallel subagents) later surfaced that the entire read-write-connection + no-staleness-check architecture means stale data is served silently with no self-healing.

**Rule:** Before advising whether a data-source change requires a downstream cache/recompute rebuild:
1. Read the actual compute path that produces the cached artifact — grep for `read_parquet` / `get_ek2*` / catalog lookups in the domain layer, not just the cache layer's `data_loader.py` (which only reads patient/cohort parquets, not gazette catalogs).
2. Distinguish "cache reads gazette catalogs directly" (rebuild definitely needed) from "cache only reads pre-computed patient summaries" (gazette changes are baked in at build time, so rebuild still needed).
3. Never hedge with "may not change much" without a concrete trace showing the dependency is absent. If you haven't traced it, say "I need to verify whether the DRG compute reads EK-2C" — don't guess.
4. A running process holding a DB lock is ALWAYS a stale-data signal worth surfacing prominently, not a footnote — DuckDB single-writer semantics mean that process has the pre-rebuild data in memory and will serve it until killed.

---

## 2026-06-19 — Latent pipeline bugs surface during data-source swaps; verify the full chain end-to-end

**Pattern:** Replacing the active SUT tebliği (2026.01.17 → 2026.04.08) exposed TWO pre-existing latent bugs that were invisible as long as the committed parquets were never rebuilt: (1) `xlrd` was never declared in `requirements.txt`/`pyproject.toml`, so all `.xls`-sourced annexes (EK-1A, EK-3B-1/2, EK-3C-1, EK-2Ç) silently failed conversion — the committed parquets were artifacts from a prior machine that had xlrd. (2) `_find_raw_parquet` (`scripts/sut/_common.py`) deliberately skipped `effective_date=unknown` partitions, which broke EK-1A (legitimately undated `.xls`, no date in filename) even though its raw parquet existed. Both only surfaced when the full pipeline ran fresh.

**Rule:** A "data source swap" (new tebliği, new SUT package, new cohort) is never just a file replacement — it is a **full-pipeline smoke test**. Before declaring the swap done, run the *entire* chain fresh (convert → curate → extract → load) and verify EVERY catalog/annex produced non-zero output, not just the ones that passed. Specifically:
1. After `convert_xlsx_to_parquet.py`, check the "Failures: N" line — if N > 0, read the failure reasons before proceeding; they are usually a dependency gap (`xlrd`, `odfpy`), not a data problem.
2. After `build_curated_catalogs.py`, grep for `[!!]` / `FAIL` / `missing` — a silently-empty curated catalog (0 rows) means an upstream annex wasn't found, even if conversion reported success.
3. A committed parquet that can't be rebuilt from declared dependencies is a **lie in git** — always confirm `pip install -r requirements.txt` on a clean venv reproduces every committed artifact.
4. When a lookup filter has a "skip X" rationale comment (like `unknown` partitions here), check whether X can legitimately apply to in-scope data before trusting the skip.

---

## 2026-06-19 — "Değişiklik tebliği" (delta) ≠ "İşlenmiş Güncel SUT" (consolidated) — don't patch rules from delta text

**Pattern:** After downloading the 23.05.2026 SUT tebliği, I initially assumed it was a full SUT and proposed patching BILUN's `drug_indication_prose.json` directly from its delta text. Reality: the download was a 1675-word Resmî Gazette delta (only MADDE 1-10 changes), NOT a consolidated SUT. BILUN's rule encoder workflow extracts rules from the *full consolidated SUT docx* via `extract_sut_prose.py` + human golden-file review — patching a hand-curated rule from delta text bypasses that review, sources from a non-canonical document, and risks stylistic mismatch.

**Rule:** Before touching any rule JSON, classify the source document first:
1. **Consolidated ("İşlenmiş Güncel 2013 SUT")** = full integrated text, ~1MB docx + EK folders. This is the ONLY valid input for the normal encoder pipeline (`extract_sut_prose.py` → clause corpus → hand-curated rule JSON). A new one warrants a full pipeline replace.
2. **Delta ("Değişiklik Yapılmasına Dair Tebliğ")** = Gazette article listing only the changed MADDE'ler (typically a few KB / few hundred words). NEVER use as a direct rule source. Its purpose is to tell you *what changed* so you can (a) flag affected rules for the next consolidated package, and (b) write a changelog entry.
3. Verify which you have by file size and content: a 30KB docx with "MADDE 1-..." headers is a delta; a 1MB docx with full BÖLÜM/§ structure is consolidated. A folder named `YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/` containing EK subfolders is consolidated; a lone `.docx` named `...Delta...` or a raw Gazette UUID filename is a delta.
4. When a delta touches a BILUN rule, the correct action is to document it as "pending next consolidated package" in `docs/gazette/changelog.md`, NOT to hand-patch the rule.

---

## 2026-06-19 — Don't infer document content from the filename (EK-4B "diyaliz" hallucination)

**Pattern:** Recommending "ingest EK-4B to fill the dialysis gap" based purely on the annex filename/title, without reading the file or even the repo's own README. The repo README (`EK-4 LİSTELERİ/README.md:18-24`) states EK-4B is *special diet products / medical nutritionals (PKU, cystic fibrosis, cow's milk allergy)* — ~76 rows, niche pharmacy scope. Dialysis materials live in EK-3 nephrology (`ek3p_nephrology_materials.parquet`), which is already loaded. Same error class: earlier in the same session I also claimed EK-1B contained a "yatak bedeli tariff" from its title, when it is a blank per-patient invoice template (`İşlem tutarı` rows empty). Both were filename-to-content inference failures.

**Rule:** Before claiming a raw-data file contains extractable tariff/rule data — or proposing it to fill a named gap — do BOTH:
1. Read the repo's own inventory (the auto-generated `raw data/.../README.md` files are the canonical source of what each EK annex actually is, including row counts and column lists).
2. Extract the actual file content (libreoffice/pdftotext/pandas) and confirm the rows are populated, not a blank form/template.
A filename like "HAST. SUN. HİZM. VE İLAVE ÜCR" describes a *form's purpose*, not its data contents. SGK annexes split into (a) real tariff tables (.xlsx with data) and (b) blank form templates / patient consent docs (.doc/.docx). Only (a) is worth building a loader for. The audit subagent already correctly labeled EK-1B/EK-1E/EK-4B as "form/template" — trust that classification; don't re-interpret titles as data.

---

## 2026-06-19 — Prefer `ss` over `lsof` for port/PID lookups on this host

**Pattern:** AGENTS.md §5 prescribes `lsof -t -i :PORT` for the zombie-process check. On this host `lsof` fails to report the `next-server` process holding a LISTEN socket on port 3000 (returns empty, exit 1), even though the process is clearly bound. The user ran `kill -9 $(lsof -t -i :3000)`, got an empty PID list, and `kill` failed with "usage" — leaving the stale next-server alive and causing repeated `EADDRINUSE: address already in use :::3000` on `./start.sh`. `ss -ltnp "sport = :PORT"` (reads procfs) reliably surfaced the same PID.

**Rule:** For port-to-PID resolution on this machine, use `ss -ltnp "sport = :PORT" | grep -oE 'pid=[0-9]+'` as the primary tool; treat `lsof` as a fallback only. `start.sh`'s `pids_on_port` is already ordered `ss` → `lsof` → `fuser`. When a port shows EADDRINUSE but `lsof` returns nothing, switch to `ss` before concluding the port is free. Also, Next.js spawns a process tree (`sh -c next dev` → `node next dev` → `next-server`); killing only the listening PID can leave orphans that respawn — sweep with a path-scoped `pgrep`/`kill_stray_bilun_dev` after freeing the port.

---

## 2026-06-19 — Feed commit messages from a file, not a -m string, when they contain backticks

**Pattern:** Using `git commit -m "..."` with a multi-line message that contains backtick-quoted code tokens (e.g. `` `t` ``, `` `loading` ``). Bash inside the tool shell interpreted the backticks as command substitution, ran the token as a command (`/bin/bash: line 1: t: command not found`), and silently dropped the token from the committed message. The commit succeeded but the message was garbled; only caught by re-reading `git log -1 --format='%B'`.

**Rule:** When a commit message contains backticks (or any shell metacharacters like `$`, `` ` ``, `\`), do NOT pass it via `git commit -m`. Instead:
1. Write the message to a temp file with the Write tool.
2. `git commit -F <file>` (or `git commit --amend -F <file>` to repair).
3. Remove the temp file.
4. Always verify with `git log -1 --format='%B'` before declaring the commit done.
For simple messages with no metacharacters, `-m` is fine.

---

## 2026-06-14 / 2026-06-16 — Don't declare a runtime missing just because it isn't on PATH (REPEATED — rule strengthened)

**Pattern:** Running `npm --version` and getting "command not found", then telling the user Node/npm are not installed, when in fact Node v22.16.0 and npm 10.9.2 were present at `/home/safa/.local/node-v22.16.0-linux-x64/bin` but that directory was not in `PATH`. This was repeated on 2026-06-16 despite an existing lesson.

**Rule:** Declaring a tool/runtime unavailable is a positive claim — it requires evidence, not just a PATH miss.
1. First check: run `which <tool>` and `<tool> --version`.
2. If that fails, check known installation locations: `ls ~/.local/*/bin`, `/opt`, `/usr/local/bin`.
3. If found anywhere, prepend its `bin` directory to `PATH` and rerun the check.
4. Only conclude "not available" after steps 1–3 all fail.
5. When a prior lesson already covers this, re-read `tasks/lessons.md` before asserting the same failure again.

## 2026-06-14 — Never claim AI/LLM usage without reading the implementation

**Pattern:** Telling a user that a script “uses LLM calls” based on its docstring/output shape without opening the actual implementation. `scripts/sut/extract_sut_prose.py` and its `scripts/sut/prose/extractor.py` use deterministic regex and DOCX XML parsing, not LLMs.

**Rule:** Before asserting that any component uses AI, LLMs, embeddings, or an external model, grep the source for provider names/APIs (`openai`, `anthropic`, `gpt`, `claude`, `embed`, `transformer`, etc.) and read the implementation. If uncertain, say “I have not verified this” instead of asserting.

## 2026-05-27 — Plan before code (AGENTS.md §7)

**Pattern:** Starting a refactor or rebuild by inspecting files and writing prose without first capturing the plan in `tasks/todo.md`.

**Rule:** For any task that touches 3+ files or sets up a new system, the first artifact is `tasks/todo.md` with the structure from §7. Code writes wait until the plan is in place.

## 2026-05-27 — Premium UI is quiet, not decorated

**Pattern:** Defaulting to glassmorphism, accent-tinted glows, radial gradient backgrounds, marketing hero panels inside the product, and the brand color used for status + action + decoration simultaneously. This reads as "AI startup template", not premium SaaS.

**Rule:** When asked for premium SaaS feel:
1. One color reserved for action/focus only — never for backgrounds, never for status
2. Status semantics are separate tokens, never the brand color
3. No backdrop-blur, no glow shadows, no accent-tinted shadows, no radial gradient backgrounds
4. Motion budget: one easing, one duration (~120ms), hover/focus only — no entry animations in workspaces
5. Content over self-description: the product never explains itself inside itself
6. No `premium` in class names. Real premium products don't label themselves premium.

## 2026-05-27 — Verify font loading, don't just declare CSS variable

**Pattern:** Declaring `--font-sans: "Plus Jakarta Sans"` in CSS without loading the font via `next/font`. Browsers fall back to system fonts and the designed font never renders, but it looks like it's wired up.

**Rule:** Web font loading requires both: (1) `next/font/google` (or equivalent) import in `layout.tsx` that injects the `@font-face` and exposes a CSS variable, (2) the CSS variable referenced in `font-family` declarations. Verify by inspecting computed font in DevTools, not by reading the CSS.

## 2026-05-27 — Inventory before deleting CSS

**Pattern:** Estimating "this class is probably unused" and deleting it, then breaking a page in a corner of the app that was never opened during testing.

**Rule:** Before deleting or rewriting CSS class rules at scale, build an evidence-based inventory: extract every `.class-name` from the stylesheets, grep every `.tsx/.ts/.css` (excluding the stylesheets themselves) for each name, and partition into used/unused. Delete only the unused set outright; for the used set, rewrite the rule without changing the selector. Never delete a selector that still has JSX references — move its rule into a clearly-labeled transitional file instead.

## 2026-05-27 — `useSyncExternalStore` for browser-state subscriptions

**Pattern:** Writing a React hook that subscribes to `localStorage` (or any browser-only store) with `useState` + a `useEffect` that calls `setState(read())` on mount. ESLint's `react-hooks/set-state-in-effect` correctly flags this — it forces a double render (SSR snapshot, then mount snapshot) and races with concurrent rendering.

**Rule:** For any value that comes from a browser-only store (localStorage, sessionStorage, matchMedia, IndexedDB) and needs to drive React UI, use `useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)`. The server snapshot is `[]` / a stable empty value; the client snapshot reads the store on demand. Cache the snapshot by the underlying raw value to keep `getSnapshot` referentially stable (otherwise React tears).

## 2026-06-06 — Flatten filled PDFs when viewer focus changes appearance

**Pattern:** Filling AcroForm text fields and only adjusting `/DA` font metadata can still fail because PDF viewers redraw editable field contents on focus using their own form-rendering behavior.

**Rule:** When the deliverable is a final application PDF and the user reports font changes after clicking fields, generate a flattened copy: draw text directly onto the page with an embedded font that supports the required language, then remove form widgets. Do not keep editable fields unless editability is explicitly required.

## 2026-05-27 — Style file collapse needs a transitional layer

**Pattern:** Trying to delete a large legacy stylesheet (`sut-premium.css`) and reduce `globals.css` to <200 lines in a single phase while pages still reference the legacy classes — would break every page mid-phase.

**Rule:** When collapsing stylesheets across multiple phases, the immediate phase deletes dead rules + strips chrome from live rules, but moves the live rules into a clearly-labeled `legacy.css` (transitional) that the global stylesheet imports. Subsequent phases burn down `legacy.css` by reskinning the pages that depend on its selectors. The legacy file is only deleted once its imports are gone from all JSX. This prevents a "big bang" CSS rewrite from breaking unrelated pages.

## 2026-05-27 — Wrap legacy reskins, don't tear them open

**Pattern:** Faced with a 6-section file (`BillingSectionShell` used by Lab/Drug/Copay/Strategy/Materials/SutOptimization), the temptation is to rewrite each call site to use `<Section>` directly. That's six dangerous diffs across an 880-line file, easy to miss a wrapper, easy to break tests that assert exact strings.

**Rule:** When a private helper is reused by multiple call sites in the same file, **rewrite the helper's internals** rather than its call sites. Keep the helper's signature stable, and swap its body to wrap the new primitive. The diff stays small (~10 lines), every call site picks up the new chrome automatically, and the existing test fixture continues to validate the integration. Tear the wrapper open in a later phase only after confirming the new look is right.

## 2026-05-27 — `next build` poisons the dev-mode cache; clear `.next` before probing

**Pattern:** Running `npx next build` and then `npx next dev` against the same project produced HTTP 500 on every route with Turbopack panicking on "ArrayLengthMismatch / corrupted database" cache deserialization errors. Initial instinct was to debug the app — actual root cause was build/dev artifact conflict in `.next/`.

**Rule:** When dev-mode 500s show Turbopack/Webpack internal errors mentioning "task data", "corrupted database", or "incompatible version" — kill all `next dev` processes, `rm -rf .next/`, then restart. Don't read application code looking for the bug. This is the disk-cache equivalent of AGENTS.md §5's zombie-process check: read the actual error message, kill the artifact, restart cleanly.

## 2026-05-27 — Two-gold rule must be checked at the page level, not the component level

**Pattern:** A component-by-component reskin can each apply "one italic-gold accent" honestly, but the page that composes those components ends up with five gold uses (H1 word + KPI value + section total + savings cells + status chips), violating the deck contract.

**Rule:** The "max 2 italic-gold serif uses per screen" rule is a **page-level invariant**, not a component-level one. When a page composes multiple primitive instances, audit the rendered page for italic-gold uses and pick the two with the highest information value (typically: one H1 word + the single primary KPI money amount). All other "gold candidates" (table savings cells, section totals, secondary KPIs, success chips) must drop to navy tabular. Gold chip backgrounds (`<Chip variant="gold">`) and gold *tinted* backgrounds are not counted under this rule because they aren't Fraunces italic display type.

## 2026-05-30 — Chat auto-brief effect must not depend on streaming store writes

**Pattern:** Removing briefing dedup while persisting every SSE token to Zustand recreated `onChatStateChange` each render, retriggered the auto-brief `useEffect`, aborted in-flight requests, and spammed `/api/chat` until 429 — UI stuck on the empty placeholder.

**Rule:** Auto-brief triggers only on `[patientId, activeTab]` via a ref to `fireAutoAnalysis`. Stream tokens into local state; persist messages once on completion. Memoize `onChatStateChange` at the route level. Guard against concurrent in-flight auto requests.

## 2026-06-30 — Do NOT act on a subagent's "drift/regression" diagnosis without verifying parquet/code state yourself

**Pattern:** A planning-stage Explore subagent reported "working-tree parquet drift from an experimental extractor — ~800 rows moved bent↔prose, possible edition mismatch" and a whole Phase 0 plan was written around resolving it. When I actually executed Phase 0 I found: (1) the on-disk parquet had been **regenerated by the subagent itself during its investigation** (mtime = the turn it ran), contaminating the very state it reported on; (2) HEAD and working-tree were built from the **same** docx (same `source_docx`/`source_effective_date`, not an edition upgrade); (3) `extractor.py` was byte-identical to HEAD. The real situation was simply: the on-disk parquet was stale relative to the canonical committed extractor — a one-step regenerate, not a multi-step "resolve drift" investigation.

**Rule:** Before acting on any subagent diagnosis that claims "drift", "regression", "edition mismatch", or "data is corrupted", verify ground truth yourself with direct commands: `git status --short <path>`, compare `source_docx`/`source_effective_date` columns between HEAD (`git show HEAD:path`) and working-tree, check the file mtime against when subagents ran, and re-run the canonical generator to a **temp** path (never overwrite the real artifact during investigation). Treat subagent reports of mutable filesystem/data state as unverified hypotheses, not facts — subagents can and do mutate the state they are observing. Never let an investigation step write to the real artifact.

## 2026-06-30 — Prove test-failure causation with a stash before claiming "my change did it" OR "pre-existing"

**Pattern:** After regenerating `sut_clauses.parquet`, 2 tests in `test_rules_catalog.py` failed on coverage counts. The honest question was whether my change caused them. The decisive test: `git stash push -- <my changed files>` then re-run the failing tests against pristine HEAD code. They failed identically → pre-existing, caused by a stale *derived* coverage parquet I never touched (read path: `rules_catalog.py` loads `sut_clause_coverage.parquet`, NOT `sut_clauses.parquet`). Reporting them as "my regression" would have been a false confession; reporting without proof would have been a guess.

**Rule:** Whenever tests fail after a change, determine causation empirically, not by intuition. Stash the changed files and re-run the failing tests against the baseline. If they fail identically → pre-existing, report as such and move on. If they pass on baseline → your change caused them, fix before declaring done. Never report a test result as "pre-existing" or "caused by my change" without having run the baseline comparison. The load-bearing distinction is *which artifact the test reads* — trace the read path before assuming your changed file is the culprit.

**Correction (same day, Phase 3):** I first claimed the 2 failing `test_rules_catalog.py` tests were caused by a "stale coverage parquet." In Phase 3 I regenerated that coverage parquet and **the tests still failed identically** — so that hypothesis was wrong too. The real read path: `kdv_pricing_clauses` comes from `src/bilun/domain/materials/coverage_scope.py::kdv_pricing_clause_count()` which reads the **prose rule JSONs** (mid-flight in the encode-waves workstream), not any parquet. The sharpened rule: "pre-existing" is not proven by a stash alone — a stash only proves *your code* didn't cause it. To name the *actual* culprit you must grep the assertion symbol back to its source function and read *that* function's inputs. Don't settle for "not mine" when you can find "whose."

## 2026-06-30 — Never squash unrelated concerns + machine-generated blobs into one giant commit

**Pattern:** Under direction to "commit and push every single uncommitted change", I created one `chore(sut): encode-waves...` commit of **93 files / +39,463 / −30,406 lines**. ~36,000 of those lines were 3 machine-generated blobs (`drug_indication_prose.json`, a trace manifest, `baseline_metrics.json`) that are impossible to code-review. The commit mixed 7 distinct concerns: domain code, 36 batch generators, 24 test files, 28 generated data artifacts, 2 new scripts, an auto-generated report, and a TypeScript build cache (`tsconfig.tsbuildinfo`) that should never have been tracked at all. A surgical revert of any one concern was impossible — if one piece was wrong, the whole 39k-line commit had to come back. The user correctly questioned this on software-engineering principles.

**Rule:** A commit must be atomic — one concern, independently reviewable and independently revertable. Before staging, categorize the working-tree changes by concern (source vs generated-data vs tests vs tooling) and make one commit per category. Machine-generated artifacts (manifests, corpus exports, baseline snapshots, build caches) go in their OWN commit, clearly labeled `chore(data): regenerate ...`, separate from the human-authored code that produces them — and question whether each belongs in version control at all. Build-cache files (`*.tsbuildinfo`, `*.pyc`, dist/) must be `.gitignore`d and `git rm --cached`, NEVER committed. A 30k-line JSON diff in a commit is a smell, not a feature. When a user says "commit everything", push back on scope the same way as on a vague implementation request — the AGENTS.md "no assumptions / clarify" and "demand elegance" rules apply to commits too. When caught, fix via `git reset --soft HEAD~1` + re-split + `git push --force-with-lease` (safe force-push that refuses if origin moved).

## Lesson: Audit findings require execution/caller proof, not just code reading (2026-07-14)

**Pattern:** During the whole-codebase audit, 3 of 30 findings were false positives because subagents read function bodies but didn't execute or trace them:
- Claimed "IndexError on clean cohorts" → code actually used `len(recoverables)` not `len(reports)`. A 5-second runtime check would have caught it.
- Claimed "duplicate dict keys" → they were intentional aliases. An AST key-count would have caught it.
- Claimed "detector never called" → both callers pass the kwarg explicitly. A `grep` for callers would have caught it.

**Rule:** Any audit finding that claims "this CRASHES" or "this is NEVER CALLED" must include either:
1. A runtime reproduction (the actual input that triggers the crash), OR
2. A grep/AST proof that no caller passes the required argument.

Reading the function body alone is insufficient — variable names can be misread, and defaults can be overridden at every call site. **Execute, don't assume.**

---

## 2026-07-16 — Deferral reasons are assumptions that must be verified, not stated

**Pattern:** In the finans coder Phase 2 plan, I deferred the DRUG crosswalk with reason "needs external TTCK brand→barcode list" and the MATERIAL crosswalk with reason "genuine 1:many ambiguity, low payoff." Both reasons sounded plausible enough to commit to a plan and ship as "Out of scope." When the user pushed back ("investigate this properly"), ~15 minutes of catalog inspection disproved both: EK-4A has a full `drug_name` column (not barcode-only) → 84% brand-match feasible; EK-3 has 3,659 codes across 23 families (not 280) → consumables DO map to categories. Both crosswalks were built in Phase 3 and hit 74% (drug) / 93% (material) coverage. The deferral cost nothing in rework, but it left ~525 mappings on the table for an entire phase because I trusted my own plausible-sounding reasons without checking.

**Rule:** When deferring work with a stated reason ("needs X", "has Y problem", "not feasible because Z"), the reason is itself an unverified claim about the codebase and MUST be checked before it ships in a plan — same standard as §11 anti-hallucination for code claims. Concretely:
1. A deferral reason citing a catalog's structure ("barcode-only", "1:many") requires a `pl.read_parquet(...)` inspection of that catalog, not a memory of what some function returned.
2. "Needs external data" is the most dangerous deferral reason — it sounds decisive but is usually wrong (the data is often already in the repo under a different path or column name). Grep the parquet columns before claiming absence.
3. If a deferral would strand >10% of the dataset, the reason deserves the same investigation budget as the implementation itself. Cheap to check, expensive to leave wrong.
4. Phrasing hedge: prefer "deferred pending investigation of whether X" over "deferred because X" when X is unverified. The former invites the check; the latter forecloses it.

---

## Polars `with_columns` in-flight column reference (2026-07-16, finans pricing audit)

**Incident:** A classifier computed `delta_pct` and derived a `flag` from `pl.col("delta_pct")` inside the *same* `with_columns` call. The flag expression read the stale (null) pre-existing column, so every row fell through to `otherwise → UNDERCHARGE`. 2019 rows mislabeled; the OVERCHARGE sign was inverted (positive deltas flagged UNDERCHARGE).

**Rule:** Polars evaluates all expressions in a single `with_columns` against the *input* schema — a column created in that call is NOT visible to sibling expressions. When a derived column feeds a classification:
1. Materialize the numeric columns (`delta_pct`, ratio, etc.) in one `with_columns` step.
2. Derive the flag in a *second* `with_columns` that reads the now-materialized column.
This is the Polars analog of not reading a variable before it's assigned.

## Verify column semantics from the data, not the name (2026-07-16)

**Incident:** Built the EK-4A tier audit assuming `INDIRIM_ORANI` ("discount ratio") was a discount fraction (0–1). It was not — values included 0.0, 1.3333, 41.87, 44.5. Produced 1989 meaningless TIER_MISMATCH flags.

**Rule:** A column's *name* is a hypothesis about its semantics, not a proof. Before building comparison logic on a column, inspect its actual value distribution (`describe()`, `unique().sort()`). If the values violate the assumed domain (e.g. a "ratio" with values >1 or negative), the assumption is wrong — find the real semantics by deriving from related columns (here: the real discount was `1 - KDVSIZ_INDIRIMLI/KDVSIZ_FIYAT`).

## `get_ek4a_drugs()` return type (2026-07-16)

**Incident:** Assumed `get_ek4a_drugs()` returned a Polars DataFrame (by analogy with other loaders). It returns `list[dict]`. Accessing `.columns` raised `AttributeError`.

**Rule:** Never assume a loader's return type from naming convention. For domain accessor functions, confirm the return type by calling it once in the REPL before wiring it into a script. When converting a `list[dict]` to a frame, use `pl.from_dicts()` (vectorized, not a row loop).

---

## Don't diagnose "bad data" from a truncated display name (2026-07-16, EK-3 audit)

**Incident:** I reported "⚠️ EK-3 catalog NOT trustworthy — KN1069 = 103K TRY for a catheter, a catheter is not 100K" and recommended a catalog-cleanup follow-up. Investigation proved this wrong: KN1069's full name is "TÜM SİSTEM KİT (İNTRATEKAL KATETER VE SABİT SALIMLI İNFÜZYON POMPASI)" — a complete implantable pump *system kit*, for which 103K TRY is realistic. I had read the truncated display name "İNTRATEKAL KAT…" and assumed "catheter." The real bug was in the crosswalk (substring collisions), not the catalog.

**Rule:** Before declaring a data value "implausible" and attributing a root cause, read the FULL untruncated field (name, description, category). A truncated display string is a hypothesis, not evidence. Concretely:
1. When a price seems absurd, print the FULL record (all columns: name, description, category, source) before judging — the qualifying noun may be past the truncation point.
2. Distinguish "this value is wrong" from "this value is surprising." Verify against the upstream source (raw parquet / original XLSX) before claiming corruption.
3. A "catalog bug" diagnosis that would defer an entire sub-system deserves the same investigation budget as the implementation — cheap to check (one `material_name` print), expensive to leave wrong.

## IDF-overlap denominator must not exclude rare query tokens (2026-07-16, material resolver)

**Incident:** `build_material_candidates` computed `query_idf` only over tokens with `df > 1`, excluding rare-in-catalog tokens. For "Serum Seti" this meant the denominator was just `idf(seti)`, so any entry containing "seti" scored `shared_idf/query_idf = 1.0` — a single common device word produced a perfect match. Result: 26+ wrong mappings (IV giving set → meniscus repair set, fixation band → anesthesia set) via generic-word collisions.

**Rule:** In IDF-weighted overlap scoring, the denominator (query self-similarity) must include the tokens you're actually matching against. Excluding rare tokens from the denominator lets one common word divide by itself. The correct exclusion is catalog-ABSENT tokens only (`df >= 1`), not rare-in-catalog tokens (`df > 1`) — brand names / SKU codes that appear in no catalog entry legitimately shouldn't inflate the denominator, but a genuinely-rare-but-present word should.

## A regression-baseline check before claiming "my change broke it" (2026-07-16)

**Incident:** The full test suite failed on `test_sut.py::test_cardiac_stent_separately_payable` (401 auth). I needed to know if my change caused it. Stashing everything was awkward (the data file is gitignored). Solution: `git checkout` ONLY the changed src file, re-run the one test, restore.

**Rule:** To isolate whether a failure is a regression from your change, revert ONLY the specific file under test (`cp file /tmp/fix.py && git checkout file && pytest ...; cp /tmp/fix.py file`), not the whole working tree. Faster, and works even when some changed files are untracked/gitignored. If the test fails with your change reverted, it's pre-existing — report it as such, don't fix it as part of an unrelated task.

---

## OpenHands + Z coding-plan: litellm requires a provider prefix the upstream rejects (2026-07-19)

**Pattern:** Configured OpenHands to use the Z coding-plan endpoint (`https://api.z.ai/api/coding/paas/v4`) with model `glm-5.2`. The first agent conversation failed with `LLMBadRequestError: LLM Provider NOT provided. Pass in the LLM provider you are trying to call. You passed model=glm-5.2`. OpenHands uses **litellm** as its LLM router, which REQUIRES a provider prefix on the model string (e.g. `openai/`, `anthropic/`, `huggingface/`). A bare model name is ambiguous and rejected. BUT — the Z-API itself REJECTS the prefixed name: sending `openai/glm-5.2` to `https://api.z.ai/api/coding/paas/v4/chat/completions` returns `code 1211: Unknown Model`. The apparent contradiction resolves because litellm STRIPS the prefix before forwarding to the upstream when `base_url` is set — so `openai/glm-5.2` + `base_url=...z.ai...` means "route as OpenAI protocol, send bare `glm-5.2` to the upstream." This is invisible unless you test both layers separately.

**Rule:** When wiring an OpenAI-compatible but non-OpenAI endpoint (Z-API, Together, Anyscale, local vLLM) into any tool built on litellm (OpenHands, Continue, Aider):
1. The model string passed to the tool MUST have a provider prefix (`openai/<model>`), even though the upstream endpoint rejects it — litellm strips it.
2. To diagnose a "model not found" / "provider not provided" error, test BOTH layers: (a) raw curl to the upstream with the bare model name (should work), (b) the same curl with the prefixed name (should fail with "Unknown Model"). If (a) works and (b) fails, the tool's litellm layer is the issue, not the endpoint.
3. `base_url` MUST be set explicitly — without it, litellm sends the prefixed call to OpenAI's real endpoint and you get an auth error.
4. The Z coding-plan base URL is `https://api.z.ai/api/coding/paas/v4` (the `/coding/` segment routes to the subscription tier; the standard PAYG endpoint is `/api/paas/v4` without it).

---

## OpenHands local install gotchas (2026-07-19)

**Pattern:** Five concrete gotchas hit during `openhands serve` install on this host, none documented in the official quickstart:

1. **`openhands serve` hardcodes `-p 3000:3000`** (`openhands_cli/gui_launcher.py:190`) — there is NO `OPENHANDS_PORT` env override. To bind a different port, bypass the wrapper and run the equivalent `docker run -p <port>:3000 ...` directly (mirror `gui_launcher.py:127-197`).

2. **Docker group changes don't propagate to existing shells.** After `sudo usermod -aG docker safa`, my bash tool shells (spawned before the change) still got "permission denied on docker.sock" because group membership is evaluated at session start. Workaround that does NOT require re-login or reboot: prefix docker commands with `sg docker -c "..."` (runs with the docker group active). Verified working.

3. **Image tag is `latest`, not the SDK version.** `get_openhands_version()` (`gui_launcher.py:80-88`) returns `$OPENHANDS_VERSION` or `latest` — NOT the installed package version (`1.16.0`) or the SDK banner version (`v1.21.0`). Pulling `docker.openhands.dev/openhands/openhands:1.21.0` 404s. Use `:latest`.

4. **LLM config is NOT in the DB** — `openhands.db` only has `alembic_version`. Settings persist as `~/.openhands/settings.json` via `FileSettingsStore`. If the user can't find the "Custom/Other" provider in the UI (common — it's buried under Advanced), write `settings.json` directly via `docker exec openhands-app python3 -c '...'`. The file is owned by root (Docker created it), so write from inside the container. The file lives outside the repo (no git risk) but `api_key` is plaintext in it — don't commit `~/.openhands/`.

5. **The agent-server REST API is the clean test path, not the app-server.** The app-server (`:3001`) wraps everything in async start-tasks that are brittle to poll. The agent-server (exposed on a random port per sandbox, e.g. `:52527`) has a SYNCHRONOUS REST API: `POST /api/conversations` (start), `POST /api/conversations/{id}/events` (send msg), `GET /api/conversations/{id}/events/search` (trace), `GET /api/conversations/{id}/agent_final_response` (result). Auth header is `X-Session-API-Key: <session_api_key>` (NOT `X-API-Key`), where session_api_key comes from `GET /api/v1/sandboxes/search` on the app-server. Get the agent-server port + key from that same response.

**Rule:** For any future OpenHands local setup, check all five before declaring done. The `sg docker` workaround and the read-only-subdir mount pattern (next lesson) are reusable on any host.

---

## OpenHands sandbox: mount as read-only subdir, NOT as `/workspace` root (2026-07-19)

**Pattern:** Mounted the Bilun repo as `/workspace` (`SANDBOX_VOLUMES=/home/safa/Documents/Bilun:/workspace:rw`) to give the agent repo access. Sandbox failed to boot: `PermissionError: [Errno 13] Permission denied: '/workspace/conversations'`. Root cause: the agent-server sandbox hardcodes its run user as uid/gid 10001 (`remote_sandbox_service.py:470-471` `'run_as_user': 10001`) — `SANDBOX_USER_ID` env is IGNORED for the sandbox (it only affects the app container's launcher). Bilun is owned by safa/1000 on the host. uid 10001 cannot write to a uid-1000-owned bind-mount. Overlaying `/workspace` (which the image pre-creates as writable-by-openhands) with the Bilun mount destroyed that writability, and the agent-server needs to create `/workspace/conversations/` there.

**Rule:** When mounting a host repo into an OpenHands sandbox:
1. **Mount as a SUBDIRECTORY, not as `/workspace` root**: `SANDBOX_VOLUMES=/host/repo:/workspace/<name>:ro`. This keeps `/workspace` itself owned by the image's openhands user (writable, so `conversations/` creates succeed) and exposes the repo at `/workspace/<name>`.
2. **Use `:ro` for read-only** — honors the "agent reads repo but can't mutate it" safety contract until write access is explicitly authorized. The agent-server correctly respects this: `touch /workspace/<name>/foo` returns "Read-only file system".
3. **Do NOT try to fix this by `chmod 777` on the host repo or by `setfacl` granting uid 10001** — both give the agent write access to the real repo, crossing the read-only boundary. The subdir-mount pattern is the correct fix.
4. The uid-mismatch is by design in this OpenHands version — don't waste time looking for a `SANDBOX_USER_ID`-style override on the sandbox side; there isn't one.
5. To verify the mount worked before running a full agent task: `docker exec <sandbox> sh -c 'ls /workspace/<name> && head -3 /workspace/<name>/AGENTS.md && touch /workspace/conversations/test && rm /workspace/conversations/test && touch /workspace/<name>/test'` — last command should FAIL with read-only.

---

## OpenHands agent iteration caps + the per-role tuning needed (2026-07-20)

**Pattern:** Ran all 3 employee agents end-to-end on the custom sandbox image. Reimbursement (15 iter, 80s) and Full-stack (15 iter, 195s) finished cleanly. Data Engineer hit `MaxIterationsReached` at 15 iterations ~260s — it ran both checkers successfully (pipeline_smoke PASS, freshness correct) but spent too many iterations reading `pipeline_smoke.py` source to understand the temp-dir behavior before writing its report, and ran out of budget. The checkers themselves weren't the cost — the agent's investigative thoroughness was.

**Rule:** Per-role iteration caps must match the role's investigation depth, not be uniform:
1. **Reimbursement** (15 iter): sufficient — 3 checkers, well-documented, agent reads AGENTS.md + runs + writes.
2. **Full-stack** (15 iter): sufficient but tight — tsc + vitest add runtime, agent barely finished. Bump to 20 if it starts hitting the cap.
3. **Data** (15 iter): INSUFFICIENT — pipeline_smoke is slow (~18s) and the agent wanted to understand its internals. Needs 20-25 iterations.
4. The cap is set per-conversation in the `POST /api/conversations` body (`max_iterations`), NOT globally. Tune per role by embedding the right default in each role's `system-prompt.md` invocation instruction.
5. When an agent errors with `MaxIterationsReached`, the checkers may have ALREADY run successfully — check `reports/agent/<role>/` for outputs before assuming total failure. The Data agent's pipeline_smoke + freshness outputs were on disk; only the report write was skipped.

---

## Checker scripts crash on the app's read-only log file (2026-07-20)

**Pattern:** `scripts/agent/endpoint_coverage.py` imports `src.bilun.api.app`, which triggers the app's startup logging. The logging config (`src/bilun/shared/state.py:27`) opens `logs/bilun.log` with a `FileHandler` for append. Inside the sandbox, the repo is mounted `:ro` AND the `logs/` dir is owned by host user `pn` — so the `openhands` (uid 10001) user gets `PermissionError: [Errno 13] Permission denied: '/workspace/bilun/logs/bilun.log'`. The checker crashes not because of its own logic but because importing the app triggers a write to a read-only path. The Full-stack agent correctly diagnosed this with file:line citation and fell back to the frozen baseline.

**Rule:** Any checker that imports `src.bilun.api.app` (or anything transitively touching the logging config) must set `BILUN_LOG_TO_FILE=0` (or the equivalent env override) BEFORE the import, OR the logging config must guard against read-only CWD. Concretely:
1. In `endpoint_coverage.py`, set `os.environ["BILUN_DISABLE_FILE_LOG"] = "1"` (verify the actual env var name in `state.py`) before `from src.bilun.api import app`.
2. The durable fix is in `src/bilun/shared/state.py:27`: wrap the FileHandler creation in `try/except (PermissionError, OSError)` so a read-only log dir degrades to stdout-only instead of crashing the whole import chain. This also helps VPS deployments where the log dir might not exist yet.
3. The pattern generalizes: importing a FastAPI app for introspection (route-walking) should NOT trigger side-effecting startup like file logging. The import path and the run path should be separable.

---

## Agent-written files have uid-10001-only perms (2026-07-20)

**Pattern:** Reports written by the agent (e.g. `findings-2026-07-20.md`) land with `-rw-------` owned by `openhands:openhands` (uid 10001). The host user `safa` (uid 1000) cannot `cat` them — "Permission denied" — even though `reports/agent/` has a default ACL granting uid 10001 rwx. The ACL governs the DIRECTORY (create files inside) but not the FILE mode the agent's process uses (Python's default `0o600` via `open(..., 'w')`). Reading required `docker exec <sandbox> cat <path>` instead of a host-side `cat`.

**Rule:** When the host user needs to read agent-written reports without `docker exec`:
1. The agent's report-writing step (or `run_checks.sh`) should `chmod 644` the file after writing, OR set `os.umask(0o022)` at the start of the checker.
2. Alternatively, the default ACL on `reports/agent/` should be `d:m::rwx` (mask) + the files inherit via `setfacl -m d:g:safa:rwx` if safa is in a group — but the simplest fix is `chmod 644` post-write.
3. This is cosmetic — the agent's findings are accessible via `docker exec`. But for the daily-driver workflow where Safa reads reports from his editor, file mode matters.

---

## mem0's LLM extractor chokes on large structured inputs (2026-07-20)

**Pattern:** `scripts/agent/memory/save.py` sent an 8KB structured markdown report to
`mem0.add()`. mem0's glm-4.6 fact-extraction LLM returned 0 memories — silently. The
underlying issue: mem0's extraction prompt expects conversational/natural-language input,
not tables + tier classifications + per-rule breakdowns. Large structured markdown has
low signal-to-noise for the extractor; it gives up and returns empty.

**Rule:** When feeding reports to mem0 for fact extraction:
1. **Cap input at ~2500 chars.** Larger inputs silently return 0 memories.
2. **Prefer the Summary section**, not the full report. If the report has a `## Summary`
   section, extract from there; the full report is the durable artifact on disk, memory
   only needs the headline distillation.
3. **Test extraction on a simple single-fact input first** ("Found 116 TIER-1 refs across
   9 rule sets") — if that works but the full report doesn't, it's an input-size issue,
   not a config bug.
4. mem0's `add()` does NOT error on empty extraction — it returns `{'results': []}`. Always
   check the result count and log it; a silent 0 is the failure mode.

---

## OpenHands Z_API_KEY env forwarding gap (2026-07-20)

**Pattern:** Set `Z_API_KEY` on the `openhands-app` container (`-e Z_API_KEY=...`), expecting
the sandbox (spawned separately) to inherit it. The sandbox did NOT — `os.environ['Z_API_KEY']`
was unset inside the agent's terminal sessions, so `python -m scripts.agent.memory.load`
failed with "Z_API_KEY env var not set." The app container has the key; the sandbox doesn't
auto-inherit arbitrary env vars.

**Rule:** To pass secrets to the OpenHands sandbox:
1. The app auto-forwards env vars with prefixes `LLM_*` and `LMNR_*` only (verified in
   `sandbox_spec_service.py:AUTO_FORWARD_PREFIXES`). `Z_API_KEY` doesn't match.
2. Workaround: set `OH_AGENT_SERVER_ENV` (JSON) on the app container to forward arbitrary
   vars: `-e OH_AGENT_SERVER_ENV='{"Z_API_KEY":"..."}'`. This injects them into every
   spawned sandbox.
3. OR rename to `LLM_Z_API_KEY` to match the auto-forward prefix (hackier).
4. For production: use a secret file mounted into both containers, not env vars.

---

## Lesson (2026-07-21): Don't assume a single VPS — confirm which box a deploy targets

**Mistake:** I assumed `165.245.243.183` (the web-app VPS documented in
`plans/deployment/vps-deploy-plan.md`) was the only VPS, and deployed the
OpenHands smoke-test plan there. It's the wrong box — Bilun has TWO VPSes:
- `165.245.243.183` — the production web app (DigitalOcean, 4 GB RAM)
- `169.58.50.165` — the Cloud VPS 8 (2026) reserved for agentic orchestration

When reviewer feedback mentioned `169.58.50.165`, I grepped the repo, found zero
matches, and dismissed it as a phantom. **The repo only documents the web-app
VPS; the agent VPS isn't in any tracked file.** Absence from the repo is not
absence from reality.

**Pattern:** Infrastructure not documented in the repo may still exist. When a
deploy target is ambiguous and someone (user or reviewer) names a specific host,
treat that as a signal to ask "is this a different box?" — not to grep-and-dismiss.

**Rule:** Before any deploy, confirm the target host with the user explicitly.
If the user or a reviewer names an IP/hostname that differs from what's in the
repo, STOP and ask which box — do not assume the repo is authoritative for
undocumented infrastructure.

**Concrete fix applied:** Aborted the deploy on the wrong box (no writes happened
— Step 0 was read-only, Step 0.5+ never ran). Re-targeting to `169.58.50.165`.

---

## Agent-surfaced bugs: pricing import + pipeline_smoke :ro + missing tabulate dep (2026-07-21)

**Pattern:** The 3 employee agents ran 2026-07-21 and surfaced 3 real Bilun bugs that
sat unfixed in the working tree. All 3 were blocking the finans pricing audit chain —
the Reimbursement Engineer correctly flagged them with file:line citations.

1. **`src/bilun/domain/pricing/__init__.py:7`** used `from src.bilun.domain.pricing.keywords`
   (absolute-from-src) — fails with `ModuleNotFoundError: No module named 'src'` whenever
   the package isn't on sys.path as `src.*` (i.e. always, in the deployed/installed layout).
   House style is relative imports (see `drugs/__init__.py:7` `from .ek4d_exempt import ...`).
   Fixed to `from .keywords import _ICD10_CHAPTER_KEYWORDS`. This fix also unblocked 3
   `test_material_kdv.py` tests that were silently failing on the broken import.

2. **`scripts/agent/pipeline_smoke.py`** wrote its temp dir at `data/gazette/.pipeline_smoke_tmp/`
   (inside the repo) because `convert_xlsx_to_parquet.py:289` calls
   `.relative_to(PROJECT_ROOT)` on output paths. Under the OpenHands sandbox's `:ro` repo
   mount this crashed with `OSError: Read-only file system` — and the Data agent correctly
   reported it as a pipeline-smoke FAIL (a false negative: pipeline is healthy, the
   CHECKER couldn't run). Fixed: detect the read-only case and exit cleanly with code 2
   ("couldn't run in this environment"), distinct from real pipeline failure. Updated
   `agents/data/run_checks.sh` to handle exit 2 as an environment limit, not a bug.

3. **`tabulate` was not in `requirements.txt`** — `finans_pricing_audit.py` calls
   `df.to_markdown()` which needs it. Worked on prior machines because tabulate got
   pulled in transitively; broke on fresh installs. Added `tabulate>=0.9` to requirements.

**Rule:** When an agent reports "X FAILED", distinguish "X is broken" from "X couldn't run
in this environment". The pipeline_smoke FAIL was the latter — the agent had no way to
know that, but the human reading the report should. Checker scripts should use distinct
exit codes for "couldn't run" (we now use 2) vs "ran and found problems" (1) vs "clean" (0).

## 2026-07-22 — i18n pattern catalog incomplete when crawl covers one patient

**Pattern:** Built EN→TR `translateApiText` patterns from a Playwright crawl of SENTETIK-HASTA-0001. Patient 0003 later showed a different strategy note (`optional §2.2.2(2) override — … higher legal option`) that never appeared in the crawl inventory, so it passed through untranslated.

**Rule:** When translating backend-generated prose via frontend regex maps:
1. Enumerate **all** string templates in the generator module (e.g. `claim_strategy.py` note builder), not only strings seen in one demo patient crawl.
2. Add golden tests for every template branch (mandatory package/itemized, optional override both directions).
3. Treat crawl as a regression gate, not the sole inventory source.

## 2026-07-25 — Don't defer approved plan phases for convenience

**Pattern:** After implementing most of brittle-test remediation, Phase 5 (FE TRY asserts + catalog stubs) was deferred as "nice to have" even though it was in the approved plan and the user had chosen full remediation.

**Rule:** If a phase is in the approved `tasks/todo.md` / plan, finish it or ask the user before cutting scope. Convenience is not a reason to leave approved work unfinished.

## 2026-07-25 — FE CI typechecks test files

**Pattern:** Frontend CI failed on `tsc --noEmit` in `*.test.tsx` after introducing `fmtTRY2Fixture(number)` helpers — fixture fields typed `number | null` / optional nested fields were passed without narrowing, so Vitest could pass locally while CI failed.

**Rule:** When adding typed helpers used in FE tests, ensure call sites satisfy `tsc` (local non-null fixtures or narrowing). Run `npx tsc --noEmit` from `frontend/` before pushing FE test changes — Vitest alone is not enough.

---

## 2026-08-09 — KAOS/FMXInno repack installers: "range check error" under Wine is the FMX UI; bypass it with Inno silent switches

**Pattern:** Installing a KAOS repack (A Way Out) under Proton/Wine: `Setup.exe` (32-bit Inno Setup self-extractor, `/SL5=` switch) launches an inner Delphi installer skinned with **FMXInno.dll** (FireMonkey UI — temp dir contains FMXInno.dll, KAOS.STYLE, FONT.OTF, KAOS.MP3). Under Wine the FMX UI throws a Delphi **"Range check error"** dialog immediately, regardless of: path spaces, bypassing Proton's steam.exe shim, CWD/data-file placement, or virtual desktop. Wasted ~6 attempts on those. The fix: the FMX UI is only a *skin* over Inno Setup — running `Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NOCANCEL /DIR="C:\Games\X"` skips form creation entirely, the range check never fires, and extraction runs to completion (~2GB/30s). A trailing "runtime error 216" (Delphi GPF) at installer exit is the FMX UI dying on teardown — harmless once files are extracted; verify by the installed tree + launching the game, not by the exit dialog.

**Rule:** For any repack installer that dies under Wine/Proton with a Delphi runtime error ("Range check error", "runtime error 216") before extraction:
1. Identify the UI layer first: extract the inner installer from `C:\users\<user>\AppData\Local\Temp\is-*.tmp\` and `strings` it — `FMXInno.dll`/`*.style`/FireMonkey markers mean the *skin* is the failure point, not the data or the path.
2. Don't iterate on path/CWD/shim/virtual-desktop guesses — the UI crash is independent of all of them. Go straight to Inno's silent switches (`/VERYSILENT /SUPPRESSMSGBOXES /NOCANCEL /DIR=...`); silent mode never instantiates the FMX forms.
3. Monitor success by the target directory growing (`du -s` deltas), not by whether the process is alive (the error dialog also keeps it alive) or by exit code (the FMX teardown GPF poisons it).
4. Treat post-extraction Delphi exit errors as cosmetic; validate by launching the installed game.
5. Cleanup hygiene: `pkill -f "Setup.exe"` from a bash tool kills the tool's own shell (the pattern matches its own cmdline) — use `pkill -f '[S]etup\.exe'` bracket form or Proton's `wineserver -k` with WINEPREFIX.

## 2026-08-16 — Quoted env values break hand-rolled dotenv parsers

**Pattern:** Verifying the patient workspace with a headless Playwright script, I minted a `bilun:session` HMAC token in Node by reading `BILUN_SESSION_SECRET` from `frontend/.env.local` and parsing with a regex — no quote handling. Next.js and the backend both load these files dotenv-style (stripping surrounding quotes), so my token's secret was 66 chars (quotes included) while both servers used 64. Every request 401'd / redirected to /login, and a cross-language HMAC check against Python "proved" the signatures differed even though the files were byte-identical. Cost ~3 debugging rounds before comparing secret *lengths*.

**Rule:** When a script reads `.env*` values directly, replicate dotenv semantics exactly: `.trim()` **and** strip surrounding `"`/`'`. When HMAC/secret mismatches appear across languages, compare `len(secret)` and hex digests before comparing the derived signatures. And never trust a comparison built through shell `echo`/`sed` pipelines without exporting every variable — `os.environ.get("X", "")` silently compares against `""`.

## 2026-08-16 — Live backend caches the dataset; plan KPIs must be validated against the API

**Pattern:** The plan's KPI numbers for SENTETIK-HASTA-0001 (26 findings, 4 revenue opportunities) disagreed with a fresh `compute_patient_billing_report` run from disk (24 findings, 2 opportunities). Both were "right": the long-running uvicorn caches the synthetic dataset in memory, and the on-disk cohort had since changed (2 copay exemption rows). Treating the plan's numbers as wrong and the disk numbers as right — then hardcoding the disk numbers into verification assertions — produced false test failures; the live UI (badges 18/4/4) was correct all along.

**Rule:** Before disputing or hardcoding any plan/UI KPI, query the *live* API (with a valid session cookie) and classify the live payload. Verification assertions for live apps should be computed from the live response, not from an offline recomputation or a plan document.

## 2026-08-16 — `git reset --hard` silently discarded uncommitted adaptation edits

**Pattern:** Preparing PR #74, I created the feature branch, then ran `git reset --hard origin/main` on main to restore it — while uncommitted adaptation edits (import fixes, i18n key moves, test fixtures) sat in the working tree. The reset wiped them; the amended-and-pushed commit was the PRE-adaptation state, so CI's typecheck failed (`SutClauseDrawer has no default export`) even though local `tsc`/`vitest`/browser checks had been green minutes earlier on the adapted tree. All edits had to be re-applied from conversation history.

**Rule:** `git reset --hard` destroys uncommitted work by design. Before any hard reset: `git add -A && git commit` (or stash) the current tree. After ANY reset/checkout that could touch the working tree, re-run the verification suite (tsc + vitest) on the exact commit that will be pushed — never trust a green result from an earlier tree state. CI runs against what is pushed, not what was verified.

## 2026-08-22 — Government program terms are training-data-stale; verify structure AND read the evidence already in search results

**Pattern:** Described TÜBİTAK BiGG as a "~200K TL grant" from training-data memory. The user corrected me: BiGG is no longer grant-based — it was restructured into **1812 "BiGG Yatırım" (investment-based)**: the TÜBİTAK BiGG Fonu invests equity (900K TL for 3% at pre-seed Aşama 2; up to 10% via tohum yatırım fonları at Aşama 3), requires an AŞ company, and signs an Investment & Shareholders Agreement instead of issuing a grant. The worst part: my own web-search results in that same turn already showed the 1812 BiGG Yatırım page with "%3 hisse karşılığında 900.000 TL yatırım" — I had the evidence on screen and still repeated the stale grant framing from memory.

**Rule:** Turkish government support programs (TÜBİTAK, KOSGEB, Bakanlık) change amounts and even funding MODE frequently — never state their terms from training data. When citing them:
1. Verify against official sources (tubitak.gov.tr, kosgeb.gov.tr) for the CURRENT call cycle before naming amounts or grant-vs-equity structure.
2. If search results already surfaced contradicting evidence, re-read them instead of defaulting to memory — having fetched a source is not the same as having checked it against the claim I'm making.
3. Distinguish superseded program codes/models explicitly (1512 old grant model vs 1812 investment model) rather than blending names.

## 2026-09-27 — Verify compiled routing and the route installed for restart

**Pattern:** A private frontend had the correct runtime `API_PROXY_TARGET` but its Next build still rewrote `/api/*` to the old backend. Separately, a Caddy route switch could replace the Caddyfile and crash before reload, leaving the loaded route and on-disk restart route different. Runtime environment and currently loaded configuration alone did not prove the deployed pair would remain correct.

**Rule:** For a release candidate, inspect the frontend's compiled `routes-manifest.json` and exercise the frontend API path against the intended backend. For a reverse-proxy transaction, verify both the loaded configuration and the installed file at every state transition; after a failed switch, reinstall and verify a maintenance barrier before reporting a blocked state.

## 2026-09-28 — Separate serving history from a rebuilt comparison baseline

**Pattern:** The Wave A receipt issuer reused one `baseline_build_id` for the protected live PR98 cache and an independent same-input PR98 rebuild. Those caches have different historical build/code identities even though all 16 legacy content tables match. A byte-equality gate between the two cache files therefore made honest signing impossible.

**Rule:** Give the serving cache and rebuilt comparison cache separate identities. Verify the serving snapshot against the live service, verify the rebuilt cache against pinned inputs, and require type-sensitive equality of every legacy content table between them before using the rebuild for candidate parity. Never rewrite cache metadata or force build IDs to match to pass a release gate.

## 2026-09-28 — Pin DuckDB's whole readable state

**Pattern:** A read-only DuckDB connection can read committed rows from an uncheckpointed `.wal` while the hash of the main `.duckdb` file stays unchanged. An independent review reproduced this against the receipt's baseline comparison.

**Rule:** Reject any WAL sidecar, including a broken symlink, before and after hashing every cache used for release attestation. Keep crash-WAL regression coverage on both the serving-to-baseline bridge and the same-input semantic checkpoint.

## 2026-10-04 — Source review windows also change test boundaries and coverage hash closure

**Pattern:** Adding the bounded October 4 source-review window moved the SMA/antifungal `future_source` fixture (`October 2 + 2 days`) into an admitted day. The coverage inventory stayed identical, but its dependency hash map still omitted the new captures/receipt and pinned the old catalog/resolver hashes. The focused source package missed these three full-CI failures.

**Rule:** After a source-review window changes, verify future-source fixtures against the first unsupported day (October 5 for this review), preserving `not_evaluated` and zero predicate attempts. Regenerate the evidence with existing helpers against the actual persisted corpus/coverage frame and `coverage_dependency_hashes` over the final source-file closure; never copy hashes from differently serialized temporary parquets. Before publishing, include documentary boundary tests, committed coverage currentness, `compile_rules.py --check`, and manifest parity in the source gates. Prove the original corpus and four coverage parquet bytes remain unchanged when only source evidence is refreshed.

## 2026-10-07 — A regression guard is only as honest as its mutation tests

**Pattern:** The phase-0 numbers-parity guard said "PARITY OK: no number changed" while a missing amount had become "0.00 TRY" (multiplicity was warning-only), two amounts had swapped labels (unlabelled multiset), "Partial exact" lines had been collapsed (presence per kind, not per line), and Turkish uppercase wording never matched (JS /i does not fold ı/İ). Every one of these passed because the guard was only tested with changes it was built to catch, not with the changes a phase will actually make.

**Rule:** For every honesty rule a tool claims to enforce, write the mutation that violates it (null to zero, swap under labels, drop one of N lines, uppercase TR text, text collapsed by CSS instead of `<details>`) and assert the tool fails; a warning-only path never counts as enforcement, and a success line must not claim more than the compared dimensions prove. Verify visibility from the layout, not from `innerText`, and test text matching with the CSS-transformed (uppercased) text the browser returns.

## 2026-10-07 — A baseline only guards what it recorded: list what the next phase will change, and record what the tool cannot show

**Pattern:** The phase-0 baseline passed two review rounds while it held page 1 of 5 of the Patients table (the headline screen of Phases 1 and 3), never opened the Source drawer (the central change of Phase 2), missed uncertainty lines such as "could not be verified" and "cannot evaluate" because the marker vocabulary was written from memory, skipped renamed or re-cased labels without a word, and judged a collapsed box with padding as visible. It also never rendered Wave A evidence (the backend needs a signed release receipt), so the largest block Phase 2 collapses was one line, and nothing in the output said so. Each gap was invisible to `--compare`, which printed "PARITY OK".

**Rule:** Before recording a baseline for a phase, write down the rows, drawers, collapsed blocks and labels that phase will change and check that each one is a state in the baseline (walk every page of a table until the cohort is covered, assert the count; open every kind of drawer). Build vocabulary lists from the real message files and test them against those strings in both locales. Test a visibility probe with the collapse patterns authors actually write (padding or border on a zero-height box, `scaleY(0)`, `clip-path`), and run that test in CI, not only by hand. Anything the environment cannot render must be recorded as data (run-meta `limits`, a line at the end of the run) and named in the header, so a page height or a missing block is never read as proof; never fake the missing data to fill the gap. A guard that skips an unmatched case (a renamed label) must count it and report it.
