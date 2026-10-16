## Task: Catalog dates (#226, #227), package-gap double count and capture-gap rounding, independent review of #283 (2026-10-16)

### Goal
- Bilun's EK-2B/EK-2C/EK-1A/EK-3O catalogs keep every row, from its own start date.
- A package-mandated bill shows the package gap once.
- Money totals keep their kuruş.
- An independent check confirms or refutes the 17 review findings on the merged session-rule code (#283).

### Subtasks
- [x] 1. PR A (#226 + #227), one branch because both change `scripts/sut/catalogs/price_history.py`:
  - Result: PR Safa675/Bilun#287 (3 commits; curated files rebuilt in the CI image, and a second rebuild gives the same bytes).
  - EK-2B: 69,546 → 70,932 rows (30 procedures back; 1,118 rows start after their list's date).
  - EK-2C: 24,063 → 24,164 rows; 140 rows start later.
  - EK-1A and EK-3O are dated.
  - Local suite and the in-image CI gate: 8,797 passed, 0 failed.
  - Showcase results and the 50-patient cohort are byte-identical.
  - Follow-ups:
    - EK-3O/EK-1A callers without a service date;
    - marker parsing in the other lists (EK-2Ç, EK-3x, EK-2G, EK-2C-1);
    - stale dental catalog.
  - [ ] EK-2B: strip the amendment marker from the code cell (as `extract_ek2c` does), and keep the amended row over the older one.
  - [ ] Every curated row gets `valid_from` = its own Yürürlük marker date when later than the file date (`ek4a_history.py` is the model). The readers use it: `gazette.py:138-146`, `catalog_membership.py:103-119`.
  - [ ] EK-1A and EK-3O get a date column.
  - [ ] Rebuild the curated files inside the reviewed CI image (runbook "Local SUT package ingest"). Run the CI gate in the image.
  - [ ] Tests:
    - a marker row is kept;
    - 609541 exists from 2026-10-10;
    - P609541 does not match before 2026-10-10;
    - a row marked 2026-09-05 does not apply on 2026-07-07;
    - the showcase bills are unchanged.
- [x] 2. PR B (defects 1 + 2), PR Safa675/Bilun#286, branch `claude/fix-package-gap-double-count-and-rounding`:
  - [x] On a claim where the package is mandated but the bill is itemized, components the package includes (SUT §2.2.2.B-1(1): bed, companion, anaesthesia, exams, labs) add no itemized uplift inside the package window; days after the window still do (§2.2.2.B-1(4)). Faulty S1: SGK uplift 4,085.87, not 4,234.07. S4's companion uplift (no package) stays 370.50.
    - Measured: faulty S1 4,234.07 → 4,085.87 (companion row 148.20 → 0); S2 bed 667.08, S3 anaesthesia 928.09, S4 companion 370.50 unchanged; clean bills 0 TL. A 12-day mandated stay still expects 4 bed days (889.44) and 3 companion nights (222.30) after the window.
    - The mandate comes from the codes, not `package_candidate`: an EK-2/B line flagged "must use package billing" at the claim's tier, no package line for its code, an EK-2/C price and group on the day.
    - Exams and labs have no itemized uplift detector. Their capture-gap rows (separate headline) are not windowed yet: open question.
    - Cohort: SGK uplift 88,920.95 → 61,310.65 TL on 11 of 50 patients (mandated EK-2/C surgery billed itemized). The #269 gate still reads `package_candidate`, so these claims show no package gap until it is fixed.
  - [x] `capture_gap_try` keeps two decimals: S7 shows 1,138.22, not 1,138. Also `package_adequacy_review_try` (cohort 12,717 → 12,717.97).
  - [x] This PR also carries this block and the wave 2 record below.
- [x] 3. Independent review of #283 on `main`. Three read-only reviewers:
  - SUT correctness;
  - each of the 17 findings fixed or not, with probes, plus the cohort effect;
  - tests, and whether any gate relies on synthetic-only fields such as `package_candidate`.

  Confirmed bugs get their own fix PR.
- [x] 4. Per PR: targeted tests, the full suite, compile check, parity and ruff, run in sequence; showcase proofs before and after; CI on `main` green before each push.
- [x] 3a. Review results (2026-10-16): 15 of the 17 findings are fixed and 2 are partial. Must-fix problems still on `main`:
  - IONM P703365 and neuronavigation P614981 get the session cut despite C001389/C001413;
  - a mixed session prices every package at 100 % (C000670 says 25 %);
  - the #269 gate depends on the generator-only `package_candidate`;
  - "billed as package" has two definitions (category vs `P` code);
  - the package gap is stacked on itemized uplifts (= defect 1, PR B);
  - the exposure map keyed by code loses the primary on repeated codes.
- [x] 5. PR C (#283 follow-up), built on PR B's branch, because both need the code-derived "package mandated" predicate:
  - Result: PR Safa675/Bilun#288. It contains #286's commits, and main is merged in (c883b0df, #287).
  - All 14 items are done, plus 2 more the agent's own review found (C000672 session switch; IONM/neuronavigation priced next to the package).
  - "2 b" is applied. S8's money is 3,584.80, the excess over the lenient separate-incision 50 %; the strict-reading part (1,792.40) is a 0-TL review.
  - Outpatient mandate follows EK-2/A-2: new curated `ek2a2_outpatient_additional_procedures.parquet`, 1,035 rows, built in the CI image. 22 codes qualify; day cases stay mandated (C003484).
  - Cohort SGK uplift: main 88,920.95 → #286 61,310.65 → PR C before the EK-2/A-2 rule 564,058.45 → final 88,015.34.
  - Full suite 8,890 passed, 0 failed. The CI-image gate is green.
  - fix the must-fix list above (except defect 1, which PR B owns);
  - plus the confirmed smaller items:
    - `is_bundled` decided by the §3.1.4/#284 classifier, not the input flag;
    - risk = billed − package, not all-or-nothing;
    - catalog price when the unit price is missing;
    - no session uplift on a must-package line;
    - only operation branches in the uplift's cross-specialty check;
    - the package side priced with the B(3) rules for several operations;
    - C000690 drugs and C000707 post-window lines not counted as replaced;
    - Turkish ı in branch keys;
    - a test pinning the EK-2B puan ranking.
  - Domain questions wait for Safa:
    - +25 points per session or per line (C000662);
    - money vs a 0-TL review row when the incision or branch is unknown;
    - §3 incisional and endoscopy scope.

### Decisions (Safa, 2026-10-16)
- #259: days before the operation on the same inpatient takip stay inside the package. SUT §2.2.2.B-1(1) (C000685): "takip alındıktan sonraki … yatak bedeli … dahil".
- **Unknown incision or branch (Safa: "2 b"):** when the bill cannot show the incision type or the branch, Bilun claims money only above the most lenient legal factor (separate incision; +25 across specialties). Between the strict and the lenient factor it shows a 0-TL "kontrol et" review row.
- **Outpatient package gap (follows the SUT text; was an open question):**
  - Rule: §2.2.2(1) (C000646) mandates packages for yatarak services only. For outpatients, §2.2.1.B-1(10)(a) (C000581/C000582) applies the package method only to EK-2/A-2 procedures that are also in EK-2/C.
  - Data: the current EK-2/A-2 list is in the repo. `data/gazette/raw/annex=EK-2A-2/effective_date=2021-06-01` comes from the 2026.10.02 package, 517 rows, 17 marker-dated amendments up to 2026-04-16. It is not curated and the engine does not read it.
  - Fix in PR C: curate EK-2/A-2 with marker dates; an outpatient line is package-mandated only when it is on EK-2/A-2 on its date.
- **+25 points per session or per line (C000662/C000674):** Safa asks Ahmet Almalı. Until then, keep today's behaviour (whole session).
- **Follow-up issues filed 2026-10-16 (Safa's yes):**
  - #289 newborn-bed "çocuk/pediatri" substring;
  - #290 capture gaps inside the package window;
  - #291 markers in 13 other lists;
  - #292 EK-3O/EK-1A callers without a date;
  - #293 stale dental history and its reader ignoring `valid_to`;
  - #294 remaining `package_candidate` reads and the crosswalk under `synthetic/`.
- Defect 3 (0-TL review rows on every bill) waits for Safa's choice of what the demo shows.

### Wave 2 record (restored; the original block was lost uncommitted on 2026-10-15)
- **Workflow `wf_f4b4dd73-12f`, materials (#262 → PR #284):** implement → 3 reviewers → fix-up (12 findings applied, 3 partly rejected with reasons) → independent verify. Every criterion passed at f480cb68, which is the merged commit.
- **Workflow, session rules (#261/#264/#269 → PR #283):** implement → 3 reviewers (17 findings, 7 must-fix). Fix-up and verify died on the usage limit.
- **#283 follow-up:** b06cfbf3 says it addressed all 17. Argon merged #283 and #284 on 2026-10-15. Item 3 above checks b06cfbf3 independently.

### Out of Scope
- Defect 3 (waits for Safa).
- Synthetic v3 P2–P7 (waits for Safa's review of stories, lab table and ICD/drug notes).
- The strict release lane.

## Task: Step 3 engine and lab fixes — #280, #281, #255, #256, #259 (2026-10-15)

### Goal
Resolve the 5 remaining engine and lab-price issues (#280, #281, #255, #256, #259) in atomic commits on a single branch so all showcase-bill and lab-pricing defects are closed and verified green in CI.

### Subtasks
- [x] 1. **#280 (`lab_capture_gap` & `prose_rules` `lookup_procedure_code` `match_type` audit):**
  - Require `lookup.get("match_type") == "exact"` in `lab_capture_gap._resolve_lab_list_price` (`src/bilun/domain/prose_rules/lab_capture_gap.py`).
  - Guard reachable `prose_rules` `lookup_procedure_code` call sites (`dental_ga_uplift.py`, `procedure_addon_uplift.py`, `procedure_capture_gap.py`, `session_pricing.py`) against `match_type == "prefix_search"`, and record the runtime audit of all 10 call sites.
  - Add regression tests in `tests/unit/domain/prose_rules/test_lab_capture_gap.py` proving `L1070`, `L100`, `L10702` emit no finding while `L107020` prices at 19.73 TL on 2026-10-15.
- [x] 2. **#281 (Remove caller-less `_load_gazette_visit_prices`, `get_visit_prices`, and `get_lab_price`):**
  - Remove `_load_gazette_visit_prices` from `src/bilun/domain/loaders/gazette.py` and its re-export in `src/bilun/domain/loaders/__init__.py`.
  - Remove `get_visit_prices` and `get_lab_price` from `src/bilun/domain/catalog.py`.
  - Update `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:52` to cite `yatak_puani.py:40`, `refakatci.py:38`, and `icu_puani.py:59,65`.
  - Verify `git grep -n -w` returns zero hits in code/tests for the 3 removed names.
- [x] 3. **#255 (`detect_icu_tier_overbilling` sourced evidence & informational-only review):**
  - Cite `SUT §2.4.4.H.(1), (2), (4)` (`C001233`, `C001234`, `C001236`) and remove the non-existent `"EK-2/C-A"` citation in `src/bilun/domain/prose_rules/icu_puani.py`.
  - Count only separately billable items on EK-2/C ICU package days as positive support evidence: EK-2/C `A/B/C`-group procedures (e.g., ECMO `605960`, `605969`–`605979`, or any line whose EK-2/C group is in `A1`/`A2`/`A3`/`B`/`C`) and `§2.4.4.H.(4)` items (`704210`, `704230`, `704290`, `704920`, plus their keywords).
  - Emit an informational review (`severity="info"`, `at_risk_try=0.0`, `savings_try=0.0`, `risk_amount=0.0`) when `P552003`/`P552008` has no separately billed support item on the episode; update `tests/unit/domain/prose_rules/test_icu_puani.py`.
- [x] 4. **#256 (Turkish capital & filler-word normalization in `_specialty_matches`):**
  - Update `_normalize_tr` and `_specialty_matches` in `src/bilun/domain/prose_rules/_drug_indication/matching.py` so Turkish capitals (`I`→`ı`→`i`, `İ`→`i`) and filler words (`"ve"`, punctuation/abbreviations like `"(KVC)"`) normalize cleanly without cross-matching unrelated specialties (e.g. `"Kalp ve Damar Cerrahisi (KVC)"` matches `"kalp damar cerrahisi"` and never `"kardiyoloji"`).
  - Remove the two strict `xfail` marks in `tests/unit/domain/prose_rules/test_specialty_scope_cases.py` and add unit tests for `"ACİL TIP"`, `"GÖZ HASTALIKLARI"`, and non-matching `"kardiyoloji"`.
  - Refresh `file_sha256["src/bilun/domain/prose_rules/_drug_indication/matching.py"]` in `data/gazette/sut_coverage_evidence.json`.
- [x] 5. **#259 (EK-2C package window for `yatak_puani.py` and `refakatci.py`):**
  - Resolve the EK-2/C group (`A1`/`A2`/`A3`/`A`: 15, `B`: 10, `C`: 8, `D`: 5, `E`: 3 days) as of the package procedure date via `get_ek2c_entry` (with fallback to `line.ek2c_group`, or 1 day when ungrouped).
  - Bundle pre-op days on the same inpatient takip (`§2.2.2.B-1(1)`) and the `1..W` package window days starting on the procedure date (`§2.2.2.B-1(3)`), expecting `510010` and `510121` only for days after `window_end` (`§2.2.2.B-1(4)`).
  - Update `tests/unit/domain/billing/test_elkitabi_tablo23.py` and add regression tests in `test_yatak_puani.py` and `test_refakatci.py` covering clean S1/S5/S8 (0 TL uplift) and stays exceeding the package window.
- [x] 6. **Verification & CI:**
  - Run `ruff check src/ scripts/`, full `pytest -q`, `compile_rules.py --check`, and `audit_manifest_parity.py --drug-only`.
  - Push branch, open PR, run CI via `laptop_runner.py`, check reviews, squash-merge to `main`, and verify `main` CI green.

### Review (2026-10-15)
- **#280:** Required `match_type == "exact"` in `lab_capture_gap._resolve_lab_list_price` and rejected `prefix_search` across the 5 reachable `prose_rules` call sites (`dental_ga_uplift.py`, `procedure_addon_uplift.py`, `procedure_capture_gap.py`, `session_pricing.py:124,436`). Added regression tests for `L1070`, `L100`, `L10702`, `L1018`, and `L107020`.
- **#281:** Removed caller-less `_load_gazette_visit_prices`, `get_visit_prices`, and `get_lab_price`, and updated the plan citation in `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:52`.
- **#255:** Removed non-existent `"EK-2/C-A"` citation in `icu_puani.py`; scoped positive Tier 3 support evidence to separately billable EK-2/C `A/B/C`-group procedures and `§2.4.4.H.(4)` items (`704210`, `704230`, `704290`, `704920`, ECMO `605960`/`605969`–`605979`); emitted informational-only review (`severity="info"`, `at_risk_try=0.0`) when `P552003`/`P552008` lacks separately billed support items.
- **#256:** Fixed Turkish capital folding (`İ`→`i`, `I`→`ı`→`i`) and filler/abbreviation normalization in `_drug_indication/matching.py`, un-xfailed both tests in `test_specialty_scope_cases.py`, and refreshed `matching.py` SHA-256 in `sut_coverage_evidence.json`.
- **#259:** Applied SUT `§2.2.2.B-1(1), (3)-(4)` EK-2/C group package windows (`A1/A2/A3/A=15`, `B=10`, `C=8`, `D=5`, `E=3`) to `yatak_puani.py`, `refakatci.py`, and `yatak_icu_overlap.py`, and updated Tablo 23 + unit tests.

### Out of Scope
- Catalog parser / temporal issues `#226` and `#227`.
- Rewriting committed showcase `results/` snapshots.

## Task: Remove three dead lab-price code paths (follow-up to Safa675/Bilun#271, 2026-10-15)

### Goal
The `get_lab_price` fallback in `lab_capture_gap._resolve_lab_list_price`, the caller-less `_load_gazette_lab_prices` with its re-export, and the never-read `_SUT_CODE_TO_BILUN` are gone with no behaviour change; the `constants.py` hash pinned in `data/gazette/sut_coverage_evidence.json` is refreshed openly in its own commit; all CI gates pass.

### Verified before planning (on main `91fb756c`)
- Fallback: `_resolve_lab_list_price` (`src/bilun/domain/prose_rules/lab_capture_gap.py:30-43`) has one caller (`:105`) and only receives `str(test_name).strip().upper()` values that start with `L` and have at least 4 characters (`:75-79`). `get_lab_price` (`src/bilun/domain/catalog.py:192`) returns a price only for a key of `BILUN_TO_SUT_CODE`, and no key has that shape (checked at runtime), so for every code that caller can pass, on every catalog date, the fallback returns `None`. (It does return a price for a BILUN name such as `"CRP"`, which the caller never passes.) `get_lab_price("L106430")` is `None`; `get_lab_price("PT")` is 55.96 on main (39.49 on #271). The first branch prices all 1,948 L-codes of the EK-2B catalog in force on 2026-10-15 (the default date), and the synthetic lab feed sends L-codes (`SUB_CODE` → `test_name`, `src/bilun/cache/loaders.py:25`). This fallback is the only caller of `get_lab_price` in the repository.
- `_load_gazette_lab_prices` (`src/bilun/domain/loaders/gazette.py:449`): `git grep` finds only the definition and the import and `__all__` entry in `src/bilun/domain/loaders/__init__.py:14,36`; no dynamic access. Its last caller was removed in `7e2cdfdc` (2026-06-22). `get_all_lab_prices` keeps two callers (`src/bilun/api/routes/pricing.py:195`, `src/bilun/domain/catalog.py:476`).
- `_SUT_CODE_TO_BILUN` (`src/bilun/domain/constants.py:246-249`): only its definition; present since the initial extraction `1f146824` (2026-05-16) as `_SUT_CODE_TO_ILAY`, renamed in `a27c5298` (2026-05-23), never read. `constants.py` has no `__all__`, and nothing imports the loop names `_name`/`_code`.
- Hash closure: `coverage_dependency_hashes` (`src/bilun/domain/sut/coverage_evidence.py`) pins `constants.py` but not `lab_capture_gap.py` or the two loader files, so exactly one pinned hash changes.

### Subtasks
- [x] 1. Baseline on unchanged main: `scripts/sut/build_sut_coverage.py --output-dir <scratch>/before` gives an evidence JSON that parses equal to the committed one and four parquets frame-equal to the committed ones; `tests/unit/domain/prose_rules/test_lab_capture_gap.py`, `tests/unit/domain/prose_rules/test_clause_provenance.py` and `tests/unit/domain/sut/test_coverage_evidence.py` pass.
- [x] 2. Delete the `get_lab_price` fallback from `_resolve_lab_list_price` and drop `get_lab_price` from the import; update the detector's line range that `data/synthetic/reference/lab_reference_notes.md:91` cites (`lab_capture_gap.py:74-136`), the only line-anchored citation the removals shift.
- [x] 3. Delete `_load_gazette_lab_prices` from `src/bilun/domain/loaders/gazette.py` and its import and `__all__` entry from `src/bilun/domain/loaders/__init__.py`.
- [x] 4. Delete `_SUT_CODE_TO_BILUN` (comment and three lines) from `src/bilun/domain/constants.py`.
- [x] 5. Commit items 2-4 together as one behaviour-preserving removal; re-run the item 1 tests.
- [x] 6. Refresh the hash: run the builder into `<scratch>/after`; prove the evidence parses equal to the committed file except `file_sha256["src/bilun/domain/constants.py"]`, that the new value equals `sha256(constants.py)`, and that the four parquets are frame-equal to the committed ones; replace only that value; `git diff` shows one changed line; commit on its own.
- [x] 7. Verify one after the other, never in parallel: `ruff check src/ scripts/`; full `python -m pytest -q -n auto`; `python scripts/sut/compile_rules.py --check`; `python scripts/sut/audit_manifest_parity.py --drug-only`; `git status` shows only the intended files, checked again after pytest.
- [x] 8. Confirm main CI is green and whether `origin/main` moved (if #271 merged first: merge main, redo item 6 on the merged `constants.py`). Before the push, main CI was green on `91fb756c`, `origin/main` had not moved, and #271 was still open.
- [x] 9. Push the branch, open the PR, follow its CI.
- [x] 10. Ask Safa before merging.

### Out of Scope
- `_load_gazette_visit_prices` (`src/bilun/domain/loaders/gazette.py:472`) has no callers either (removed in the same `7e2cdfdc`), and `get_visit_prices` (`src/bilun/domain/catalog.py:235`) is only called by it. These are visit and bed prices, not lab prices, so they are reported, not removed.
- `get_lab_price` (`src/bilun/domain/catalog.py:192`) has no caller once the fallback is gone (#271 adds none). It sits in the catalog's public price-lookup section next to `get_all_lab_prices`, so it is reported, not removed.
- Found on main during review, not caused here: `_resolve_lab_list_price` ignores `match_type`. `lookup_procedure_code`'s prefix search (`src/bilun/domain/catalog.py:414-437`) returns its first candidate as `entry`, so a truncated or unknown code is priced as another test and labelled `ek2b_list_price`. `"L1070"` gives 1,810.89 TL (L107000, a lymphocyte crossmatch) and `"L1018"` gives 222.55 TL (L101800). This is flagged as a separate task.
- The lab map values (#271), and any behaviour change.

### Merge order
#271 changes the same evidence line and also adds its entry at the top of this file. Whichever PR merges second merges main, redoes item 6 on the merged `constants.py` and keeps both `tasks/todo.md` entries. Both PRs also edit `data/synthetic/reference/lab_reference_notes.md`, at lines 91 and 96-107, which merge cleanly. #271 moves `HEMOGRAM_TESTS` to `constants.py:235-251`, so the `constants.py:228-244` citation on line 88 of that file goes stale once #271 is in; this PR does not cause that.

### Review (2026-10-15)
- Commits: `10d67d68` (the three removals and the shifted citation in `lab_reference_notes.md`), `76316b99` (the hash refresh, one line), then this plan. After the review only the first commit's message was reworded. The trees are those of the verified `51e67ebd`/`032b071e`.
- Hash refresh: outside `file_sha256` the regenerated evidence parses equal to the committed file; of its 163 pinned hashes only `constants.py` changed (`e0c90e5f…` → `13f37977…`); the four coverage parquets are frame-equal. On unchanged main the regenerated evidence also parses equal. Its bytes differ only in where the `input_clauses` key sits, because the committed file lists it first instead of in the builder's sorted order, so the value was replaced in place.
- No file at HEAD pins the old SHA-256 or blob id of any of the five changed files. As a control, the same search on main finds the evidence file. `data/gazette/source_authority/corpus_consumer_review_pr128.json:25730` pins an older `loaders/gazette.py` (`725191e1…`, the state at `d0337600`). It is already stale on main, no code reads it, and the ILAY Phase 1 entry below keeps it on purpose.
- Local environment (miniforge: pandas 2.3.3, polars 1.41.2, pyarrow 24.0.0): ruff clean; pytest 8,406 passed, 1 failed, 1 skipped, 4 xfailed; `compile_rules.py --check` 119 byte-identical; parity 0 issues over 23 manifests. The failure (`tests/unit/scripts/test_curated_catalog_idempotence.py::test_pandas_string_storage_variation_does_not_change_decoded_semantics`) also fails on unchanged main in this environment. pandas 2.3.3 turns `None` into `'None'` under `astype("str")`; CI locks pandas 3.0.6.
- CI image `bilun-laptop-ci:20261008-runtime-complete` with `requirements-ci.lock` (Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1), on a shallow clone of `032b071e` (same tree as `76316b99`), running CI's backend steps in order: ruff clean; pytest 8,407 passed, 1 skipped, 4 xfailed; `compile_rules.py --check` 119 byte-identical; parity 0 issues; no tracked file changed.
- `git status` after every step showed only `tasks/todo.md`.
- Independent read-only review: none of the three claims falsified. A differential run of main's and this branch's `_resolve_lab_list_price` over 23 catalog dates and 1,971 inputs made 45,333 calls with 0 differences; main's fallback was reached 359 times and never returned a price. I re-ran it with the same result. The review's corrections, all applied: "every input" became "every code the caller can pass"; the map's history starts at `1f146824`, not `a27c5298`; the 1,948 count is dated; and `get_lab_price` is left without callers. It also found the `match_type` problem listed under Out of Scope, which I reproduced. Commit `10d67d68` alone fails the coverage-evidence test until `76316b99` refreshes the hash. That split is the separate commit Safa asked for, and it is harmless under the squash merges this repo uses.

## Task: Fix wrong EK-2B codes in the BILUN lab test map and its old-code aliases

### Goal
Every name in `BILUN_TO_SUT_CODE` and every old code in `_OLD_TO_NEW_CODE` (`src/bilun/domain/constants.py`) resolves to the EK-2B code whose in-force catalog name is that test, so `/api/lab-prices` serves PT/INR `L106430` 39.49, aPTT `L101050` 35.53, Prokalsitonin `L106240` 167.91 and Protein `L106300` 7.20 TL (2026-07-07 edition), and a test fails when a mapped code is missing from the catalog in force or names another test.

### Subtasks
- [x] 1. Add `tests/unit/domain/catalog/test_lab_code_map.py` and see it fail on the current map:
  - every mapped code is a real entry of the EK-2B catalog in force (`load_sut_catalog()`, today, as `/api/lab-prices` serves it) and `get_all_lab_prices()` prices every name;
  - the test name appears as whole words in the catalog name after Turkish case folding (`turkish_lower`, `src/bilun/domain/utils.py:16`); names the catalog spells differently are listed explicitly (13 hemogram components -> Hemogram, GFR -> Kreatinin, ALP -> Alkalen fosfataz, HbA1c -> Hb A1c, PT/INR -> Protrombin zamanı, Albumin -> Albümin);
  - every entry is pinned to its reviewed exact catalog name (the containment check alone accepts e.g. T3 -> Revers T3, Kreatinin -> Albümin/Kreatinin);
  - every old code resolves through `lookup_procedure_code` to the entry, and reviewed name, of its test name's code;
  - the `/api/lab-prices` route function returns, for every row, the mapped code and that code's catalog price (no 0.00 rows).
- [x] 2. Fix `BILUN_TO_SUT_CODE`: PT and INR -> `L106430`, aPTT -> `L101050`, Prokalsitonin -> `L106240`, Protein -> `L106300`; Kalsiyum -> `L103860` (total, not ionized) and CRP -> `L101850` (quantitative, not latex), both confirmed by Safa on 2026-10-15.
- [x] 3. Replace the literal `_OLD_TO_NEW_CODE` values with an old-code -> test-name table and derive the codes from `BILUN_TO_SUT_CODE`, so an alias cannot point elsewhere than its test name (fixes 905320, 904290, 903170).
- [x] 4. Refresh the `src/bilun/domain/constants.py` hash pinned in `data/gazette/sut_coverage_evidence.json` (checked by `tests/unit/domain/sut/test_coverage_evidence.py::test_committed_coverage_artifacts_match_current_source_rules_and_api`): run `scripts/sut/build_sut_coverage.py --output-dir <scratch>`, prove the four coverage parquets equal the committed ones and the evidence JSON differs from HEAD only in that hash, then copy only the JSON.
- [x] 5. Verify: the new test passes; `ruff check src/ scripts/`; full `python -m pytest -q -n auto`; `python scripts/sut/compile_rules.py --check`; `python scripts/sut/audit_manifest_parity.py --drug-only`; `git status` lists only the intended files.
- [x] 6. Commit the fix and test, then the hash refresh as its own commit; confirm main CI is green; push the branch, open the PR, follow its CI.

### Out of Scope
- `src/bilun/domain/prose_rules/lab_capture_gap.py:39` passes an SUT code to `get_lab_price`, which expects a test name, so that fallback never resolves; the map fix does not change it.
- `_load_gazette_lab_prices` (`src/bilun/domain/loaders/gazette.py:449`) and `_SUT_CODE_TO_BILUN` (`constants.py:254`) have no callers.
- Renaming test-name keys (e.g. `Albumin`), adding tests to the map, the synthetic cohort's lab units, staging deploy.

### Review (2026-10-15)
- Confirmed with Safa before coding: Kalsiyum -> `L103860` (total) and CRP -> `L101850` (quantitative); merge after green CI.
- `/api/lab-prices`: PT/INR 55.96 -> 39.49, aPTT 17.09 -> 35.53, Prokalsitonin 46.06 -> 167.91, Protein 55.96 -> 7.20, Kalsiyum 17.09 -> 7.20, CRP 9.86 -> 16.46 TL; 40 rows, none at 0.00.
- Test (107 cases) fails on the old map for exactly PT, INR, aPTT, Prokalsitonin and Protein in the containment check; the exact-name pins (all 40 entries, added after review) also catch Kalsiyum and CRP. A mutation script caught 14 wrong map codes (e.g. T3 -> Revers T3, Kreatinin -> Albümin/Kreatinin) and the 5 old wrong aliases.
- `sut_coverage_evidence.json`: only the `constants.py` hash changed; the regenerated evidence parses equal and the four coverage parquets are frame-equal.
- Main moved during the work (#257, #258). After merging it (only `tasks/todo.md` conflicted; both sides kept): ruff clean; pytest 8,514 passed, 1 skipped, 4 xfailed; `compile_rules.py --check` 119 byte-identical; parity 0 issues; tree clean. Item 6 of `data/synthetic/reference/lab_reference_notes.md` now says the codes are fixed.
- PR: Safa675/Bilun#271.

## Task: Synthetic demo v3 — P0 decisions and baselines, P1 reference data, showcase story drafts (2026-10-15)

### Goal
Start `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`:
- record Safa's answers;
- keep the engine baseline;
- classify the test pins;
- build the P1 reference tables with schema tests;
- hand Safa 8 showcase story drafts to review.

The generator and the cohort do not change in this task.

### Subtasks
- [x] 1. Record the answers in the plan:
  - Q1 2026 February–September service dates;
  - Q2 one SGK-contracted private hospital;
  - Q3 Safa reviews the 8 showcase stories;
  - Q4 TİTCK price list;
  - Q5 public ICD-10 list;
  - Q6 50 patients, 100–150 bills, 8 showcase.
- [x] 2. P0 baseline: commit the engine numbers before and after the overnight fixes (`6b35d543` vs `1c22ee9c`) to `reports/synthetic-data/2026-10-15-engine-baseline.md`, with a JSON summary next to it.
- [x] 3. P0 test pins: classify each test file that pins synthetic IDs, tags, amounts or counts as drop, re-point or keep, with a fixture strategy. A read-only subagent does this; the result goes into a plan appendix.
  - Result: `plans/data/2026-10-15-synthetic-v3-test-pins.md`. P6 has 25 files and about 280 pins. The fixture strategy (cohort registry plus helper) is now in plan D4. It also found that traffic-accident detection reads `scenario_tag`/"kaza" substrings (`traffic_accident_billing.py:84-90,122-129`; `treatment_pricing.py:603-608`).
- [x] 4. P1 chapter table:
  - builder: `scripts/synthetic/reference/build_ek2b_chapters.py`, from the raw EK-2B heading rows;
  - outputs: `data/synthetic/reference/ek2b_chapters.csv` (chapter ranges, reviewable) and a code→chapter parquet;
  - a schema test, plus a check that each chapter's codes are contiguous.
  - Result: 7,175 codes in 43 chapters, each one block in the list. The pattern handles lettered ("9.A") and two-line headings. Every code in force on 2026-02-01, 2026-07-07 and 2026-09-30 has a chapter (10 tests).
- [x] 5. P1 anaesthesia groups. **Changed:** the engine's bands switch on the wrong dates, so the generator takes the bands and their dates from the list instead (`code_sets.yaml` → `surgical_group_bands`).
  - The raw EK-2B markers say the 32,561 table starts 2024-08-07 and the 39,001 table starts 2026-04-16. `_group_table_for_date` switches on 2026-01-01 and 2026-07-07.
  - Pinned by two strict `xfail` tests.
  - Filed as Safa675/Bilun#265. The re-check found a third wrong cutover: the 12001 bands are marked 04/08/2022, but the engine uses them from 2022-09-03.
- [x] 6. P1 code sets: `data/synthetic/reference/code_sets.yaml` (visits by setting, beds, ICU tiers, anaesthesia, companion). A test checks that every code exists in the catalog in force across 2026-02-01..2026-09-30.
  - Result: 15 tests pass. Notes quote the EK-2B explanation column (510120 under 24 h; 510090 bundles ventilation and monitoring; 520021 never with other procedures; 530000 once a day).
- [ ] 7. P1 EK-3 prices. **Changed:** no general dated index yet.
  - The surgical sub-annexes have full lists only up to 2025-12-13; later changes are amendment markers, the mechanism of open #227.
  - Pathways will use a small reviewed material set instead. A test checks each code's price on its service date against every snapshot and marker.
  - The general index waits for #227's fix.
- [x] 8. P1 lab reference table draft: about 40 routine and condition tests, each with EK-2B L-code, unit, sex-specific range and panel. A subagent drafts it and Safa reviews it.
  - Result: `data/synthetic/reference/lab_reference.csv` (45 billed tests, 77 result rows, 16 panels) with notes; it is a draft for Safa's review.
  - `test_reference_lab_table.py` checks codes, names and prices across the window.
  - It also found two engine bugs: the hemogram keyword match catches HbA1c, and wrong codes in `BILUN_TO_SUT_CODE` (PT/INR, aPTT, procalcitonin, protein).
- [x] 9. Price-history cleanup: already done by #248 (0 zero-length rows, 0 duplicate windows, `valid_to` honoured; checked 2026-10-15).
- [x] 10. Downloads (Q4, Q5): find the exact files (URL, name, size, terms) and ask Safa per file. Only then fetch them into a scratch folder and build the ICD-10 table and the drug crosswalk.
  - [x] 10a. Safa approved the 7 files on 2026-10-15. They are fetched into separate scratch folders, and each size matches the HEAD check (9,428,064 bytes in all):
    - SKRS `ICD10Listesi.xlsx` (15,805 codes, Turkish names) and `ICD10MSVSIliskisiListesi.xlsx` (sex flags on 97 cancer codes);
    - WHO `icd102019enMeta.zip`;
    - TİTCK licensed-product lists of 2026-02-06 and 2026-09-25;
    - SKRS e-prescription lists of 2026-02-03 and 2026-09-29.
  - **The September e-prescription list** links to another workbook. Its 3 essential-medicine-list columns are formulas over a March file, so they are not used.
  - **The WHO file** has no sex/age edits. Its licence is CC BY-ND 3.0 IGO, so it serves only as a local cross-check, and nothing derived from it is committed.
  - [x] 10b. ICD-10 table `data/synthetic/reference/icd10_tr.parquet`, built from the SKRS export:
    - code, Turkish name, parent, level, active flag, high-risk-pregnancy flag, created/updated/passive dates;
    - sex from the active SKRS ICD10MSVS rows.
    - Result: 15,804 codes (15,799 active) and 97 sex-flagged (63 F, 34 M).
    - SKRS follows an older WHO edition plus national codes (COVID-19 = U07.3, no K35.8, no X85–Y09). In the story draft, K35.8 is invalid and M48.0, M81.0 and S72.0 have sub-codes (question 12).
  - [x] 10c. Drug crosswalk `data/synthetic/reference/drug_crosswalk.parquet`:
    - one row per curated EK-4A barcode;
    - from TİTCK: product name, active ingredient, ATC code;
    - from SKRS e-prescription: ATC name and active/passive status;
    - both 2026 snapshots;
    - an exact barcode join, with the match coverage reported.
    - Result: 8,078 rows. Coverage: 8,048 matched (99.6%), 7,692 with active ingredient, 8,047 with ATC.
    - The ATC comes from the e-prescription list first, so code and name come from one row; the licence list lags the WHO ATC moves on 182 barcodes.
    - 10 barcodes with ambiguous licence rows stay blank.
    - 12 rows are filled from EK-4A old barcodes.
  - [x] 10d. Builder `scripts/synthetic/reference/build_icd10_and_drugs.py` (Polars over openpyxl, the repo's convention):
    - the download folder is passed as an argument; raw files stay outside the repo;
    - the builder refuses any input whose sha256 differs from `data/synthetic/reference/sources.yaml` (publisher, page, file URL, date, size, sha256, terms).
    - Result: it never loads external links, and two runs give byte-identical output.
    - Terms recorded as found: no data licence, footers "Tüm hakları saklıdır"; WHO is CC BY-ND, so nothing derived from it is committed.
  - [x] 10e. Tests: schema, unique keys, code formats, sex flags matching the source, crosswalk coverage, and well-formed provenance entries. The parse is cross-checked against an independent stdlib reader.
    - Result: `test_reference_icd10_drugs.py` has 24 tests and passes; the rebuild test skips without downloads.
    - With `BILUN_REFERENCE_DOWNLOADS`, all 25 pass under `python -I`, including the byte-identical rebuild.
    - The stdlib parse matches: 8 sheets, 0 differing key cells.
    - 20 deliberate faults were all caught.
    - Notes for review: `data/synthetic/reference/icd10_drugs_notes.md` (6 questions).
  - Still open for Safa:
    - drug prices: the TİTCK price list needs a login;
    - sex/age edits beyond the 97 SKRS codes: none of these files has them, so the pathway table (D2) carries sex and age per pathway.
- [x] 11. Showcase story drafts (8) for Safa's review. Each gives:
  - patient, diagnosis, setting and dates;
  - every line with a code valid on its date;
  - one injected fault and the engine rule that should catch it.

  Draft to the scratchpad first; it goes into `plans/data/` once Safa has reviewed it.
  - Result: `plans/data/2026-10-15-showcase-stories-draft.md`, with proofs in `reports/synthetic-data/2026-10-15-showcase-proofs/`.
  - All 8 faults fire, and the clean versions stay silent for their target rule.
  - Other rules misfire on every clean bill (N1–N13). I verified N1 (SUT §2.2.2.B-1(1)(a),(h),(3)), N2 (`common_billing_errors.py:527`) and N4 (P612320 "Protez ayrıca faturalandırılır").
  - The draft is waiting for Safa's review.
  - **Filed 2026-10-15 (Safa's yes):** #259–#269, 11 issues covering N1–N6, N8, N9 and N11–N13, the traffic-accident "kaza" match and the S1 strategy amount. N10 and the lab-code map are being fixed in separate sessions; N7 stays Safa's call.
  - The re-check for the issues corrected the draft: N9's amount, the cause of S1's 1.231,00, N11's scope, N13's rule count, and the N2, N4 and N1 citations. Those edits are marked "Corrected 2026-10-15".
  - The proof scripts now find the repo from their own path, and a re-run reproduced `results/` byte for byte.
- [x] 12. Verify, in sequence: ruff, the new tests, the full suite, `compile_rules.py --check`, manifest parity. One PR; merge is Safa's call.
  - Result (2026-10-15, at `4465fe3c`), all green:
    - `ruff check src/ scripts/` clean;
    - 8,382 passed and 2 xfailed (the band-date pins);
    - 134 artifacts byte-identical;
    - parity 0 issues.
  - Pushed; PR Safa675/Bilun#258 is open.

### Out of Scope
- The generator rewrite (P3–P4), the loader change (P3) and the regeneration (P7).
- Any download without Safa's yes for that file.
- Fixing #255 or #256.

## Task: Engine fixes wave 1 — false findings on correct bills (#260, #263, #265, #266, #267, #268, #270) (2026-10-15)

### Goal
Seven independent PRs, each making one rule stop misfiring on correct bills. Each keeps the rule's true positives and pins the fix with the issue's acceptance criteria as tests.

### Subtasks
- [x] 1. #270 hemogram: identify CBC lines by code (L107020, L103120) or exact parameter names, not substrings (`claim_lab.py`). `constants.py` stays untouched, because the lab-code session edits it.
  - Result: PR Safa675/Bilun#272 (`fdf2180a`), with 12 new tests.
  - Suite: 8,419 passed, 0 failed. Showcase results byte-identical.
  - The stale note in `lab_reference_notes.md` item 1 gets updated after #271 (the lab-code PR, same file) merges.
- [x] 2. #260 `tablo15_4`: stop reading `is_package_included` as "billed as package". Review `detect_vakabasi_wrong_method`, which shares the helper.
  - Result: PR Safa675/Bilun#277 (`0c5f091b`). #4 emits nothing: the payment-method check already flags the same 26 cohort cases, so a second row would double every fault. #3 is unchanged.
  - Suite: 8,411 passed, 0 failed. Showcase: tablo15_4 rows gone from S1/S5/S8.
  - Open for Safa: Tablo 15 #3/#4 may concern the outpatient visit fee (520030 vs EK-2/A), not EK-2C. That needs the El Kitabı text.
- [x] 3. #263 temporal anomaly:
  - LOS density counts services, not tariff or lab lines.
  - Ghost stay means "bed lines only".
  - No same-date overlap finding without real times.
  - Result: PR Safa675/Bilun#274 (`01e5bb7f`), 9 net new tests. Suite: 8,416 passed, 0 failed.
  - Showcase: the density warning is gone from S2/S4 and the overlap warning from S8. Cohort overlap warnings went from 29 to 0.
- [x] 4. #265 anaesthesia bands: switch on the list's markers (2022-08-04, 2024-08-07, 2026-04-16) and drop the two strict xfails in `test_reference_code_sets.py`.
  - Result: PR Safa675/Bilun#273 (`35df6544`). Bounds were verified against the raw rows; the 2024-01-09 amendment restates the same bounds, so it adds no switch date.
  - Suite: 8,418 passed, 0 failed. Showcase results byte-identical.
- [x] 5. #266 capture gap: a package line counts as submitted for its own code, with or without `P`. Never price a gap from EK-2B when the claim carries that code's package.
  - Result: PR Safa675/Bilun#275 (`1f6bfa74`), 10 new tests. Suite: 8,417 passed, 0 failed. Showcase results byte-identical.
  - Left open: package scope/window coverage (no code-based package contents in the repo).
  - Found: `lab_capture_gap.py` flags in-package labs on package bills (candidate issue).
- [x] 6. #267 §4.2.27.A:
  - Remove vitamin K and FFP names from the 4 rules' drug lists, then recompile.
  - Refresh the `sut_coverage_evidence.json` hash pins.
  - Result: PR Safa675/Bilun#278 (`e4af299f`), 11 new tests. Suite: 8,418 passed, 0 failed.
  - FFP was also removed from a fifth rule (`coumarin_noac_bleed_report_free`): same defect, and it skewed routing.
  - Two coverage-evidence lines changed (1945, 2056). #271 changes line 2020, which is not adjacent.
- [x] 7. #268 traffic accident: match explicit values, never the substring `kaza`. Stop reading `scenario_tag` if a real header field carries the accident type.
  - Result: PR Safa675/Bilun#276 (`c1f5116e`), 61 new tests. Suite: 8,468 passed, 0 failed.
  - `scenario_tag` and `department` are no longer read. Showcase results and the 50-patient demo output are unchanged.
  - Open for Safa: should a traffic accident during work use the iş kazası or the trafik kazası provision?
- [x] 8. Per PR, in sequence:
  - targeted tests, then the full suite;
  - `compile_rules.py --check` and manifest parity;
  - the showcase proofs show the rule's noise gone on the clean bills and the target faults still firing;
  - ruff.
  - Result: every branch has 0 failed. A baseline on clean `main` in a fresh worktree gave 8,407 passed / 1 skipped / 4 xfailed.
  - Full suites ran one at a time behind a shared `flock`.
  - Every target fault still fires, and `results/` was never committed.
- [x] 9. Before each push: CI on `main` is green, and the lab-code session's diff still does not touch the PR's files. One PR per fix; merges are Safa's call.
  - Result: `main` CI is green at 91fb756c.
  - Across the 7 branches and #271, the only shared file is `sut_coverage_evidence.json` (#278 vs #271), on non-adjacent lines.

### Review (2026-10-15)
- **Opened:** 7 PRs, #272–#278, with 116 new tests across them (#270 12, #265 9, #263 9, #266 10, #268 61, #260 4, #267 11).
- **Showcase noise removed:**
  - tablo15_4 on S1/S5/S8;
  - density on S2/S4;
  - overlap on S8.
  - #265, #266, #267, #268 and #270 do not change the committed showcase bills. Their cases are covered by unit tests.
- **Questions for Safa:**
  - the meaning of Tablo 15 #3/#4 (outpatient visit fee?);
  - the provision for a traffic accident during work;
  - whether `lab_capture_gap.py` (in-package labs flagged as gaps) should become an issue.
- **After merge:**
  - update `lab_reference_notes.md` item 1 (after #271);
  - remove the agent worktrees;
  - wave 2 (#261 + #264 + #269, #262) and #259, after Safa's answer.

### Out of Scope
- #259 (waits for Safa's reading of the package window), #261/#264/#269 and #262 (wave 2), #255, #256, #226, #227.
- `BILUN_TO_SUT_CODE` (the lab-code session).
- Staging (waits for Safa's yes).
- Showcase `results/` files (a historical record at 1c22ee9c; not rewritten).

## Task: Fix companion-bed (510121) ICU suppression, admission-date pricing, and billed subtraction (Safa675/Bilun#236)

### Goal
`detect_refakatci_opportunities` (`src/bilun/domain/prose_rules/refakatci.py`) suppresses companion-bed opportunities on all ICU indicator codes (`510090` and `P552001`–`P552008` / `552001`–`552008`), prices `510121` at the EK-2B rate in force on the claim's admission date instead of the undated 2026 rate, subtracts any already-billed `510121` amount on the claim into `recoverable_uplift_try`, and `RefakatciReview.confirmed_refakat_try` sums `recoverable_uplift_try`.

### Subtasks
- [x] 1. Write failing unit tests in `tests/unit/domain/prose_rules/test_refakatci.py` covering:
  - ICU suppression when a claim carries `P552001`–`P552008` (or bare `552001`–`552008`) without `510090`;
  - historical admission-date pricing (`2023-06-15` → `27.44 TL/day`, `2024-07-01` → `61.75 TL/day`, `2026-07-10` → `74.10 TL/day`);
  - subtracting already-billed `510121` lines (`actual_billed_try` and `recoverable_uplift_try = max(0.0, expected_try - actual_billed_try)`), including full billing (`recoverable_uplift_try == 0.0` and `RefakatciReview.confirmed_refakat_try == 0.0`).
- [x] 2. Update `src/bilun/domain/prose_rules/refakatci.py`:
  - Replace `_ICU_PROCEDURE_CODES = frozenset({"510090", "P55200x"})` with `_ICU_PROCEDURE_CODES` matching `510090` and `("552001", "552002", "552003", "552006", "552007", "552008")` (with or without leading `P`/`p`, case-insensitive, matching `icu_puani.py` and `yatak_icu_overlap.py`);
  - Resolve `puan` and `daily_rate` per claim as of `claim.admission_date` via `get_ek2b_price_for_date("510121", claim.admission_date, ...)` (falling back to the undated catalog only when `admission_date` predates the catalog history);
  - Sum billed `510121` lines on the claim as `actual_billed_try` and set `recoverable_uplift_try = _money(max(0.0, expected - actual_billed_try))` (and `0.0` on suppressed rows).
- [x] 3. Update `RefakatciReview.confirmed_refakat_try` in `src/bilun/domain/billing/types.py` to sum `recoverable_uplift_try` when present (without truthiness fallback when `0.0`), and add `"actual_billed_try": true` to `refakatci.opportunities` in `src/bilun/api/public_contracts.json`.
- [x] 4. Run `ruff check`, the new and existing unit tests (`test_refakatci.py`, `test_elkitabi_tablo23.py`, `test_claim_integration.py`, `test_sgk_uplift_synthetic_demos.py`, `test_orchestrator_grand_total.py`, `test_orchestrator_claim_cohort_flow.py`, `test_focused_legacy_materializer.py`), and `compile_rules.py --check` / `audit_manifest_parity.py --drug-only`; confirm zero unintended tracked file diffs.

### Out of Scope
Changing the default policy that unbilled non-ICU inpatient stays emit a confirmed uplift (`included_in_sgk_total=True`, confirmed with Safa), fixing the `valid_to` price-history loader bug (#241), or changing other prose/billing rules (#230–#234, #237–#242).

### Review (2026-10-14)
- Confirmed with Safa before coding: keep unbilled non-ICU inpatient stays in confirmed uplift (`included_in_sgk_total=True`) while fixing `P552001`–`P552008` ICU suppression, admission-date EK-2B pricing, and subtracting already-billed `510121`.
- Cohort effect on the 50 synthetic patients: `total_refakatci` drops from `34,308.30 TL` (priced at 2026's `74.10 TL/day`) to `17,709.88 TL` (priced at each claim's 2023–2024 admission-date EK-2B rate) across 22 patients.
- Verification: `ruff check` clean; 18 unit tests in `test_refakatci.py` (including RED→GREEN tests for `P552001`–`P552008`, 2023/2024/2026 admission-date rates, partial/full `510121` billing subtraction, and public response projection) + 40 billing/orchestrator integration tests pass; `compile_rules.py --check` (134 byte-identical) and `audit_manifest_parity.py --drug-only` (23 manifests, 0 issues) pass.

## Task: Fix price history valid_to, MULGA_ duplicates, and date-aware pricing in 5 rules (Safa675/Bilun#241)

### Goal
Curated EK-2B and EK-2C history tables contain zero duplicate `(code, valid_from)` or `valid_to < valid_from` rows and cap `valid_to` when a code disappears in the next snapshot; runtime readers enforce `valid_to`; and the 5 inpatient/bed/ICU/anaesthesia rules look up catalog prices as of the claim/procedure date.

### Subtasks
- [x] 1. Update `scripts/sut/build_curated_catalogs.py` (`_build_history`) to prefer non-MÜLGA raw parquets when an `effective_date` has both current and `MULGA_` files, and update `scripts/sut/_common.py` (`_add_validity_ranges`) to deduplicate `(key_col, effective_date_parsed)` (`keep="last"`) and cap `valid_to` at `next_global_eff - 1 day` when a code disappears in the next snapshot.
- [x] 2. Rebuild `data/gazette/curated/ek2b_catalog_history.parquet` and `data/gazette/curated/ek2c_catalog_history.parquet` and verify zero rows have `valid_to < valid_from` or duplicate `(code, valid_from)`, and `804460` expires before `2024-08-01`.
- [x] 3. Enforce `valid_to` in `src/bilun/domain/loaders/gazette.py`, `src/bilun/domain/pricing/temporal.py`, and `src/bilun/domain/prose_rules/catalog_membership.py`.
- [x] 4. Pass claim/procedure dates into catalog lookups in `yatak_puani.py`, `yenidogan_yatak.py`, `anestezi_puani.py`, `icu_puani.py`, and `refakatci.py` so historical claims use historical tariffs.
- [x] 5. Add unit tests for `valid_to` expiration (`get_ek2b_price_for_date("804460", "2024-08-01") is None`), history invariant checks, and historical tariff resolution in the 5 rules; run unit tests and `ruff`; commit, check `main` CI, push, open PR for `#241`, and return to `main`.

### Out of Scope
Re-generating the synthetic demo cohort parquets or changing EK-4A drug catalogs.

### Review
- Rebuilt `ek2b_catalog_history.parquet` (`69,546` rows, down from `76,673`) and `ek2c_catalog_history.parquet` (`24,063` rows, down from `26,489`) with zero `valid_to < valid_from` rows and zero duplicate `(code, valid_from)` rows.
- Enforced `valid_to` in `gazette.py`, `temporal.py`, and `catalog_membership.py`; `804460` expires on `2021-05-31` and returns `None` on `2024-08-01`.
- Wired claim/procedure dates into `yatak_puani.py`, `yenidogan_yatak.py`, `anestezi_puani.py`, `icu_puani.py`, and `refakatci.py`.

## Task: Fix temporal-anomaly surgical code prefix filter (Safa675/Bilun#237)

### Goal
`detect_procedure_time_overlap` (`src/bilun/domain/prose_rules/temporal_anomaly.py`) classifies EK-2B/EK-2C surgical procedure codes (`60xxxx`–`62xxxx` and `P60xxxx`–`P62xxxx`) as surgical when `procedure_category` lacks a surgical keyword, and never classifies `50xxxx`/`51xxxx` bed/stay tariffs (`510010`–`510121`) as surgery.

### Subtasks
- [x] 1. Write failing unit tests in `tests/unit/domain/prose_rules/test_temporal_anomaly.py` covering:
  - two same-date, same-specialty `60xxxx`–`62xxxx` (and `P60xxxx`–`P62xxxx`) lines with generic `procedure_category="islem"` / `"paket"` flagging `procedure_time_overlap`;
  - two same-date, same-specialty `51xxxx` bed/stay lines (`510010`, `510121`) not flagging `procedure_time_overlap` even when `procedure_category` is `"islem"` or `"cerrahi"`.
- [x] 2. Update `src/bilun/domain/prose_rules/temporal_anomaly.py`:
  - Change `_SURGICAL_CODE_PREFIXES` from `("50", "51")` to `("60", "61", "62")` and exclude `51xxxx` bed/stay codes (`_BED_CODE_PREFIXES = ("51",)`) in `_is_surgical`, normalizing optional leading `P`/`p` and punctuation.
- [x] 3. Run `ruff check`, `pytest` on `test_temporal_anomaly.py`, `compile_rules.py --check`, and `audit_manifest_parity.py --drug-only`.

### Out of Scope
Populating `procedure_specialty_code` in the synthetic generator (tracked under the care-pathway generator plan) or changing `detect_los_procedure_density_anomaly`.

### Review (2026-10-14)
- `_SURGICAL_CODE_PREFIXES` updated from `("50", "51")` to `("60", "61", "62")` (matching all 2,407 EK-2B surgical procedures in `600000`–`629999` and `P600000`–`P629999` in EK-2C), and `51xxxx` bed/stay tariffs (`510010`–`510121`) are excluded unconditionally in `_is_surgical`.
- Verification: `ruff check` clean; 16/16 unit tests in `test_temporal_anomaly.py` pass (RED→GREEN on 8 new cases); `compile_rules.py --check` (134 byte-identical) and `audit_manifest_parity.py --drug-only` (23 manifests, 0 issues) pass.

## Task: ILAY Phase 1 — take the real ILAY-derived files out of the repo (2026-10-15)

### Goal
`main` tracks no file under `data/synthetic/sut/claims/ilay_validation/` or `data/gazette/prose_rules/golden/ilay/`. One local copy is kept outside every repo. The specialty regression test runs on synthetic cases instead of real rows. A CI test fails if either folder comes back. This is Phase 1 of `plans/security/2026-10-14-remove-ilay-real-data-plan.md`, approved by Safa on 2026-10-15 with the synthetic-test adjustment.

### Subtasks
- [x] 1. File the issue for the specialty-name matching defects ("Kalp ve Damar Cerrahisi (KVC)"; Turkish capitals such as "İÇ HASTALIKLARI"), using the evidence from a run on `main` @ `1c22ee9c`. → Safa675/Bilun#256: 29 of the 102 specialty tokens fail in Turkish capitals, and 266 of the 404 specialty-restricted rules list at least one of them.
- [x] 2. Copy both folders to `~/bilun-local/ilay-validation/` (not a git repo, mode 700). Check the copy by checksum without printing any content.
- [x] 3. Fast-forward local `main` and create a branch from it in this checkout. Do not add a worktree, which would be one more copy of the files.
- [x] 4. `git rm -r` both folders (20 files). Add `.gitignore` lines for them.
- [x] 5. Harness (`scripts/validation/validate_drug_rules.py`, `validate_specialty_rules.py`, `build_golden_dataset.py`):
  - write and read under `$BILUN_ILAY_VALIDATION_DIR` (default `~/bilun-local/ilay-validation`);
  - refuse any path inside the repo.
- [x] 6. Replace `tests/unit/domain/prose_rules/test_specialty_real_data.py` with `test_specialty_scope_cases.py`:
  - synthetic cases for the same three rules (rule ids are the only thing read from the old files);
  - mismatch and match cases;
  - the two known matching defects as strict `xfail` cases linked to the new issue.
- [x] 7. Add `tests/unit/test_no_real_patient_data_paths.py`:
  - a pure check over tracked paths;
  - a mutation test that feeds it the forbidden paths;
  - the check run against `git ls-files`, with a filesystem fallback when the checkout has no `.git`.
- [x] 8. Update the references:
  - `scripts/validation/README.md`: output paths, and make the line-81 promise true;
  - `plans/backend/specialty-scope-validation-plan.md:157,180-181,194,269,287`: add a note;
  - `plans/update/2026-08-07-track-e-phase0-audit.md:34`: the wrong "synthetic" label;
  - tick Phase 1 in the ILAY plan.
- [x] 9. Verify (full suite run alone: 8,354 passed, 2 xfailed; an earlier run done in parallel with the artifact checks gave 4 false failures, which passed on `main` and alone; lesson added):
  - `git ls-files | grep -c -E "ilay_validation|golden/ilay"` is 0;
  - ruff on `src/` and `scripts/`;
  - the new and changed tests;
  - the full pytest suite;
  - `compile_rules.py --check` and `audit_manifest_parity.py --drug-only` (the other CI steps).
- [x] 10. Check CI on `main` (green on `1c22ee9c`), make one commit, push and open the PR. Merge is Safa's call. Return the checkout to `main`.

### Out of Scope
- Phases 2–5 of the ILAY plan: staging, live, history rewrite and laptop copies.
- Fixing the matching defects (only filed and pinned as `xfail`).
- The hash manifest entries in `data/gazette/source_authority/corpus_consumer_review_pr128.json`, left as they are on purpose (hashes only, no code reads them).

## Task: Plans and issues from the 2026-10-14 synthetic data audit

### Goal
Two reviewed plans exist in `plans/` (removing the real ILAY data; redesigning the synthetic generator), GitHub issues track the engine bugs from `reports/synthetic-data/2026-10-14-demo-cohort-audit.md` each with its evidence, and the audit, its scripts, the plans and these task files are on `main` through one docs PR.

### Subtasks
- [x] 1. ILAY footprint, by file name only (the data is never opened): tracked files, the commits and branches that contain them, and every code, test, doc, CI and deploy reference. Read-only listing of whether the staging (`/opt/bilun-staging`) and live release trees on the VPS hold copies.
  - Result: 5 files plus a second set in `golden/ilay` (15 JSON files).
  - Copies: 2 staging releases, the staging bare repository and its bundle, 2 live trees (pinned in live's own release records), and 88 laptop folders.
- [x] 2. Write `plans/security/2026-10-14-remove-ilay-real-data-plan.md` (draft done; review is subtask 7). It covers removal from the repo, staging cleanup through the wrapper, the live tree as a decision for Safa, the optional history purge with its costs, and verification steps.
- [x] 3. Generator research: reusable catalog data (EK-2B chapters and surgical groups, anaesthesia groups, bed and ICU codes, EK-3 ↔ procedure links, EK-4A groups, a drug price source), the tests that pin synthetic patient IDs, and the consumers of the schema.
  - Key results: there is no ICU-tier detector; the loader enforces the circular labels; the engine reads demo vignette prices and `scenario_tag`; about 42 test files hold about 375 pins.
- [x] 4. Write `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`. It covers Tier A first, care pathways, prices in force on the service date, labels from injected causes, plausibility validators in CI, re-pinning tests, and open questions.
- [x] 5. Confirm the E1–E5 mechanisms with file:line references, check for duplicate issues, and draft the five issue bodies.
  - No duplicates were found.
  - I re-checked every citation. E1 gained the EK-2B group table (raw 2026-07-07 rows 124–130); E5 turned out to be wrong on this cohort.
- [x] 6. Open the five issues in Safa675/Bilun and record their links in the audit report: Safa675/Bilun#230, #231, #232, #233 and #234, all labelled `bug`.
- [x] 7. Have a subagent review both plans independently against the audit and the code, then fix what it finds.
  - Verdict: the ILAY plan was "not ready" and the generator plan "ready after fixes".
  - Both plans are rewritten (rev 2). I re-checked every reviewer claim I used, against the code, the git metadata or the VPS, read-only.

- [x] 8. Safa approved the second batch (2026-10-14): the docs PR and the further engine issues, but not ILAY Phase 1. Confirmed and reshaped the seven candidates (companion bed and ICU, temporal-anomaly 50/51, duplicate material code, demo-only inputs, loader answer rows, price-history `valid_to`, ICU-tier detector), checked duplicates across all open/closed issues and PRs, and drafted the seven bodies.
- [x] 9. Re-checked each citation in the drafts against the repository code and data, then filed them in Safa675/Bilun: #236, #237, #238, #239, #240, #241 (all `bug`) and #242 (`enhancement`).
- [x] 10. Replaced the "not filed yet" lists in the generator plan (D6) and in the audit report with the new issue numbers (#236–#242).
- [x] 11. Docs PR from a branch of `main` (no extra worktree, so no further copy of the ILAY files): KVKK and secret scan of the files first (0 patient IDs, 0 token-like strings); CI of `main` green on `6b35d543` (checked before the push, rule 10); PR #235 opened and updated with #236–#242. Merge is Safa's call.
- [x] 12. Return the checkout to `main` (rule 11.5); leave no extra branch or worktree. (The PR branch stays on origin only.)

### Out of Scope
Executing either plan, fixing the engine bugs, deleting any file (locally, on the VPS or in git history), starting ILAY Phase 1 (waiting for Safa's answer), and merging the PR (Safa's call).

### Review
**Delivered so far**
- **Issues:** Safa675/Bilun#230–#234 and #236–#242 (12 total: 11 `bug`, 1 `enhancement`).
- **Plans:** `plans/security/2026-10-14-remove-ilay-real-data-plan.md` and `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`, both rev 2.
- **Audit report** updated with all 12 issue links (#230–#234, #236–#242).
- **Audit scripts** preserved in `reports/synthetic-data/2026-10-14-audit-scripts/`.

**What the review changed**
- **ILAY plan.**
  - Added the `golden/ilay` set and the live releases' baseline copy.
  - Stopped any hand deletion on live.
  - Gated the history rewrite behind the "No force-push" exception, a backup and green CI.
  - Added three full bundles and two more real-data files in history (`reports/finans_flagged.xlsx`, the interviews docx).
- **Generator plan.**
  - Moved the fault registry before the showcase bills.
  - Tied the anaesthesia source to #230.
  - Fixed the EK-3 date claim, the drug price facts and the reconcile reuse.

**KVKK side effect**
- Two subagent logs on this laptop contain pseudonymized ILAY patient IDs: `~/.claude/projects/-home-safa-Documents-Bilun/a9cf6beb-…/subagents/agent-a225743e213a4fbab.jsonl` (6 distinct IDs) and `agent-a93e236386ee82143.jsonl` (11).
- Reported to Safa. Deleting them is his call.

## Task: Evaluate material pre-check and §3.1/§3.3 prose rules per material line (#238)

### Goal
`precheck_materials_from_claims()`, `check_material_bundling_prose()`, and `check_specialty_materials_prose()` evaluate pre-auth, bundling, and §3.1/§3.3 prose rules per `material_line_id` (preserving `material_line_id` and `claim_id` on every finding) while keeping cross-line `material_code` grouping exclusively for cross-claim MIAT interval checks.

### Subtasks
- [x] 1. Write RED unit tests in `tests/unit/domain/billing/test_claim_materials_precheck.py`, `tests/unit/domain/prose_rules/test_material_bundling.py`, and `tests/unit/domain/prose_rules/test_specialty_materials.py` covering duplicate `material_code` lines (including `F-SENTETIK-HASTA-0038-053` `GHC1220` where `MLZ-…-003` has `requires_pre_auth=True` and `MLZ-…-004` has `requires_pre_auth=False`, plus `material_line_id` and `claim_id` preservation across multi-claim contexts).
- [x] 2. Update `src/bilun/domain/billing/claim_materials.py`, `src/bilun/domain/prose_rules/material_bundling.py`, `src/bilun/domain/prose_rules/specialty_materials.py`, and `src/bilun/api/public_contracts.json` so pre-auth, bundling, and prose rules evaluate every material line and attach `material_line_id` and `claim_id`.
- [x] 3. Run unit/contract test suites (`5,359 passed` across billing/prose/materials + `608 passed` in API tests) and `ruff check` to verify GREEN and zero regressions, then return checkout to `main` (Rule 11.5).

### Out of Scope
Changing MIAT catalog rules, modifying synthetic cohort parquet files, or changing non-material prose evaluators.

### Review
- Scoped `latest_line_by_code` in `claim_materials.precheck_materials_from_claims` strictly to the cross-claim MIAT check (`if code in miat_catalog and latest_line_by_code.get(code_key) is line:`), so `pre_auth_required` and `bundled_separate_billing` evaluate every material line.
- Updated `check_material_bundling_prose` and `check_specialty_materials_prose` to key `seen` by `(material_line_id or f"idx:{idx}", rule_id)` instead of `(code or name, rule_id)`, and forwarded `material_line_id` and `claim_id` from `PatientClaimContext.material_lines` through `_violation_from_rule` and `_enrich_material_precheck_row`.
- Added `material_line_id` to `MaterialPreCheck` list schemas in `src/bilun/api/public_contracts.json`.
- Verified `F-SENTETIK-HASTA-0038-053` emits `pre_auth_required` for `MLZ-F-SENTETIK-HASTA-0038-053-003` (`GHC1220`, `requires_pre_auth=True`) and prose findings for both `MLZ-…-003` and `MLZ-…-004`.

## Task: Stop the runbook from quoting live PIDs that change on every VPS reboot

### Goal
`docs/operations/AI-RUNBOOK.md` points at the `LIVE_PIDS` pin in `staging-update.sh` instead of quoting PIDs, and says what to do when the wrapper stops after a reboot.

### Subtasks
- [x] 1. Find every place the repo quotes the live PIDs: `git grep` for 914/915, 898/899, 911/912 and "live PIDs" finds only `docs/operations/AI-RUNBOOK.md:63` ("live PIDs **914/915**"); no test or script pins that text.
- [x] 2. Replace the numbers in that sentence with "the live pair's MainPIDs and start times against the `LIVE_PIDS` pin in the script (a VPS reboot changes them; see below)".
- [x] 3. Add one short paragraph after "Interrupted transfer": the wrapper stops before any VPS write (`update_exit: not_started`, "Canlı backend beklenen PID … değil"); read the live pair first (read-only, the `systemctl show` and `/proc/<pid>/cwd` check); only if both units are in the frozen `5c89ed53` bundle, re-pin `LIVE_PIDS` in the operator's script (outside this repo) and rerun; never loosen the check. No PID numbers in the paragraph.
- [x] 4. `git diff` shows only that sentence and the new paragraph; `git grep -E "914/915|898/899|911/912"` finds nothing; `tests/unit/scripts/test_sgk_watch.py` (it names this file) passes in the CI image.
- [x] 5. One commit; CI status of `main` checked before the push (rule 10); PR opened; checks green. (PR #229, merged as `6b35d543`.)
- [x] 6. Merge is Safa's call; after the merge remove this worktree and branch and leave the main checkout on `main`. (Merged by Safa; `git worktree list` shows only the main checkout and `git branch -a` only `main`, checked 2026-10-14.)

### Out of Scope
Changing the wrapper (it lives in `~/work/bilun-deploy-plan/staging-ops`, outside the repo), `RELEASE-LANES.md`, any deploy behavior, a script that reads the live PIDs.

## Task: Make expected_rule_outputs.parquet and expected_*_payable_try optional in real_claims mode (Safa675/Bilun#240)

### Goal
`load_sut_claim_dataset(mode="real_claims")` and `read_claim_tables(mode="real_claims")` succeed when `expected_rule_outputs.parquet` is absent or empty and `expected_*_payable_try` / `expected_total_billed_try` / `discount_tier_expected` / `unit_price_try` / `scenario_tag` columns are null or absent, while present `expected_rule_outputs` rows in `synthetic_demo` and `real_claims` still validate their linkage and payable reconciliation.

### Subtasks
- [x] 1. Write failing RED unit tests in `tests/unit/domain/claims/test_loader.py` covering:
  - `load_sut_claim_dataset(claims_dir, mode="real_claims")` when `expected_rule_outputs.parquet` is absent and `expected_total_billed_try`, `expected_total_payable_try`, `expected_payable_try`, `discount_tier_expected`, `unit_price_try`, and `scenario_tag` columns are absent or null;
  - `load_sut_claim_dataset(claims_dir, mode="real_claims")` when `expected_rule_outputs.parquet` exists with 0 rows;
  - `SUTClaimDataset.from_rows` validating present `expected_rule_outputs` linkage and payable reconciliation without requiring answer rows for clean baseline claims/lines.
- [x] 2. Update `src/bilun/domain/claims/parquet_reader.py` so `read_claim_tables` resolves `mode` via `resolve_sut_data_source(..., require_clean_dir=False)` and, in `real_claims` mode, treats `expected_rule_outputs.parquet` as optional (`optional=True`, `reject_if_empty=False`, `scenario_tag` optional) and `expected_total_billed_try` on `claim_headers.parquet` as optional.
- [x] 3. Update `src/bilun/domain/claims/parsing/row_parsers.py`, `src/bilun/domain/claims/dataset_builder.py`, `src/bilun/domain/claims/totals.py`, and `src/bilun/domain/claims/validation/expected_outputs.py`:
  - Default missing `expected_payable_try` and `unit_price_try` on procedure/material/drug lines to `billed_amount_try` and missing `discount_tier_expected` on drug lines to `0.00` (while still rejecting malformed values);
  - Backfill missing `expected_total_billed_try` / `expected_total_payable_try` on `ClaimHeader` from `claim_totals` while reconciling any explicitly supplied header totals;
  - Validate linkage and payable reconciliation for all present `ExpectedRuleOutput` rows without requiring exhaustive claim/line answer rows for clean baseline claims/lines;
  - Update `src/bilun/domain/claims/README.md` to document the `real_claims` optionality contract.
- [x] 4. Run `ruff check`, the claims/deploy/synthetic/billing unit tests, update `tasks/todo.md`, commit, push `claude/fix-claims-loader-real-mode-240`, open the PR, and return to `main`.

### Out of Scope
Changing `REQUIRED_CLAIM_TABLES` / `SUT_CLAIM_FILENAMES` roster constants used by the paused strict paired-release lane, or modifying synthetic data generator scripts (`#239`, `#241`, `#242`).

### Review (2026-10-14)
- Kept `REQUIRED_CLAIM_TABLES` and `OPTIONAL_CLAIM_TABLES` intact in `src/bilun/domain/claims/schema.py` so the strict-lane source-roster contract (`tests/unit/deploy/test_generate_candidate_source_roster.py`) and `build_synthetic_claim_validation_columns()` remain untouched.
- In `src/bilun/domain/claims/parquet_reader.py`, `_effective_spec_for_mode` relaxes `EXPECTED_RULE_OUTPUTS` (`optional=True`, `reject_if_empty=False`, `scenario_tag` optional) and `CLAIM_HEADERS` (`expected_total_billed_try` optional) when `config.mode == "real_claims"`.
- In `src/bilun/domain/claims/parsing/row_parsers.py` and `src/bilun/domain/claims/dataset_builder.py`, missing `expected_payable_try` / `unit_price_try` default to `billed_amount_try`, missing `discount_tier_expected` defaults to `0.00`, and missing header `expected_total_billed_try` / `expected_total_payable_try` are backfilled from `claim_totals` while explicitly supplied values continue to be reconciled.
- In `src/bilun/domain/claims/validation/expected_outputs.py`, all present `ExpectedRuleOutput` rows still validate their claim/patient/line linkage and `expected_payable_try` reconciliation without requiring exhaustive answer rows for clean baseline claims/lines.
- Verification: `ruff check` clean; 318 unit tests across `tests/unit/domain/claims/`, `tests/unit/deploy/`, and `tests/unit/synthetic/` (including 3 RED→GREEN tests in `test_loader.py`) pass.


## Task: Complete the ingestion of the 2026-10-02 SUT package (Safa675/Bilun#217)

### Goal
`data/gazette/ingest_state.json` says `completion_scope: complete` with `last_ingested_date: 2026-10-02` after every current workbook of the official package is converted and validated, while the prose corpus, the EK-4A snapshot catalog and the clause diff stay byte-identical and the review delta is committed.

### Subtasks
Setup (read-only)
- [x] 0.1 `git fetch origin`; `.worktrees/sut-package-2026-10-02` is at the `origin/main` tip (b003ae12 or newer) and `git status` is clean. Done when both are shown.
- [x] 0.2 Choose the environment and write the choice in Review: the CI image `bilun-laptop-ci:20261008-runtime-complete` if it carries `requirements-ci.lock` (pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1), else `.venv` (pandas 3.0.3, polars 1.41.2, pyarrow 24.0.0) with the byte-identity checks below as the guard.
- [x] 0.3 Record the sha256 of the files that must not change (scratchpad): `data/gazette/sut_clauses.parquet` (40b2b7eb…), `data/gazette/curated/ek4a_drugs.parquet` (6ed75694…), `data/gazette/deltas/2026-10-02_clause_diff.json` (faa8909f…), `data/gazette/curated/ek4a_history.parquet`, `data/gazette/curated/ek4a_windows.parquet`, `data/gazette/ek4a_announcements.json`, `data/gazette/sut_coverage_evidence.json`.

Fetch (one 33 MB download from sgk.gov.tr)
- [x] 1.1 `python scripts/sut/sut_fetch.py "https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06" 2026-10-02` (it downloads the same file again; the script cannot read a local ZIP). Done when: exit 0; the inventory's `zip_sha256` is `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61`; 349 files, 318 workbooks (49 current, 269 MÜLGA); the 3 files already committed show no change in `git status`.

Convert and curate
- [x] 2.1 Copy `data/gazette/sut_clauses.parquet` to the scratchpad as the old side of the clause diff.
- [x] 2.2 `python scripts/sut/convert_xlsx_to_parquet.py --input-dir <input_dir> --defer-state` exits 0 and converts the 49 current workbooks (the 269 MÜLGA files are skipped by design). Verified with Polars, no row loops, per rewritten raw partition ignoring `__source_file` and `__ingested_at`: values change only in EK-1A (+N11 on one row), EK-2B (+2 rows), EK-2C (+3 net rows) and EK-3O (one row's text); every other partition differs in provenance only.
- [x] 2.3 `python scripts/sut/build_curated_catalogs.py --overwrite` exits 1 from exactly one spec, the EK-4A snapshot ("marker-dated rows", by design: `reports/sut-ingest/2026-10-10-ek4a-service-date.md`); no other spec fails; `ek4a_drugs.parquet` keeps its hash; the other curated changes derive from EK-1A, EK-2B, EK-2C or EK-3O only.
- [x] 2.4 `python scripts/sut/sut_ingest_state.py --input-dir <input_dir> --inventory <input_dir>/.sut_package_inventory.json --prepare-corpus` exits 0 and `sut_clauses.parquet` keeps its hash. If it changed: stop, restore the file and report (a corpus change forces coverage closure, `tasks/lessons.md:5-9`).

Reports
- [x] 3.1 `python scripts/sut/sut_clause_diff.py <old corpus> data/gazette/sut_clauses.parquet --new-date 2026-10-02 --legacy-input-fingerprints data/gazette/deltas/2026-10-02_clause_diff_inputs.json` exits 0 and `2026-10-02_clause_diff.json` stays byte-identical.
- [x] 3.2 `python scripts/sut/sut_delta.py 2026-08-29 2026-10-02` creates `data/gazette/deltas/2026-10-02_delta.json` (no `2026-10-02_delta_inputs.json` receipt exists, so no legacy argument). Done when its annexes and row counts agree with the independent cell diff under Evidence; a disagreement is investigated first, not waved through.

Completion
- [x] 4.1 Write `reports/sut-ingest/2026-10-13-package-2026-10-02-completion.md`: the delta table, the hashes, the commands, and the EK-4A component receipt copied verbatim. Completion removes `component_receipts` (`scripts/sut/sut_ingest_state.py:147-149`) and the service-date report does not hold those hashes.
- [x] 4.2 `python scripts/sut/sut_ingest_state.py --input-dir <input_dir> --inventory <input_dir>/.sut_package_inventory.json` exits 0. Done when `ingest_state.json` shows `completion_scope: complete`, `last_ingested_date: 2026-10-02`, `completed_package.zip_sha256` `03bf37df…`, no `pending_full_package_*`, no `component_receipts`, and `manifest_row_count` / `manifest_sha256` equal `version_manifest.parquet`.

Follow-through (small, separable)
- [x] 5.1 `tests/unit/scripts/test_sgk_watch.py` first (RED), then `scripts/sut/sgk_watch.py:48-57`: the `sut_package` and `drug_list` action texts stop pointing at the disabled SUT Monitor workflow and at the receipt that completion deletes; they point at the local steps and the service-date report.
- [x] 5.2 `docs/operations/AI-RUNBOOK.md`: a short "Local SUT package ingest" section with steps 1.1 to 4.2, because the hosted workflow cannot run.

Verify
- [x] 6.1 The CI commands of `.github/workflows/ci.yml:56-68` (ruff, `python -m pytest -q -n auto`, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`), reading every "Failures: N" and FAIL line (`tasks/lessons.md:270-280`); the SUT and EK-4A tests first.
- [x] 6.2 `git status` after pytest lists only intended paths (pytest mutates the tree, `tasks/lessons.md:109-119`); `git diff --check` is clean; `sut_coverage_evidence.json` and `src/bilun/domain/constants.py` are untouched.
- [x] 6.3 `python scripts/sut/sgk_watch.py --dry-run` (read-only listing request) reports nothing new for 2026-10-02.
- [x] 6.4 A second agent reviews the diff; real findings are fixed, skipped ones are written down with the reason.

Hand-off (nothing is pushed)
- [x] 7.1 Five local commits: (A) raw package files plus inventory, (B) generated data plus the completion report, (C) sgk_watch, its test, the runbook and one stale sentence, (D) the changelog entry, (E) plan, review and lesson. Generated data stays in its own commit (`tasks/lessons.md:429-433`).
- [ ] 7.2 Stop and report. Push, draft PR, CI check and PR review check (AGENTS.md rules 10 and 11) only on Safa's go.
- [ ] 7.3 After the merge, on Safa's go: close #217 with the PR link, remove this worktree and branch; the main checkout stays on `main`.

If any gate above fails, stop and report. No gate is loosened and no pinned hash is refreshed to make a step pass.

### Out of Scope
Rule and product follow-ups that the new data enables: procedures 608310 and 609541 (rule coverage, the "not billed together with 604070/604071/608880" exclusions), EK-1A code N11 in co-payment logic, EK-4G Satralizumab (a `.doc`; no converter exists), the retroactive 2026-09-05 marker on the bone-marrow package row. Promoting the 2026-10-02 EK-4A list into `ek4a_drugs.parquet` (regenerates the synthetic demo cohort). Fixing or re-enabling the SUT Monitor workflow and the hosted-runner refusal; letting `sut_fetch.py` read a local ZIP; the stale comment at `sut-monitor.yml:93`. Any change to the prose corpus, rules, coverage-evidence hashes or the frontend.

### Evidence (2026-10-13)
- Package: the official ZIP (32,973,194 bytes) hashes to the pinned `03bf37df…`; 349 files, 318 workbooks of which 269 are MÜLGA (repealed lists the converter skips) and 49 are current; no current workbook name carries a "Yür." date after 2026-10-13, so the future-date gate cannot trip.
- State today: `completion_scope: partial`, `pending_full_package_date: 2026-10-02`; prose corpus (8,413 rows) and EK-4A are already in (`data/gazette/ingest_state.json`).
- Independent cell diff of the package against the 2026-08-29 one (341 files identical, 6 changed):
  - EK-1A: the row "Kronik Tübülo-İnterstisyel Nefrit" gains code N11.
  - EK-2B: +608310 (Bronkoskopi, 1,073.67; amended by RG-02/10/2026-33388 art. 3-a, effective 2026-10-10) and +609541 (Özofagus atrezi primer onarımı, 25,278.02; art. 3-b, effective 2026-10-10).
  - EK-2C: +P608310 (group D, 5,456.7) and +P609541 (group A3, 215,007.17); the "Kemik İliği Nakilleri" row gains a second marker (art. 4-b, effective 2026-09-05).
  - EK-3O: HO1000 FOTOFEREZ SETİ gains only the marker "(Ek: RG-02/10/2026-33388/5 md. Yürürlük: 08/10/2026)"; its values are unchanged.
  - EK-4A: already handled (#222). EK-4G (.doc): "92. Satralizumab" added (art. 7, effective 2026-10-10).
- The hosted workflow cannot do this: `SUT Monitor` is `disabled_manually`, its builder step exits 1 on the October EK-4A list, and `ubuntu-latest` jobs are refused for this account (`reports/sut-ingest/2026-10-10-ek4a-service-date.md:75-81`).
- Gates that completion enforces: inventory bytes and workbook set, one manifest row per sheet, raw parquet equals a fresh read, corpus equals the DOCX extraction (`scripts/sut/sut_ingest_state.py:34-158`).
- Size: earlier full ingests were one ~600-file PR (#84); this one is about 350 raw-data paths plus ~48 rewritten raw parquets, most of them provenance-only.

### Decisions (before step 1.1)
1. Keep `data/gazette/curated/ek4a_drugs.parquet` as the 2026-05-23 snapshot. Recommended: yes. No runtime module reads it (only the synthetic generator), and promoting it changes the demo cohort.
2. Approve this plan as written.

### Review (2026-10-13)
Both decisions were approved as recommended. Steps 1.1 to 4.2 and the CI commands ran in `bilun-laptop-ci:20261008-runtime-complete` with `requirements-ci.lock` installed offline (Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1), the worktree mounted in. `sut_fetch.py` downloaded the 33 MB package once more; its hash equals the pinned one.
- Result: `completion_scope: complete`, `last_ingested_date: 2026-10-02`, `completed_package.zip_sha256` 03bf37df…, `manifest_sha256` equal to the file on disk. 49 workbooks converted, 48 raw partitions rewritten (44 provenance only, 4 with values). Curated: ek1a (+N11), ek2c (+P609541, amended P608310), ek3o (clause (3) and marker); ek2b unchanged. Guarded files byte-identical.
- CI commands: ruff passed; pytest 8,306 passed; `compile_rules.py --check` and manifest parity exit 0; `sgk_watch.py --dry-run` finds 0 new.
- Where the run differed from the plan: 2.3 exits 1 as predicted, from the EK-4A snapshot spec only. 3.2 shows no EK-2B or EK-2C change because `sut_delta.py` cannot see in-place amendments (report F1); the raw-level comparison in the report is the review delta. Follow-through added after the review: a changelog entry (the 2026-08-29 ingest added one), four runbook gaps and one stale sentence in the 2026-10-10 report.
- Independent review (second agent) reproduced the numbers, hashes and byte-identity. Findings and what was done:
  - Real, claims: the EK-3O clause (3) and the EK-2C bone-marrow row were described wrongly in the report and in a commit message. Fixed in both; lesson added (`tasks/lessons.md`, 2026-10-13).
  - Risk, runtime: rows with a later "Yürürlük" date are eligible from the list's file-level date, so P609541 is eligible from 2026-07-07 (report F3). Written up, not fixed: it needs service-date reading for EK-1A, EK-2B, EK-2C and EK-3O the way #219 to #222 did for EK-4A.
  - Risk: the known gaps (30 EK-2B procedures, Satralizumab) are recorded only in the report and the changelog; no issue tracks them. Left for Safa's decision.
  - Risk: the new baseline might hide announcements. Checked: none are hidden (the 4 without an issue are dated 2026-08-12 to 2026-08-29).
  - Nits fixed: runbook steps 2, 4, 5 and 6; the test also checks `raw data/` paths; changelog entry; stale monitor sentence.
  - Nit skipped: `ingest_state.json` has no trailing newline; `sut_ingest_state.py:153` writes it that way and the old file was written by the same code.
- Not done on purpose: nothing is pushed, no PR is opened, #217 stays open until the merge.

## Task: Fix demo-only vignette and scenario_tag inputs (Safa675/Bilun#239)

### Goal
`claim_strategy.py` computes optional-override package and itemized totals purely from claim/performed procedure lines and the as-of EK-2B/EK-2C catalogs (with `demo_vignette_lookup.py` removed from `src/bilun/`), and `gap_closing.py` / `fatura_inceleme.py` derive `is_emergency` from `claim_type` and `department` without reading `scenario_tag`.

### Subtasks
- [x] 1. Remove `src/bilun/domain/billing/demo_vignette_lookup.py` and `tests/unit/domain/billing/test_demo_vignette_lookup.py`, and update `tests/unit/domain/test_money_helper.py` to drop the removed module path.
- [x] 2. Update `src/bilun/domain/billing/claim_strategy.py`:
  - Inline `recommended_package_code_for_claim(claim, claim_procs)` using `claim_procs` `paket` line codes, `package_code`, and EK-2C procedure code lookups (no vignette lookup).
  - Extend `resolve_package_total_try` to fall back to `get_ek2c_entry(line.procedure_code, as_of_date=as_of)` when `package_lines` and `line.package_code` are absent.
  - Add `resolve_catalog_itemized_alternative(claim, claim_procs, performed_lines=...)` so package-only submissions (when `eligible_lines` is empty) resolve their itemized alternative from `performed_procedure_lines` or `claim_procs` via `get_ek2b_price_for_date` and `compute_session_adjusted_itemized_total` (`itemized_price_methodology = "ek2b_catalog"`).
- [x] 3. Update `src/bilun/domain/prose_rules/gap_closing.py:341-345` and `src/bilun/domain/prose_rules/fatura_inceleme.py:190-194` to derive `context["is_emergency"]` from `claim_type_lower` and `dept` (`"acil" in claim_type_lower or "emergency" in claim_type_lower or "acil" in dept or "emergency" in dept`), never `scenario_tag`.
- [x] 4. Update synthetic demo golden bands in `data/synthetic/demo_vignettes.json` (`0002` and `0003`) and test assertions in `tests/unit/domain/billing/test_billing_actions.py`, `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py`, `tests/unit/domain/billing/test_claim_strategy_sut.py`, and `tests/unit/domain/prose_rules/test_gap_closing_for_context.py` to match catalog-resolved prices and add regression tests verifying:
  - Blanking `scenario_tag` across all 50 synthetic patients leaves `compute_patient_billing_report` outputs and rule evaluations unchanged.
  - A claim with `claim_type="acil"` and `department="Ic Hastaliklari"` has `is_emergency is True` in `_build_gap_closing_context`.
- [x] 5. Run `ruff` and relevant unit tests, commit, check `main` CI (Rule 10), push `claude/fix-demo-vignette-emergency-239`, open PR for `#239`, and return to `main` (Rule 11.5).

### Out of Scope
Regenerating `data/synthetic/sut/claims/*.parquet`, removing `data/synthetic/demo_vignettes.json` from `scripts/deploy/generate_candidate_source_roster.py` (strict-lane pause rule), or changing `traffic_accident_billing.py`.

### Review
- Removed `src/bilun/domain/billing/demo_vignette_lookup.py` and `tests/unit/domain/billing/test_demo_vignette_lookup.py`.
- Added `recommended_package_code_for_claim` and `resolve_catalog_itemized_alternative` in `src/bilun/domain/billing/claim_strategy.py` so optional-override package and itemized totals resolve from claim/performed procedure lines and the as-of EK-2B/EK-2C catalogs.
- Updated `src/bilun/domain/prose_rules/gap_closing.py` and `src/bilun/domain/prose_rules/fatura_inceleme.py` so `is_emergency` is derived from `claim_type` and `department`, never `scenario_tag`.
- Verified `ruff` clean and `1,275` synthetic, billing, and deploy unit tests + `18` `test_gap_closing_for_context.py` tests pass.

---

## Task: Start the laptop CI runner automatically while jobs are queued (2026-10-12)

### Goal
A pushed PR, or a merge to main, has its backend and frontend jobs served by the laptop within about a minute without anyone starting `laptop_runner.py`, and no runner stays registered once the queue is empty.

### Subtasks
- [x] `tools/ci/laptop_watcher.py`: each run reads the jobs queued for the `bilun-laptop-ci` label (runs that are `queued` or `in_progress`; a run last updated more than a day ago is a stale record and ignored); only while jobs are queued, no runner with the label is online and the image exists, it starts `laptop_runner.py --jobs 1`, re-reads the queue after every job and stops after `--max-runs`.
- [x] Safety: a file lock stops overlapping runs; a runner that receives no job within `--pickup-timeout` is stopped with SIGTERM (the script then removes its container, volume and registration); a busy runner is never stopped; SIGTERM to the watcher is forwarded; a failing runner makes the run exit 1 and the next timer run retries.
- [x] `tools/ci/systemd/bilun-ci-watcher.service` (oneshot) and `bilun-ci-watcher.timer` (30 s after start, then 60 s after each run ends). The service runs a copy under `~/.local/share/bilun-ci`, so a PR branch checked out in a working tree cannot change code that an unattended timer runs with admin credentials.
- [x] Tests in `tests/unit/tools/test_laptop_watcher.py` with a fake GitHub and a fake process: label, status and age filter; nothing queued; online runner present; serve until empty; max runs; never-picked-up runner stopped; busy runner kept; failure stops the run; dry run; missing image; lock; missing image argument.
- [x] Real checks: `ruff check`, the new tests, `systemd-analyze --user verify`, `--dry-run` against GitHub, and one run as a transient systemd user service (gh keyring and docker are reachable there).
- [x] `docs/operations/AI-RUNBOOK.md`: install, update, status, log and stop commands, and the limits (laptop awake, Docker up, linger for logged-out use).
- [x] Independent review of the diff by a second agent (findings and what was done about them in Review below).
- [ ] PR against main. Nothing is installed on the laptop before it merges.

### Out of Scope
Installing or enabling the timer on the laptop (done by the owner after the merge), changes to `laptop_runner.py`, the CI image, the workflows or the runner labels, an always-on runner, GitHub-hosted runners.

### Review (2026-10-12)
An independent review found two real bugs and several risks; all were checked against the code before acting on them.
- Real: systemd signals the whole cgroup on stop and the watcher then forwards another SIGTERM, which can abort `laptop_runner.py`'s cleanup (its handler raises even inside `finally`). Fixed with `KillMode=mixed`, `TimeoutStopSec=120` and `SuccessExitStatus=143`.
- Real: only `RuntimeError` was caught around the status poll, so a non-JSON answer or a missing `gh` could orphan a running job. `github()` now turns every failure (missing `gh`, timeout, non-JSON) into `RuntimeError`, and the poll catches any exception and retries.
- Risk: a hung `gh` or `docker` call would stall the timer for good. Both calls have a 60 s timeout and the service has `TimeoutStartSec=8h`.
- Risk: a job that asks for a label our runner lacks would make an idle runner start and stop all day. A job now counts only if its labels are a subset of the runner's.
- Smaller: `--dry-run` reported "would start" without checking the image; a down Docker daemon was reported as a missing image; a misleading `Nice=`; runbook statements about stopping, linger with the keyring-stored `gh` login, and where the image tag lives were corrected.
- Tests: the behaviours the review found unpinned (runner-label filter, kill fallback, pickup-timeout boundary, runner command line, defaults, SIGTERM handler, non-JSON and missing-`gh` answers, a job assigned after the pickup timeout) now have tests, and the vacuous `online == []` assertion is gone. A mutation check of 14 injected regressions found one survivor (a runner that gets its job after the timeout); a test now pins it, so 14 of 14 are caught.
- Found by the first live run (a transient systemd unit serving the queued jobs): `gh` failed its very first connection with "error connecting to api.github.com" and the run exited 1 after 10 s; two retries a moment later worked. `github()` now asks again up to 3 times, 5 s apart, for a dropped connection only (a real API error such as 401 is not retried); the runbook already says to retry connection errors.
- Left as is on purpose: a status that keeps failing never stops a runner, because not knowing is not a reason to stop a job; an unpicked runner exits 1 so the failure is visible in `systemctl --user status`.

## Task: Fix icu_puani day counting and add §2.4.4.H ICU tier overbilling detector (Safa675/Bilun#242)

### Goal
`icu_puani.py` derives ICU days from billed ICU procedure lines (`510090` and `P552001`–`P552008`) without defaulting to 3rd-level `P552003` or treating the entire hospital stay as ICU days, and `detect_icu_tier_overbilling` flags 3rd-level ICU packages (`P552003` / `P552008`) billed without 3rd-level organ-support / invasive mechanical ventilation / dialysis / ECMO procedures on the episode.

### Subtasks
- [x] 1. Update `src/bilun/domain/prose_rules/icu_puani.py` (`detect_icu_puani_opportunities`) to compute ICU days from billed `510090` and `P552001`–`P552008` procedure lines (capped by hospital LOS) and remove the `_DEFAULT_INTERMEDIATE_CODE = "552003"` fallback when no intermediate package is on the claim.
- [x] 2. Implement `detect_icu_tier_overbilling` in `src/bilun/domain/prose_rules/icu_puani.py` and wire it into `src/bilun/domain/billing/engine.py` (`analyze_claim`) so 3rd-level ICU packages (`P552003` / `P552008`) without 3rd-level qualifying organ-support/ventilation/dialysis/ECMO procedure codes emit a §2.4.4.H audit-exposure finding with the price gap to 2nd-level (`P552002` / `P552007`) and 1st-level (`P552001` / `P552006`).
- [x] 3. Update and expand `tests/unit/domain/prose_rules/test_icu_puani.py` to test ward stays with 3-day ICU segments, no-default-`P552003` behavior, and `detect_icu_tier_overbilling` (with and without 3rd-level qualifying procedures); run unit tests and `ruff`; commit, check `main` CI, push, open PR for `#242`, and return to `main`.

### Out of Scope
Re-generating the synthetic demo cohort parquets or adding new columns to `ClaimHeader`.

### Review
- **Delivered:**
  - `src/bilun/domain/prose_rules/icu_puani.py`: replaced hospital-LOS day counting and the `_DEFAULT_INTERMEDIATE_CODE = "552003"` fallback with `_infer_billed_icu_days` (derived from `510090` and `P552001`–`P552008` quantities/distinct service dates, capped by hospital LOS), and implemented `detect_icu_tier_overbilling` for §2.4.4.H / EK-2/C-A 3rd-level ICU packages (`P552003` / `P552008`) billed without invasive ventilation, dialysis/hemofiltration/plasmapheresis, or ECMO/cardiopulmonary-support procedure codes.
  - `src/bilun/domain/billing/engine.py`: wired `detect_icu_tier_overbilling` into `analyze_claim` alongside `detect_yatak_icu_overlap`.
  - `tests/unit/domain/prose_rules/test_icu_puani.py`: updated `test_basamak_inferred_from_submitted_package` and added 4 unit tests covering segmented ICU day counting, no-default-`P552003`, and `detect_icu_tier_overbilling`.
- **Verification:** `78 passed` across `test_icu_puani.py`, `test_claim_compliance.py`, and `test_claim_compliance_pipeline.py`; `ruff check` clean.

## Task: Stop counting missing amounts as zero in uplift, savings and recoverable totals

### Goal
Each `?? 0` flagged in the zero-for-null sweep is classified with evidence; the ones where a missing amount is shown as a bare number now show a dash or a labelled partial figure (stacked on the billed-at-risk fix).

### Subtasks
- [x] Verify the six flagged places against the API types (`frontend/src/lib/domains/sut.ts`), the backend response models (`src/bilun/api/schemas.py`) and the callers.
- [x] Fix (a): `SessionUpliftSection` fallback sum and `PatientInvoiceTable` opportunity fallback (dash / partial note, en and tr messages); shared `sumKnownAmounts` / `amountCoverage` next to `complianceBilledAtRiskSummary`.
- [x] Leave (b) unchanged with a one-line reason comment: `OptionalOverrideSection`, `SUTOptimizerTab` grand total, `recoverableUplift`, `sutChatPageContext` copay savings.
- [x] Tests: all present, one null, all null, en and tr (`SessionUpliftSection.test.tsx`, `PatientInvoiceTable.test.tsx`, `workspaceViews.test.ts`).
- [x] `npx tsc --noEmit`, full `npx vitest run`, eslint on changed files, `npm run build`.
- [ ] Draft PR against main, stacked on the billed-at-risk PR; do not merge before the pending production deploy is activated.

### Out of Scope
Backend, rules, exactness semantics, API shape. Backend defaults of 0.0 in the response models are noted in the PR, not changed.

## Task: Never show a zero or partial sum for missing billed amounts at risk

### Goal
The compliance view's "Billed amount at risk" stat shows an exact sum only when every counted at-risk action has a billed amount; otherwise a dash or a labelled partial sum with "x of y findings".

### Subtasks
- [x] Reproduction reported by independent review (not re-run against the live API here): SENTETIK-HASTA-0003 (5 nulls shown as 0.00 TRY) and 0029 (25,000.00 TRY = 2 of 7 findings) on the synthetic cohort; 0017 (2 x 192.32) is complete and unchanged.
- [x] Add `complianceBilledAtRiskSummary` ({total, known, count}) in `frontend/src/lib/workspaceViews.ts`; `complianceBilledAtRisk` returns null instead of a partial sum; keep the `drug_indication` exclusion.
- [x] Render dash / partial hint in `ComplianceViewSection.tsx` with en and tr messages.
- [x] Tests: one null, all nulls, no nulls, drug_indication exclusion, en and tr rendering.
- [x] `npx tsc --noEmit`, full `npx vitest run`, `npm run build`.
- [ ] Draft PR against main; do not merge before the pending production deploy is activated.

### Out of Scope
Backend, rules, exactness semantics, API shape, and other aggregations (uplift/savings fallbacks) that are not this billed-at-risk total.

## Task: 5 Ekim kaynak yenilemesi ve doğrulanmış paket entegrasyonu

### Goal
Main499dff4 tabanında PR154(150 dahil), PR153(152 dahil) ve PR151'i tek kez birleştir; pozitif resmî kanıtla desteklenen 5 Ekim penceresi ve kanonik ortak veri kapanışıyla bağımsız incelenmiş draft PR ve exact-head full CI teslim et.

### Subtasks
- [x] Güncel main/5PRhead/exactCI ve repoAGENTS/lessons doğrula; özgün dirtyfiles koru.
- [x] Ayrı integration-2026-10-05 ve source-renewal-2026-10-05 çalışma ağaçlarını kur.
- [x] Semantic child planını review et; PR153→PR152 exactdiff yalnız contextmemoization üç dosyadır; prioroutcome/evidence kodu aynı, ikinci taşıma yok.
- [x] Git merge sırasıyla PR154 → PR153 → PR151; üç ort merge temiz, b5beedda; ortak evidence final üretime kadar provisional.
- [x] Kaynak writer RG33391/SGK resmî gözlemlerini 06:08:50–06:12:51UTC kaydetti; 12 [5Ekim,5Ekim] continuity eklendi, 6Ekim 12/12 review_required. Kaynak worktree'sinde dokuz tam dosya 691PASS/3warnings.
- [x] Frozen20sourcepath gerçekSHA doğrulamasıyla integration tree'ye taşındı; source tasks/todo dışlandı, eski receipt/history kimlikleri değişmedi.
- [x] Mevcut compiler iki WRITE/iki CHECK134byte-stable; coverage bütün değer/order/dtype eşitliğiyle reviewed4parquet korundu (yerel pandas serialization farkı QA'da ayrı). Consumer496input/68test/134output → catalog yalnızreportpin → final159dependency evidence kapandı.
- [x] Kaynak691PASS, birleşiksemantics306PASS ve boundaries26PASS; compiler/parity23/0/Ruff/surfacing/freshcoverage1PASS; rawcorpus40b2/vector683a/verifier73f/policy/pending55/organ3/CLOSED invariants korundu.
- [x] Ayrı incelemeci final604PASS/2warnings/37.33s ve2410watchedfile0SHAchange bildirdi; finalhashaudit/code/source P1/P2none. YeniCI henüz çalışmadı, exactheadmapping mevcuttestedfileSHA'larıyla kaydedilecek.
- [ ] CI beforepush kontrolünden sonra onaylı draft integration PR yayımla; exact final head hosted fullCI sonucunu gerçek loglarla doğrula.
- [ ] Main'e merge yapmadan verifiedtree/head/CI ve tekrar etmeyen merge planını koordinatöre teslim et.

### Out of Scope
Üretim/VPS/deploy/mainmerge, mesothelioma runtimegate açılması veya yeni klinik kriter/admission, clinical_eligibility_complete=true, tarihî boşluk/hukukaltı doldurmak, kanıtsız tarih/hash uzatmak, genel mimari, historicalold→3e deploymentverifier/servingpermission genişletmek, tüm ingest/annex yenilemesi veya özgün dirtyfiles/stash temizliği.

### Specification and plan review
Kullanıcı 2026-10-05 06:01UTC'de kaynak yenileme, sıralı paket entegrasyonu, ortak veri regeneration ve birleşik CI için 'do it' dedi. Aynı adımlar için yeniden onay gerekmez. Python3.13 mevcut Bilun .venv; Git approved remote; main499 exactAPI identical ve tümPRheadCIgreen. .agents/skills seçili ortamda mevcut değil; repoAGENTS ve ilgili role/lessons okundu. Başarı: 12 bounded family yalnız kanıtlı5Ekim source review, 6Ekim unsupported/falsecomplete; legal/gaps, exact3 organneutral ve55pending korunur; PR151 CLOSED; historicalreceiptc4→40b2 ve immutable releaseverifier korunur; current maps/produceroutputs/querysource eşitliği; bağımsızreview ve exactheadfullCIgreen. Sharedcatalog/report/coverage aşamalarında tek namedwriter; Git/publish root only. Runtime yeni semantik gerekiyorsa açık risk bildir, unaffected work devam.

### File ownership
Root: Git integration, tasks/todo, delivery-status ve yayın. Kaynak writer ayrısourceworktree: yeni5Ekimreview/captures/receipt, clinical_versions yalnızappendwindow/review, .gitattributes/docs ve source_authority/source_authority_transport/followup_request_integration/mecasermin_request_integration/mecasermin_known_as_of/enteral_ravulizumab_clinical/report_documentation_completion/renal_runtime_observations/sma_antifungal_documentary_facts dar tarih testleri. Semantic child: yalnız gerektiğinde explicitlyassigned conflict/runtime paths; şu an read-only. Closure child: final tekowner olarak compiler/rulemanifest/4coverageparquet+JSON/commonconsumerreport/catalogreportpin aşamaları root GO ile; kaynağın Oct5catalog transportu bitmeden sharedwrite yok. Bağımsızreview ayrıchild, implementationowner olamaz.


## Task: Implement public billing and protected developer access

### Goal
Implement the approved public-billing/developer-login plan, verify security and billing behavior, and publish a new reviewed PR without deploying.

### Subtasks
- [x] Review the approved plan and repository instructions; create isolated branch `feat/public-billing-developer-access` from current `origin/main` at `3db12d53` (includes deployed #99, billing UX #100 and refactors #101–106).
- [x] Implement explicit backend access policies, authoritative capabilities and public response projections.
- [x] Secure officer chatbot context/tools and bound public computation.
- [x] Implement capability-driven frontend, developer sign-in, logout/expiry and public billing workflow.
- [x] Add release migration instructions, protected health probes, credential/session cutover support and asset confidentiality verification.
- [x] Review integrated behavior, run focused tests, full CI parity and production browser security checks; resolve failures.
- [x] Review final diff, verify branch CI status, publish/attach a new PR and confirm its checks.

### Out of Scope
Merging, live deployment, live credential rotation, changing clinical/payment calculations, new real-patient datasets or multiuser/SSO provisioning.

### Review
Plan approved by the user; implementation follows `plans/security/2026-09-29-public-billing-developer-access-plan.md`. Main checkout and existing deployment are preserved. Public access defaults disabled pending the documented release cutover.

Implementation & verification evidence:
- Backend access control, authoritative session resolution, and public JSON response projections verified.
- Fixed cohort projection test `test_public_projection_preserves_cohort_business_results_and_cached_nulls` by popping internal `wavea_evidence_detail` payload before projection comparison.
- Fixed Next.js Playwright strict mode conflict on `getByRole("alert")` in `test-access-browser.mjs` by filtering on text.
- Full CI test parity:
  - Ruff check (`ruff check src/ scripts/`): clean
  - Rules compiler check (`python scripts/sut/compile_rules.py --check`): 134 rule/manifest artifacts byte-identical
  - Drug manifest parity check (`python scripts/sut/audit_manifest_parity.py --drug-only`): 23 manifests scanned, 0 issues
  - Unit tests: 964 passed in 538s
  - Cohort projection test: 1 passed in 86s
  - Vitest frontend suite: 70 files passed, 402 tests passed in 17s
  - TypeScript build check (`npx tsc --noEmit`): clean
  - Frontend production build (`next build`): clean
  - Browser E2E security tests (`node scripts/test-access-browser.mjs`): all 4 scenarios passed
  - Public asset verification (`verify_public_assets`): 52 files checked, 0 problems
  - `git diff --check`: clean

---

## Task: Use recoverable_uplift_try for bed-day and ICU totals and actions (Safa675/Bilun#233)

### Goal
`YatakPuaniReview.confirmed_yatak_try` and `collect_billing_actions` read `recoverable_uplift_try` (skipping zero-gap bed-day actions), and `IcuPuaniReview.confirmed_icu_try` uses `recoverable_uplift_try` even when it is `0.0` instead of falling back to `total_try`.

### Subtasks
- [x] 1. Update `YatakPuaniReview.confirmed_yatak_try` and `IcuPuaniReview.confirmed_icu_try` in `src/bilun/domain/billing/types.py` to use `row["recoverable_uplift_try"]` whenever `row.get("recoverable_uplift_try") is not None` (preserving `0.0`).
- [x] 2. Update `collect_billing_actions` in `src/bilun/domain/billing/billing_actions.py` to read `recoverable_uplift_try` for `yatak_puani` and skip `yatak_puani` action rows when the gap is `0.0`.
- [x] 3. Update and add unit tests in `tests/unit/domain/prose_rules/test_yatak_puani.py` and `tests/unit/domain/prose_rules/test_yatak_icu_overlap.py`; run pytest and ruff.

### Out of Scope
Re-generating the synthetic demo cohort parquets.

### Review
- **Delivered:** `YatakPuaniReview.confirmed_yatak_try` and `IcuPuaniReview.confirmed_icu_try` read `recoverable_uplift_try` when present (including `0.0`), and `collect_billing_actions` reads `recoverable_uplift_try` for `yatak_puani` and omits zero-gap bed-day action rows.
- **Verification:** `62 passed` across `test_yatak_puani.py`, `test_yatak_icu_overlap.py`, `test_icu_puani.py`, `test_billing_actions.py`, `test_claim_integration.py`, and `test_block_spec_integrity.py`; `ruff check` clean.

---

## Task: Complete hotspot refactoring delivery F — audit decomposition

### Goal
Give audit discovery, classifications, reconciliation, rendering, and CLI their own modules without changing generated outputs or the supported CLI, then publish the final focused PR after E.

### Subtasks
- [x] Create an isolated F worktree from C head `b5bae476` with D/E integration deferred until their verified merges.
- [x] Independently review the approved F boundaries, existing imports/test patch points, source root behavior, and every CLI mode before code edits.
- [x] Capture byte-exact baseline JSON/Markdown, CLI outputs and 1,119 tracked artifact hashes in this worktree before any Python test writers.
- [x] Mechanically extract model, metadata, Python source resolution, inventory validation/rollups, rendering and CLI into `scripts/audits/rule_surfacing/`; keep the old script pathname and callable compatibility.
- [x] Prove generated JSON/Markdown and all supported CLI modes are byte identical; preserve missing-surface and source-contract failures.
- [x] In a separate commit, replace only the exact-format literal deep-link map regex using the bounded token reader, with realistic valid syntax and computed/spread/unresolved rejection regressions.
- [x] Run focused audit tests, full backend gates, standalone CLI from repository and isolated cwd, sequential compiler/manifest checks, and tracked artifact drift checks.
- [x] Obtain independent review of source-vs-classification proof, path handling, imports/patch points and diff; resolve substantive findings.
- [x] Integrate verified E main, rerun affected checks, publish focused PR #106 and request task attachment; complete independent integration review.
- [ ] Verify current-revision CI/GitHub feedback and merge only after all gates pass.
- [ ] Run both frontend and backend gates on final integrated main and complete all three responsibility-locality walkthroughs in the approved plan.
- [ ] Record PR/revisions/verification and finish the agreed refactor only after the completion audit passes.

### Out of Scope
Changing detector semantics, rule coverage/classifications/counts, audit report formatting, frontend/clinical/financial behavior, canonical findings, new dependencies, production data/cache, deployment and unrelated user work.

### Review
The independent read-only inventory defines explicit ownership across `model`, `metadata`, `python_sources`, `surface_sources`, `inventory`, `render`, and `cli`, with the old script retaining compatible callables and a single root/path context. Tests patch nine old-script path globals, three path helpers, and `PATIENT_REPORT_META`; the extraction must keep those seams observable. The map reader is a separate bounded change after pure extraction. Baseline direct `python -I` behavior was captured from `/tmp` for default, check, full/chunk/combined prints and invalid arguments in `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`; successful full JSON and Markdown hashes exactly match C's baseline. All 1,119 tracked artifacts are unchanged. F can be implemented in parallel with D/E integration, but publication remains last. Worktree `/root/worktrees/bilun-audit-decomposition`, branch `refactor/hotspot-audit-decomposition`.

The frozen mechanical extraction moves audit ownership to the planned modules while retaining a script-path facade with explicit call-time `AuditContext` from the original root, patched globals and three helper callbacks. Independent review found no actionable issue: all 52 original function bodies are unchanged apart from explicit context plumbing, all 27 facade wrapper signatures and 12 metadata tables remain compatible, and import/source-proof boundaries hold. Scoped Ruff and 78 focused tests passed. All 12 captured direct CLI cases preserve exit codes and stdout; successful modes and parser-exclusivity stderr are byte-identical, while invalid-chunk exception text remains exact with expected relocated traceback frames. Generated JSON/Markdown bytes and all 1,119 tracked artifact hashes remain unchanged. Evidence and the independent review are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`. The literal-map reader was implemented and reviewed in a separate second commit.

The second stage replaces only the exact-layout map regex with a bounded literal reader in `surface_sources.py`. It accepts the existing 17-entry map plus ordinary comments/whitespace, literal quote styles, trailing commas and explicitly supported type annotations; it rejects dynamic/computed/spread/unresolved/duplicate entries and unsupported syntax. Independent review found a regex-literal false-evidence case, which was fixed by a local fail-closed top-level slash guard and four regressions; re-review found no remaining blocker and A's tokenizer/resolver remain unchanged. Before E integration, corrected source passed 122 focused tests, all 12 captured CLI exit/stdout comparisons, byte-identical full JSON/Markdown, 4,133 full backend tests (eight warnings), full/scoped Ruff, isolated direct CLI `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23/zero). All 1,119 tracked artifact hashes remained unchanged after every gate. A pre-fix interrupted run is separately labeled and not counted. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`.

F was rebased onto E's merged main `46a694d0`; all reviewed F source/tests remained byte-identical apart from three trimmed signature spaces with unchanged AST. [PR #106](https://github.com/Safa675/Bilun/pull/106) opened at this integrated candidate. Independent final review cleared its source and contracts. Local integrated gates passed 964 focused and 4,145 full backend tests (three/eight warnings), TypeScript, 383 frontend tests in 65 files, production build, full/scoped Ruff, isolated audit and all 12 CLI modes, exact generated JSON/Markdown, compiler `--check` (134 byte-identical artifacts) and manifest parity (23/zero). All 1,119 tracked data/report artifact hashes were unchanged after every gate. The app attachment request did not return, so attachment is unconfirmed. Its initial current-source CI run `36489935324` passed both jobs at `6fb194cd`; final documentation-only PR-head CI, merge and merge-main CI remain. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`.

---

## Task: Count patients with recoverable > 0 in n_patients_with_actions (Safa675/Bilun#234)

### Goal
`CohortRecoverySummary` exposes `n_patients_with_actions` (counting patients with `total_recoverable_try > 0`) while keeping `n_patients` as the loaded patient count, and `RevenueRecoverySummary.tsx` displays `n_patients_with_actions` under "Eylemli Hastalar" / "Patients with Actions".

### Subtasks
- [x] 1. Add `n_patients_with_actions: int = 0` to `CohortRecoverySummary` (`src/bilun/domain/billing/types.py`), compute it in `build_cohort_recovery_summary` (`src/bilun/domain/billing/cohort_summary.py`) and backfill in `get_revenue_recovery` (`src/bilun/api/routes/optimization.py`), and allowlist it in `src/bilun/api/public_contracts.json`.
- [x] 2. Add `n_patients_with_actions?: number` to `CohortRecoverySummary` in `frontend/src/lib/domains/sut.ts`, update `RevenueRecoverySummary.tsx` and `SUTOptimizerTab.tsx` cohort filtering, and add unit tests in backend and frontend.

### Out of Scope
Changing `n_patients` semantics or regenerating the synthetic demo cohort parquets.

### Review
- **Delivered:** Added `n_patients_with_actions` across `CohortRecoverySummary`, `cohort_summary.py`, `optimization.py`, `public_contracts.json`, `sut.ts`, `RevenueRecoverySummary.tsx`, and `SUTOptimizerTab.tsx`.
- **Verification:** Backend `test_cohort_recovery_summary.py` and frontend `RevenueRecoverySummary.test.tsx` pass; `ruff check` clean.

---

## Task: Complete hotspot refactoring delivery E — drug routing, constraints and evaluation

### Goal
Make route selection, ordered constraints and detailed-result construction independently changeable while preserving every existing public result and clinical decision. Deliver a separate PR after verified D.

### Subtasks
- [x] Review approved Phase E and the stable D implementation for ownership, public wrapper/patch seams, raw-versus-decorated violation shape and ordered constraints.
- [x] Create an isolated E worktree at C head `b5bae476`, with D integration deferred until D is verified and merged.
- [x] Add targeted dynamic-wrapper/default-loader, competing-failure precedence and primary-plus-supplemental identity tests and prove them on the unchanged monolith; re-run after D integration before source edits.
- [x] Integrate verified D main, refresh import/patch inventory, and compare the unchanged D full-output baseline.
- [x] Mechanically extract routing, constraints and evidence helpers into the three approved internal modules, retaining callable identities, public wrappers and cached objects.
- [x] Give the internal evaluator explicit rules; keep default loading in the facade and preserve first-hit, nested payload and supplemental-ID behavior.
- [x] Compare the immutable complete result snapshot and new pre-extraction tests; run focused/full backend, Ruff, isolated audit, compiler/manifest gates sequentially and tracked-artifact hash checks.
- [x] Obtain independent review of AST/signature/dependency and output parity; resolve substantive findings.
- [x] Publish E PR and request task attachment, verify current-revision CI/GitHub feedback, merge with exact-head guard after checks pass, then verify main CI.
- [x] Record PR/revision/evidence and advance to F.

### Out of Scope
New clinical rules or messages, route semantics, corpus/cache changes, canonical findings/projections, rule data/schema/artifact changes, audit parser expansion, deployment or unrelated cleanup.

### Review
The read-only map and explicit extraction traps are recorded at `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e/read-only-extraction-checklist.md`. E's source changes wait for D integration; targeted baseline tests can be authored on the unchanged monolith in parallel. Worktree `/root/worktrees/bilun-drug-evaluation`, branch `refactor/hotspot-drug-evaluation`.

Three targeted groups (ten cases) passed against the unchanged C monolith at `b5bae476` before E source work: facade default-loader calls for `None` versus explicit `[]`, dynamic public detailed calls and context order/orphan behavior, first-hit precedence across overlapping failures, and primary/supplemental inner-versus-outer identities. Ruff passed. Source/test hashes and logs are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e`. The verified D source can be integrated provisionally before its PR merge; E publication remains dependent on D's final merged main and hosted gates.

After provisional D integration, 12 boundary/cache tests and the immutable complete comparator passed before E source edits. The reviewed extraction gives routing, constraints and evaluation their own modules while keeping all 46 other original function ASTs, 47 signatures, 44 exact callable aliases and four cache objects. The 20,339,608-byte detailed/canonical/legacy/cache/API payload snapshot remains identical. Independent review found no actionable finding, including first-hit order, raw/common nested fields and supplemental inner/outer IDs. The final isolated E source passed 868 focused tests, 4,087 full backend tests (eight warnings), full Ruff, isolated audit `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23 scanned, zero issues), with all 1,119 tracked artifact hashes unchanged after each gate. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e`. Rebase onto D's merged main and hosted current-revision CI remain before publication/merge.

E was rebased onto D's head-guarded merged main `ec368706` with byte-identical E source/test content. The immutable complete comparator, 868 focused tests (three warnings), Ruff and isolated audit `--check` passed again on the integrated tree; all 1,119 current tracked artifact hashes remain unchanged. D's merge-main CI run `36487251655` passed. PR publication and E current-head hosted CI remain.

E publication: [PR #105](https://github.com/Safa675/Bilun/pull/105) at `671fc9e0` passed both hosted jobs in run `36488702448`, independent review and feedback review, with no human/inline findings (Copilot reported quota exhaustion). It merged with an exact-head guard as `46a694d054ec3a557e25977de386c09405bce215` at 2026-09-28 21:57:26 UTC; the merged tree equals the tested branch. Both main CI jobs passed in run `36489455355`. The app attachment call did not return, so attachment is unconfirmed. Delivery F was then rebased onto this merged tree.

---

## Task: Restrict anaesthesia uplift to EK-2B §6 surgeries, use service-date EK-2B §4 group table, and subtract billed anaesthesia (Safa675/Bilun#230)

### Goal
`detect_anestezi_puani_opportunities` evaluates only EK-2B §6 surgical lines (`600000`–`629999`), resolves single-surgery (`550130`–`550190`) and multi-surgery same-session (`550200`–`550260`) anaesthesia groups from the service-date EK-2B §4 group table (with no 5,000 puan ceiling), subtracts already-billed anaesthesia (`550130`–`550346`) from `recoverable_uplift_try`, and cites SUT §2.2.2.A + EK-2/B §4 instead of §2.4.4.A (ESWL).

### Subtasks
- [x] 1. Restrict `_surgical_puan` in `src/bilun/domain/prose_rules/anestezi_puani.py` to EK-2B §6 surgical codes (`600000`–`629999`) so lab, exam, bed, and anaesthesia codes are skipped.
- [x] 2. Replace the wrong hardcoded `1–5000` group table in `anestezi_puani.py` with the service-date EK-2B §4 group table (`2026-07-07` onwards: A1 `>=39001`, A2 `18501–39000`, A3 `9001–18500`, B `6001–9000`, C `3005–6000`, D `1301–3004`, E `0–1300`; plus `2026-01-01`, `2022-09-03`, and `2020-03-11` historical tables) and emit one increased anaesthesia (`550200`–`550260`) per multi-surgery session.
- [x] 3. Subtract already-billed anaesthesia (`550130`–`550346`) from `recoverable_uplift_try`, update `AnesteziPuaniReview.confirmed_anestezi_try` and SUT §2.2.2.A / EK-2/B §4 citation, and update unit tests (`test_anestezi_puani.py`, `test_elkitabi_tablo23.py`).

### Out of Scope
Newborn/geriatric ASA 3–4 modifiers (`550270`–`550346`) when ASA score is not present in claim inputs.

### Review
- **Delivered:** Restricted `_surgical_puan` to EK-2B §6 (`600000`–`629999`), implemented service-date EK-2B §4 single (`550130`–`550190`) and multi-surgery (`550200`–`550260`) group tables, subtracted billed `550130`–`550346` into `recoverable_uplift_try`, updated `AnesteziPuaniReview.confirmed_anestezi_try` and SUT §2.2.2.A citation.
- **Verification:** `test_anestezi_puani.py`, `test_elkitabi_tablo23.py`, and `test_claim_integration.py` pass; `ruff check` clean.

---

## Task: Prepare and implement hotspot refactoring delivery D — drug corpus and matching

### Goal
Extract drug matching and corpus responsibilities behind the existing public module with exact output/cache compatibility, then integrate after delivery C as its own verified PR.

### Subtasks
- [x] Read the approved phase D/E boundaries and create an isolated worktree at main `63df008d`; rebase onto the verified delivery C main before publication.
- [x] Independently inventory public/private accesses, cached objects and monkeypatch seams; review the planned ownership before runtime edits.
- [x] Capture complete representative baseline detailed/canonical/legacy/cache/API results using existing fixtures, including the plan's edge cases, and save an executable before/after comparison outside tracked artifacts.
- [x] Add only meaningful missing compatibility regressions exposed by the extraction risk.
- [x] Extract pure matching and corpus/coverage responsibilities with the same cache instances and shallow-copy semantics; preserve public names and signatures.
- [x] Compare complete outputs and source/audit contracts, obtain independent review, and resolve substantive findings.
- [x] Run focused drug checks and full backend gates sequentially with tracked artifact hash checks; preserve all data and financial/clinical behavior.
- [x] Integrate the verified predecessor, publish and request task attachment for a focused PR, verify current-revision CI/review, and merge only after all gates pass.
- [x] Record evidence and advance to delivery E.

### Out of Scope
Routing/constraint/evaluation extraction (delivery E), semantic or clinical rule changes, canonical/API/cache redesign, generated corpus/manifest rewrites, new dependencies, deployment, and live service changes.

### Review
Preparation may run in parallel with frontend deliveries in this isolated worktree; integration remains B then C then D. The user approved the full hotspot plan and unattended execution with merging only after tests and independent review pass. Runtime edits begin after the concrete baseline/ownership review. The original `/opt/Bilun` checkout remains untouched.

Baseline/ownership review is complete before runtime edits: matching owns pure predicates/normalization/specialty/INN/ICD functions; corpus owns paths/loading/manifest/subsection coverage/promotion/stop conditions. All four original decorated caches and shallow list/dictionary identities remain contracts. The immutable comparator captures 54 line cases, nine full report contexts, all 968 corpus rules, detailed/canonical/legacy/cache/API projections and coverage, including full-corpus order permutations. A second monolithic capture is byte-identical (20,339,608 bytes; SHA256 `5c046be33ba9eccf305034baac29bc1b02ff9b7542fd1e272f4154e9a403d7c1`). It verifies loaded `bilun` and `src.bilun` modules originate inside this worktree (284 origins). The focused baseline passed 122 tests including two missing public cache/default-input contracts; 1,119 tracked artifact hashes remained unchanged. Evidence and executable comparator: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-d`.

The extraction preserved all 47 original function ASTs and directly re-exports all 22 moved callables, including the four original cache objects, with no internal facade/billing dependency. The immutable complete payload snapshot is byte-identical after extraction. Independent source/runtime review found no actionable regression. Focused checks passed 858 tests; full backend passed 4,077 tests with eight warnings; full Ruff, isolated audit `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23 scanned, zero issues) passed. Hashes of all 1,119 tracked data/report artifacts are unchanged after every writer. These results apply to the isolated D source before integration on C main; publication and current-revision CI remain.

Delivery D publication: [PR #104](https://github.com/Safa675/Bilun/pull/104) at `79fefdcf` passed both hosted jobs in run `36486246248` and independent review, with no human or inline findings (Copilot reported quota exhaustion). It merged head-guarded as `ec368706047d3b3d95ddd5e76131825aa1f18940` at 2026-09-28 21:36:38 UTC; its tree equals the tested branch. Main CI run `36487251655` passed. The app attachment call did not return, so attachment is unconfirmed.

D was rebased onto C's merged main `20873ff6` without any source/test content change. The frozen full-output comparator remained byte-identical; the integrated tree passed 858 focused tests (three warnings), Ruff and isolated audit `--check`, with hashes of all 1,119 current tracked artifacts unchanged after each check. Relative to D's original A base, only the previously reviewed B report matrix provenance differs. C's merge-main CI run `36484758171` passed. D PR publication and current-head hosted CI subsequently passed, as recorded above.

---

## Task: Narrow §3.1.4(g) coronary-stent keyword and zero informational §3.1.4 risk (#231)

### Goal
Ensure `3.1.4.(g).coronary_stents` matches only coronary stents (not tracheal, urology, or other non-coronary stents), keep informational `§3.1.4` findings at `0.0` risk amount (`0 TL` billed at risk), and continue evaluating subsequent `§3.1` rules on lines that match an informational rule.

### Subtasks
- [x] Replace bare `stent` with `stent, koroner` in `data/gazette/prose_rule_sources/material_bundling/3.1.4.yaml` and recompile `data/gazette/prose_rules/material_bundling_prose.json`.
- [x] In `src/bilun/domain/prose_rules/material_bundling.py`, set `risk_amount = 0.0` when `action.get("severity") == "info"` and do not terminate the per-line rule loop on `severity == "info"` matches.
- [x] Add unit tests in `tests/unit/domain/prose_rules/test_material_bundling.py` covering non-coronary stents (`STENT, TRAKEAL, SİLİKON`, `Üreteral J stent`), coronary stents (`KORONER STENT, İLAÇ SALINIMLI`, `STENT, KORONER, BALONA MONTE EDİLMİŞ ÇIPLAK`), zero billed-at-risk on `§3.1.4` info findings, and non-info `§3.1` rules firing alongside `§3.1.4` info findings.

### Out of Scope
Re-architecting other `§3.1.4` sub-clauses or line-level billed-at-risk deduplication (`#232`).

### Review
Replaced bare `stent` with `stent, koroner` in `3.1.4.(g).coronary_stents`, recompiled `material_bundling_prose.json`, set `risk_amount = 0.0` for `severity == "info"` findings, and allowed subsequent `§3.1` rules to evaluate after an informational rule match. Verified with `test_material_bundling.py`, `test_material_bundling_golden.py`, `test_material_bundling_gate_b.py`, and `tests/smoke/test_sut.py`.

---

## Task: Complete hotspot refactoring delivery C — section presentation decisions

### Goal
Give copay, strategy, drug review, and material presentation clear local ownership while preserving current payload precedence, row decisions, focus behavior and UI output, then deliver a separate verified PR after B.

### Subtasks
- [x] Review delivery C against the actual extracted code and tests; create an isolated branch at B commit `9a539d5d`, to integrate onto verified main before publication.
- [x] Add focused compatibility regressions and verify them against unchanged B components before rewiring those components.
- [x] Extract section-local copay/strategy models preserving existing overlapping filters, row order, first-row header selection, null/zero values, and shared `billingReportFields` behavior.
- [x] Make drug display states explicit and split substantial card/legacy/evaluation rendering while keeping section-owned refs, focus effects and the same precedence/array identity.
- [x] Split material tables into named local components while retaining simultaneous groups, order, source/coverage notices and empty/partial behavior.
- [x] Remove only the proven unreachable strategy override notice, after confirming overrides remain in their dedicated section.
- [x] Run focused tests, full frontend typecheck/tests/build, audit checks and artifact parity; exercise changing/unknown finding selection and drawers in the isolated browser preview.
- [x] Obtain independent implementation review, resolve findings and complete the hypothetical local-column-change walkthrough.
- [x] Integrate verified B main, publish and request task attachment for the focused PR, verify current-revision CI and reviews, then merge only after all gates pass.
- [x] Record evidence and advance to D.

### Out of Scope
Clinical or financial reinterpretation, new features/labels, payload or schema changes, removal of supported legacy data, new generic frameworks/dependencies, deployment, and live data/service changes.

### Review
The approved plan and read-only extraction review establish the five drug states (hidden, structured, legacy, evaluations, empty), first-non-insight copay header selection, per-row mixed shape handling, overlapping strategy categories with violations before claim rows, explicit zero-count preservation, and simultaneous material groups. Detailed scope is saved at `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c-scope.md`. Worktree: `/root/worktrees/bilun-report-presentation`; branch: `refactor/hotspot-report-presentation`. B merged as [PR #102](https://github.com/Safa675/Bilun/pull/102), main `f63bb12b`, with successful main CI run `36482614267`.

Local C verification is complete against frozen source. Ten independently authored public-section compatibility cases passed on unchanged B before rewiring; after extraction, 41 focused tests and all 383 frontend tests in 65 files passed, as did final TypeScript and the production build. The 64 focused audit/source tests and isolated CLI `--check` passed. Both generated audit files are byte-identical to the B baseline, and hashes of all 1,119 tracked data/report artifacts remain unchanged. Independent source review matched 16 moved markup/helper bodies and found no local import cycles. Chromium passed 20 checks, ten per locale, on both the B baseline and C candidate; every case result is identical, with no page errors or unexpected APIs. The preview used actual patient-page content and synthetic intercepted APIs in a minimal embedded shell; it does not claim production data or full-shell visual coverage. The local-column walkthrough found `MaterialKdvReviewTable` owns its own header/cell rendering and focused test; the owning section's availability, order and other seven renderers need no change. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c`.

Delivery C publication: [PR #103](https://github.com/Safa675/Bilun/pull/103) at `b5bae476` passed hosted frontend/backend CI run `36483840115` and independent review, with no human or inline findings (Copilot reported quota exhaustion). It was merged head-guarded as `20873ff6e66e75bb3d95b0af5206d58fe6d8d788` at 2026-09-28 21:14:27 UTC. Its merge tree matches the tested source tree. Main CI run `36484758171` passed. The app artifact attachment call is still pending; do not assume attached.

---

## Task: Deduplicate billed-at-risk per bill line across cohort and patient compliance views (#232)

### Goal
Ensure a bill line hit by $N$ compliance rules adds its `billed_try` amount once in both `build_cohort_compliance_index` / `slice_compliance_index` and `complianceBilledAtRiskSummary` while preserving all individual rule findings.

### Subtasks
- [x] Propagate `material_line_id` onto material action rows in `src/bilun/domain/billing/billing_actions.py` and allowlist it on `RecommendedActionItem` in `src/bilun/api/public_contracts.json` and `frontend/src/lib/domains/sut.ts`.
- [x] Preserve `material_line_id` on compliance index rows and deduplicate `billed_try` per `(patient_id, line_key)` in `_summarize_rows` (`src/bilun/domain/billing/cohort_compliance.py`).
- [x] Deduplicate `billed_try` per line in `complianceBilledAtRiskSummary` (`frontend/src/lib/workspaceViews.ts`) so patient-level and cohort-level billed at risk agree.
- [x] Add unit tests in `tests/unit/domain/billing/test_cohort_compliance.py` and `frontend/src/lib/workspaceViews.test.ts`.

### Out of Scope
Changing which rules fire or removing duplicate findings from the action lists.

### Review
Carried `material_line_id` onto `RecommendedActionItem` and compliance index rows, and deduplicated `billed_try` per distinct bill line in both `_summarize_rows` (`cohort_compliance.py`) and `complianceBilledAtRiskSummary` (`workspaceViews.ts`). Verified with backend pytest/ruff and frontend vitest.

---

## Task: Complete hotspot refactoring delivery B — report section extraction

### Goal
Move each existing report section into its owning module while preserving public imports, markup, behavior, and verified audit provenance, then publish and merge the independently reviewed PR after all gates pass.

### Subtasks
- [x] Confirm the approved plan and unattended authorization; use an isolated branch from merged delivery A at `63df008d` with successful main CI.
- [x] Review the 23-export inventory, helper ownership, source-resolver fixture dependency, and frontend verification requirements before implementation.
- [x] Move the 19 existing report components and genuinely shared helpers into `billing-report/`, preserving bodies and client boundaries; retain explicit named exports at the original module.
- [x] Adapt the real-extraction audit fixture to the new source graph without weakening full-output/evidence assertions.
- [x] Compare candidate audit outputs and record only explained provenance changes; verify tracked artifact hashes.
- [x] Run focused audit checks and full frontend typecheck, tests, and build; exercise the required focus/highlight/drawer/locale/partial-state flows in an isolated browser preview.
- [x] Obtain independent implementation review and resolve substantive findings; complete diff/scope checks.
- [x] Commit, check CI before push, open and attach the focused PR, verify current-revision CI/review, and merge only after all gates pass.
- [x] Record PR/revision/verification and advance to delivery C.

### Out of Scope
Section decision cleanup (delivery C), drug engine changes, general type/schema restructuring, changes to UI or financial/clinical behavior, new dependencies, deployment, live cache/data updates, and unrelated user edits.

### Review
The existing approved plan and fresh export/helper/fixture inspection define this mechanical delivery. The user authorized unattended B–F completion and merges after tests and independent review pass. PR #101 was already merged by `Safa675` when this run resumed; its merge commit is `63df008d9ac91564247b53c83231d283754931ce`, and main CI run `36479428919` passed. The original `/opt/Bilun` checkout and its uncommitted work remain untouched. Worktree: `/root/worktrees/bilun-report-sections`; branch: `refactor/hotspot-report-sections`.

Local verification is complete at source/artifact commit `1dc0b239`: 19 component modules and shared helpers preserve all 23 facade exports and all 29 original declarations (independent AST comparisons). Baseline frontend checks passed 102 tests; final TypeScript, all 373 tests in 64 files, and production build passed. All 64 focused audit/source tests and isolated CLI `--check` passed. Only the matrix changed among 1,119 tracked artifacts: 17 added source-path occurrences across 16 of 97 rows, with every non-provenance field and all Markdown bytes unchanged. No package/lockfile changes remain.

Publication/integration: [PR #102](https://github.com/Safa675/Bilun/pull/102), head `9a539d5d`, passed hosted CI run `36481871547`. Final GitHub review fetch found no human or inline findings; Copilot reported exhausted review quota, so independent agent review provides the completed review evidence. Merged with a head-SHA guard as `f63bb12b1568f5cc02632cdeccff728a6ec9ea54` on 2026-09-28 at 20:55:32 UTC. Main CI run `36482614267` passed. Release Hold remains unchanged; no deployment occurred. The primary checkout remains on main with its original uncommitted edits preserved.

Independent structural review found no import cycles, reverse facade dependencies, or changed declarations. Playwright/system Chromium passed 14 interaction/state checks across English and Turkish, including selected-finding focus and viewport visibility, action-to-invoice highlighting, clause fetching/closing, 390px table scrolling, and exact-empty/partial-noncoverage/collapsed-legacy states. The isolated preview used the actual patient-page content and matching source hashes with intercepted synthetic APIs, `embedded=true`, a minimal provider/layout shell and fallback font; it does not claim production backend or whole-shell visual verification. Logs, scripts, hashes, parity results, and screenshots are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-b`.

---

## Task: Fatura uyumluluğu ekranını faturalama görevlisi için anlaşılır hale getir (2026-09-28)

### Goal
Mevcut eyleme dönük bulgular, Wave A inceleme gözlemleri, bilgi/izin kayıtları ve değerlendirme kapsamı hasta ekranında açıkça ayrışsın; her tekil kanıtın kimliği ve bağlantısı korunsun. Ayrıntılı kapsam ve kabul ölçütleri [UX planında](../plans/billing/2026-09-28-billing-officer-compliance-ux-plan.md).

### Subtasks
- [x] Mevcut hasta/kohort bileşenlerini, sayım kaynaklarını, sayfalama sınırını ve test kapılarını incele.
- [x] Ürün düzeni, güvenli gruplama, metin kataloğu, belirsizlik gösterimi ve doğrulama için ayrıntılı plan yaz.
- [x] Planı mevcut veri sözleşmeleri ve testlerle bağımsız olarak karşılaştır; yanlış toplulaştırma ve kayıp deep link risklerini plana işle.
- [x] Ürün planı gözden geçirilip onaylandıktan sonra uygulamaya başla.
- [x] Hasta inceleme sunum modeli, erişilebilir grup/ayrıntı etkileşimi ve seçili tekil kayıt bağlantısını uygula.
- [x] Yapısal/Wave A kapsamını, advisory bölümünü ve iki dilli açıklamaları güncelle; kohort ortak bileşen etkisini doğrula.
- [x] Odaklı davranış testleri, dar ekran yan menü kontrolü, masaüstü/mobil tarayıcı kontrolü ve tüm frontend CI kapılarını tamamla.
- [x] Son diff'i ve sayısal/finansal değişmezleri gözden geçir; incelemeye hazır yeni PR aç.

### Out of Scope
Kural motoru, backend/API/cache, finansal toplamlar, kohortta sayfalar arası gruplama, canlı dağıtım ve mevzuatın hukuki teyidi.

### Review
Plan, mevcut `ComplianceViewSection`, `WaveAEvidenceSection`, `CohortWaveAEvidenceSection`, veri tipleri ve frontend testleriyle iki bağımsız salt-okunur incelemede karşılaştırıldı. Hasta önizlemesi/kohort sayfalaması nedeniyle yalnızca yüklenmiş satırlara ait gruplama sayıları kullanıldı; tekil `evidence_id` bağlantıları korundu. Kullanıcı planı onayladı. Hasta 0043/0001 üzerinde masaüstü, 390 px mobil, klavye, sayfalama ve önizleme dışındaki seçili kayıt tarayıcıda doğrulandı; mobil yan menü tercihi masaüstünde korunuyor. Tam frontend doğrulaması: 64 Vitest dosyasında 373 test, TypeScript ve üretim derlemesi geçti. Backend/API/cache/kural kararları ve finansal hesaplar değiştirilmedi. İncelemeye hazır [PR #100](https://github.com/Safa675/Bilun/pull/100) açıldı; ilk [GitHub CI koşusunda](https://github.com/Safa675/Bilun/actions/runs/36469974065) backend ve frontend başarılı.

---

## Task: Implement hotspot refactoring delivery A and open a draft PR

### Goal
Make the surfacing audit follow supported patient component imports and named re-exports while preserving source evidence, then publish the verified first implementation delivery as a draft PR.

### Subtasks
- [x] Confirm the user-approved hotspot plan and create an isolated worktree on current main `46ae9fdf`, including the merged billing-officer UX work.
- [x] Capture the baseline audit output, focused tests, generated-artifact hashes, and relevant current source contracts.
- [x] Implement the bounded frontend component-source adapter and integrate it without changing application behavior or the later-phase map reader.
- [x] Add meaningful moved-component and missing/false-evidence regressions; preserve existing audit checks.
- [x] Independently review the implementation and resolve findings.
- [x] Run the applicable full backend gates, audit parity checks, and artifact-drift inspection; record results.
- [x] Check branch CI, commit and push the reviewed changes, open and attach a draft PR, and report its CI status.

### Out of Scope
Deliveries B–F, component moves, drug-rule changes, a general TS parser, new dependencies, production data/cache changes, merge, and deployment.

### Review
Implementation authorized by the user after review of `plans/refactor/2026-09-28-bilun-hotspot-refactor-plan.md`. Delivery A is published as [draft PR #101](https://github.com/Safa675/Bilun/pull/101), attached to this task; later deliveries remain tracked in the plan. Work is isolated from the original checkout and its uncommitted planning documents. Independent review's demonstrated false-evidence cases are fixed. Full backend verification passed **4,075 tests, 8 warnings, in 734.61s**, including all 38 new regression cases and the existing committed-output parity check. Reviewed regeneration adds evidence paths to 16 rows, preserving every other serialized field and Markdown bytes. Full Ruff, isolated direct CLI checks, compiler check (**134 byte-identical rule/manifest artifacts**), and manifest parity (**23 manifests, zero issues**) pass. The final 1,091-file artifact hash comparison found only the reviewed matrix change. Base CI was green before the first push; the branch had no failed runs. Hosted PR CI started at publication; current status is available on the PR. No merge or deployment was performed.

---

## Task: Reduce full-suite runtime without reducing coverage

### Goal
Publish a reviewed implementation PR that preserves every backend/frontend test and generated SUT artifact while making full-suite local runs faster and measuring the Polars thread setting on GitHub Actions before selecting its final CI value.

### Subtasks
- [x] Independently review and confirm this plan against the measured three-file prototype and the existing CI gates before implementation.
- [x] Apply safe C YAML loading with the Python SafeLoader fallback in the rule-source and deferral-table loaders, preserving fresh parsed objects and safe-tag behavior.
- [x] Resolve the unchanged all-rule source union once in a module-scoped immutable fixture, preserving all manifest cases and assertion expressions.
- [x] Document `POLARS_MAX_THREADS=1 python -m pytest -q --durations=20` as the standard full-suite local command and add CI duration reporting, leaving the first PR revision's CI thread setting unchanged; add no wrapper, dependency, or pytest bootstrap.
- [x] Review the final source/configuration diff independently, including loader semantics, fixture lifetime, command argument handling, and CI trial attribution.
- [x] Run the complete backend suite from an empty worktree-local cache and compare all 2,774 test identities and statuses with the investigation baseline; run Ruff, compiler `--check`, and manifest parity, requiring 134 byte-identical generated artifacts and no tracked data drift.
- [x] Run all frontend CI gates on the final branch: TypeScript, the complete 320-test Vitest suite, and production build, coordinating heavy local execution with the backend run.
- [x] Record reproducible local timing, exact validation evidence, independent review, and any limitations in the review section; inspect the final diff and check existing CI before each push.
- [x] Commit, push the new branch, and open and attach a draft implementation PR after independent diff review and the completed exact-prototype gates; overlap hosted CI with final-branch local confirmation, keeping the PR draft until final local gates and repeated CI validation pass.
- [x] After the uncapped PR revision is green, add the step-scoped CI thread trial as an environment-only workflow revision; repeat uncapped/capped GitHub Actions attempts with the same source changes, compare full-test and compiler steps, retain the measured CI choice, and record the final result without projecting local speedup onto CI.

### Out of Scope
Merging or deploying; touching the live database/cache; removing, skipping, narrowing, or weakening tests; xdist; broad resolver, artifact-writer, or cleanup refactors; changing production thread settings; changing generated rules/manifests or clinical/payment semantics.

### Review
Plan reviewed and confirmed before implementation. Independent review found no correctness issues: the three backend files have AST parity with the measured prototype, parsing retains the safe fallback and fresh objects, and manifest assertions and parameters are unchanged. [PR #95](https://github.com/Safa675/Bilun/pull/95) contains the implementation on `perf/full-suite-runtime`; no merge or deployment is part of this task.

Local gates passed: **2,774 backend tests, zero skips/errors/failures, 9 warnings, 569.13s pytest / 573.18s external**, with exactly the same ordered identities/statuses as the original baseline; Ruff; compiler check **134 artifacts byte-identical** (47.54s); manifest parity **23 manifests, zero issues**; frontend TypeScript, **55 Vitest files / 320 tests**, and production build. The backend began with an absent worktree-local cache, source/configuration hashes stayed stable throughout validation, and the worktree was clean afterward with no generated-data drift. The original local baseline was 1,024.55s; host activity varies, so local percentages are not CI predictions.

Hosted comparison retained identical installed dependencies, Python 3.13.15, runner image, and cache key. Two successful attempts per configuration ran all 2,774 backend tests and reproduced all 134 compiler artifacts:

| Configuration | Python test step (seconds) | Backend job (seconds) | Compiler step (seconds) |
|---|---|---|---|
| Original main, `7a6e854f` | 329 / 336 | 404 / 415 | 34 / 38 |
| Parser/fixture changes, default threads, `782fe49f` | 231 / 167 | 289 / 225 | 19 / 11 |
| Same source, CI one-thread trial, `61e63746` | 214 / 136 | 270 / 185 | 16 / 10 |

Final decision: retain **default CI threads** and the measured **one-thread local command**. The CI trial's ranges overlap substantially with default-thread runs, and unchanged compiler/startup paths also varied across runner regions; these samples do not establish an isolated CI thread-budget benefit. The parser/fixture improvement is retained, and CI now reports its slowest 20 phases. All existing backend/frontend/compiler/build gates remain enabled. Evidence: [baseline attempts](https://github.com/Safa675/Bilun/actions/runs/36152110893), [default-thread implementation attempts](https://github.com/Safa675/Bilun/actions/runs/36260747322), [one-thread trial attempts](https://github.com/Safa675/Bilun/actions/runs/36261536404). Raw logs, source hashes, case parity, and independent reviews are retained in `/root/artifacts/bilun-test-implementation-2026-09-26`.

---

## Task: Complete the deferred PR #89 Wave A groups in one verified release (2026-09-27)

### Goal
Cover all 25 deferred detector/engine groups (18 focused and seven broad) through canonical, single-evaluation patient/cohort projections, with each authored outcome honestly classified. Ship in reviewable checkpoints on one integration branch, then activate once after a validated cache rebuild and verify the live patient and cohort experience. This is group coverage, not a claim that every possible authored rule ID fires in live data. PR #96's post-merge CI and Deploy completed successfully before this task began.

This is an explicit user-approved expansion of the original strict Wave A filter: mixed monetary outputs use existing financial sections and informational outputs use review-only presentation. Do not label those rows unpriced violations merely because their engines appeared on the deferred candidate list.

### Locked decisions from the grilling interview
- Keep the ten excluded synthetic `kind:<callable>` identities outside this release and report them honestly.
- Compliance contains only eligible, unpriced violations; positive actions are evaluations, review-only outcomes remain outside violation counts, and missing inputs remain unavailable rather than a clean pass.
- Preserve detector decision semantics; add status/skip metadata as needed. A wrong detector is held for a separate focused correction, and the combined release waits for that blocker.
- Give every distinct finding and per-line evaluation a stable source/line identity across patient, cache, cohort, API, and UI. Never collapse multiple rows into one claim identity.
- Show financial-only outcomes in existing patient and cohort financial/recovery sections with separately labeled billed/risk/uplift values and verified source/basis. If provenance or amount is unverified, show an honest review/unavailable state rather than a sourced or confirmed number. Keep existing savings/recovery totals byte/value-equivalent and do not double count or invent zero amounts.
- Show actual findings plus compact evaluated/unavailable summaries, not the full static ID catalog. Verify all cached rows and representative live triggers; use synthetic per-rule tests for rare rules with no live positive case.
- Validate the rebuilt cache and cohort before one user-visible activation; block unexplained financial drift, identity collisions, or finding-count changes; provide a tested rollback to the previous version/cache.

### Release checkpoint, 2026-09-27

The exact-main receipt preflight exposed a separate historical identity: the live PR98 serving cache has build `b1fdcb54` from code `b08c4797`, while the independently rebuilt same-input corrected baseline has build `8065e1d8` from PR98 code `4af38b28`. The issuer currently requires one baseline build ID and identical cache bytes for both, so it cannot sign honestly. A focused follow-up must preserve both identities, verify type-sensitive equality of every legacy content table between the protected serving cache and rebuilt baseline, tie that bridge to the observed old cache, and recheck both caches before receipt issuance. A changed row, missing row, malformed build, or drifted cache must block signing. After merging the correction, rebuild all candidate artifacts from its new exact `main` SHA before activation.

The follow-up now also rejects uncheckpointed DuckDB WAL sidecars at each cache hash, after independent review showed that a read-only query could otherwise observe committed rows absent from the pinned main file SHA. Crash-WAL and broken-symlink regression tests cover the trust boundary. Keep Wave A held until this correction is reviewed, merged, and re-attested from the exact new `main` SHA.

The final route/rollback review found three trust-boundary gaps and one product gap, now addressed in the integration branch. The release transaction checks both the route loaded by Caddy and the Caddyfile installed for restart; recovery reinstalls the barrier if old-route verification fails. Exact GitHub CI verification also requires the candidate SHA to remain current `main`. A protected old-pair recovery adapter seals the PR98 snapshot, stages independent backend/frontend/cache copies, and records a new PID-bound tuple after restart. Mixed cohorts now retain available evidence rows and show selected/available/unavailable coverage rather than suppressing the whole cohort.

Premerge proof at `f4daa876` includes a successful 50-patient/94-bill private candidate-pair Caddy rehearsal after rebuilding the frontend with its build-time API rewrite to port 8002. The new protected old-pair manifest and staged copy passed byte and WAL checks; its real launcher passed an isolated network-namespace rehearsal with all 50 patient and 94 bill legacy API payloads plus frontend assets matching the PR98 equivalence report. These checks are **nonactivating**. The currently pushed `5980538b` PR #97 head has green backend/frontend hosted CI; the new local integration changes still require their own exact-head CI, final merge SHA build, signed receipt, supervised rollback/public barrier verification, and live sign-off. Wave A remains inactive.

PR #98's EK-3B correction is merged and serving, with a protected old runtime/cache/environment snapshot. Draft PR #97 contains the 25-group patient, bill, cohort, API, and UI integration. Production Wave A remains inactive. A traced candidate build for the earlier `a7754c1c` head passed all-cache structural and same-input legacy/financial parity on 50 patients and 94 bills, and a real old/candidate private Caddy rehearsal restored the old pair. That artifact is **not** a release candidate for later code heads.

The release implementation now has a signed startup receipt, exact main-CI issuer, private candidate launcher, actual loaded-Caddy route adapter, old/barrier/candidate route preparation with retained old static assets, a sealed manifest producer, concrete public/private HTTP probes, and a journaled activation/recovery CLI. These are code checkpoints, not activation evidence. The old serving backend still lacks an in-memory code SHA, so the release uses protected byte/behavioral equivalence and keeps that limitation explicit. Final code must still be merged, rebuilt from the exact main SHA, privately rehearsed again, signed only after all independent gates, and switched through the public barrier with rollback verified.

The previous PR #97 head `29e21241` had a red backend CI run because the rule-surfacing audit still looked for the old capability string. The audit now requires the signed startup check and draft cache; its 26 tests pass, including removal-of-signature rejection. A local full suite at the previous head produced 3,988 passes and exactly those 11 audit failures in 889 seconds. After the fix, 224 focused deploy/API/audit tests, Ruff, and manifest parity passed; generated rules and the next hosted CI run remain pending. Never treat the draft PR, an earlier candidate, or a prepared route manifest as authorization to change the public route.

### Subtasks
- [ ] Reconcile all 25 groups: the historical PR #89 baseline has 516 hidden static inventory identities (20 focused entries including a synthetic radiation grouping, plus 496 broad authored IDs) and 526 possible runtime IDs (30 focused plus 496 broad). After source-backed corrections, track 32 focused identities across 18 groups, of which 29 can currently emit rows: #9 and #22 are unavailable until missing dates are ingested, the unsupported hyperthermia grouping cannot emit, and two distinct radiation course candidates were added. Keep the 496 broad authored identities separate from claims of live evaluability. Check emitted IDs, source rows, `billable`/review semantics, input availability, stable identity, monetary paths, and the ten explicit exclusions.
- [ ] Capture baseline code/data identities, financial totals, current patient/cohort payloads, and active cache build ID without changing production state; record representative and negative cases.
- [x] Write detailed focused, broad, and financial/release architecture maps in `plans/billing/`; independently review and approve this task plan and those maps before production code changes.
- [x] Inventory the four flat-only monetary focused outputs from their detector results and patient-report totals before implementing their display; identify exact amount basis, source strength, and whether they currently participate in headline calculations.
- [ ] Extend the canonical finding/evaluation contract with per-rule outcome classification, stable distinct finding/evaluation identities, honest missing-input/skip status, source evidence, review-only status, and a separate typed financial projection while preserving detector decisions.
- [ ] Integrate the 18 focused groups into one-pass evaluation, including explicit classification of the four money-bearing groups and source-derived identity for multirow detectors; add group-level regressions.
- [x] Correct the duplicate-exam ten-day false negative in a separately reviewed detector change, with A/day1 and two B/day2-3 line regressions and unchanged existing cases.
- [x] Resolve the admission 60-day detector's use of service-range end as a purported submission date: official handbook and current SUT do not support the old inference; legacy false emission removed and a per-claim unavailable evaluation added for the missing period-closure date (`5af8985a`; 35 targeted tests/Ruff and independent review passed).
- [x] Correct Tablo 15 #22's mismatch predicate separately: the official handbook concerns an outpatient exam date versus acceptance date, which is not ingested; false inpatient/procedure-date emissions are removed and per-claim unavailable status records the missing input (`632fc517`; 57 targeted tests/Ruff and independent review passed).
- [x] Correct the donor detector's unreachable category branch from official El Kitabı §4.2/Table 15 #24: same-claim donor-preparation evidence now flags distinct exam lines as review-only, with no claim of confirmed MEDULA donor identity (`e22f0261`; 34 direct/provenance tests and Ruff passed).
- [x] Correct the dental GA zero/credit-only anesthesia false positive in a separately reviewed detector change, without inferring a missing uplift.
- [x] Correct yatak zero/credit-only bed false positives and non-ICU evidence attribution separately, preserving the existing bed-day financial calculation (commit `9689247f`; 22 direct tests and Ruff passed; independent review approved).
- [x] Correct radiation predicates against current EK-2B explanatory cells: design, planning, dose, device, application, and session limits now use source-backed review evidence, grouped multi-day quantities are not treated as confirmed same-day excess, and billed amount stays separate from null unverified risk. Distinct 800370 and 800430 course identities were added; unsupported hyperthermia grouping is unavailable. Detector/direct integration passed 49 tests and Ruff with independent source/diff review (`e0ca7875`). Full inventory/report/cache parity remains a release gate.
- [x] Correct the dental precious-metal matcher in a separate Q9 detector checkpoint: reject term-local negations such as `altın içermeyen`, `platin içermeyen`, and `altınsız`, preserve independently affirmative metal/product matches and first-winner/raw ordering, and verify real material-line regressions against the official July/August 2026 §2.4.1(1) source evidence before promotion (`2ee13b08`; 102 targeted tests/Ruff and independent review passed). Free-text ambiguity remains a classification hold.
- [x] Correct EK-3B-1/2 false findings in a separate, independently reviewed checkpoint: separate lexical candidates from matched/not-matched/unavailable annex applicability; honor sterile-glove, inpatient syringe and blood-strip, dressing oxygen, and viscosupplementation exceptions; preserve ordinary glove, urine-strip, and inflow-catheter cases. Use actual owned claim/header facts, clear stale derived flags, expose nullable regulatory status without changing package CSV flags, and require resolved eligibility before any material uplift. Prove dictionary/typed validator, pricing DTO, precheck, uplift, source-line identity, and full patient/bill/cohort financial deltas. If legacy money changes, merge this correction separately and recapture the same-input Wave A baseline before release; never waive financial parity.
- [x] Keep the EK-3B reference catalog source-only: mark entries not evaluated for a patient, preserve conditional exceptions, remove the unsupported effective-date display, and avoid blanket non-reimbursable labels. Retain its collection keys for compatibility and test the rendered explanation.
- [ ] Classify transplant carveouts, missing monetary source/basis, and unverified dental uplift as review/unavailable with null confirmed amount, preserving existing patient/cohort totals.
- [ ] For line-owned financial reviews, show an observed billed charge only when it is reconciled to the exact procedure claim line, with a distinct source/basis field; keep unverified risk or recoverable uplift null and outside all totals. Independently match the observed charge against pinned procedure Parquet before activation. Dental claim-level expected fee remains unavailable as net recovery without a verified basis.
- [ ] Freeze and independently review the exact 496-ID broad classification matrix: source authority/version, authored action meaning, predicate sufficiency, claim-field provenance, proof or withholding gate, and stable reason for every ID, including all 31 `ai_generated_pending_review` rows; retain raw parity and fail closed when an authored condition/action/source digest changes.
- [ ] Integrate the seven broad engines with rule-level authored-action classification and status metadata; account for every authored ID as eligible finding, positive, review, monetary, or unavailable without blanket conversion to violations.
- [ ] Carry canonical nonfinancial, review-only, and financial projections through patient report, cache, cohort index, API, and old-cache fallback; prove identity parity and bounded honest status summaries without new aggregate money.
- [ ] Persist each bill's exhaustive v2 evidence in a separate build-scoped table keyed by `patient_id::claim_id`; keep default bill JSON bounded, validate exact bill/detail key sets and claim ownership, and reconcile bill previews/coverage against its own detail. Do not equate a bill slice with patient evidence filtered by claim when cross-claim context can differ.
- [ ] Reconcile the existing `validate_claim()` public `violations`/validity contract with typed positive/review outcomes; migrate its API, chatbot, frontend validator, and tests together so public counts no longer call permitted or informational actions violations, retaining a documented compatibility path.
- [ ] Render eligible findings and review-only statuses in the existing patient/cohort Compliance UI and sourced monetary outcomes in the existing patient/cohort financial sections; preserve links, pagination, and old-cache honesty.
- [ ] Update surfacing inventory and regression gates so the 25 groups are classified correctly, visible where eligible, and not double counted; retain the ten excluded synthetic identities.
- [ ] Implement a single-activation release gate according to `plans/billing/2026-09-27-wavea-release-gate.md`: listener-aware read-only discovery, protected and privately rehearsed **actually serving** old runtime/cache/effective env/Caddy tuple, and independently reviewed legacy-equivalence attestation without a fabricated old code SHA. Current P0 correctly blocks because old health lacks code SHA, frontend `.env` drifted after its listener started, and protected snapshots are missing.
- [ ] Build an immutable candidate backend/cache/frontend on private :8002/:3099 and verify it through a private :3100 route: stable source-byte manifest, all patient/bill/cohort payloads and financial/action parity, exact CI/code/frontend/build identity, old/new client and asset behavior, plus resource/duration evidence. Never alter :8001/:3000 or the public route during preparation.
- [ ] Replace the current frontend-first deploy with one Caddy maintenance barrier and one public route switch to the verified candidate pair, under a shared lock and fsynced recoverable journal. Recheck SHA/artifact/input identity immediately before switching; rehearse rollback to the old :8001/:3000 routes and restart from protected artifacts on disposable fixtures. Split the 25-minute workflow if measured preparation/recovery cannot fit without weakening same-SHA/stale-head guarantees.
- [ ] Run focused domain, API/cache, frontend, financial, and release-gate tests; then run full backend/frontend CI-equivalent checks, generated-artifact checks, and a no-drift financial snapshot comparison.
- [ ] Independently review the final source, classification, UI, and release diff; resolve all correctness findings and re-run affected checks.
- [ ] Check branch CI before pushes; publish reviewable checkpoint commits/PR, obtain final hosted CI and review feedback, then merge for one production activation.
- [ ] Verify the merged production deploy, active cache build, every cached patient/cohort payload, representative live findings and statuses, financial-path identity/amount labels, unchanged totals, and rollback readiness; record exact evidence and remaining limits.

### Out of Scope
The ten synthetic-identity rows previously excluded from Wave A; new clinical/regulatory rule decisions; new claim-data ingestion solely to make dormant authored IDs fire; changing existing savings/recovery totals; treating positive or review-only outcomes as compliance violations; activating partial checkpoints in production.

### Review
Plan independently reviewed and approved for staged implementation by three agents after correction of classification, identity-count, detector-correctness, retained-client, and deployment-timeout gaps. Product integration and production payload baseline capture remain pending. Latest main is `bbf9acaf` (merged PR #96); its [post-merge CI](https://github.com/Safa675/Bilun/actions/runs/36316401829) and [Deploy](https://github.com/Safa675/Bilun/actions/runs/36316669982) passed. The original read-only audit found 18 focused groups (20 static inventory identities, expanding to 30 possible emitted runtime IDs because radiation had 11 IDs) and seven broad engines (496 authored IDs) hidden. Subsequent correctness fixes changed the current focused tracked/emittable inventory as recorded above; these IDs are possibilities, not guaranteed live findings. Financial, positive, review, missing-input, and stable-identity classification must precede activation. A read-only synthetic baseline at `bbf9acaf` covers 50 patients, 94 bills, and 636 legacy validator rows; its 5.25 MB JSON is saved outside the worktree at `/root/artifacts/bilun-wavea-2026-09-27/baseline-synthetic.json` (SHA-256 `12cfec6940a2beae19de08881e56c88bd018bc166a24ee9e56f536317ff4f5b3`). Patient report baseline sums: SGK uplift/recoverable ₺348,340.41, audit exposure ₺673,902.64, action count 452; bill report financial sums match, with 563 bill actions. These are synthetic comparison fixtures, not production values. A read-only production `/health` response on 2026-09-27 reported `status=ok`, `database_reachable=true`, `cache_ready=true`, active build `b1fdcb54-0abb-426a-94fb-f00d006144a7`, and gazette version `2026-07-07`. This establishes only the health/build baseline; authenticated patient/cohort payloads and source-code identity still need capture before release. A read-only unauthenticated request to `/api/compliance-index?limit=1` returned HTTP 401, so the health response is not a substitute for private payload verification.

Checkpoint commits on the integration branch: `c19293ff` adds seven real line IDs and fixes duplicate-exam matching (independent review, 46 focused tests/Ruff); `f45f7f54` adds stable per-line evaluation IDs through patient/cohort and fixes mixed old/new dedup (independent review, 82 targeted tests/Ruff); `f64ee242` records the reviewed plan and four-group financial inventory; `845f6850` freezes all 496 broad corpus IDs with conservative candidate classifications (independent review, 15 tests/Ruff); `d46dc53b` verifies canonical finding IDs and fails on conflicts (independent review, 25 cohort/API tests/Ruff); `f553edb0` fixes zero/credit-only dental anesthesia false positives (independent review, 18 direct tests/Ruff). All commits are local; the 25-group product, public API/UI, full release gate, full CI, merge and live verification remain outstanding.

Further reviewed local checkpoints: `9689247f` corrects ICU-overlap charge/evidence attribution; `8acce3ab` adds 42-ID information-only payment traceability metadata; `5af8985a` and `632fc517` remove false #9/#22 date verdicts and add unavailable-status helpers; `e22f0261` corrects donor same-claim evidence; `e0ca7875` aligns radiation review candidates with current EK-2B and leaves excess risk null. Read-only release-host findings are recorded in `reports/rule-engine-surfacing/2026-09-27-wavea-host-preflight.md`. These remain local checkpoints, with no public activation.

`0151aeec` adds an independently reviewed, still unintegrated focused adapter for all 18 groups: 32 tracked identities, 29 presently emittable, source-owned line IDs, quarantined stale #9/#22/hyperthermia rows, explicit missing/unavailable statuses, and no confirmed financial amount. Final focused and existing El Kitabı tests passed 28 cases with Ruff. The public report/cache/UI remain unchanged until the later integration checkpoint.

`3b801e9e` subsequently integrated the 18 focused groups into the canonical patient/bill report in one detector pass. The 50-patient/94-bill same-input synthetic comparison against the `bbf9acaf` baseline found **0/50 patient and 0/94 bill differences in legacy report fields**, with unchanged ₺348,340.41 SGK/recoverable sums, ₺673,902.64 audit sum, and 452 patient/563 bill action counts. The separate focused-evidence checkpoint now adds source-linked review and null-amount financial rows, exhaustive 32-ID status detail in a build-scoped patient table, exact cohort counters and sparse paginated review/financial rows, and draft-gated API/old-cache fallback. Its cache trial wrote 50 patient detail rows and one index alongside the 50 reports/94 bills in 122.48 seconds wall time, using about 1.05 GiB peak RSS. The 50-patient detail has 52 review rows and no financial trigger; an additional real-detector fixture verifies both review and financial rows through patient/bill/cache/cohort APIs. Rebuilding the sparse index from those detail blobs produces 52 rows in a 285 KB JSON singleton. Current default patient JSON averages 83 KB; trimming the 32 focused statuses from that default is the next bounded-payload checkpoint. The draft cohort fallback measured 171 ms median across the 50 reports versus 21 ms for a stored-index slice; it stays fail closed on missing/corrupt index or rows. The focused evidence/API/cache suites passed **118 tests**, changed-file Ruff and diff check; a production app integration test also verified unauthenticated 401 and authenticated 200 for all new evidence endpoints. This is an independently reviewed draft-only checkpoint; the seven broad groups, UI, complete-25 attestation, full CI, and release gate remain pending.

`3daf489b` wires all 25 groups into report/cache/API as draft-only evidence, including 50 patient and 94 independently scoped bill details. The matched-input build used four-row bill-detail writes and completed in 126.28 seconds with 1,448,152 KB peak RSS, versus 131.46 seconds/1,654,232 KB before streaming and 122.48 seconds/1,097,784 KB for the focused-only build. Default JSON averaged 65.3 KB per patient and 46.0 KB per bill. Legacy report fields differed in 0/50 patients and 0/94 bills; SGK ₺348,340.41, audit ₺673,902.64, and 477/638 current patient/bill actions were unchanged. The 528-rule, 25-group evidence is still unavailable publicly until independent source/financial/rollback attestation and one activation pass.

---

## Task: Correct EK-3B annex applicability before Wave A activation

### Goal
Prevent EK-3B-1/2 lexical matches from becoming unsupported billing violations, reimbursement decisions, or material uplift; preserve exact source-line ownership and record any resulting financial baseline change separately.

### Subtasks
- [x] Pin and compare official SGK July/August 2026 annex workbooks, extract the exception rows, inspect current SGK notices, and document the limit of historical service-date applicability.
- [x] Audit every existing consumer of EK-3B match flags and money, including legacy validator, material pricing, patient/bill precheck, uplift, and cohort totals; record the before-change baseline boundary.
- [x] Define an immutable tri-state annex assessment (`matched`, `not_matched`, `unavailable`) with candidate row, match kind, and stable reason; keep lexical matching separate and expose only confirmed candidates through old boolean helpers.
- [x] Apply the source exceptions and use/setting qualifiers to both dictionary and typed paths: surgical sterile gloves; inpatient disposable syringes; inpatient blood-sugar strips without broadening that condition to urine strips; dressing-only oxygen; conditional viscosupplementation; preserve ordinary gloves and exact inflow-catheter matches.
- [x] Recompute nullable regulatory flags from actual claim/header facts, clear stale derived flags, and keep the independent package CSV `is_bundled` fact unchanged. Legacy material pricing and API DTOs must distinguish unknown from reimbursable or excluded.
- [x] Keep unresolved or fuzzy-only annex matches out of material uplift; require affirmative resolved eligibility, with regression cases for source-line ownership, duplicate names, code-resolved candidates, stale flags, and missing care/clinical-use facts.
- [x] Run focused suites, full financial patient/bill/cohort comparison, Ruff and generated-artifact checks; independently review the correction and publish it as an isolated checkpoint/PR if existing decisions or money change.
- [ ] Rebuild and pin a new same-input Wave A baseline after the correction is merged, then keep the combined 25-group activation blocked until full-cache parity and rollback gates pass.

PR #98 merged at `4af38b28` after green hosted backend/frontend CI; the synthetic patient/bill/cohort financial trees remained unchanged. Its production deployment and post-merge baseline capture remain separate Wave A release gates.

### Out of Scope
Changing package CSV flags, inventing clinical use or care setting, promoting unknown materials to payable, changing unrelated monetary rules, or treating the 2026 annex file name alone as proof of every earlier service interval.

### Review
The interface and consumer boundary were reviewed before edits against the pinned annex rows and the read-only monetary impact audit. The official consolidated announcement and current GSS listing were checked on 2026-09-27; historical service-date applicability remains a source-manifest gate.

---

## Task: Fix PR #94 CI after repricing removal

### Goal
Make PR #94's backend CI pass by reconciling the committed registry-coverage artifact and cohort-tier test with the retired repricing rule, without changing service-date pricing or unrelated coverage data.

### Subtasks
- [x] Remove only the obsolete `gazette_repricing` row from `sut_registry_coverage.parquet` and verify every remaining row equals the current registry-derived summary.
- [x] Update the cohort-tier test to the current 8/16/26 split and assert former demo patient 0011 is no longer Tier A.
- [x] Run the exact backend CI gates on the final branch: Ruff, full Python test suite, rule compiler artifact check, and manifest parity audit; inspect binary/test diff.
- [x] Commit and push the fix to PR #94, then confirm the new CI result.

### Out of Scope
Restoring the repricing algorithm, broad synthetic regeneration, other SUT coverage changes, PR merge, deployment, or production cache rebuild.

### Review
Local verification passed on the narrow fix: Ruff; full Python suite **2774 passed, 9 warnings**; rule compiler `--check` found **134 byte-identical artifacts**; manifest parity scanned **23 manifests with 0 issues**; targeted registry and cohort-tier suites passed. The parquet change contains only the obsolete registry row removal, with all 46 survivor rows/schema/order unchanged. Full pytest and an interrupted duplicate compiler check temporarily rewrote unrelated drug manifests; their generated changes were cleaned before commit. Fix commit `10d04811` was pushed to PR #94; GitHub CI run `36150469229` completed successfully for backend and frontend.

---

## Task: Publish gazette repricing removal PR

### Goal
Put the completed and verified removal on a fresh branch from current `origin/main`, then open a reviewable PR containing only that removal.

### Subtasks
- [x] Confirm the old PR #92 branch is merged and choose a fresh branch from current `origin/main`.
- [x] Audit and commit the removal patch without unrelated or sensitive additions.
- [x] Transfer the commit to a fresh `origin/main` branch; resolve any conflicts and verify the resulting diff and focused checks.
- [x] Push the branch, open and attach a PR, and confirm its commit/file scope.

### Out of Scope
Merging the PR, deploying, rebuilding production caches, or adding a replacement pricing rule.

### Review
Opened PR #94 on `fix/remove-unsupported-gazette-repricing` against current `main`; the first PR commit contains only the 70-file repricing-removal patch and no older PR #92 commits. Fresh-branch verification: 104 focused backend tests passed (one existing pytest deprecation warning), 134 remaining rule/manifest artifacts were byte-identical, surfacing audit check and Ruff passed, and the worktree/diff were clean before publication. No deployment, production cache rebuild, or merge was performed.

---

## Task: Remove unsupported post-service gazette repricing rule

### Goal
Remove the 30-day price-staleness opportunity from Bilun's runtime and product surfaces so no later SUT tariff increase is shown as recoverable for an earlier procedure.

### Subtasks
- [x] Inventory all runtime, API, frontend, registry, compiler, synthetic, test, and generated references; lock the deletion boundary.
- [x] Remove the detector, billing adapter, runtime registration, rule metadata, opportunity fields and totals, and API projections without changing service-date price lookups.
- [x] Remove patient/cohort UI sections, deep links, translations, frontend types and tests for the opportunity.
- [x] Remove dedicated fixtures, synthetic scenario generation, demos, tests, and generated rule/audit artifacts that specifically advertise repricing.
- [x] Update current architecture/coverage documentation so it no longer claims this rule is implemented; leave historical plans/reports identifiable as historical when appropriate.
- [x] Verify no live repricing references remain, run focused backend/frontend checks and relevant generated-artifact checks, and record results.

### Out of Scope
Changing valid temporal EK-2/B or EK-2/C lookups, adding a replacement pricing detector, editing unrelated SUT rules, regenerating all synthetic cohort data without a dependency need, deployment, or production cache rebuild. PR publication is tracked separately above.

### Review
Removed the post-service repricing evaluator, billing adapter, API/report/cohort fields, registry/compiler entry, patient and optimizer UI, translations, synthetic demo, and current documentation claims. Historical EK-2/B and EK-2/C service-date price lookups remain. Removed the dedicated rule source/compiled JSON/empty manifest/golden and regenerated the rule-surfacing audit matrix and report. The checked-in synthetic cohort was already out of sync with a pristine-HEAD regeneration, so only retired scenario tags, one demo workbook column, and one obsolete metadata row were mechanically scrubbed from its binary artifacts; all other logical records/cells were verified unchanged.

Verification: backend focused suites 139 passed; synthetic billing 22 passed; frontend focused Vitest 63 passed and `tsc --noEmit` passed; temporal pricing 2 passed; synthetic validator and Tier A assertion passed; rule compiler `--check`, surfacing inventory `--check`, changed-file Ruff, compileall, and `git diff --check` passed. A broader `tests/unit` run reached 231 passed with no failures, then was interrupted because it was still at 7% after two minutes. No deployment or production cache rebuild was performed.

---

## Task: Phase 5 Checkpoint 4 — loop-complete closure metadata

### Goal
Record truthful loop-complete metadata for the verified Checkpoint 4 without modifying production code, tests, generated audit artifacts, plans, or configuration.

### Subtasks
- [x] Replace pending-commit closure status/phase/status values with truthful `loop_complete` wording.
- [x] Record the exact final acceptance results, artifact-hash reconciliation, added-line secret/patient-data scan, and temporary symlink check.
- [x] Preserve empty blockers, explicit exclusions/deferred Wave B/C/D scope, and the no-push/no-merge/no-deploy/no-cache-rebuild boundary.
- [x] Run JSON parsing and `git diff --check` after the metadata-only update.

### Out of Scope
Production code, tests, generated audit artifacts, plans, configuration, detector medical semantics, new detector migrations, projection rule-ID allowlists, registry dispatch changes, pricing or financial behavior, production cache rebuilds, commits, pushes, PRs, merges, deployments, and deferred Wave B/C/D or broad prose-family candidates.

### Review
Loop is complete and verified. Final acceptance evidence is focused inventory `17 passed in 2.53s`; authoritative combined backend `272 passed, 1 warning in 32.46s`; frontend `4 passed files, 29 passed tests`; `npx tsc --noEmit` exit 0; generator `--check` exit 0; compileall exit 0; `git diff --check` exit 0; artifact hash reconciliation pass; added-line secret/patient-data scan pass; and temporary frontend/node_modules symlink absent. Blockers are empty. Deferred Wave B/C/D and broad prose-family candidates remain outside scope and require separately approved future scope. No push, PR, merge, deploy, or production cache rebuild occurred; no commit was created. This loop is ready for the acceptance commit, but no further action is required in this loop.

---

## Task: Phase 5 Checkpoint 2 — generic cohort/cache/API projection

### Goal
Project all five supported canonical nonfinancial `RuleFinding` rules through existing patient/bill cache payloads, the generic cohort compliance index, and existing API routes with stable identity, honest evaluation availability, and unchanged financial totals.

### Subtasks
- [x] RED→GREEN: add the smallest cohort regression proving a selected Wave A canonical finding was rejected, then remove the K21/K26 product gate with generic fail-closed serialized-contract validation.
- [x] Remove the rule-ID allowlist and consume canonical serialized findings/evaluations generically without duplicating per-rule mappings, rebuilding finding IDs, or calling detectors.
- [x] Preserve canonical `finding_id == action_id` and validate patient/claim/line ownership and generic line-kind source identity across patient → cache → cohort → API.
- [x] Carry canonical finding fields needed by patient/bill/cohort consumers, including identities, detail/source/severity/evaluation metadata, existing display fields, and null money, while collapsing exact duplicates.
- [x] Aggregate evaluations generically by `(rule_id, claim_id)` so distinct claim evaluations and missing-input statuses are retained; keep missing top-level cache artifacts unavailable rather than fake zero.
- [x] Extend synthetic cache/API regressions for Wave A visibility, future-rule passthrough, stable line-kind IDs, duplicate collapse, null money/unchanged totals, invalid-row fail-closed behavior, and K21/K26 compatibility.
- [x] Run required domain/cache/API tests, compile changed Python files, enforce the no-allowlist/no-ID-rebuild invariant, and run `git diff --check`; record exact evidence in the checkpoint journal.
- [x] Set state to `checkpoint2_accepted` after independent Chief review.

### Out of Scope
Frontend changes, detector-set expansion or medical logic changes, audit generator/matrix/report changes, pricing formulas or financial semantics, DuckDB schema migration, new API routes, deployment or production-cache work, source dirty work, commits, pushes, PRs, merges, and any rule outside the five canonical rules.

### Review
Checkpoint 2 is accepted by Chief. `cohort_compliance.py` now projects serialized findings/evaluations generically with no rule-ID allowlist and no finding-ID reconstruction; canonical IDs are copied unchanged, future well-formed rules pass through, exact duplicates collapse deterministically, and evaluations retain distinct `(rule_id, claim_id)` statuses. Existing cache/API routes and payload JSON were reused without schema migration or cache rebuild. Independent verification: `255 passed, 1 warning` for all billing-domain tests plus claim-compliance and compliance-index API suites; financial invariance `4 passed, 1 warning`; compileall, `git diff --check`, and the forbidden-symbol invariant passed. Audit generator/matrix updates remain intentionally deferred to Checkpoint 4; frontend work is authorized next as Checkpoint 3.

---

## Task: Phase 5 Checkpoint 1 — canonical finding contract + domain plumbing

### Goal
Implement one canonical nonfinancial rule-finding evaluation path for K21, K26, `tablo15_10`, `tablo15_20`, and `tablo15_5`, preserving legacy analyzer output while making patient claim-compliance projection reuse the precomputed batch.

### Subtasks
- [x] RED→GREEN: add deterministic claim/procedure/drug/material finding identity and typed `RuleFinding` / `RuleEvaluation` / batch contract.
- [x] RED→GREEN: add canonical one-pass evaluation for exactly the five authorized detectors, including explicit missing-input evaluations, ownership validation, normalization, de-duplication, deterministic ordering, and null money.
- [x] RED→GREEN: route `analyze_claim` through the canonical evaluation for the five detectors while preserving legacy flat violations and detector order/fields.
- [x] RED→GREEN: make `compute_patient_billing_report` evaluate the batch once and make `project_claim_compliance` a pure projection with zero detector/analyzer calls.
- [x] RED→GREEN: surface the three selected Tablo 15 findings in patient `claim_compliance`, preserving K21/K26 identity/serialization compatibility, duplicate handling, missing context behavior, and unchanged financial totals.
- [x] Run the required focused suites, compileall, and `git diff --check`; record exact RED/GREEN and final verification evidence in the checkpoint journal.
- [x] After all tests are green, update checkpoint state and complete this review section with exact changed paths/results.

### Out of Scope
New Wave A cohort visibility, API/schema/route changes, cache schema changes, frontend work, audit generator/matrix/report changes, pricing/totals semantics, detector medical/regulatory semantics, deployment, production cache rebuild, pushes, merges, and migration of any detector outside the five authorized rules. A minimal existing-K21/K26 cohort compatibility fix was accepted because canonical five-component IDs otherwise regressed across patient and cohort projections.

### Review
Checkpoint 1 is accepted by Chief. Canonical finding identity includes URL-quoted `line_kind` between `claim_id` and `line_id`; K21/K26 cohort projection preserves and validates that identity without surfacing the three Wave A rules yet. Compileall exited 0; focused domain/cohort/API verification passed `96 passed, 1 warning`; the full billing-domain plus claim-compliance API gate passed `244 passed, 1 warning`; `git diff --check` exited 0. Phase 5 Checkpoint 2 is now authorized; frontend work remains pending its acceptance.

---

## Task: Rule Engine surfacing audit + generic finding surface (2026-09-18)

### Goal
Execute `plans/billing/2026-09-18-rule-engine-surfacing-audit-plan.md`: produce exact runtime/visible/hidden/duplicate/financial counts and the complete hidden-rule list before migrating additional existing rules into a generic finding surface.

### Subtasks
- [x] Freeze audit definitions and baseline: registry family, runtime detector, finding kind, visibility, duplicate, and money semantics.
- [x] Build a deterministic static inventory of `analyze_claim` and `compute_patient_billing_report` runtime calls and reconcile it with `RULE_REGISTRY` without treating the registry as a dispatcher.
- [x] Trace every runtime output through report fields, `recommended_actions`, `claim_compliance`, totals, cache/API, and patient/cohort frontend surfaces.
- [x] Generate the machine-readable coverage matrix plus human audit report with exact counts, hidden list, duplicate groups, and financial/nonfinancial classification.
- [x] Add an inventory completeness regression so new runtime detectors cannot appear without a surfacing classification.
- [ ] Review the audit output and lock migration scope before changing runtime/UI behavior.
- [ ] Define one canonical finding contract and migrate the approved hidden nonfinancial validation wave without one-off per-rule wiring.
- [ ] Verify patient/cohort reachability, old-cache honesty, stable finding identities, duplicate behavior, and unchanged financial totals for nonfinancial migrations.

### Dispatch scope: baseline audit only (Phases 0-4)
- [x] Phase 0: freeze taxonomy, source revision, registry breakdown, canonical runtime entrypoints, and product projection entrypoints.
- [x] Phase 1: generate a deterministic static runtime inventory for `analyze_claim` and `compute_patient_billing_report`, including gated calls and registry/artifact reconciliation.
- [x] Phase 2: trace every runtime output through report fields, recommended actions, claim compliance, dedicated sections, and monetary totals.
- [x] Phase 3: trace cache/API plus patient/cohort frontend reachability and deep-link behavior; treat Rule Database as metadata only.
- [x] Phase 4: generate the exact JSON matrix and Markdown audit report, including hidden findings, duplicate groups, unknown mappings, and separate inventory-level counts.
- [x] Add and execute completeness tests for canonical runtime calls, the current two-rule claim-compliance allowlist, registry-only classification, and unmapped runtime-call failure.
- [x] Review the Phase 0-4 diff and executed evidence, create coherent local audit checkpoint commit(s), and stop at `ready_for_review` for Chief acceptance.

### Out of Scope
New SUT/medical detectors, diagnosis-procedure medical-necessity logic, coverage-status metric manipulation, unrelated pricing/recovery changes, and production deployment/cache rebuild during the audit phases.

---

## Task: PR87 claim-compliance correctness fixes (2026-09-18)

### Goal
Implement `plans/billing/2026-09-18-pr87-claim-compliance-fixes-plan.md` on `feat/compliance-k21-k26` so K21/K26 are correct, cohort evaluation payloads are bounded, and claim-compliance findings have their own reachable server-side pagination path.

### Subtasks
- [x] Enforce same-day K21 semantics and replace the different-day regression.
- [x] Reconcile K26 diagnosis presence from header plus normalized primary diagnoses while preserving blank-vs-unavailable behavior.
- [x] Replace unbounded cohort evaluation identities with exact counts plus bounded non-evaluated details and truncation metadata.
- [x] Fetch and paginate `surface=claim_compliance` independently in the frontend, preserving active patient/cohort filters and total-count badges.
- [x] Make claim-compliance monetary summary values nullable in TypeScript and render them nonfinancially.
- [x] Run focused backend/frontend tests, Ruff, TypeScript, changed-file ESLint, then full backend/frontend suites where feasible.
- [x] Record exact verification outcomes in `tasks/k21-k26-result.md` and complete this review section.

### Out of Scope
New SUT detectors, monetary integration for claim-compliance, broad compliance redesign, diagnosis-conflict adjudication, production cache rebuild/deploy, pushing or merging the branch.

### Review
Implemented from plan commit `58f3308a` on `feat/compliance-k21-k26`. K21 now joins bundled services to exact 510090 dates. K26 reconciles a nonblank header diagnosis with normalized primary `ClaimDiagnosis` rows while preserving explicit-blank versus unavailable provenance. Cohort cache data stores per-patient status counts plus at most 20 non-evaluated details; API responses expose exact filtered counts without unbounded successful evaluation identities. Compliance surfaces are fetched and paginated server-side; large patient cohorts fall back to a JSON POST when the GET query would exceed 6,000 characters. Claim-compliance money remains nullable/nonfinancial and old-cache absence stays unavailable.

Final verification on the final tree: focused backend **84 passed**; focused frontend **22 passed**; full backend **2631 passed**; full frontend **266 passed**. Changed-file Ruff, ESLint, TypeScript, and `git diff --check` passed. Independent review first found and drove fixes for stale cohort aggregate state and backend-first rolling-deploy compatibility; the final fresh `codex review --uncommitted` returned **0 findings / patch is correct (0.91 confidence)**. Its read-only sandbox could not run pytest, so the writable-workspace suites above are the execution evidence. No production cache rebuild/deploy, push, merge, or commit was performed.

---

## Task: K21 + K26 reviewer blockers

### Goal
Prevent late-money inference crashes and show accurate scoped presentation counts while retaining legacy actions and financial totals.

### Subtasks
- [x] Confirm the three requested fixes and existing test/runtime conventions; review this narrow plan against the request.
- [x] Use full inference for cohort rows and regress >100 null-money findings before a monetary legacy row, including preserved totals and row money.
- [x] Count scoped claim findings in patient/claim KPI and tab badge only; regress patient, claim and legacy-only counts.
- [x] Omit the claim-compliance dashboard badge for old caches and assert rendered absence.
- [x] Run focused backend/frontend tests, changed-file lint and tsc; record exact outcomes in tasks/k21-k26-result.md.

### Out of Scope
Pagination redesign, broad refactoring, other detectors, money/action integration, other worktrees, commits, pushes and live changes.

### Review
46 backend and 18 frontend tests passed; final tsc and Ruff passed. Changed-file ESLint found only the existing PatientWorkspaceViews navigation-effect error; HEAD stdin lint reproduced the same error, and all other touched frontend files passed lint. No suppression or out-of-scope navigation rewrite. Full inference regression demonstrated red before/green after; scoped counts and old-cache badge have rendered assertions. Exact commands, limitations and results recorded in tasks/k21-k26-result.md. No commit/push/live changes.

---

## Task: K21 + K26 reporting reachability

### Goal
Expose only the existing ICU bundled leakage and missing diagnosis detectors through full-context reporting, cache/API and native compliance UI without any money contribution.

### Subtasks
- [x] Verify normal ingestion provenance and positive/negative scenarios before wiring detectors.
- [x] Add backward-compatible availability tracking and a narrow report-owned nonfinancial projection with stable claim/line identities.
- [x] Connect cache/index/API and native frontend filtering/rendering with patient links.
- [x] Run real-function ingestion integration tests, financial regressions, frontend tests, typecheck and lint sequentially for pytest.
- [x] Replace unbounded evaluation rows with a compact summary and closed, bounded details; verify 120-evaluation rendered regression.
- [x] Inspect artifact drift and record exact evidence in tasks/k21-k26-result.md.

### Out of Scope
Engine merging, validator changes, other detectors, rule catalogs, shipped data, live services, commits, pushes and PR creation.

### Review
K21/K26 implemented through normal ingestion/context, report-owned nonfinancial projection, cache/index/API and native UI. Chief independently reported 71 backend tests and 9 frontend tests passing before the final compact-summary change; typecheck and Ruff passed. Final UI verification: dashboard Vitest file 10/10 passed; ESLint passed for the test and table. Large-list regression verifies 120 evaluations, correct counts, closed details bounded to 20 entries, distinct unknown/clean empty states, findings, links and null money. Prior status inspection showed only scoped source/tests/tasks changes, no catalog/generated-data drift; no new broad inspection or backend run in this final finish. Evidence and limitations: tasks/k21-k26-result.md. No commits, pushes or live changes.

---

## Task: 2026-08-29 SUT rule corpus (PR 80 follow-through)

### Goal
PR 80 ingest is on this branch; encoded YAML/wave keys resolve against the 2026-08-29 clause corpus; compile + coverage artifacts are regenerated; the two new grandfathering bents are encoded; inventory/coverage goldens match the live 08-29 corpus.

### Subtasks
- [x] Remap stale `coord#hash` cites in YAML + `gate_b_wave_config.py` to new hashes (similarity-matched)
- [x] Remap positional `C*` `gate_b_sources` + `clause_type_overrides.yaml` (07-01 → 08-29 id shift)
- [x] Update YAML messages for real law changes (4.1.4.c, 4.2.1.C-3/C-5.a, 4.2.8.A.b, 4.2.14.C KLL, 4.2.15.D-2 radiology)
- [x] Encode new `4.2.1.C-3.d` and `4.2.1.C-5.d` grandfathering rules
- [x] `compile_rules.py` then `compile_rules.py --check`
- [x] `build_sut_coverage.py`
- [x] Changelog
- [x] Recompile §4.2.1 against current coverage so empty-hash `is_in_force=false` ghosts leave traces (pending 16+2)
- [x] Skip extractor empty-hash out-of-force rows in Gate B export
- [x] Freeze coverage/C* inventory goldens to live 08-29 counts (215 gaps / 28 deontic / 215 C* / 249+15 eligible)
- [x] Recompute w4 tier_b resolved C* set from live YAML cites
- [x] Decision note for accepted remap tolerances
- [x] Targeted pytest; `git status` after (pytest can mutate artifacts)
- [x] Full `tests/unit` (2564 passed, 9 skipped)
- [x] Commit, push, update PR #84

### Review
PR 80 ingest is on this branch. Encoded YAML/wave keys resolve against the 2026-08-29 corpus. Gate B export skips extractor empty-hash out-of-force copies. Historical wave2/r6 manifests remapped by clause_key. `tests/unit`: 2564 passed. Do not merge #80 separately; this PR already contains `5f05d3a4`.

### Out of Scope

### Out of Scope
Merging PR 80 itself; encoding unencoded AMENDED coords (2.4.2.B-1.(2), 4.1.4.(4), 4.2.14.B.(1), 4.2.15.D-1.(3)); deferral_table historical stale hashes not on the compile path; synthetic cohort regen.

---

## Task: Chrome tab navigation — left-click replaces, “Yeni sekmede aç” stays

### Goal
Left-click / sidebar navigate in this strip tab (replace unless that tab already exists). Ctrl/middle/right “Yeni sekmede aç” add a background tab and stay; if it already exists, switch to it. The menu click must not fall through onto the patient link.

### Locked decisions (2026-09-03 grill)
- Left-click a patient on Hastalar: this strip tab **becomes** that patient (Hastalar gone).
- Left-click patient B from patient A: this tab becomes B (A gone), unless B already exists → switch to B, leave A.
- Sidebar Hastalar: same rule (replace this tab if Hastalar is not already a tab; switch if it is).
- “Yeni sekmede aç” / Ctrl / middle: not open yet → add unselected tab, **stay**. Already open → switch to it.
- Click-through after the context menu is a bug, not “open and go”.

### Subtasks
- [x] `applyWorkspaceSync` replaces the active tab when the dest is new; still switches when dest exists
- [x] `useOpenPatientBackground` stays on add; `router.push` when that tab already exists
- [x] Context menu swallows the ghost click so the patient link does not navigate
- [x] Update workspace tab unit tests; vitest + tsc
- [x] Browser: left-click replaces; “Yeni sekmede aç” stays on Hastalar with a new unselected tab

### Review
“Yeni sekmede aç” was navigating because the menu click fell through onto the patient link. Menu now adds a background tab and stays on Hastalar. Left-click replaces this strip tab (Hastalar becomes that patient) unless the dest tab already exists, in which case it switches. Ctrl/middle match the menu. Playwright: menu on 0001 stayed on `/?tab=patients` with both tabs; left-click 0043 replaced Hastalar and kept 0001.

### Out of Scope
Chrome “switch immediately” preference; duplicate strip tabs for the same patient; drag-reorder.

---

## Task: Keep local Next.js from OOM-exiting

### Goal
`http://localhost:3000` stays up; Turbopack is not allowed to fill the Node heap and vanish.

### Subtasks
- [x] Switch `next dev` to webpack (Turbopack leaked ~15GB and exited)
- [x] Restart frontend; confirm `/login` returns 200

### Review
Cause was Next 16 Turbopack OOM (~15GB), not a closed browser tab. Dev server now uses webpack. `/login` 200 at http://localhost:3000.

### Out of Scope
Fixing the Turbopack leak itself; changing Node version.

---

## Task: Chrome-gestures to open patient strip tabs

### Goal
Ctrl/Cmd-click, middle-click, and right-click “Open in new tab” on any patient profile link add an in-app strip tab and leave the current view. Five patients = five of those clicks while staying on Hastalar.

### Locked decisions (2026-09-02)
- Workspace strip tabs only (never a new browser window).
- Per-row Chrome gestures, no multi-select.
- Every patient-id navigation: cohort table, compliance, red kuyruğu, revenue/optimizer lists, Ctrl+K, in-workspace patient search.

### Subtasks
- [x] `openBackground` on the workspace store (`ensureWorkspaceTab`, do not change `activeTabId`)
- [x] Shared `PatientTabLink` + context menu; helper tests for href → view and modifier detection
- [x] Cohort table: real patient href + row Ctrl/middle/right-click stay on Hastalar
- [x] Replace remaining patient `<Link>`s (compliance, findings, red kuyruğu, optimizer)
- [x] Ctrl+K and PatientSearch: same gestures; Ctrl+Enter in palette opens background and stays open
- [x] i18n en/tr `openInNewTab`
- [x] vitest + tsc; browser: five Ctrl-clicks on Hastalar leave you on the list with five new strip tabs

### Review
Chrome gestures open in-app strip tabs without leaving the current view. `openBackground` keeps `activeTabId` unchanged. Cohort, compliance, red kuyruğu, optimizer, Ctrl+K, and in-workspace PatientSearch all use the same Ctrl/Cmd-click, middle-click, and right-click “Open in new tab” path. `npx vitest` 249 passed, `npx tsc --noEmit` clean. Browser on http://localhost:3000 Hastalar: five Ctrl-clicks stayed on `/` with five new strip tabs; right-click showed “Open in new tab” and added SENTETIK-HASTA-0039 while still on the list.

### Out of Scope
Multi-select; native browser “Open in new tab”; Shift+click new window.

---

## Task: Chrome-style workspace tabs (equal width, no cap, scroll)

### Goal
The tab strip behaves like Chrome: every open tab is the same width, they keep a standard size until they hit the search/feedback cluster, then they shrink together. No 6-tab cap, no silent LRU close, no `+N`. When they hit min width, a scroll arrow reaches the rest.

### Locked decisions (2026-09-02)
- Equal width (not content-sized).
- Sections AND patients stay as tabs; sidebar click still opens a tab.
- No cap, no eviction; close only via ×.
- Kill `+N`. At min width: hidden-scrollbar track + scroll chevron (Chrome), not an overflow menu.

### Subtasks
- [x] Remove `WORKSPACE_MAX_TABS` eviction from `applyWorkspaceSync`, `ensureWorkspaceTab`, and `readWorkspaceSession`; update unit tests (opening a 7th tab must keep all 7)
- [x] Delete `countInlineWorkspaceTabs` / `splitWorkspaceTabs` and the `+N` overflow UI
- [x] Tab track: `flex-1 min-w-0`, each tab `flex: 1 1 13rem; min-width: 4.5rem; max-width: 13rem` so few tabs stay standard-sized with empty space before search, many tabs shrink equally
- [x] When `n × min-width` exceeds the track: keep min width, `overflow-x` hidden (no visible scrollbar), left/right chevrons, wheel scrolls the track, activating or opening a tab scrolls it into view
- [x] Close/split stay hover-only and must not inflate min width (overlay, not extra flex space)
- [x] i18n: overflow string → scroll-more aria labels (en + tr)
- [x] `npx vitest` + `npx tsc --noEmit` green
- [x] Browser: 3 tabs stay ~208px with a gap before search; 8+ tabs shrink together; more than fit at 72px → chevron, no `+N`; closing a tab restores width; chat-dock open shrinks available width

### Review
Chrome-style strip is live. No 6-tab LRU cap; no `+N`. Playwright: 3 tabs = 208px equal with a gap before search; 8 tabs = 159px equal filling the track; 18 tabs at 720px = 72px min + left scroll chevron. App is running at http://localhost:3000.

### Out of Scope
Drag-reorder, tab groups, a Chrome “new tab” `+` button, pinned tabs, changing how sidebar/search opens tabs, raising keep-alive of hidden patient panes.

---

## Task: Fit workspace tabs to top-bar width

### Goal
The workspace tab strip shows every open tab that actually fits; `+N` appears only when remaining tabs cannot fit beside the search/feedback actions.

### Subtasks
- [x] Add a pure `countInlineWorkspaceTabs` / `splitWorkspaceTabs` helper (fit-to-width, keep active tab inline)
- [x] Unit-test the helper: all fit, overflow needed, tiny bar, active tab in overflow
- [x] Replace the hardcoded `WORKSPACE_INLINE_TABS = 5` split in `WorkspaceTabStrip` with ResizeObserver measurement
- [x] Close the overflow menu when it becomes empty; remeasure on resize and chat-dock inset
- [x] Run `npx vitest` on the helper + `npx tsc --noEmit`
- [x] Verify in the browser: 6 open tabs on a wide window show all; shrinking the window reveals `+N`; no large gap before search

### Review
Root cause was `WORKSPACE_INLINE_TABS = 5`: the 6th tab always went into `+1` regardless of leftover width. Overflow is now measured with ResizeObserver. Playwright: 1600px viewport → 6 inline tabs, no `+N`; 720px → `+4` with the active tab kept visible.

### Out of Scope
Changing `WORKSPACE_MAX_TABS` (still 6). Redesigning tab chrome, labels, or the overflow dropdown itself.

---

## Task: Fix Hermes Cursor proxy HTTP 502 Invalid User API Key

### Goal
Telegram/gateway POSTs to `127.0.0.1:8765` authenticate with the stored Cursor user key instead of a foreign Bearer, so CreateAgent no longer returns 401.

### Subtasks
- [x] Confirm stored `CURSOR_API_KEY` still works for catalog + SDK oneshot (no key echo)
- [x] Prove incoming Hermes `Authorization` is what CreateAgent uses (prefix/len only)
- [x] Patch proxy to always use systemd `CURSOR_API_KEY`; ignore non-`crsr_` Bearer
- [x] Restart `hermes-cursor-proxy`; smoke POST with dummy Bearer + real CLI
- [x] Add gateway `EnvironmentFile` only if `hermes setup` is not mid-run — skipped; setup still on pts/0, proxy fix is sufficient
- [x] Document cause in this review section

### Review
The 502 was not a bad Cursor key. Hermes Telegram sent `Authorization: Bearer no-key-required` to the loopback proxy; the proxy forwarded that to CreateAgent and Cursor 401'd. Proxy now ignores non-`crsr_` Bearers and uses systemd `CURSOR_API_KEY`. Smoke: POST with the placeholder header returned `AUTHFIX_OK` (CreateAgent 200). Retry the Telegram turn; no gateway restart needed.

### Out of Scope
Replacing the live Hermes tree; changing default Muse Spark model; printing the API key.

---

## Task: Wire Cursor Grok into Contabo Hermes (Hermes stays the agent)

Full plan: `plans/ops/2026-08-29-hermes-cursor-provider-vps.md`

### Goal
On `contabo-vps`, Hermes can use Cursor-billed Grok 4.6 / Composer while Hermes keeps tools, memory, and Telegram. Default model stays `muse-spark-1.2-contributor`.

### Subtasks
- [x] Inventory VPS Hermes 0.20.0, gateway unit, plugins, env (no CURSOR_API_KEY yet)
- [x] Drop `cursor_sdk_client.py` (Nous #88212 / hermes-agent-sdk) into the install
- [x] Loopback OpenAI proxy on `127.0.0.1:8765` with Cursor tools disabled
- [x] `pip install cursor-sdk` in the Hermes venv
- [x] systemd user unit `hermes-cursor-proxy`
- [x] `custom_providers` entry; do not change default model
- [x] Add `CURSOR_API_KEY` when available; smoke `grok-4.6` oneshot
- [x] Restart gateway only if `hermes setup` is not mid-run

### Out of Scope
Replacing `/usr/local/lib/hermes-agent` with a fork; Cloud Agent handoff plugins; reverse-engineered `api2.cursor.sh` proxies.

---

## Task: Rebuild SUT coverage parquet + pin RULE_REGISTRY in CI

Full plan: `plans/billing/2026-08-23-demo-coverage-rebuild-and-registry-pin.md`

### Goal
Kural Veritabanı shows SUT clause text for `blood_component_isbt128_barcode` and `yatak_icu_overlap`, and CI fails if a `RULE_REGISTRY` id is missing from `sut_registry_coverage.parquet`.

### Subtasks
- [x] Branch `chore/sut-coverage-rebuild-registry-pin` from up-to-date `main`
- [x] Add `tests/unit/domain/sut/test_registry_coverage_artifact.py` (set equality + blood/yatak `matched_clause_count > 0`; fail if parquet missing)
- [x] Confirm that test **fails** on current parquet (missing those two ids)
- [x] Run `python scripts/sut/build_sut_coverage.py`
- [x] Confirm parquet has 47 rows, ids == `set(RULE_BY_ID)`, blood 3, yatak 12, icu 9
- [x] Re-run the new test + `tests/unit/domain/sut/test_rules_catalog.py` — green (full suite: 2583 passed)
- [x] Commit parquet + test (+ drift fix below, atomic) — `5a3ad53`; manifest sync `34849c6`
- [x] Open PR (#79), CI green (backend 6m13s + frontend)
- [ ] Merge to `main` — BLOCKED on branch protection (review required); needs Safa's merge click or explicit --admin go-ahead (deploy.yml follows)
- [ ] Verify production: `zero_clause_matches` length 6, those two rules have clause cards in the browser (after merge + deploy)

### Drift surfaced by the rebuild (fixed in-PR)
The parquet committed at `1c38126` was stale-at-birth: a pristine-worktree repro
proved that commit's own builder disagreed with it for 5 §4.2 clauses. Fixed via
`deferral_table.yaml` entries (C003658/C003756/C003834 tier_c_deferred, C004257
existing entry un-dropped, C004299 non_actionable) + `load_deferral_table`
resolves non-encode-eligible rows and same-clause_key content duplicates +
`repair_untraced` honest set aligned with the audit + compiled 4201/4210
manifests regenerated + 6 committed-manifest pins recalibrated.

### Out of Scope
Synthetic `skipped_no_data` fields; Fatura İnceleme UI; filling the remaining six zero-clause rows; rebuilding coverage inside CI.

---

## Task: Purge fake "demo"-coded claim lines from the synthetic cohort

**Rev 2 (2026-08-22)** — patched after plan review. Review verified against repo:
all 8 gap claims + 3 fact corrections confirmed. Do-not-implement-as-written lifted;
this rev addresses every item.

### Goal
No claim line in the synthetic cohort carries a fabricated `demo` code. All 13
fake-coded lines are removed at the generator (not filtered out of the parquet),
their scenario machinery is deleted or re-anchored, and the cohort is regenerated
+ cache rebuilt + verified end-to-end.

### Background (verified findings)
- 13 fake-coded lines exist, in 4 families:
  - **Drug-indication demos (6)** — patients 0014,0015,0016,0017,0019,0020,
    codes `SUT-DEMO-BEV/NIVO/DARA/PEM/TRAS/TRAB`.
  - **MEDULA 0411 drug anchor (1)** — patient 0031, code `SUT-DEMO-BEV`.
  - **Material-prose demos (2)** — patients 0021 (`SUT-DEMO-OPT`), 0022 (`SUT-DEMO-GRF`).
  - **§3.3/L4.4 keyword demos (4)** — patient 0001, codes `DEMO-L44-W1/W2/CL1/SS1`.
- None of these codes exist in any real catalog (0 hits in `ek4a_drugs` + all `ek3*`).
- **Fact correction (rev 2):** 5 of 6 oncology BRANDS DO exist in EK-4A
  (OPDIVO×2, DARZALEX×3, KEYTRUDA×1, HERCEPTIN×1, YONDELIS×1); only
  AVASTIN/bevacizumab is absent. Replacement is still out of scope (Safa chose
  deletion), but the earlier "cannot be replaced" claim was overstated for 5/6.
- **Fact correction (rev 2):** patient 0001 is **Tier C** filler (not "unranked").
  The other 9 demo patients are Tier B. Tier A is untouched.
- Rule engines match by drug name/INN and material-name keywords, NOT by code — the
  fake codes are cosmetic placeholders, but the lines are load-bearing for showcases.

### DECISION POINTS (confirmed by Safa 2026-08-22)
- **D1 — MEDULA 0411 (patient 0031):** CONFIRMED re-anchor from `drug` → `claim`
  (claim-level rejection, same pattern as scenario 0032). Keeps the MEDULA Red-Queue
  scenario but drops the fake-coded drug line.
  - *Verified alternative (not taken):* the same claim carries a REAL drug line
    `A16712` (MEXIA XR 14 MG); anchoring 0411 to it would keep drug semantics with
    no fake code. Claim-level kept because it is simpler and matches the confirmed
    decision; `related_line_*` is display-only, playbook matches on `sonuc_kodu 0411`.
- **D2 — Patients 0014–0022 after demo removal:** CONFIRMED keep them as ordinary
  background patients (no renumbering), but strip their scenario entries from
  `demo_manifest.json` / `demo_vignettes.json` and the tier lists. They fall to Tier C.

### ACCEPTED PRODUCT LOSS (recorded, not a surprise after regen)
After the purge, no synthetic patient showcases these in the UI (engines + unit
tests remain; live cohort demos do not):
- §4.2 drug indication (6 oncology lines, 0014–0020) — gone from cohort
- §3.3 optical lens upgrade (0021) and hip-graft no-pay (0022) — gone from cohort
- §3.3 keyword L4.4 (0001, the original UI complaint) — gone (intended)
Kept: §3.1 material prose real codes (0023 OP1592, 0024 OP1000), claim readiness
(0033 OP2000), MEDULA 0411 red-queue (claim-level), all Tier A live demos.

### Subtasks

**Phase 0 — Baseline**
- [x] 0.1 Re-confirm the 13 lines + codes with a fresh parquet read; record counts (drug=7, material=6).
- [x] 0.2 D1/D2 confirmed by Safa: re-anchor MEDULA-0411 to claim-level; keep 0014–0022 as background patients.

**Phase 1 — Generator surgery (`scripts/synthetic/`)**
- [x] 1.1 `gen/specs.py`: delete `_DRUG_INDICATION_DEMO_SPECS` (all 6 SUT-DEMO).
- [x] 1.2 `gen/specs.py`: remove `optical_lens_upgrade` + `hip_graft_no_pay` from `_MATERIAL_PROSE_DEMO_SPECS` (KEEP `kdv_ceiling_exceeded`=OP1592, `procurement_incomplete`=OP1000).
- [x] 1.3 `gen/specs.py`: re-anchor `_MEDULA_DEMO_SPECS["0031"]` drug→claim (per D1).
- [x] 1.4 `gen/patients.py`: delete demo wiring for 0014–0020 (drug) and 0021–0022 (material OPT/GRF); KEEP 0023–0024.
- [x] 1.5 `gen/orchestrate.py`: drop `_DRUG_INDICATION_DEMO_SPECS` import + `drug_indication_demo/spec` wiring, **AND delete the inline drug-row injector block (~lines 405–458: `if drug_indication_spec:` → `ctx.drug_claims.append` + `ctx.expected.append`)** — leaving it would let fake lines be re-created. Keep `material_prose_spec` path (still used by 0023/0024 + claim_readiness).
- [x] 1.6 `gen/reconcile.py`: delete active `_inject_specialty_keyword_demo_rows`.
- [x] 1.7 `gen/materials_flags.py`: delete dead duplicate `_inject_specialty_keyword_demo_rows`.
- [x] 1.8 `gen/workbook.py`: remove its import + the `_inject_specialty_keyword_demo_rows(materials, claims)` call.
- [x] 1.9 `gen/__init__.py` + `generators.py`: remove `_DRUG_INDICATION_DEMO_SPECS` re-exports.
- [x] 1.10 `gen/medula_anchor.py`: delete now-unused `drug` anchor branch (dead-code cleanup).

**Phase 2 — Validator (`validate_sut_synthetic_data.py`)**
- [x] 2.1 Delete `_validate_drug_indication_demos` + `DRUG_INDICATION_DEMO_PATIENTS` + `DRUG_INDICATION_DEMO_TIER_B_FIELDS` + its call site (~line 1278).
- [x] 2.2 Remove 0021/0022 from `MATERIAL_PROSE_DEMO_PATIENTS` / `MATERIAL_PROSE_DEMO_MATERIAL_CODES` / `MATERIAL_PROSE_DEMO_FLAG_EXPECTATIONS` (KEEP 0023/0024).
- [x] 2.3 Keep `DRUG_INDICATION_WORKBOOK_COLUMNS` + §4.2 drug columns (still required schema); keep `_empty_drug_indication_fields` / `_ensure_drug_indication_columns`.
- [x] 2.4 **(rev 2)** Gate/delete the MEDULA `0411` drug-content branch (~lines 966–978): it requires a drug anchor with `uzmanlik_kurulu_raporu_var=False`, which no longer exists after the claim-level re-anchor. Skip the check when the anchor type is claim-level.

**Phase 3 — Curated data + golden + docs**
- [x] 3.1 `demo_manifest.json`: remove `scenario_by_index` entries 0014–0017,0019–0022 and drop the same 8 indices from `tier_b_patient_indices` (KEEP 0018, 0023–0028, 0030–0033); 0031 stays (claim-level).
- [x] 3.2 `demo_vignettes.json`: remove vignettes 0014–0017,0019–0022; keep 0031 (update its description if it references the drug anchor).
- [x] 3.3 **(rev 2)** Trim `data/gazette/prose_rules/golden/material_prose_sprint2.json` (remove the 0021/SUT-DEMO-OPT and 0022/SUT-DEMO-GRF entries). Update human docs that advertise the purged patients: `data/synthetic/README.md`, `docs/gazette/partial-coverage-scope.md`. (`DEMO_COHORT.md` is auto-regenerated by the generator — verify after regen.)

**Phase 4 — Tests**
- [x] 4.1 `test_sgk_uplift_synthetic_demos.py`: delete `TestDrugIndicationSyntheticDemo`; remove the 2 SUT-DEMO params from `TestMaterialProseSyntheticDemo` (keep kdv/procurement); keep the MEDULA 0411 param (claim-level still passes).
- [x] 4.2 `test_claim_drug_indication.py`: KEEP (engine test, in-memory fixtures); optionally rename fixture `SUT-DEMO-BEV`→neutral token.
- [x] 4.3 `frontend/.../SutBillingReportSections.test.tsx`: optionally rename fixture `SUT-DEMO-OPT`→neutral token.
- [x] 4.4 **(rev 2)** `tests/unit/api/test_patient_billing_drug_indication_api.py`: delete/rewrite the 0014, 0017, 0019 tests (they pin violation counts against cohort patients that lose their drug lines).
- [x] 4.5 **(rev 2)** `tests/unit/scripts/test_synthetic_specialty_prose_flags.py`: delete `test_keyword_demo_material_names_present` (asserts DEMO-L44 material names in a live-built workbook).
- [x] 4.6 **(rev 2)** `tests/unit/synthetic/test_vignette_golden.py`: remove 0014–0017,0019–0022 from `test_sprint_demo_indices_0012_to_0033_documented` index list (keep 0012,0018,0023–0028,0030,0031,0033).
- [x] 4.7 **(rev 2)** `tests/unit/synthetic/test_cohort_tiers.py`: update hardcoded counts `tier_b == 24 → 16`, `tier_c == 17 → 25` (8 indices move B→C).

**Phase 5 — Regenerate + validate**
- [x] 5.1 Run `python scripts/synthetic/generate_sut_synthetic_data_v2.py` (runs validator + Tier A assert).
- [x] 5.2 Assert 0 `demo` codes remain — **(rev 2)** across `claims/*.parquet` (drug_code, material_code, equivalence_group), `clean/*.parquet`, AND the `sentetik_sut_v2_50_hasta.xlsx` sheets (the generator writes the workbook too; parquet-only grep is insufficient).
- [x] 5.3 Confirm Tier A patients (0002,0003,0006,0009,0010,0011,0013,0029,0038) still pass `assert_tier_a_post_regen.py`.

**Phase 6 — Test suite + typecheck**
- [x] 6.1 `pytest` (at minimum: `tests/unit/synthetic/`, `tests/unit/scripts/test_synthetic_specialty_prose_flags.py`, `tests/unit/api/test_patient_billing_drug_indication_api.py`, `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py`, `test_claim_drug_indication.py`, MEDULA suite).
- [x] 6.2 Frontend `vitest` + `tsc --noEmit` if any fixture renamed.

**Phase 7 — Cache rebuild + end-to-end**
- [x] 7.1 Rebuild billing cache (`BILUN_STARTUP_POLICY=rebuild` + restart backend); confirm `/health` shows a completed build (not `active_build:null`).
- [x] 7.2 Spot-check a regenerated Tier B patient + the API to confirm no `demo` codes surface.

### Out of Scope
- Touching the real rule engines (`drug_indication.py`, specialty-prose, §3.3 keyword rules) — they stay.
- The real-coded material demos: `kdv_ceiling_exceeded` (OP1592), `procurement_incomplete` (OP1000), claim-readiness (OP2000).
- All Tier A showcase patients and the MEDULA scenarios with real-coded anchors.
- Replacing the 6 oncology demo codes with real EK-4A barcodes (5/6 brands DO exist in EK-4A — feasible in principle — but deletion was the chosen path; not requested).
- Renumbering patients or changing the 50-patient cohort size.

### Review
**Done 2026-08-22. Purge complete and verified end-to-end.**

- **Purge:** all 13 fake-coded lines removed at the generator (7 drug `SUT-DEMO-*`,
  2 material `SUT-DEMO-OPT/GRF`, 4 material `DEMO-L44-*`). Zero `SUT-DEMO`/`DEMO-L44`
  cells remain in `claims/*.parquet`, `clean/*.parquet`, and the `.xlsx` (verified).
  Remaining "demo" strings are only legit scenario-tag names of kept demos (copay
  exemption, payment-method) and internal line-IDs of kept real-coded material demos.
- **Regen:** `generate_sut_synthetic_data_v2.py` passes (validator + Tier A assert).
  Tier counts now B=16 / C=25 (8 purged indices moved B→C).
- **Cache:** rebuilt offline (`BILUN_STARTUP_POLICY=rebuild`), new build
  `a5bb830b` activated; active build has 0 demo-code cells across every VARCHAR
  column (the 121 "demo" cells first seen were from superseded builds — filter by
  `build_id`).
- **Tests:** 2570 unit tests pass; frontend `SutBillingReportSections` 26 pass;
  `tsc --noEmit` clean.

**Pre-existing drift fixed along the way (NOT caused by the purge).** The cohort was
last regenerated 2026-06-28 (`21aa6a9`); 318 commits later — incl. the 2026-07-01
SUT amendment (`5e82c31`), 163 newly-wired billing rules, and a generator RNG-path
change — the committed data was stale. Regen surfaced it; fixed:
- 3 validator bugs (missing `hasta_katilim_payi_profilleri` sheet, over-strict
  vignette-manifest alignment, EK-3B-1/2 derived flags wrongly required in parquet).
- Recalibrated drift-pinned goldens/tests: Tier A 0003 band (6300→6750),
  `test_f011` (6300→6750), `test_f015` (new §2.2.1 613080 violation + 3 doc rows),
  `test_0001`→retargeted to 0045-078 (0001-001 flipped to itemized),
  `test_copay_outcome_kind` rate patient 0012→0002.

**Accepted product loss (per D1/D2):** cohort no longer showcases §4.2 drug-indication
(0014–0020), §3.3 optical/hip-graft (0021–0022), or §3.3 keyword L4.4 (0001) — engines
+ unit tests remain. MEDULA 0411 kept as claim-level rejection.

**Not committed** (left for Safa to review/push). Backend left running on the rebuilt
cache (port 8001).

---

## Task: Fill TÜBİTAK 1812 pitch deck template (RV1) with Bilun content — Turkish

**Date: 2026-08-22**

### Goal
Produce a filled, panel-ready Turkish pitch deck from
`/home/safa/Documents/BIGG/Medipol/RV1_1812_Pitch_Deck_Sablonu.pptx` (19 slides),
using ONLY facts from existing sources (no invented numbers):
- AGY112 iş planı formu (`BIGG/Medipol/1812_agy_112_pdf_form_v1.2.pdf`) — primary source
- Başvuru formu (`112 Numaralı İş Fikri Çağrı Dokümanı.doc`) — thematic area (Sağlık ve İyi Yaşam), TRL 4→7
- `Bilun Extras/Presentations/Bilun.pptx` (TR investor deck) — team/advisors, market framing
- Kent Hastanesi interview docs (customer validation evidence)

### Subtasks
- [x] Extract template structure (all 19 slides, shapes, tables, guide rails)
- [x] Extract content from AGY112 form, call doc, TR deck, interviews
- [x] Write plan (this file)
- [x] Python script (python-pptx): fill every placeholder/table with Bilun content, preserving run formatting
- [x] Delete guide-rail scaffolding per template's own instruction ("Nihai sunumdan önce bu rehber alanını silin") + kullanım notu + "Önerilen görsel/Eklenebilecek Unsurlar" boxes
- [x] Fix slide 12 "İŞ PAKETİ 7" → 6; replace generic timeline milestones with Bilun milestones
- [x] Fill checklist slide (18) with Evet + slide refs; adapt backup slide list (19)
- [x] Save as NEW file `RV1_1812_Pitch_Deck_BILUN.pptx` (template untouched)
- [x] Verify: reopen output — zero `[...]` placeholders except `[LOGO / ÜRÜN GÖRSELİ]` and `[FOTOĞRAF]`; zero guide shapes; all table cells filled (231 ops, all tables N/N); rendered to PDF via LibreOffice and visually inspected slides 1/2/7/12 — layout intact

### Content decisions (flagged to user)
- Numbers come verbatim from AGY form even where the form is internally inconsistent
  (2M TL vs 350K TL price points; 5M vs 15M at 12/2028) — deck quotes each section's
  own figure; inconsistencies flagged in final message.
- Slide 13 budget split (45/20/25/10%) is explicitly marked "taslak" — no Bilun budget
  document exists; total = 900.000 TL for %3 equity per current 1812 model.
- Customer validation stated honestly: sözlü pilot onayı, imzalı sözleşme yok.

### Out of Scope
- Adding real images (logo, photos, screenshots) — placeholders kept.
- Fixing AGY form's internal inconsistencies (flagged only).
- Modifying the template file itself.

### Review
Delivered: `/home/safa/Documents/BIGG/Medipol/RV1_1812_Pitch_Deck_BILUN.pptx` (19 slides, Turkish).
- All 19 slides filled from AGY112 form + call doc + TR investor deck + Kent Hastanesi interviews; no invented numbers.
- Guide rails / kullanım notu / scaffolding boxes deleted per the template's own "nihai sunumdan önce silin" instruction.
- Slide 12: 6 work packages with Bilun milestones (KVKK veri aktarımı → 10+ kurum hedefi); "İŞ PAKETİ 7" typo fixed.
- Slides 16/18: risk matrix from AGY 5.1 (5 risks, real B plans, KVKK/etik note); checklist all Evet with slide refs.
- Verification: text dump (0 leftover placeholders), raw-XML spot check, LibreOffice PDF render + visual inspection.
- Known template quirk: small circle cards on slides 2–6 overflow slightly with full sentences — acceptable, polish in PowerPoint if desired.
- Flagged to user: AGY form internal inconsistencies kept as-is per section (2M vs 350K ₺ price points; 5M vs 15M ₺ at 12/2028; 45K vs 50K ₺ unit cost); slide 13 budget split marked "taslak".
- User must still add: logo/ürün görseli (slide 1) and 3 team photos (slide 14).

---

## Task: Reconcile financials (tiered pricing), fill Maliyet Formu (1.35M TL), fix deck overflow

**Date: 2026-08-23**

### Goal
Apply the approved tiered-pricing framing (2M ₺ flagship tier / ~350K ₺ blended ARPU)
consistently across (a) pitch deck, (b) AGY112 fillable PDF; fill Maliyet_Formu.docx with a
1.350.000 ₺ budget tied to work packages; shorten circle-card copy on deck slides 2–6.

### Subtasks
- [x] Plan (this section)
- [x] Deck: 1.35M investment (slides 13/15), slide 13 rows = Maliyet Formu categories, tiered-price notes (slides 7/10/15), shortened circle cards (slides 2–6), checklist row 13 note
- [x] Maliyet_Formu.docx → fill 5 tables (personel 990K / M013 150K / M015 150K / diğer 60K = 1.350.000), save as Maliyet_Formu_BILUN.docx
- [x] AGY fillable PDF: §1.4 tier note; §2.3 tier paragraph; §2.4 break-even sentence → 2M/50K/1.95M/5.4M; 4.4-2 diğer değişken 25K→30K; §4.2 350K→blended; 4.3 milestone 15M→~5M; §4.5 15M→8.75M+; save as v1.3_BILUN.pdf
- [x] Verify: deck re-render slides 2–6/13 visually (circles fit, tables clean); maliyet docx dump (totals 990+150+150+60=1.350K); PDF field dump (all 7 fields updated)

### Budget design (1.350.000 ₺)
- PERSONEL 990.000 (%73): Safa 1,0×18×33K=594K; Enes 0,5×12×33K=198K (Ay 7–18, mezuniyet sonrası); Kadir 0,5×12×33K=198K
- ALET/YAZILIM 150.000 (%11): 2× geliştirme bilgisayarı 90K; TR bulut barındırma+hesaplama 60K
- HİZMET 150.000 (%11): YMM 30K; hukuk 45K; sağlık ekonomisi 45K; sızma testi 30K
- DİĞER 60.000 (%5): seyahat 25K; TÜRKPATENT+telif harçları 15K; iletişim/ofis 20K
- MALZEME: boş (yazılım ürünü)
- Estimates flagged: monthly 33K ≈ 2026 asgari ücret işveren maliyeti tahmini; oranlar kullanıcı onayına açık.

### Out of Scope
- Changing any other AGY content; PRODİS submission; equity % (kept %3, flagged).

### Review
Delivered (all in /home/safa/Documents/BIGG/Medipol/):
- RV1_1812_Pitch_Deck_BILUN.pptx — regenerated: 1,35M ₺ yatırım (slayt 13/15); slayt 13
  satırları Maliyet Formu kategorileriyle birebir; tier notları (7/10/15); daire kartları kısaltıldı
  (2–6, render ile doğrulandı); checklist satırı güncellendi.
- Maliyet_Formu_BILUN.docx — 5 tablo dolu; TOPLAM 1.350.000 ₺.
- 1812_agy_112_pdf_form_v1.3_BILUN.pdf — 7 alan düzeltildi; tüm finansal ifadeler artık
  tier modeliyle tutarlı (2M amiral / ~350K blended; 4.4 tablosu 2M/50K/1.95M/5.4M).
Flagli tahminler (kullanıcı onayına açık): personel 33K ₺/ay ≈ 2026 asgari ücret işveren
maliyeti tahmini; Enes/Kadir 0,5 oran × Ay 7–18 (mezuniyet sonrası); pay oranı %3 korundu.
## Task: Build 5 jury-Q&A backup presentations (TÜBİTAK 1812 RV1)

**Date: 2026-08-23** — source table: RV1 deck slide 19 "Hazır Bulundurulması Gereken Yedek Slaytlar".
Output: `/home/safa/Documents/Bilun Extras/BIGG/Medipol/Back Up Presentations/`

### Goal
Five Turkish backup decks, facts-only (every number cited to AGY-112 v1.3 / RV1 deck /
interviews / repo artifacts; internal inconsistencies flagged, never silently picked).

### Subtasks
- [x] Extract facts via 3 parallel agents (technical; finance/IP/risk; competitor/customer) with "no source" lists
- [x] Write build script (python-pptx, 16:9, quiet design) producing 5 decks
- [x] Deck 1 Teknik Mimari & Test: pipeline, rule lifecycle, Track E diff (8263/94/26/0), coverage numbers (4757/2431/55/2271/622=%13,1), test protocol (2580 pytest + 242 frontend), fact-check 28 units (12/15/1/0), determinism+security, 6 zero-rows limits
- [x] Deck 2 Patent & FSMH: "Henüz başvuru yok" honest; legal rationale; ticari sır+telif+marka (Sınıf 9/42); FSMH envanteri; kurucu→AŞ devir; no EPO search / no university protocol (do not claim)
- [x] Deck 3 Rakip & Müşteri: statüko (Cerebral field quotes), Bizmed/EczAILab/RaporınAI, CodaMetrix/Waystar/Optum (unverified caveats), Olive AI lessons; Kent interviews verbatim; "Sözlü pilot onayı — imzalı sözleşme yok"; TAM/SAM/SOM AGY basis + inconsistency footnotes; Almalı paper 0.13–1.72% caveat
- [x] Deck 4 Finans & Ortaklık: price layers (2M flagship + 15–45K SaaS + %3–4 prim), unit economics, break-even both bases (2.8 vs ~6), milestones, 1812 budget %73/11/11/5 (Maliyet Formu empty-template caveat), %100 kurucu + %10 ESOP + %60 floor, investment path
- [x] Deck 5 Regülasyon & Risk: not-a-medical-device position; KVKK roadmap; etik kurul note; AGY 5-risk matrix table; expanded indicators/responsibles
- [x] Verify: LibreOffice PDF render of all 5; visual inspection of decks 3+4 (tables fit, TR intact, footers present)
- [x] Review section in this file

### Out of Scope
Redesigning RV1 main deck; adding logos/photos; inventing missing artifacts (LoI, EPO search, filled Maliyet Formu).

### Review
Delivered 2026-08-23 to `/home/safa/Documents/Bilun Extras/BIGG/Medipol/Back Up Presentations/`:
Yedek_1_Teknik_Mimari_ve_Test (8 slayt), Yedek_2_Patent_ve_FSMH_Devir_Plani (4),
Yedek_3_Rakip_ve_Musteri_Analizi (7), Yedek_4_Finans_ve_Ortaklik_Yapisi (7),
Yedek_5_Regulasyon_ve_Risk_Matrisi (7). Facts-only: every slide carries a source
footer (AGY-112 v1.3 §, RV1 slayt, interview date, repo path). Internal
inconsistencies (1M vs 2M price, 2.8 vs 6 break-even, TAM bases, 5.40 vs 5.46M
fixed cost, %3-7 vs measured %0.13-1.72) are flagged on-slide, never silently
picked. Missing artifacts NOT claimed: no patent/EPO search, no LoI, no signed
pilot contract, empty Maliyet Formu, no university devir protokolü — each slide
states the honest status instead.
## Task: Phase B migration scope lock (2026-09-19)

### Goal
Produce a Chief-reviewable `migration_scope_proposed` decision for the smallest coherent hidden, unpriced compliance migration slice without changing runtime, API, cache, frontend, or test behavior.

### Subtasks
- [x] Re-read the accepted audit plan, matrix, audit report, state, and journal; derive Wave A candidates only from matrix rows that satisfy every required eligibility condition.
- [x] Select the smallest coherent first vertical slice and document exact detectors, stable emitted rule IDs/kinds, explicit exclusions, and deferred candidates with reasons.
- [x] Define the one-evaluation canonical data flow, initial `RuleFinding` contract, identity/serialization rules, and exact implementation/test file map from domain through patient/cohort Compliance UX.
- [x] Define hard invariants, verification commands, and bounded implementation checkpoints for contract/domain, backend projection/cache/API, frontend surfaces, and CI regression.
- [x] Write `reports/rule-engine-surfacing/2026-09-19-migration-scope.md` and update state/journal while preserving accepted audit counts, hashes, and checkpoint provenance; leave state at `migration_scope_proposed` with next action Chief review.
- [x] Verify only the four authorized files changed, JSON remains valid, provenance/counts/hashes are preserved, no runtime behavior changed, and record the review evidence below.

### Out of Scope
Phase 5 implementation; runtime detector changes; API/cache schema or behavior changes; frontend changes; test behavior changes; financial/revenue migrations; production cache rebuild/deploy; commits, pushes, or merges.

### Review
Phase B proposes exactly three Tablo 15 line-integrity detectors for the first Wave A vertical: `detect_unreported_lab_result`, `detect_missing_drug_barcode`, and `detect_material_identity_errors`. The decision document derives them from the accepted matrix, records their stable rule/line identities, excludes all verified rerun equivalents and synthetic/financial/aggregate/catalog-only rows, defines the one-evaluation `RuleFinding` architecture, maps implementation/test files, and defers all remaining candidates with reasons.

State is `migration_scope_proposed` / `proposed`, phase remains 4, implementation remains `not_started`, and Chief review is the next action. Verification: the accepted starting checkpoint was confirmed as `5122d63472fcc8eb7182e7d45d3daf14c24c7a67`; `jq empty tasks/rule-engine-surfacing-loop/state.json` passed; the committed plan, audit generator, focused audit test, accepted matrix, and accepted audit SHA-256 values recomputed exactly to the hashes retained in state; all accepted audit counts remained unchanged; `git diff --exit-code -- src/bilun frontend tests scripts` passed; `git diff --check` passed; and trailing-whitespace inspection of all four authorized files found no matches. `git status --short` showed only the requested report/state/journal/todo paths. No runtime tests were run because this checkpoint intentionally changes no runtime or test behavior.

Chief review: accepted after independent matrix/source/rerun reconciliation. The next authorized unit is Phase 5 Checkpoint 1 only: canonical finding/evaluation contract and domain plumbing for K21, K26, and the three selected Tablo 15 line-integrity rules.
## Task: Final VPS correction — finding deep links and missing evaluations

### Goal
Consume canonical `finding` patient deep links with deterministic generic row highlighting and preserve only legitimate canonical `claim_id=null` unavailable evaluations in cohort counts, with truthful closure metadata and focused GREEN verification.

### Subtasks
- [x] Reopen the closure state against the current VPS worktree and record the exact migration-scope identity correction before implementation.
- [x] Add focused frontend RED regressions for route finding-query propagation, canonical finding selection/highlighting, and unknown-finding safe fallback.
- [x] Add focused backend RED regressions for counting a legitimate null-claim missing-input evaluation and rejecting malformed null-claim evaluations.
- [x] Run the new frontend and backend regressions and capture the expected RED evidence without changing production behavior first.
- [x] Parse `finding` in the patient route and pass it through the existing generic patient Compliance view to visibly select/highlight the canonical matching row while preserving legacy `action_id` fallback and safe unknown handling.
- [x] Update cohort evaluation validation to retain only well-formed null-claim unavailable evaluations with explicit missing-input metadata, without fabricating claim IDs or changing finding identity, deduplication, financial fields, or totals.
- [x] Run only the affected frontend/backend focused suites, `npx tsc --noEmit`, changed-module/test compileall, `git diff --check`, and invariant scans for financial/rule-allowlist/generated-cache changes.
- [x] Record exact GREEN results, changed files, remaining blockers, and no-commit/no-push boundary in this plan, the loop journal, and closure state; mark loop complete only after all focused gates are GREEN.

### Out of Scope
Financial formulas or totals, detector/rule semantics, rule-ID allowlists, canonical finding identity changes, new routes or schemas, broad/full test suites, generated dependency/cache files, production cache rebuilds, deploys, commits, pushes, PRs, merges, and patient data or credentials.

### Review
Implemented and verified the final VPS correction. Patient URLs now parse and propagate the generic `finding` query through the existing Compliance view; canonical `finding_id` rows visibly highlight, legacy `action_id` remains the fallback, and unknown/missing IDs leave normal rendering unchanged. Cohort validation now preserves only well-formed JSON-null claim evaluations with unavailable status and non-empty required/missing-input metadata, retains deterministic identity semantics without fabricating claims, and keeps financial rows/totals unchanged. Focused backend passed `22 passed, 1 warning`; frontend passed `5 files, 38 tests`; `npx tsc --noEmit`, compileall, Ruff, `git diff --check`, and invariant scans passed. One unrelated HTTP/cache dedup integration test exceeded the bounded 60-second VPS runner timeout; the financial regression passed. No commit, push, PR, merge, deploy, or production cache rebuild occurred.
## Task: Drug indication correctness, canonicalization, and UX — correction pass 1

### Goal
Resolve the independent-review blockers in the first-pass Drug Indication implementation: make route arbitration semantic and order-independent, restore the public legacy contract, keep live/cache/API/UI projections truthful and consistent, and leave the production correction ready for independent review.

### Subtasks
- [x] Add RED regressions for reversed/permuted full-corpus M06/M08 arbitration, canonical diagnosis ordering, corpus-derived diagnosis-specific/ICD-less families, public `validate_claim()`, cache/API round-trip counts, legacy normalization, noncoverage, deep-link selection, empty states, nonfinancial summaries, severity/contract fields, truncation metadata, and fail-closed structured validation.
- [x] Make route arbitration semantic and order-independent; return bounded `ambiguous_route` evidence instead of selecting by corpus order, and prevent ICD-less rules from establishing indication applicability.
- [x] Restore the complete public `/validate-claim` legacy projection, including `rule`, user-safe message, drug identity, explicit nonfinancial values, and stable canonical identities.
- [x] Unify live and cached report normalization/serialization and derive missing nested counts from structured findings/legacy violations without disagreement.
- [x] Add narrowly scoped honest normalization for genuine legacy cache payloads, including old empty/no-result and mixed modern/legacy payloads.
- [x] Represent `not_in_encoded_corpus` as a distinct bounded evaluation/manual-review state without inventing missing inputs, violations, routes, or financial values.
- [x] Thread exact `selectedFindingId` deep links through patient Drug Indication cards; add safe exact selection/highlighting and unknown-ID fallback.
- [x] Fix not-applicable, evaluation-only, noncoverage, and legacy progressive-disclosure UI states.
- [x] Preserve null/nonfinancial Drug Indication semantics through index, filtering, HTTP, and frontend summary/rendering paths.
- [x] Carry severity and every retained structured cohort field through action, cache/cohort, API, and frontend contracts; remove any intentionally patient-only fields from cohort output.
- [x] Add bounded-evidence counts/flags and truthful route/observed-diagnosis truncation disclosures, including available SUT source labels.
- [x] Tighten structured-entry validation fail-closed while retaining honest legacy parent compatibility, and remove plan trailing whitespace.
- [x] Run every requested RED/GREEN verification gate, direct original-vs-reversed corpus probe, deferred-path hash check, and changed-file security/artifact scan; record exact results here.

### Out of Scope
New §4.2 rules or corpus rewrites, broad Wave A/B/C/D expansion, frontend ICD disease dictionaries, financial/recovery semantics, production cache rebuild or deployment, dependency-lock changes, pushes, merges, PRs, and changes to `main`.

### Review — superseded first-pass evidence
The earlier first-pass review claimed completion, but independent review found blocking gaps in semantic arbitration, public legacy serialization, cached/live normalization, legacy-cache honesty, corpus noncoverage, deep-link consumption, empty-state UX, nonfinancial cohort semantics, projection contracts, truncation disclosure, and structured validation. That review is superseded; no audit checkpoint is claimed here.

### Correction pass status
Production correction and the post-production audit checkpoint are ready for independent review. The resumed saved worktree established a RED baseline of `28 failed, 124 passed`; after the bounded corrections, the exact requested suite passed `155 passed in 12.66s`, the affected backend corpus/API/cohort/financial suite passed `661 passed, 2 warnings in 67.53s`, and frontend Drug Indication/dashboard/deep-link coverage passed `3 files, 59 tests`. The direct M06.9/M08.0 probe produced byte-identical original/reversed/permuted payloads with honest `ambiguous_route` results and no selected rule.

After production commit `0e709489a54339f9fd4c2d143f0ce30a53ffb94c`, the deferred audit generator/test/matrix/Markdown checkpoint was refreshed with that exact source revision. The explicit noncoverage contract is that present but unencoded drug lines remain `not_in_encoded_corpus` manual-review evaluations, contribute no violation or money, invent no missing input, and make the Drug Indication/report rollup `partial_exact`. The CI repair focused suite passed `46 passed in 49.67s`; the exact backend CI command passed `2771 passed, 9 warnings in 1120.68s`; all 137 generated SUT rule/manifest artifacts were byte-identical; the surfacing generator `--check`, full-source Ruff, changed-file Ruff, and `git diff --check` passed. No merge, deploy, production cache rebuild, branch switch, or `main` change occurred.

---
## Task: Restore trustworthy frontend asset verification in Deploy

### Goal
Make the production deployment check find its verifier, accept healthy Next.js assets, reject missing assets, and run only after successful CI on this repository's main push.

### Subtasks
- [x] Reproduce the missing verifier on the GitHub runner and the escaped-asset false 404s against the live login page.
- [x] Add a same-repository main-push guard, ensure the VPS deploys only the exact commit whose CI passed, and check out that trusted CI commit on the Deploy runner without persisting checkout credentials.
- [x] Parse escaped Flight asset paths without retaining the escape backslash; preserve de-duplication and checks for real missing assets.
- [x] Add a regression using raw escaped Flight HTML and a local mock server, covering valid direct and Flight-only assets plus a genuinely missing asset.
- [x] Run focused verifier tests, source/workflow checks, and the verifier against the live login page; confirm the expected asset set has no malformed URLs.
- [x] Review the workflow privilege boundary, final diff, and focused test evidence independently.
- [x] Commit on an isolated branch, check existing branch CI, push, open a reviewable PR, and verify its backend/frontend CI checks.
- [x] Record final results and any remaining deployment limitation in this review section.

### Out of Scope
Additional Wave A detectors or rule migration, changes to production cache or pricing, and unrelated deployment architecture. Merging and production deployment wait for review of this specific PR.

### Review
Plan independently reviewed and approved before implementation, with a same-repository main-push gate, read-only checkout of the triggering CI SHA, and a remote SHA match before checkout or service work. Evidence: latest failed Deploy run 36263168625 completed the VPS step but could not find `scripts/deploy/verify_frontend_assets.py` in the runner workspace. The existing verifier separately found 16 malformed escaped URLs among 33 extracted live references; the corresponding clean assets returned 200. A diagnostic run found 23 unique healthy assets; this observed count is not a permanent contract. The workflow currently fetches latest main at deploy time, so an older green CI could otherwise ship a newer unverified commit; compare remote main with the triggering successful CI SHA before changing services.

Implementation verification: two escaped-Flight regressions failed against the old parser. Independent review caught a multiply escaped Flight-only path that the first fix still missed; its regression failed before the follow-up correction and passed after it. The focused file now passes 10/10 tests in 3.46 seconds from this worktree. Ruff and `git diff --check` passed. The workflow parsed as YAML, its deploy shell block passed `bash -n`, and targeted assertions checked its guard/checkout/remote-SHA ordering. The corrected verifier checked the live `/login` endpoint: 23/23 local assets returned nonempty HTTP 200 responses with zero malformed backslash URLs. Independent final diff review found no remaining blocker.

[PR #96](https://github.com/Safa675/Bilun/pull/96) contains the code on `fix/deploy-asset-verification`. Existing branch CI had zero runs before the push. Its [first hosted CI run](https://github.com/Safa675/Bilun/actions/runs/36315626985) completed successfully on commit `a55bb2a4` with both backend and frontend jobs green. The actual Deploy workflow can only validate this change after it lands on `main` and that main commit's CI succeeds; production deployment and merge remain outside this PR implementation task.

---


## Task: Resolve public-access review findings

### Goal
Fix the three verified PR #107 regressions on a branch based on verified current source, with regression tests and one new commit in a draft pull request from current main.

### Subtasks
- [x] Read current repository instructions and verify immutable current main source and PR state.
- [x] Bound outgoing chat context to 20 messages, 8,000 characters per message, and 32,000 total characters; validate new questions before persistence and preserve display history.
- [x] Remove the special developer exemption for username `test`; explicitly configure test allowlists and cover session revocation.
- [x] Include both supported LLM credential environment variables in public-asset scanning and cover the CLI environment path.
- [x] Run focused regressions, relevant broader checks where available, and independent review; record exact verification limits.
- [ ] Confirm the publication target, check its CI and current source, create one new commit and verify its remote contents when authorized.

### Out of Scope
No deployment, real LLM requests, main-branch updates, merges, or unrelated changes. The user approved a new pull request; merge and deployment remain out of scope.

### Plan Review
Reviewed against the three reproduced findings and current main bb41c3f6d78e25e5c0d766f1b0b64be6d4709274. Server limits remain unchanged; frontend display history remains complete. Allowlist policy is the sole developer authority. Only supported credential names are added to the existing scanner.


### Verification Review
- Full frontend Vitest: 71 files, 419 tests passed.
- Frontend TypeScript and production build passed.
- Asset scanner: 14 focused pytest cases passed, including four formerly missed LLM-key leak cases and redacted output.
- Revocation: eight real-session cases passed in an isolated real-auth/middleware harness; the original source failed the two `test` username unset/empty allowlist cases. Thirteen existing password/credential/token tests also passed in isolation.
- Scoped Python Ruff and compileall passed. Independent review found no blocking issue.
- Local Python is 3.12 and the backend checkout is partial; full backend pytest, generated-rule parity, and manifest checks require hosted CI on the published commit. Component handler tests use mocked React hooks; no browser interaction coverage is claimed.
- Original main bb41c3f6d78e25e5c0d766f1b0b64be6d4709274 was rechecked before branch creation; its backend and frontend CI passed. Exact new-commit hosted CI remains pending at publication.

## Task: Fix compatible health cache probes

### Goal
Return truthful health readiness while the running API owns a writable load-only cache connection, without mutating the cache or disturbing that connection.

### Subtasks
- [x] Verify current main source, repository instructions, existing health contract, and the DuckDB mixed-configuration failure.
- [x] Add regressions for existing writable and verified read-only runtime connections, missing caches, non-mutating fallback probes, and probe cleanup.
- [x] Reuse an existing runtime cursor only for the same database; otherwise open an independent read-only probe without initializing runtime state.
- [x] Run RED/GREEN regressions, focused lint and compilation, and independent review.
- [ ] Check base CI, publish one atomic commit on a new branch, open a draft pull request, and verify exact-commit hosted CI.

### Out of Scope
No merge, deployment, production database access, schema migration, cache build, or Wave A rule/activation changes.

### Plan Review
Reviewed against current main 05aba8152087cf049cebcd70ce1629e03ca94649 and the authorized health fix. Preserve the HTTP readiness and detail-access contracts. The probe executes SELECTs only, never calls get_cache_con/get_cache_reader (which can initialize schema), closes only its owned cursor/connection, and does not create a missing database. Success requires active-build health to pass with both runtime access modes while failure paths remain 503 and leave the runtime connection usable.

### Verification Review
- The original probe failed the real load-only singleton regression and misreported an existing writable database with an empty pointer as unreachable (RED: 2 failed, 8 passed).
- The final focused connection suite passed 17/17 tests with DuckDB 1.5.6, including both runtime access modes, repeated and parallel probes, first-reader initialization serialization, missing/other database paths, no schema initialization, byte-identical read-only fallback, startup-not-ready, and owned-cursor cleanup on success/error.
- Scoped Ruff and Python compilation passed.
- Local execution uses Python 3.12 with a partial checkout and an isolated import harness that loads the exact health functions, runtime, storage connection and schema modules. Full application imports, HTTP health tests, Python 3.13, and the full backend/Frontend suite are reserved for hosted CI on the published commit.
- Base main 05aba8152087cf049cebcd70ce1629e03ca94649 has passing backend and frontend checks. No production state was changed.

- Independent review reran all 17 focused regressions successfully and found no remaining blocking issue. The initialization-race case exercises real runtime initialization while the fallback probe holds the cache lock.

## Task: Fix secondary procedure payable bases

### Goal
Apply each procedure occurrence's session factor to its own whole-line payable, add regression coverage, and publish a draft PR with verified CI.

### Subtasks
- [x] Verify current main, repository instructions, pricing semantics, and downstream callers.
- [x] Add failing synthetic regressions for unequal line amounts, duplicate normalized codes, package memberships, quantities, exclusions, fallback amounts, and rounding.
- [x] Replace primary-derived amounts with own-line amounts while preserving occurrence alignment and existing blood caps.
- [x] Run focused regression and integration tests, repository quality gates where available, and independent review.
- [x] Reconcile the two F011 synthetic golden expectations exposed by hosted CI with exact own-line arithmetic.
- [ ] Check base CI, publish an atomic commit on a new branch, open a draft PR, and verify remote commit and hosted CI.

### Out of Scope
No merge, deployment, production records, blood/session overlap arbitration, blood applicability changes, historical catalog ranking fixes, or Wave A changes.

### Plan Review
Reviewed against main 45f97a64385c7b1959c44125b949f2d2e3e1e90b and the authorized standalone secondary-pricing fix. Preserve expected-payable/billed fallback, whole-line quantity semantics, exclusion filters, session grouping, final-total rounding, and existing blood caps. Use source-order factors without normalized-code collisions, retaining the factor-1 fallback for empty/invalid codes. Success includes 1000 + 100 at 30% = 1030, conservation for discount-only factors, and correct downstream DRG/strategy comparisons. Tests use synthetic records and explicit catalog fixtures.

### Verification Review
- RED: the original implementation failed 31 of 35 focused amount/occurrence cases. GREEN: the final focused selection passed 99 tests across session factors, amounts, specialties, DRG uplift, strategy, care-setting review, unbundling, and session uplift. Four existing tests requiring missing dental/synthetic assets were deselected from this focused run.
- New strategy and DRG regressions exercise the real session calculation: a 1100 package produces no false uplift, while a 1000 package produces exactly 30. The payment-compliance exclusion fixture keeps its real eligibility checks and now asserts the correct own-line total, 1885.96, with deterministic catalog ranking.
- Full source/script Ruff, changed-test Ruff, and changed-file Python compilation passed. Independent review reran the 60-case core suite and found no blocking source issue.
- Local verification uses Python 3.12 and a partial source/data checkout. Full pytest was attempted but stopped at collection on missing manifests/raw source assets and a missing requests dependency. Generated-rule checking also requires the absent manifests; manifest parity scanned zero files, so it is not counted as a pass. Complete Python 3.13 backend tests, generated-artifact/parity checks, and frontend gates remain for hosted CI on the published commit.
- Base main 45f97a64385c7b1959c44125b949f2d2e3e1e90b was rechecked with successful backend and frontend checks before publication. No production state was changed.
- First hosted run on 8567ee5: frontend passed all 419 tests and all frontend gates; backend passed 4290 tests with two stale F011 golden failures. SHA-verified synthetic rows and independent review confirm primary 600160 has payable 1800 and secondary 600150 has payable 2200 at 25%, giving itemized 2350 and package-9000 uplift 6650. Updated only the exact vignette/action expectations, added explicit itemized/package assertions, and retained existing tolerances. Five registry/lookup tests and Ruff/compilation passed; the complete hosted rerun remains pending for the follow-up commit.

## Task: Reconcile blood and session uplift

### Goal
Compute one recoverable gap per shared blood/session procedure line using the existing minimum-ceiling composition, then publish a separate draft PR with verified hosted CI.

### Subtasks
- [x] Verify current main after PR111, repository instructions, detector/report consumers, and encoded ceiling composition.
- [x] Add failing direct and report regressions for overlap, no-gap constraints, review-only amounts, identities, ordering, and partial overlap.
- [x] Share the session secondary assessment, cap its blood-line ceiling, and exclude its exact line identities from the independent blood detector.
- [x] Run focused tests, repository quality gates where available, and independent review.
- [ ] Check base CI, publish an atomic scoped commit, open a draft PR, and monitor hosted CI to completion.

### Out of Scope
No merge, deployment, production records, blood-rule package applicability changes, patient-history fixes, historical catalog ranking changes, or Wave A changes.

### Plan Review
Reviewed against main 09749e23f8ba6907f7addca8c7fddea8b66f8475 and the authorized F02 roadmap. Independent review agrees that matching opportunities must compose actual monetary ceilings with min, consistent with the existing session-adjusted payable calculation. A shared secondary-line assessment must cover lines without positive session gaps; ownership remains in the session block so DRG/add-on de-duplication consumes reconciled amounts. Keep the existing clinical-review restriction even when a blood cap reduces a review gap below its heuristic threshold. Never identify opportunities by code alone. Preserve independent lines and blood-only sessions, inputs, rounding, and existing package applicability. Python 3.12/partial data are available locally; hosted CI provides the full Python 3.13 and frontend gates.


### Verification Review
- Reproduced on merged main 09749e2: plasma billed 200 with session ceiling 340.41 and blood ceiling 408.50 emitted 140.41 + 208.50 = 348.91. The reconciled session-owned gap is 140.41; billed plus uplift is 340.41.
- RED: 15 of the first 17 new regressions failed before the fix. GREEN: all 26 final regressions pass, including the actual report assembler, DRG/add-on input boundaries, recommended actions, API serialization, live/cached recovery summaries, and cohort totals for confirmed and review-only cases.
- The broader focused selection passes 135 tests; two existing tests requiring absent synthetic claim tables are explicitly deselected. Source/script Ruff, changed-test Ruff, changed-file compilation, and diff whitespace checks pass.
- Independent review found no blocking issue and passed 104 focused cases plus 1,440 synthetic parameter combinations across amounts, quantities, fractions, incision/specialty settings, and ordering.
- Local Python is 3.12 with a partial source/data checkout. Full pytest was attempted and stopped on nine collection errors from missing manifests/raw source assets and requests. Generated-rule checking reports absent artifacts; manifest parity scans zero manifests, so neither is counted as a pass. The complete Python 3.13 backend, generated-artifact/parity, and frontend gates remain for hosted CI.
- Base main 09749e2 has successful backend and frontend checks. No production state, rule JSON, or unrelated task was changed.
- First hosted run on 98a296c passed 4316 backend tests and all frontend gates, with two scoped failures: the new ceiling evidence fields were absent from the frozen public DTO, and the blood demo still expected the duplicate confirmed 310 TRY. Added only those two scalar DTO fields with patient/bill public-projection assertions that retain private-field filtering. SHA-verified synthetic claim 0004 has blood list/payable 1000, billed 50, and primary P611720 billed 101019.30: min(300,360)-50 = 250, retaining the existing clinical-review restriction. Updated the demo to pin those exact amounts, identity, and zero confirmed blood uplift. The 26 regressions plus the actual 0004 test pass locally; hosted rerun remains the final gate.

## Task: Preserve bill-scoped claim history

### Goal
Restore known same-patient evidence for existing dated rules while keeping every bill's monetary lines and emitted findings limited to that bill, based on verified main 0e40e09f.

### Subtasks
- [x] Reproduce MIAT and ICU failures on verified main and add failing regression tests
- [x] Retain separate historical claim/procedure/material rows when slicing a bill, preserving active-row semantics and rejecting foreign or orphan history
- [x] Route MIAT, ICU overlap, duplicate exam/test and SCT temporal checks through history with their existing per-event date boundaries; scope results to active rows
- [x] Cover boundary dates, future/foreign evidence, repeated slicing, patient behavior, report/cohort additivity, public projection and cache serialization
- [x] Run focused suites, full pytest, lint and artifact checks; disclose environmental gaps
- [ ] Obtain independent diff review, verify main and prior CI, publish a separate draft PR, then monitor and fix scoped CI failures until terminal

### Out of Scope
Other audit findings; new rules or changes to rule constants and authored authority; broad Wave A work; real patient data; access/authentication changes; merge/deploy

### Plan Review
Independent reviewer confirmed the separate history design and the known consumers. History views must replace any retained active-claim rows with current active rows so repeated slicing and dataclass replacements cannot resurrect stale inputs. Duplicate detectors must see prerequisite history before filtering emitted target rows; focused projection must validate historic evidence without broadening source ownership. ICU report/audit rows, MIAT legacy/prose and SCT checks keep their existing dated predicates. Existing unavailable treatment-course/prior-therapy metadata remains unchanged. Success: ICU service bed 3→2 days, MIAT warning restored, unchanged current-bill billed totals and no future/foreign-triggered findings. Local partial checkout limitations will be distinguished from complete hosted CI.

### Verification Review
- RED on verified main 0e40e09f: all five new direct regressions failed (MIAT, ICU bed reconciliation, duplicate exams, duplicate tests, and SCT prior-transplant eligibility). GREEN: all 39 expanded regressions pass, covering date-window boundaries, unknown/future dates, ownership, active-row replacement, repeated slicing, and source-order ties.
- Real report/cohort runs cover single-worker and threaded bill calculations, current-bill money, per-patient additivity, another patient's isolation, focused evidence ownership, public projection, and a DuckDB bill-row round trip. The public DTO adds only ICU overlap day/date evidence and MIAT claim/section/package-code attribution; unknown/private fields still filter out.
- Independent review passed 132 focused tests and 960 bill slices over 240 seeded input orderings, comparing MIAT/ICU/exam/test/SCT results with the same bill's full-patient findings. A same-day SCT tie-order regression caught during review was fixed with identity-preserving history overlays and permutation regressions.
- The combined local focused selection passes 234 tests, including the actual 50-patient/per-bill synthetic report suite, existing public access/probe tests, and deterministic surfacing inventory. Source/script and changed-test Ruff pass.
- Full pytest was attempted on the local Python 3.12 partial checkout and stops at nine collection errors from missing manifests/raw source data and the requests dependency. Generated-rule checking requires absent artifacts; manifest parity scans zero manifests, so neither is counted as a pass. Complete Python 3.13 backend, frontend and artifact/parity gates remain for hosted CI.
- Main 0e40e09f was rechecked immediately before publication: backend, frontend and release-hold checks are successful. No rule constants, source authority, broad rule expansion, access controls, production data, merge or deployment are changed.
- First hosted CI395 on db322e6 passed 4356 backend tests and all frontend gates. Its sole failure was an existing deployment-verifier test explicitly asserting that cross-claim ICU evidence disappears from a bill. Updated that test to require exact ICU evidence parity with the service claim's patient finding while asserting service-only claim inventory and evaluation scope. No runtime code changed. The deployment/cache/history selection passes 61 tests locally; full hosted rerun remains the final gate.


---

## Task: Simplify single-VPS Wave A releases

### Goal
Provide one prepare/status/activate/rollback release interface with version-aware current-cache verification, exact final-artifact attestation and coherent paired recovery on ports 8001/3000.

### Subtasks
- [x] Verify source against main 3f5540cf and read repository instructions and prior tested rollout helpers.
- [x] Bound changes to release tooling, versioned activation integration and focused fault-injection/regression tests.
- [x] Implement original-five and strict current full-v2 baseline comparison across all persisted report/evidence rows without rewriting inputs.
- [x] Confirm and implement the paired-release state machine, preserving current history/mutable state and attesting actual final serving bytes.
- [x] Add operator prepare/status/activate/rollback interface and concise migration/runbook documentation.
- [x] Add explicit opt-in preparation snapshot maintenance for the initial writable load-only deployment; default refuses unsupported online snapshots before stopping services, and durable recovery restores the unchanged old pair before builds.
- [x] Independently verify baseline and candidate build-config environments against their stored hashes, preserving exact historical metadata.
- [x] Build the preparation bundle from explicit machine/input paths: consistent serving snapshot and retained baseline roster, fresh detached target/frontend, traced cache and all verification/rehearsal/signing gates; test fail-closed ordering, default no-mutation snapshot rejection and explicit recoverable snapshot-maintenance integration.
- [x] Verify rollback for failures around both service stops/restarts, database/source/frontend switches, interruption and retry; preserve all historical/mutable state.
- [ ] Obtain independent review and resolve substantive findings.
- [ ] Run applicable local checks, publish only changed blobs on a new draft PR, then verify full hosted CI at the exact final head.

### Out of Scope
Merging or deploying, user-computer/VPS operations, production credential/security/network configuration changes, broad runtime or billing redesign, historical crash attribution, data pruning, and unrelated cleanup.

### Review
User approved this PR. Work uses the authorized GitHub connector and isolated cloud workspace because the declined local task will not be retried. Source inventory is partial only for unavailable data/binary assets, so publication must derive from the verified complete remote base tree and include changed files only. Current-baseline design is confirmed: version comes from complete persisted evidence/report contracts, not API feature visibility or unchanged build_meta schema; original-five migration remains supported; current full-v2 comparisons validate both sides and normalize only independently bound identity fields. The paired transaction design must explicitly bind the final serving database; changing bytes after signing or weakening hashes is prohibited. No production command is executed during implementation.

Snapshot design decision: the current ordinary load-only service owns a writable DuckDB connection. Do not claim an undocumented hot-copy snapshot. The authorized PR includes explicit opt-in snapshot maintenance with warnings, shared locking, durable recovery and interruption tests; actual VPS execution remains out of scope. Later read-only online snapshot support requires tested reader-lock semantics.

## Task: Date-aware SUT drug amendments

### Goal
Select source-verified amendments by the actual drug service date, preserve older rule behavior and disclose missing temporal or clinical evidence.

### Subtasks
- [x] Verify current-main blobs and baseline focused tests.
- [x] Review plan and official October amendment evidence with coordinator.
- [ ] Add a versioned, source-pinned amendment catalog and strict date resolver.
- [ ] Integrate affected drug evaluation with explicit unresolved clinical gates.
- [ ] Propagate optional drug service dates through dict adapters and typed evidence.
- [ ] Add boundary, historical, unknown-date, source and no-false-compliance tests.
- [ ] Run focused and aggregate tests, lint and independently review selected-file overlay.

### Out of Scope
No merge, deployment, VPS access, invented clinical criteria, blanket source dates or claims that historical lower bounds are verified. Other SUT groups remain separate workstreams.

### Verified implementation contract
The service date is optional `drug_context.service_date`, mapped to the actual drug line, never the server date. Date-aware selection uses half-open validity intervals and fails closed on absent, invalid, overlapping or unsupported versions. The three explicitly annotated October 10 successor clauses are source-backed partial evaluations, not complete eligibility decisions. Legacy clinical checks may still run before that boundary, with an explicit unverified historical-version review. Thiotepa stays quarantined; no active amendment is inferred from consolidation. Temporal records do not inflate encoded-rule coverage. Public evidence is bounded and allowlisted, with source IDs/dates/hashes but no raw rule payload. Stream B owns the form/type; this stream owns backend contracts and domain tests.
## Task: 4 Ekim 2026 sınırlı klinik kaynak incelemesi

### Goal
Resmî pozitif kanıt varsa yalnız desteklenen klinik inceleme gününü eklemek; kanıt yetersizse 4 Ekim inceleme gerekliliğini koruyan, kaynak ve yürürlük sınırları doğrulanmış dar sonuç teslim etmek.

### Subtasks
- [x] Ana dizüstü kirli dosyalarını koru; 499dff4 tabanında bağımsız worktree oluştur ve repo talimatlarını oku.
- [x] 4 Ekim SGK ilan dizini, Resmî Gazete günlük içerik ve mükerrer göstergesini canlı resmî kaynaklardan gözle.
- [x] PR128 49af201 başındaki 10 Ekim ilaç / 2 Kasım organ nakli sınırlarını resmî belgeyle eşleştir.
- [x] Kanıt ve ortak dosya sahipliğini üst göreve bildir; clinical_versions.json sahipliği çözülmeden yazma. Üst görev tek yazarlığı 4 Ekim'de açıkça verdi; corpus sahibi patch aktaracak.
- [x] Yeterli kanıt halinde yeni gözlem/makbuz ve tek günlük pencereyi ekle; yetersizse salt inceleme kanıtını ve açık engeli kaydet.
- [x] Tarihsel boşluk, hukuki alt sınır, klinik kapsam, ertesi gün ve tahrif edilmiş kanıt kontrollerini hedefli çalıştır.
- [x] Bağımsız inceleme yaptır; doğrulanmış dar sonucu ve kalan engelleri Türkçe teslim et.

- [x] Yeni pencere eklendiğinde geçmiş continuity günü kendi makbuz kimliğini korusun; dar provenance düzeltmesini regresyonla doğrula.

### Out of Scope
Corpus/parquet yenilemesi, genel mimari, tam tıbbi ödeme uygunluğu, merge, VPS ve deploy.

### Specification and plan review
Kullanıcının devredilen talimatı kapsamı ve küçük taslak PR akışını onaylıyor. Yeni hukuki tarih veya hash çıkarımı yapılmayacak. 12 mevcut aile, Python kaynak otoritesi kataloğu ve hedefli pytest katmanı kullanılacak. Başarı: yalnız gözlenen gün için pozitif resmî kanıt veya dürüst kapalı sonuç; tarihi boşlukları doldurmayan ve clinical_eligibility_complete=false sonucunu koruyan doğrulama. Ortak dosya yazımı üst görevin sahiplik paylaşımına bağlı.

### Progress evidence
Baseline gerçekten çalıştırıldı: `/home/safa/Documents/Bilun/.venv/bin/python -m pytest tests/unit/domain/prose_rules/test_clinical_source_authority.py -q`: 100 passed (2.70s). Aynı runtime ile `scripts/sut/verify_clinical_source_authority.py --check`: 12 aile, 17 yerel asset, through 2026-10-03, exit 0. Yarım fetch commit nesnesi kontrol edildi: 49af201 mevcut. Geçici transport kesintisinde belirsiz yazım tekrarlanmadı; tek yazım bu plan.

New-window implementation review: Yeni pozitif 4 Ekim kanıtı aynı gün ve dört gerekli kategori için dondurulduktan sonra ayrı tek günlük pencere eklenecek. İncelemede mevcut resolver'ın geçmiş continuity gününe son makbuz metadata'sını atadığı görüldü; yalnız eşleşen continuity penceresinin makbuz kimliğini koruyan dar düzeltme kapsamda. Bu, evaluator değişikliği veya yeni mimari değil.

Frozen source result: 4 Ekim RG normal sayı 33390 günlük içerik, current homepage/Son Mükerrer göstergesi (6 Eylül), SGK GSS yeni SUT ilanları (2 Ekim) ve 3 Ekim ayrı ilaç geri ödeme yönetmeliği aynı gün 18:16:11 UTC'de başarılı HTTP200 gözlemlerle donduruldu. Canlı SGK değişiklik DOCX SHA a717ac7e9e932449461c353fcb3d3845ed834d104f35a75505c53185bbcfccbb ve konsolide DOCX SHA227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573 önceki proof ile bayt düzeyinde aynı. Yeni strict makbuz sgk-rg-clinical-2026-10-04T182213Z: 12 aile, 5 gözlem/4 tür, aynı İstanbul günü, tüm capture ve raw-byte hash kontrolleri exit0. Kanıt bütünlüğü ve resmî dijital imza farklıdır; birlikte yeniden yazılıp pinlenen tüm veriyi runtime bağımsız resmî doğruluk diye onaylamaz.

Commencement result: Resmî SGK konsolide body/w:p indeks1096 organ 02/11/2026;5572/5579/6056 ff/gg/aaaa ilaç10/10/2026. Takvim hesabıyla tarih üretilmedi. Gerçek ilaç temporal suite34 passed; helper suite2 passed; üç ilaç×09/10/11Ekim/None=12 doğrudan assertion geçti. Organ tarih alan runtime selector bulunmadı; PR128 yeni GateB(4)/(5) çıplak koordinatları eski transfer/donör anlamlarıyla çarpışabilir. Bu veri uyumluluğu görevinin açık inceleme konusu, bu kaynak PR'ı çözmez.

### Review
Son dokuz dosyalık hedefli paket, kaynak/HTTP/evaluator/observation testleri ve ilaç temporal testleriyle gerçekten çalıştı: **538 passed, 3 warnings, 17.82s**. Normal sandbox'ta TestClient/AnyIO portal askısı görüldü; izin incelemesinden geçen minimal in-process client 0.34s'de geçti ve aynı tam paket onaylanan ortamda exit0 tamamlandı. Gerçek server/port veya VPS kullanılmadı. Scoped Ruff ve `git diff --check` exit0. Final verifier:12 aile/25 repo-local asset/through2026-10-04, clinical_eligibility_complete=false; `/tmp/bilun-source-authority-assets-20261004.json`.

Bağımsız final diff incelemesinde P1/P2 bulgu yok. Eski katalog tüm alanları/pencereleri korunmuş; yalnız12 tek günlük pencere ve bir makbuz eklenmiş. Bağımsız36 gerçek3/4/5Ekim tarih kontrolü ve final8proof hash kontrolü geçti; ayrı HTTP dışı hedefli koşu394passed39deselected. İncelemecinin yarım HTTP koşusu exit130 ile durduruldu, pass sayılmadı. Kaynak sahibi full HTTP538pass sonucunu yukarıda ayrı doğruladı.

Yayın sırası: Bu kaynak yenilemesi mevcut9639c457 corpus üzerinde bağımsız dar taslak PR olacak. Corpus sahibinin gerçek veri geçişi+catalog seam paketi bunun üstüne ikinci taslak PR olarak taşınacak; ilk kaynak PR'ında corpus veya binding değişikliği yok. Merge/deploy yok.

## Task: PR150 kaynak CI onarımı

### Goal
Mevcut c4f736b kaynak ağacındaki üç doğrulanmış CI hatasını yalnız desteklenmeyen gün fixture'ı ve türetilmiş coverage kanıt hashleriyle düzeltmek; corpus ve dört coverage parquet dosyasını byte düzeyinde korumak.

### Subtasks
- [x] future_source SMA/antifungal fixture'ını ilk desteklenmeyen 5 Ekim'e taşı; not_evaluated ve sıfır predicate beklentilerini koru.
- [x] Mevcut coverage generator'ını geçici dizine çalıştır; dört özgün parquet dosyasının Git HEAD byte eşitliğini ve geçici çıktıyla tam schema/frame eşitliğini doğrula, yalnız mevcut helper'larla sut_coverage_evidence.json dosyasını yenile.
- [x] Coverage evidence ve documentary facts testlerini, anlamlı kaynak paketini, compile_rules.py --check ve 23 manifest parity kapısını çalıştır.
- [x] Değişen dosyaların dar kapsamını, corpus/parquet hashlerinin korunduğunu ve gerçek test sonuçlarını üst göreve teslim et.
- [x] Üst görevin açık yetkisiyle kaynak pencere uzatması, future fixture ve coverage hash kapanışı için kısa önleyici ders kaydı ekle.

### Out of Scope
Corpus geçişi, diğer branch dosyaları, runtime klinik veya tarih penceresi değişiklikleri, frontend kodu, commit/push/merge/deploy. Git işlemleri üst görevin sorumluluğunda.

### Specification and plan review
Üst görev üç hatanın düzeltmesini açıkça yetkilendirdi. DAY+2=4 Ekim artık geçerli kaynak günüdür; ilk desteklenmeyen gün 5 Ekim'dir. Kanıt yenilemesi yalnız dört kalıcı parquet dosyasının Git HEAD ile byte eşitliği ve generator çıktısıyla tam schema/frame eşitliği doğrulandığında uygulanacak; input corpus SHA256 9639c4578223ff46a40499270af5043d229ab2a1a1c3783114b43b64787384ac korunacak. Kaynak kapsamı sekiz yeni 4 Ekim gözlem/makbuz dosyasıyla kapalıdır. Plan uygulamadan önce mevcut generator ve CI komutlarıyla doğrulandı.

Plan refinement before evidence write: Geçici generator Arrow24.0.0 kullanıyor, kayıtlı parquet writer Arrow25.0.1; schema ve frame eşit olsa da serileştirilmiş byte farklı. Bu ayrım üst göreve bildirildi ve yalnız evidence yenilemesi açıkça yeniden yetkilendirildi. Dört özgün parquet ve input corpus Git HEAD ile byte düzeyinde aynı doğrulandı; evidence mevcut build_drug_coverage_evidence helper'ına özgün kalıcı coverage frame verilerek ve coverage_dependency_hashes helper'ıyla gerçek repo dosyaları hashlenerek oluşturuldu. Geçici parquet dosyalarının hiçbiri repo'ya yazılmadı.

### Review
Tek birleşik 11 dosyalık kaynak/ilaç temporal/documentary/coverage paketi gerçekten çalıştı: **721 passed, 2 warnings, 36.17s**. Normal sandbox'taki önceki documentary-only HTTP koşusu asılı kaldığı için exit130 ile durduruldu ve pass sayılmadı; birleşik koşu izin incelemesinden geçen süreç içi TestClient ortamında exit0 tamamlandı. Full backend suite yeniden çalıştırılmadı.

`compile_rules.py --check`: **134 rule/manifest artifacts byte-identical**, exit0. `audit_manifest_parity.py --drug-only`: **23 scanned, 23 with traces, 0 issues**, exit0. Kaynak verifier: **12 families, 25 repository-local assets, through2026-10-04**, exit0. Scoped Ruff ve git diff --check geçti. Dört kalıcı coverage parquet ve 9639 corpus Git HEAD byte hashleriyle aynı; JSON envanteri file_sha256 dışında değişmedi. Kaynak/test/evidence düzeltmesi ve görev/ders belgeleri dışında yazım yok; commit/push üst göreve bırakıldı.

Frontend job111504177367 yalnız bir kez individual rerun edildi; aynı c4f736b kaynak başını kullanan job111510110080'de **83 files/575 tests, typecheck, build, public-assets52files** geçti. Backend yeniden çalıştırılmadı; ilk run'ın başarısız backend sonucu tam CI başarısı sayılmaz. Bağımsız final kaynak diff incelemesi üst görev tarafından atandı.


## Task: PR128 corpus'unu kaynak PR'ı üstünde mekanik doğrulamayla taşı

### Consumer scope update and ownership — 2026-10-04
Üst görev, konumsal consumer uyumluluğunu mevcut veri uyumluluğu kapsamına açıkça aldı: eski coverage ile yeni corpus arasında toplam 4.177 key/4.174 hash uyumsuzluğu ve 36 manifestte 3.066 farklı kayda kayan C* atfı doğrulandı. Provisional dosyalar nihai diye kopyalanmaz. Aşağıdaki gerekli bağımlılıklar önceki beş dosyalık başlangıç kapsamını tamamlar; genel mimari ve klinik tarih/sınır/predicate değişiklikleri eklenmez.

- [x] authority_audit: aynı metnin bent/prose kaymasını mevcut canonical override ile düzelt; compiler ve gerekli manifest/rule çıktılarını mevcut üreticilerle yenile. Tam metin/parent/context değişen atıfları otomatik taşıma; kesin engeli raporla.
- [x] corpus_seam_review: nihai manifest/rule/catalog/source-authority kapanışından mevcut build_sut_coverage.py ile sut_clause_coverage.parquet, sut_coverage_by_rule.parquet, sut_coverage_by_section.parquet, sut_registry_coverage.parquet ve sut_coverage_evidence.json dosyalarını yeniden üret; gerçek consumer ID/key/fullhash ve negatif eski artifact testlerini doğrula.
- [x] independent_review: gerçek corpus40b2 ile hazır local-hash-v1/512 embedding dosyasının 4.090 ID/body/vector eşitliğini bağımsız doğrula ve exact dosyayı kur; 14 retrieval testi ve sıcak indeks kontrolünü çalıştır. Runtime mimarisini genişletme.
- [x] root: kaynak PR'ın bağımsız coverage_evidence pin kapanışını doğrula, gerekiyorsa kaynak corpus'u değiştirmeyen dar evidence düzeltmesini ayrı tut; ortak plan/katalog ve son Git yayını sahipliğini koru.
- [ ] Nihai source/migration/consumer testleri, scoped Ruff, compile --check, manifest parity, evidence closure ve bağımsız inceleme sonucundan sonra ikinci draft PR/full CI durumunu kaydet.

Coverage üretimi diğer girdi sahiplerinin FINALmanifestready sinyaline kadar bekler. Kaynak PR bağımsızdır; merge/deploy/VPS yapılmaz. Mevcut görevde Git yayını yalnız root tarafından yapılır.

### Existing consumer gates — scope confirmed for the night run
Üst görev mevcut veri uyumluluğu kod/test/inceleme/CI akışını tekrar onay almadan tamamlamayı onayladı. Negatif gerçek tüketici kanıtı organ kaynaklarının yalnız pending metadata ile korunmadığını, kaldırılan Carmustine guard-rule'ın ise mevcut correction kapısını atladığını gösterdi. Gerekli düzeltme mevcut iki tüketicinin dar kaynak kapısındadır; yeni klinik aile, genel admission mimarisi, tarih penceresi veya tıbbi predicate eklenmez.

- [x] boundary_audit: treatment_pricing mevcut legacy ve typed tüketicisinde explicit source_review_required durumunu predicate/ödeme sonucu öncesinde tarafsız review çıktısına taşı; kaynak inceleme flag'i olmayan kuralları koru, negatif ve normal tüketici regresyonlarını çalıştır.
- [x] authority_audit: organ kaynak locators/pending marker/policy digest verisini mevcut kapı sözleşmesiyle koordine et; değişen criteria'yı encoded sayma. İlaç correction guard'ının kaldırılmış geçersiz cite-rule'a bağlı olmadan source_target_mismatch davranışını korumasını mevcut temporal seam'de doğrula/düzelt.
- [x] authority_audit: deferral kaynak geçmişiyle kanıtlanan kayıtları mevcut canonical/ID sözleşmesiyle taşı; aynı key'deki farklı body/context veya çelişen judgment'ı otomatik medikal sınıfa atama, belirsiz kalanları açık raporla.
- [x] authority_audit: değişmeyen 2.4.1.(1) dental tam metin/context'i resmî October2 DOCX ile doğrula; mevcut dental_source_proof içinde yalnız gözlenen October2 snapshot sürümünü destekle ve ilgili mevcut policy digestini yenile. Hizmet tarihi/attestation alt sınırlarını, kaynak body hash'ini ve parasal davranışı değiştirme; unsupported snapshot/değişmiş body negatiflerini koru.

### Changed-source compiler contract — reviewed before implementation

Yalnız mevcut treatment_pricing_2_4 ailesinin üç değişmiş kaynak kaydı source_review_required=true, pending verification ve boş gate_b_sources ile derlenecek; tarihsel atıflar inert açıklama/makbuzda korunacak. İki mevcut consumer flag'i predicate öncesi tarafsız review olarak ele alır. Guard'ı olmayan ailelerde review-only marker kabul edilmez; normal encoded atıfların active/fullkey/heading kuralları gevşetilmez. İki değişmiş ff/gg kaydı ve bir yanlış hedefli Carmustine executable kaydı kaldırılırken mevcut temporal correction review davranışı korunur. Bu veri/derleyici sınırına pozitif/negatif test ve bağımsız inceleme gerekir.

Kaynak PR150 exact head58a73b117e71d9610d7e51cf854c3a23aba4fd7b tam CI476 başarılı:8069 backend/575 frontend,134 byte-identical artifacts,23 manifest/0issue. Corpus çalışma ağacı bu head'e ff edilmiş, başlangıç mekanik makbuzunun c4f736be baseline kanıtı değişmemiştir.

### Goal
Kaynak PR c4f736be tabanından PR128 corpus40b2 geçişini aynı klinik tarih ve binding sözleşmesiyle doğrulayıp ikinci dar PR için incelemeye hazır dosya paketi teslim etmek.

### Subtasks
- [x] Temiz corpus-transition worktree tabanı c4f736be ve 17f3694c kod/test kapsamını doğrula; mevcut repo talimatlarını oku.
- [x] Yalnız 17f3694c içindeki beş verifier/diff/test dosyasını ve iki clause-delta açıklama düzeltmesini taşı.
- [x] Gerçek PR128 candidate corpus ve tek atıf yapılan October2 DOCX baytlarını/hash'lerini doğrula; gerekli dosyaları seçerek hazırla.
- [x] Henüz değişmemiş c4f736be baseline katalog/corpus'u üzerinde yeni mechanical migration receipt üret; eski owner receipt'ini kopyalama.
- [x] Gerçek candidate corpus'u kur, katalogda yalnız corpus pinini ve Oct4 review evidence'e yeni receipt pinini ekle; tüm aile/pencere/hukuk/source alanlarını aynen koru.
- [x] Migration verifier/testleri ve kaynak PR'ın 538 hedefli testini onaylanan in-process ortamda gerçekten çalıştır; asset closure ve diff kontrollerini kaydet.
- [x] Exact CI generated gate engelini mevcut dar override/dependency yüzeyinde incele; önerilen ek dosya kapsamını yazmadan önce üst göreve bildir.
- [x] Aynı fulltext ve literal b) Word maddesi kanıtıyla mevcut YAML'da yalnız 4.2.8.A.b#2882a47a türünü bent olarak sabitle; başka key/opaque ID'ye taşınmadığını test et ve generated gate'i yeniden çalıştır.
- [x] Son dosya listesini, gerçek test sonuçlarını ve kalan engelleri üst göreve teslim et; bağımsız incelemeyi bekle.

### Out of Scope
Merge, deploy, VPS, commit/push, PR yayınlama; owner/parent repo yazımı; ingest_state, genel manifest/annex ve tüm442 PR asset'inin taşınması; klinik tarih, hukukî sınır, binding, schema/runtime değişiklikleri ve yeni ödeme uygunluğu iddiası.

### Specification and plan review
Üst görev iki PR sırasını ve bu dar implement paketini açıkça onayladı. Hedef Python3.13 mevcut Bilun .venv'dir. Başarı: c4f736be baseline ile gerçek PR128 Git blobu arasında72 unique binding/8 proof dosyası/12 aile bağlam uyumu; actual installed corpus40b2 ve yeniden üretilmiş makbuzla verifier/test geçişi;5Ekim fail-closed ve source PR continuity receipt fix'i aynen kalır. Plan kapsamı delegated talimatla eşleştirilerek implement öncesi gözden geçirildi.

### Progress evidence
Narrow dependency plan reviewed before write: Üst görev mevcut canonical YAML override desteği ile tek tür düzeltmesini gerekli corpus dependency olarak onayladı. Eski C004159 ve yeni C004167 için full normalized text SHA256 `2882a47a74ff4d7ab0194f6eb1ed4a2aeef8653bd3e370268280d125cc395d24`, coordinate4.2.8.A.b,section4.2.8.A,parent4.2.8,letterb,in_force ve non-heading aynıdır. Git DOCX direct body w:p indeksleri4377/4385 literal `b)` ile başlar ve full normalize edilmiş Word metni corpus'a birebir eşittir. Öneri yalnız `data/gazette/clause_type_overrides.yaml` canonical key→bent ve `tests/unit/scripts/test_stable_clause_type_overrides.py` persistent regression guard'dır; corpus, runtime/schema/strict encode şartı veya generated çıktı değiştirilmez. Kesin dosya/kanıt üst göreve yazmadan önce bildirildi.

Fresh receipt `corpus_migration_pr128.json` c4f736be kaynak baseline'ından gerçek49af2019 candidate Git blobu ile yeniden üretildi:12 aile/8 binding dosyası/72 unique binding; SHA256 `3c7f781b8e223adc6073e69b1dff4af7b5b0e7cb106814a1ca016dde8b3c5bde`. Kurulu corpus gerçek40b2,8413 satır,1421343 bayt. Katalogu yalnız corpus pinini ve Oct4 makbuz evidence satırını geri alarak karşılaştıran assertion tüm eski alanların birebir korunduğunu doğruladı; source_authority.py c4f736be ile bayt düzeyinde aynı. Yalnız tek October2 DOCX taşındı; ingest_state, annexler ve genel manifestler değişmedi.

Son 12 dosyalık birleşik pytest koşusu onaylanan in-process ortamda gerçekten tamamlandı: **579 passed, 3 warnings, 28.54s**. `TESTING=1 BILUN_AUTH_OPTIONAL=1 BILUN_AUTH_USERNAME= BILUN_AUTH_PASSWORD= BILUN_SESSION_SECRET= PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, pytest `--confcutdir=tests/unit -p no:cacheprovider -o faulthandler_timeout=30` kullanıldı. İlk koşudaki tek hata renal testin eski opaque ID beklentisiydi; beklenti runtime collector'dan değil sabit6 canonical clause key ve kurulu corpus lookup'tan türetildi. Oct4 parity günü migration testlerine eklendi; Oct5 review_required kaldı. Scoped Ruff ve `git diff --check` exit0. Kaynak verifier `--check --json-output /tmp/bilun-corpus-transition-source-assets-20261004.json`:12 aile/26 asset/through2026-10-04, exit0.

Exact CI `scripts/sut/audit_manifest_parity.py --drug-only`:23 manifest/23 trace/0 issue, exit0. `scripts/sut/compile_rules.py --check`:exit1, `csv_wave_clause_ids_metabolic_mid` hedefinde `4.2.8.A.b#2882a47a` candidate C004167(prose) strict encode-eligible şartını karşılamıyor. Aynı metin/key eski corpus'ta C004159(bent); candidate raw Git blobu da prose. Compiler finally bloğu önceden var olan çıktıları geri yükledi; git durumunda generated artifact değişikliği yok. Engelin dar dependency teşhisi sürüyor, bu gate başarılı diye sayılmadı.

### Final producer dependency closure — 2026-10-04

Üst görev, gerekli consumer source guard, runtime/code ve Git/draft PR akışını yetkilendirdi. Başlangıç owner paketinin Out of Scope listesi bu sonraki yetkiyi kısıtlamaz. Genel mimari, yeni medikal predicate/eligibility, tarih uzatması, merge/deploy/VPS kapsam dışında kalır.

Yenilenmiş coverage engine-owned ID envanteri yedi mevcut GateB manifestinin çıktısını değiştirdi. Mevcut compiler WRITE 43 hedefte exit 0; CHECK 134 artifact için byte eşitliği ve drug parity 23/23, sıfır issue ile tamamlandı. Mevcut 939 kural JSON'u byte düzeyinde değişmedi. Eklenen 214 trace aynı baseline full body/parent/context kaynaklarına eşleşti: 80 encoded trace mevcut kural cite'lerinden, 134 deferred trace mevcut authored judgment'tan geldi. Dört trace, existing other-engine primary ownership filtresiyle export'tan çıktı; eski trace payload değişimi sıfır. Provisional/current envanter ile final in-memory normalized producer, yedi engine-owned ID kümesinde birebir aynı doğrulandı.

Consumer report SHA256 `e348650810218bed7e7c8eec18be7e4161d66feda859f8103fa51a4a2bec456d`; catalog SHA256 `07d86ce0a1a978683a72457abe9400a954b0b1e69e9e8ce94b8d308ae2e24471`. 457 fixed input ve 134 monitored output pini kapalıdır (128 mevcut, 6 açıkça absent). Yalnız Oct4 review içindeki mekanik report pini yenilendi; kaynak pencereleri, hukukî sınırlar, tarihsel boşluklar ve clinical_eligibility_complete=false korundu. Kaynak verifier 12 family/27 asset, through Oct4 ile exit 0.

Önceki birleşik author testi **1.662 passed, 3 warnings, 33.65s** ayrı aşamadır. Coverage üreticisinin mevcut authored normalizer çağrısı ve stable source catalog fixture paketi **101 passed, 1 warning, 6.41s** tamamlandı.

Son beş coverage dosyası existing CLI ile final girdilerden üretildi; **124 passed, 1 warning, 7.57s**. 150 dependency hash'i freeze öncesi/sonrası ve evidence içinde birebir aynı; source corpus 40b2 değişmedi. 4.781 aktif satırın immutable ID/key/full body/context alanları ve production-normalized 31 kaynak alanında sıfır uyuşmazlık var. Meşru duplicate-key ekstra 111 satırın multiplicity'si korundu. Root final coverage sonrası compiler --check (134 byte-identical), global Ruff src/scripts, git diff --check ve 58-parent catalog deep comparison exit 0. Yalnız corpus pini ve iki mekanik evidence kaydı geri alınınca katalog tamamen parent ile eşit: version/date/legal/history/receipt alanları değişmedi.

Final coverage evidence SHA256 `6a4d26407b1c3ad8d365a523912aaff5dc4b2002562b07fffef1ea150c4d3092`; diğer dört parquet hash'i bu dosyada gerçek dosya baytlarıyla kayıtlıdır. Bağımsız final test hükmü ve hosted full CI henüz bu kayıtta başarı sayılmadı.

### Independent final review

Tek bağımsız birleşik paket gerçekten **468 passed, 2 mevcut RefResolver warnings, 25.25s** tamamlandı; failure/skip yok, 15 retrieval testi dahil. HTTP/fullsuite veya generator çalıştırılmadı; ayrı task-2 basetemp kullanıldı. Bağımsız source verifier 12 family/27 asset, through Oct4 exit 0. Son read-only assertions exit 0: 457 input, 29 test hash'i, 134 output (128 mevcut/6 deliberate absent) ve 150 coverage dependency hash'i birebir eşit. Katalog 58-parent ile yalnız corpus pini ve iki mekanik kanıt kaydı dışında tamamen aynı. 36 family/date kontrolünde Oct3–4 admitted, Oct5 uncovered_service_date/review_required, clinical_eligibility_complete=false. 4.781 coverage satırının 31 normalized kaynak alanı eşit; gerçek PR128 corpus 8.413 satır/40b2 byte uyumlu. Embedding 4.090×512 local-hash vektörlerinin tamamı yeniden hesaplanarak birebir eşleşti; body hash mismatch sıfır, cold/warm index aynı ve beş query kaynakla uyumlu. Runtime retrieval hash guard eklenmedi; doğrulanan mevcut artifact ve CI coherency testidir.

Bağımsız code/data review P1/P2 bulgu yok; yedi manifestin ek 214 atfı ve 500 mevcut trace payload eşitliği ayrı salt okunur incelemede doğrulandı. Geniş 44-manifest audit'indeki iki copay sorunu 58-parent ile aynı ve bu değişiklikte giderilmiş sayılmadı. Hosted full CI hâlâ bekleniyor; merge/deploy/VPS yapılmadı.

## Task: Corpus CI484 gerçek hatalarını dar kaynak/consumer kapılarıyla düzelt

### Goal
PR154 e11bd142 üzerindeki gerçek 41 backend hatasını mekanik fixture bağımlılığı ile gerçek runtime/snapshot driftini ayırarak düzelt; tarihsel serving izinlerini ve klinik sınırları koruyarak yeni exact head için hosted CI ve bağımsız incelemeyi tamamla.

### Subtasks
- [x] Root: CI484 logunu sakla ve 41 failure sınıflamasını gerçek kaynak/projection kanıtıyla kaydet; frontend tek retry sonucunu backendden ayrı raporla.
- [x] authority_audit: domain/prose stale C* beklentilerini old9639→40b2 aynı full body/context kanıtıyla değiştir; gerekirse yalnız test amaçlı static source identity helper/fixture sahipliğini seam ile paylaş. Consumer çıktısını oracle yapma.
- [x] corpus_seam_review: scripts/GateB/context fixture'ları ve negatif mutasyon hedeflerini gerçek kanıtlı kaynak satırlarına taşı; strict rejection beklentilerini koru. 4.2.14.C census'u bağımsız current source inventory ile doğrula.
- [x] boundary_audit: semantic fingerprint, focused legacy eşitliği, dental fallback, runtime coverage, pipeline smoke ve mevcut surfacing raporlarının gerçek kök nedenini önce bildir. Expected değerlerini yalnız CI geçsin diye değiştirme; gerekli mevcut dar consumer düzeltmesini projection/source kanıtı ve negatif test ile yap.
- [x] independent_review: özellikle historical old→3e release verifier fingerprint/source/serving kapsamının genişlemediğini, fixture bağımsızlığı ve negatif davranışın korunduğunu salt okuyarak doğrula.
- [x] Root: sahipler final code/test/output freeze bildirdikten sonra mekanik consumer report/catalog pin ve coverage evidence kapanışını mevcut helper'larla yenilet; dört coverage parquet'in değişmeden kaldığını veya gerçek gerekçeli üretim farkını açıkça doğrula.
- [ ] Gerçek değişen hedefli testler, compiler/parity/Ruff/source closure ve bağımsız review sonrası yalnız CI hata düzeltmesini commit/push et; yeni head hosted full CI sonucunu ayrı kaydet.

### Out of Scope
Yeni klinik yorum/predicate, tarih penceresi/hukukî sınır uzatma, genel mimari, historical old→3e fingerprintlerini global yeniden baselining, yeni serving transition izni, diğer PR151/152/153 entegrasyonu, frontend kodu, local fullsuite tekrarları, merge/deploy/VPS.

### Specification and plan review
Üst görev mevcut corpus geçişi kapsamındaki mekanik fixture/generated rapor düzeltmelerini açıkça onayladı; kritik fingerprint/dental/legacy durumlarında kaynak/projection kanıtı ve negatif test olmadan gevşetme yasak. Plan owner'lara uygulama öncesi bildirildi. Kaynak PR150 exact58a ve başarılı CI476 değişmez. CI484 gerçek sonuç **41 failed, 8239 passed, 27 warnings, 1124.41s**; compiler/parity backend failure nedeniyle hosted çalışmadı, başarılı sayılmaz. Frontend ilk job111533647997 typecheck/575 test geçti, build font-query hatasıyla düştü. Run bitince yalnız o job için bir rerun kabul edildi; backend rerun yapılmadı. Log task-2/corpus-ci484-backend-failure.log içinde.

### CI484 repair evidence before common closure

CI484 gerçek 41 failure node: 13 domain source-ID fixture, 20 scripts/GateB/source-context fixture, 8 kritik boundary alanı. Kritik alanlar iki gerçek consumer/package hatası (optional dental fallback None ve pipeline seçilen DOCX input-dir eşleşmesi), iki source/projection fixture, bir tarihsel public-coverage fixture ve üç existing surfacing generated-report kontrolüdür. Hosted ilk backend sonucu 41 failed/8239 passed kalır; ayrı frontend tek retry job111538195898 575 test/typecheck/build/public52 ile başarılıdır. Bu sonuç bütün CI başarısı sayılmaz.

Owner koşuları ayrı gerçek aşamalardır: authority RED13 failed/371 passed → GREEN393 passed13.18s; seam RED19 failed/47 passed (committed writer eski test hariç) → GREEN68 passed16.68s; boundary birleşik136 passed22.40s. Bunların toplamı fullsuite sonucu olarak kullanılmaz. 4214c writer tmp_path'a yazar; 655 census bağımsız gerçek source inventory ile hesaplanır. Static fixture131 aktif kimlik taşır; inactive C004584 remap edilmez,10 aynı full body/context eşleşmesi komşulukla ayrıştırılır.

Bağımsız salt okunur inceleme actual immutable Git3f/3e public generatorlarını yeniden çalıştırdı: baseline6ff617…/28input/c556eaf… ve product375aed…/30input/fa4e9ce… fixture/provenance birebir eşleşti. Release verifier/deploy source byte-unchanged; old→current ve current→current actualcoverage reddedilir, üç current route fingerprint pozitif kontrolü korunur. Consumer helper'dan bağımsız131source ve262komşuluk pini doğrulandı. Surfacing97row94byte-equivalent dictionary, exact3invaliddrugIDremoved, financial findings359→359. Ortak report/catalog/evidence kapanışı, final tek focused gate ve yeni exacthead hosted CI henüz pending.

### Final CI repair closure before publication

Consumer report SHA256 b273b9b6a972d5e963a55bda0e5731b35c1b06d7ff6bcf491c63d414e19820c8 (1466826B); catalog b4e65f80f2846699875679ce5ef74d6f55280aac6415189262ddebe89a154194 (19550B). Actual maps467 input/60 test/134 output(128present+6expectedabsent) sıfır uyuşmazlıkla kapandı; yeni3helper ve3historicalpublicfixture açıkça test provenance girdileridir, production/serving yetkisi değildir. Catalog yalnız existingconsumerreportSHA alanında değişti. Finalcoverageevidence227efe04c7cc785b4560d0f9e1b5b3712d1dd9d8e67ac6494809a08161f11dbe (127548B)150dependency içerir; yalnızcatalog/reporthashleri değişti, dörtcoverageparquet HEADe11 ile byte-identical kaldı.

Root compiler --check134byte-identical, drugparity23/23zeroissues, globalRuffsrc/scripts ve gitdiff--check gerçekten exit0. Tek son bağımsız pytest174passed/2mevcutwarnings/30.11s, exit0: CI484 original41failurenode (kanıtlı yeniden adlandırmalar dahil), helper/dental/pipeline negatives, historicalgolden/currentrejection, kaynak/coverageclosure ve11retrieval testi. JUnit sayımıyla ayrışan dört index initialization testi bu174 sayısında yoktur; yalnız bu eksik dört test ayrıca gerçekten4passed/0.20s ile tamamlandı. Son retrieval kapsamı11+4 ayrı koşudur. Independentfinalreadonly467/60/134/150hashpin,58-parentdeepcatalogcomparison,36family/date ve12family/27assetsourceclosure assertions exit0. Full hosted CI yenihead için henüz çalışmadı; bu174 sonuç CI484 history41fail/8239pass veya fullsuite sonucu ile toplanmaz. Merge/deploy/VPS yapılmadı.

CI repair bağımsız final code/data review: P1/P2 bulgu yok; post-test pin/dış hash/diff kontrolleri geçti. Tam actual komutlar ve sonuçlar task-2/independent-ci484-final-commands.json, review makbuzu task-2/independent-ci484-review-result.json içinde. Hosted yenihead fullCI sonucu bu incelemeye dahil değildir.

## Task: Exact-source EK-4A and idempotent SUT ingestion

### Goal
Publish a small verified draft PR repairing the producer and metadata while preserving clause history and admitting only exact-source EK-4A data.

### Subtasks
- [x] Verify current remote main and closed PR128 in a clean isolated worktree.
- [x] Prove stale-state/self-comparison root cause and write exact path plan in plans/update/2026-10-05-ek4a-ingest-idempotence.md.
- [x] Complete official-source decoded schema/key/history/name/discount/date comparison; record final exact source and partition before writing.
- [x] Preserve historical dated clause reports with positive, negative and idempotent rerun tests.
- [x] Repair exact-input completion and future-date handling without claiming full ingestion of partial source capture.
- [x] Admit exact current/MÜLGA EK-4A source/raw and honest partial manifest/state; preserve runtime curated bytes per approved deferral.
- [x] Run focused regression and canonical artifact checks.
- [ ] Open new draft PR, finish independent exact-head review and hosted full CI.

### Out of Scope
Main writes, merge, force push, deploy/VPS, secrets/auth setup, sourceauthority/clinical catalog/coverage edits, new payment or clinical interpretation, and duplicate local full-suite runs.

### Review

Final combined focused gate after the independent fetch finding: 250 passed in 22.15s. Global Ruff, compiler --check (134 byte-identical artifacts), drug manifest parity (23/23, zero issues) and git diff --check passed. Current main remains 3d29a1fe. Source/raw/manifest/state rerun preserves all six admitted file bytes; runtime EK-4A 8078, corpus 8413 and historical clause reports remain byte-identical to base. Official future markers prevent pre-October-10 curation; current catalog promotion and full 318-workbook October reconciliation are explicitly deferred. Draft PR162 is open. Independent review reproduced the exact source/raw and historical report proof; its fetch process-death P2 is fixed by atomic publication, with four abrupt-exit and two concurrent-publication regressions. Revised exact-head review and hosted full CI remain pending; no laptop full-suite repeat.
## Task: App UI overhaul, phase 0: screenshot baseline and numbers-parity capture (2026-10-07)

### Goal
One command produces the screenshot set, the numbers-parity JSON and the layout metrics for the plan routes from a local production build on the synthetic cohort, and a second command proves that two runs show the same numbers; the shipped UI does not change.

### Subtasks
- [x] Add `frontend/scripts/lib/numbers-parity.mjs`: pure functions that normalise rendered text and tokenise money (EN and TR forms, one canonical key), counts, percents and honesty markers, and that compare two runs; add `numbers-parity.test.mjs` (vitest picks it up) with EN/TR money, date masking, compare and exception cases.
- [x] Add `frontend/scripts/capture-screens.mjs`: CLI, identity (public by default, dev optional), chat stub, per-state settle, expand-all, extraction, screenshots, metrics, run-meta, fail-loud rules, `--compare`.
- [x] Put the verified local run commands (backend cache, backend with `--timeout-keep-alive 65`, build, start, capture) in the script header and run them from a clean shell.
- [x] Run the full capture twice on one build: `numbers/` and `text/` are byte-identical (`diff -r`), `metrics/` is identical at 1440 and 1280 except the deep-link scroll offset (390 px patient-page heights may differ by up to about 60 px, measured 19 to 59 px on 6 of 60 files); EN and TR canonical money maps are equal for every state.
- [x] Negative checks: backend stopped or injected 5xx gives a non-zero exit and no partial baseline; `--compare` fails on a changed amount and passes on an identical run.
- [x] Record the baseline set from a build whose `frontend/src` equals `approved/main` (`git diff approved/main --stat -- frontend/src` is empty) into `lanes/ui/baseline`.
- [x] `npx tsc --noEmit`, `npx vitest run`, `npm run build` stay green; `git diff approved/main --name-only` lists only the two scripts, the test and `tasks/todo.md`.

### Out of Scope
Any change under `frontend/src`, any backend, rule, amount, exactness or API change, the deploy lane, phases 1 to 8 of the plan, fixing the pre-existing 404 of `/api/frontend-config`, committing screenshots or recordings.

### Review (2026-10-07)
- Changed paths: `frontend/scripts/capture-screens.mjs`, `frontend/scripts/lib/numbers-parity.mjs`, `frontend/scripts/lib/numbers-parity.test.mjs`, this file. Nothing under `frontend/src`, no `package.json` or lockfile, no backend, no `.gitignore`.
- Gates (Node 22.16.0; CI uses Node 20, GitHub CI is the final arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 85 files / 614 tests passed (84 / 596 before plus the new 18); `npm run build` exit 0.
- Local run: backend :18001 (public billing mode, `--timeout-keep-alive 65`), `next start` :13000, capture with system Chrome 154. Full matrix: 86 numbers files, 86 text, 60 metrics, 120 PNG, `failedRoutes: []`, `warnings: []`, 325 to 338 s.
- Determinism: two full runs, `diff -r numbers` and `diff -r text` empty (86 + 86 files); `metrics/` identical except `deepLink.top` and 6 patient pages at 390x844 (height and first-money top differ by 19 to 59 px, the chat textarea autosize race); 95 of 120 PNGs byte-identical, so PNGs are evidence only. EN and TR money maps equal in 43 of 43 states.
- Fail loud (all run): injected 500 on one billing report gives exit 1 and no numbers file for that route; backend stopped gives exit 1 with only `run-meta.json`; backend without public billing gives exit 2; a proxy reporting `is_synthetic: false` gives exit 2. `--compare`: identical run passes; a changed amount, a hidden partial marker, a missing state and a changed identity fail; a multiplicity-only change warns and fails with `--strict-multiplicity`; the allow list suppresses exactly its entries and prints unused ones.
- Additions to the scout's code: unknown options, bad values and unknown route ids exit 2 instead of being ignored; `--out` must not already hold capture output (`--overwrite` replaces it) so a run never mixes with stale files; the deep-link route needs a finding on patient 0029 or `--no-extras`; unused allow entries are printed by `--compare`. The header no longer points at a plan file that is not in the repo.
- Baseline: `lanes/ui/baseline` (outside the repo, not committed), captured with `frontend/src` equal to `approved/main` (`c44aa78c`); `run-meta.json` records `dirty: true` because the two scripts and this file were not committed yet.
- Not run: Node 20 and Node 26, the standalone deploy runtime, a real LLM key (the chat is stubbed), `npm run lint`, backend pytest (forbidden in this lane), the developer identity (`--identity dev`, only run by the scout).

## Task: App UI overhaul, phase 0 fixer round: make the parity guard honest (2026-10-07)

### Goal
Every blocking finding of the phase-0 review is either fixed in the capture tool or answered with a measured reason, so that a pass of `--compare` can no longer hide a missing amount that became "0.00 TRY", two swapped amounts, or uncertainty wording that was collapsed away.

### Subtasks
- [x] Verify each finding against the code and the recorded baseline (scenarios re-run with the old tool: F1, F2, F3 and F4 reproduced; F5, F7, F8 and F9 reproduced in the browser or on disk; F6 and A5 measured).
- [x] numbers-parity: fail when the zero-amount count rises or a lone "-" placeholder disappears; never print "PARITY OK: no number changed" when warnings exist.
- [x] numbers-parity: record standalone amounts under their label and fail when a label that exists in both runs now holds other amounts.
- [x] numbers-parity: compare honesty wording by lines (default view: failure, expanded page: warning), add the "not evaluated", "missing inputs" and "amount unverified" families, fold Turkish dotted and dotless i so CSS-uppercased text still matches.
- [x] numbers-parity: warn when a baseline default-view amount is no longer in the default view; refuse to compare runs of different schema (schema 2).
- [x] capture: decide default-view visibility from the layout (probes in `lib/page-probes.mjs`, `--self-test` proves it in Chrome), write `<state>.visible.txt` next to `<state>.txt`.
- [x] capture: add money overlap and clipped-amount metrics, the TR postfix amount form and the chat input height to the metrics; print and record routes with collisions.
- [x] capture: add the 14 other Compliance and Reference Tools sub-views as routes (`lib/capture-routes.mjs`, drift test against `workspaceSubtabs.ts`).
- [x] capture: `--overwrite` stages the new run in `<out>.incomplete` and replaces the old output only after a complete run.
- [x] capture: errors go through `safeMessage` (no call log, no cookie, no ANSI codes) before they reach stderr, the log or run-meta.json.
- [x] Re-run tsc, vitest, build; re-record the baseline with the new tool and prove it is deterministic.

### Out of Scope
Anything under `frontend/src`, backend, rules, amounts, exactness, API shapes; fixing the app's chat textarea sizing or the deep-link scroll offset (they are app behaviour; Phase 1 replaces the chat panel); the other lanes; committing screenshots or baselines.

### Review (2026-10-07, fixer round)
Findings, one by one (all re-run against the old tool first; "answer" means a measured reason instead of a code change):
- F1 zero amount from a missing amount: correct. Old tool: `compareRuns` ok, warning only, "PARITY OK: no number changed", exit 0. Now `zero_amount_added` and `placeholder_removed` fail (default mode), and the last line is "PARITY OK WITH n WARNINGS ... not proof" whenever a warning exists.
- F2 amounts compared as an unlabelled multiset: correct. Now every amount that stands alone on the line under a label is recorded (`labelled`, 704 labels in the 86 old states) and a label that exists in both runs with other amounts fails (`label_amount_changed`). Limit, by design: amounts inside table rows or prose have no label, and it is text adjacency, not DOM structure.
- F3 marker presence only and missing vocabulary: correct. Now counted by lines (default view: failure, expanded page: warning) and extended by not evaluated, missing inputs, amount unverified, partial totals. "Unknown date" is not a UI string (no hit in `frontend/src`), so it was not added.
- F4 Turkish case folding: correct. `foldText` maps İ and ı to i before matching; tests cover KISMİ KESİN, KULLANILAMIYOR, DEĞERLENDİRİLMEDİ, TUTAR DOĞRULANMADI.
- F5 innerText keeps CSS-collapsed text: correct (Chrome 154: height 0, max-height 0, grid 0fr, opacity 0, clipped sr-only box, left -9999px; excluded only display none, [hidden], visibility hidden, closed details). Now the default view is read from the layout (`lib/page-probes.mjs`); `node scripts/capture-screens.mjs --self-test` proves it in Chrome (also with the probe weakened: it fails). In today's UI the two readings are identical (checked on Patients, Revenue, Compliance, patients 0003 and 0017), so the baseline numbers did not change; the guard protects Phase 6.
- F6 coverage: correct. 14 more routes (7 Compliance and 7 Reference Tools sub-views, 84 more states, 170 in total); a drift test ties the ids to `workspaceSubtabs.ts`. A baseline default-view amount that leaves the default view but stays on the page is a warning (`default_view_amount_hidden`), not a failure, and there is no must-stay-visible list: Phase 2 collapses on purpose, so a person reviews each warning.
- F7 money wrap blind in TR and no overlap measure: correct. `moneyOverlapCount` (two text boxes sharing a line band) and `moneyClippedCount` (amount cut off by a clipping ancestor or the page) now exist, plus the TR postfix form "9000.00 ₺". They find the split-pane collisions of the review (EN 1440: 5, EN 1280: 7, TR 1440: 8, TR 1280: 9; confirmed on the PNGs) and the cut-off bill chips on patient 0003; single-pane desktop routes report 0 overlaps.
- F8 `--overwrite` deleted the baseline before the preflight: correct. The new run is staged in `<out>.incomplete` and replaces the old output only after a complete run (run: backend down gives exit 1 with all 34 old files intact; success path replaces everything).
- F9 session cookie in stderr and run-meta.json: correct. `safeMessage` drops the call log and ANSI codes and redacts registered secrets (run: fake env file and closed port gives exit 1, zero hits for bilun:session, the secret and ESC in stderr, stdout and run-meta.json). Not run: `--identity dev` against a real backend.
- F10 marker vocabulary and TR case: same defects as F3 and F4, fixed together.
- A5 metrics jitter at 390: the 45 px bound was too tight, the tool is not at fault. Cause found: `SutInlineAIPanel.tsx` sizes the chat textarea once at mount (`syncInputHeight`, effect on `input` only) while the width is not final, so the textarea is 114, 133 or 144 px tall in the baseline instead of 55 or 75 px, and it flips between runs. `metrics.chatInputHeight` now records it. Measured: of 48 files at 390 the two final runs differ in 1 (tr patient-0029: chat 144 vs 133, scrollHeight, firstTableRowTop and firstMoney.top all 11 px apart, nothing left unexplained). The review saw up to 59 px (3 lines). At 1440 and 1280 all 96 metrics files are identical. `deepLink.top` is the page's own scroll offset, not a stable number. This is app behaviour, so it stays; the criterion now reads "identical at 1440 and 1280, and at 390 identical after removing the chatInputHeight difference".

Results:
- Gates (Node 22.16.0; CI uses Node 20, GitHub CI is the final arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 87 files / 641 tests passed (614 before: parity tests 18 to 40, routes 2, safe message 3); `npm run build` exit 0 (API_PROXY_TARGET unset, like CI); `npx eslint` on the scripts exit 0; `--self-test` OK.
- Baseline re-recorded because the stored JSON gained fields (schema 2) at `lanes/ui/baseline`: 170 states, 144 route captures, 288 PNG, 631 s, no failed route, cohort 50. The schema-1 baseline is kept at `lanes/ui/baseline-schema1-e20a206a`; comparing against it exits 2 with a re-record hint. The 86 old states have the same expanded text (86 of 86 files) and the same money, counts and percents as before, so the app recorded is the same (`frontend/src` equals `approved/main`).
- Determinism, two full runs: `diff -r numbers` (170 files) and `diff -r text` (340 files) empty; `--compare --strict-multiplicity` exit 0 with 0 failures and 0 warnings; metrics identical at 1440 and 1280, see A5 for 390; 263 of 288 PNGs byte-identical (evidence only).
- Reviewer scenarios through the real CLI (`--compare`) on the new baseline: null money to 0.00 exit 1; swapped amounts exit 1; one of two Partial exact lines or two of three unavailable lines collapsed exit 1; Not evaluated lines removed exit 1; TR uppercase partial line removed exit 1; unchanged control exit 0; headline amounts leaving the default view exit 0 with "WITH 19 WARNINGS"; a merged duplicate exit 0 with "WITH 1 WARNING".
- The run-meta.json of the baseline records the sha256 of the five tool files; `git.dirty` is true because the commit came after the recording, the hashes match the committed files. One trailing blank line of `numbers-parity.mjs` was removed after the recording (whitespace only, diff checked); its hash in run-meta.json was updated and the old value is kept in `toolHashNote`.
- Not run: Node 20 and Node 26, GitHub CI, `npm run lint` on all of `src`, backend pytest (forbidden in this lane), `--identity dev` against a real backend, a real LLM key (chat stubbed). Servers on 18001 and 13000 were stopped by PID; scratch captures under `~/.cache/ui-capture-tmp` and `.next` were removed.

## Task: App UI overhaul, phase 0 fixer round 2: close the guard's remaining blind spots (2026-10-07)

### Goal
The seven blocking findings of the second phase-0 review are each either fixed in the capture tool (with a failing case first) or answered with a measured reason, so that the baseline covers all 50 patients, the Source drawer and the wording a collapse would hide, and a collapsed box can no longer pass as visible.

### Subtasks
- [x] Verify each finding against the code and the recorded baseline before touching anything (baseline text, the live app on 18001/13000, Chrome 154).
- [x] Page walk: add `page-2` to `page-N` states for the Patients tab (`?p=N`, primary size, both locales), fail the route when the pages do not show every cohort patient, record the pager of every captured route in the metrics, list paged tables that are not walked (Reference Tools Drugs, Compliance Materials) in run-meta.
- [x] Source drawer: add `source-drawer` (page-level drawer opened by "Inspect clause") and `source-drawer-copay` (the second drawer instance) per primary patient where the button exists; include the modal dialog in the scope (nested scopes counted once); add a viewport PNG per drawer state.
- [x] Marker vocabulary: add the families that today's uncertainty lines need (could not be verified, cannot evaluate, estimated, manual review, no value inferred, no match, not exact, more findings available) in EN and TR, tested against the real strings of `messages/en` and `messages/tr`; bump the schema to 3 so an old baseline is refused.
- [x] Labels: compare label keys case- and dotted-i-folded, and warn (with a count) for every baseline label that holds amounts and has no counterpart in the candidate, so a renamed label is never skipped silently.
- [x] Probes: decide hidden for a clipping box from its content box (padding and border do not keep a collapsed box visible), also for a transform that scales a box to nothing and for a clip-path inset that clips everything; add the padded cases to the self-test first (they fail today).
- [x] CI: move the self-test cases into `lib/probe-selftest.mjs` and run them from vitest when Chrome is installed (skipped with a visible reason otherwise), so `npx vitest run` guards the probe.
- [x] Wave A: record in run-meta whether the backend serves Wave A evidence (it does not in a local synthetic run; the receipt cannot be issued here), print it at the end of a capture and write the limit into the header; no data is faked.
- [x] Re-run tsc, vitest, build; re-record `lanes/ui/baseline` with the schema-3 tool (the schema-2 baseline is kept), prove determinism with a second run, replay the reviewers' scenarios through the real CLI.

### Out of Scope
Anything under `frontend/src`; backend, rules, amounts, exactness, API shapes; faking or stubbing Wave A evidence or a signed activation receipt; walking all 270 pages of Reference Tools Drugs; the split-pane drawer state; opening every clause button (one per kind and patient); fixing app behaviour the tool only measures; the other lanes; committing screenshots or baselines.

### Review (2026-10-07, fixer round 2)
Findings, one by one (each reproduced against the old tool or the recorded baseline before any change):
- F1 Patients table captured for page 1 of 5: correct (baseline: "Page 1 of 5", 10 rows, 10 amounts; 40 of 50 patients in no file). Fixed: states `page-2` to `page-5` through `?p=N` at the primary size in both locales; the route fails unless the pages show all 50 cohort patients (verified live: 5 pages, 50 distinct ids, `?p=6` clamps to page 5, which the tool also rejects). Reference Tools Drugs (page 1 of 270) and Compliance Materials (rows 1-100 of 163) are NOT walked: 270 pages of reference data is not worth 540 states, and Materials has no URL page param. They are recorded as data (`run-meta.json` `limits.unwalkedPagers`, `metrics/*.json` `pagers`), printed at the end of a run and named in the header and in the baseline README. The Materials gap (63 findings and their amounts) matters for Phases 3 and 4.
- F2 Source drawer in no state: correct (0 hits of "Legislation" or "Mevzuat" in 170 states). Fixed: `source-drawer` (page-level drawer, first "Inspect clause" button) and `source-drawer-copay` (the second instance in the copay section) for patients 0003, 0029 and, copay only, 0017; the modal dialog renders outside `#main-content`, so dialogs are part of the scope (nested scopes counted once, `scopesOf`); one viewport PNG per drawer state. Limits found while doing it: on the three primary patients the Compliance findings table has no row with a clause key, so only Recommended actions rows (revenue view) and copay links open a drawer; patient 0017 has no "Inspect clause" button (listed in `skippedStates`); other clauses, the split pane and the drawer's loading and error states are not captured. The drawer text is Turkish in both locales and its kicker reads "Legislation" or "Mevzuat".
- F3 uncertainty wording outside the vocabulary: correct (tokenise returned `{}` for all seven lines). Fixed: families unverified, estimated, manualReview, notInferred, mismatch, notExact, incompleteList, and cannotCompute widened to "cannot evaluate" (EN and TR), tested against the real strings read from `messages/en` and `messages/tr` (28 key checks plus the estimate lines) and by the review's repro. The vocabulary is words, not meaning: a line worded differently is not protected until its words are added (header of `numbers-parity.mjs`). Schema is now 3, so a schema-2 baseline is refused (exit 2).
- F4 renamed or re-cased label skipped silently: correct. Fixed: labels are compared folded (case, dotted and dotless i), so the review's repro (swap plus re-case) now fails with `label_amount_changed`; a baseline label with amounts that has no counterpart is a `label_not_in_candidate` warning with the label and its amounts (the verdict then says "WITH n WARNINGS"), and `--strict-labels` turns it into a failure that an allow entry (kind labelled) can waive. Limit that stays: a swap hidden behind a rename cannot be told from a rename; by default it is a warning (exit 0), so a script that gates only on the exit code must pass `--strict-labels`.
- F5 and F7 padded or bordered collapsed box counted as visible: correct (all four review cases, plus a padded grid child, `scaleY(0)`, `scaleX(0)` and `clip-path: inset(50%)` or `inset(0 0 100% 0)` were kept). Fixed in `page-probes.mjs`: a clipping box is hidden when its content box (clientWidth or clientHeight minus padding) is under 2 px; a transform that shrinks a laid-out box to nothing; a clip-path inset that leaves no area. The 10 hidden cases (and 4 visible controls: padded box, absolute badge in the padding, translate and scale, a small inset) were added to the self-test first and failed on the old probe, then passed; three weakened probes (no content-box rule, no transform rule, no clip-path rule) make the vitest test fail. Not detected, and said so in the header: other clip-path shapes, `color: transparent`, `text-indent: -9999px`, text covered by another element.
- F5 CI part: the self-test cases moved to `lib/probe-selftest.mjs`; `page-probes.test.mjs` runs them in system Chrome under `npx vitest run` and is skipped (visibly) when no Chrome is installed (`BILUN_CHROME_PATH`, `/usr/bin/google-chrome`, `/opt/google/chrome/chrome`). The ubuntu runner image of GitHub is documented to include Google Chrome, but I have not verified that here and could not run GitHub CI: that is the open risk of this round (if Chrome is missing there the test is skipped, not failed).
- F6 Wave A never rendered: correct and NOT fixable here. The backend serves Wave A only with a signed release receipt (`wavea_capability_unavailable`), which a local synthetic run cannot have, and faking it would put invented data in a baseline. Recorded as data (`run-meta.json` `limits.waveAEvidence`, a line at the end of every run), in the header and in the baseline README. Consequence, stated plainly: the Phase 2 criterion "page height at 1440 with default collapses at most 3,500 px, measured by the Phase 0 script" cannot be judged honestly with this baseline (patient 0003 is 5,657 px here without the largest block), and the collapse rule "partial and unavailable stay in the header line" must be tested with component fixtures or on an environment that serves Wave A.

Results:
- Gates (Node 22.16.0; CI uses Node 20, GitHub CI is the final arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 88 files / 684 tests passed (87 / 641 before: parity 40 to 77, routes 2 to 7, probes 1 new file); `npm run build` exit 0 (API_PROXY_TARGET unset, like CI); `npx eslint scripts` exit 0; `--self-test` OK.
- Baseline re-recorded at `lanes/ui/baseline` (schema 3, commit 2f57b401, clean tree, six tool hashes in run-meta): 188 states, 144 route captures, 298 PNG, 702 s, no failed route, cohort 50. The schema-2 baseline is kept at `lanes/ui/baseline-schema2-00088602`. New states: 8 pages, 10 drawers. The 170 old states: all 340 text files byte-identical to the schema-2 baseline (so the new probe rules and the dialog scope change nothing today), money, counts, percents, placeholders and labelled identical, old marker counts identical; only new marker kinds appear.
- Determinism, two full runs (A at 78d80d5f, B at 2f57b401, the only tool change between them is `--strict-labels`): `diff -r numbers` (188) and `diff -r text` (376) empty; `--compare B A --strict-multiplicity --strict-labels` exit 0 with 0 failures and 0 warnings; metrics identical at 1440 and 1280 (96 of 96) and at 390 except 4 patient pages whose every difference equals the `chatInputHeight` difference (30, -30, -30, -11 px); 267 of 298 PNGs byte-identical (evidence only).
- Review scenarios through the real CLI (`--compare` on the new baseline): control exit 0; "could not be verified" line hidden in the default view exit 1 (`marker_hidden_in_default_view unverified`); "cannot evaluate" line hidden exit 1; TR "doğrulanamadı" line hidden exit 1; "is estimated from the EK-3" line hidden exit 1; amounts swapped and labels re-cased exit 1 (2 x `label_amount_changed`); one amount of a patient on page 3 changed exit 1; page 5 of the Patients table missing exit 1; Source drawer state missing exit 1; amounts swapped and labels renamed exit 0 with "WITH 2 WARNINGS" and exit 1 with `--strict-labels`.
- Not run: Node 20 and Node 26, GitHub CI, `npm run lint` on all of `src`, backend pytest (forbidden in this lane), `--identity dev` against a real backend, a real LLM key (chat stubbed), the split-pane drawer, a walk of Drugs and Materials.
- Cleanup: backend (18001) and `next start` (13000) stopped by PID, ports free; `.next`, scratch captures under `~/.cache/ui-capture-tmp` and the scenario work dirs removed.

## Task: App UI overhaul, phase 1: page frame, content first (2026-10-07)

### Goal
At 1440x900 and 1280x800 the first Patients table row is above y = 300 and the patient money summary is in the first screen; the chat is a one-line collapsed bar that calls the model only after it is opened, the cohort filter is one toolbar row, the patient page has no standalone search card, and a sub-view tab reads "Parent · Subtab"; no amount, count, exactness state, rule or API changes.

### Subtasks
- [x] Dock model: add `"collapsed"` to `SutChatDockPosition` and make it the store default (owner decision D1); add `lib/chatDockPreference.ts` (key `bilun:chat-dock`, SSR-safe read and write, an unknown value gives the default) with a test; the store action `setAiDockPosition` remembers the user's choice, `NavigationProvider` applies the saved choice in a layout effect after hydration, `WorkspaceSplitLayout` forces right-to-center with `setState` so it never overwrites the saved dock, and `AppSidebar` reads the saved dock itself for its first width.
- [x] `SutInlineAIPanel`: render the collapsed one-line bar ("Ask Bilun…" plus dock buttons) after all hooks; one collapse/open button in both states that hands keyboard focus to its twin; new prop `allowRightDock` (false while a split view is open: collapse and open stay, the right column goes); the component's own default dock stays `center`.
- [x] Auto-brief gate on every path (mount debounce, locale change) and a new effect that briefs once when the panel opens; keep `dock` out of the context effect's dependencies so docking or collapsing never aborts a stream; the Regenerate button lives only in the open panel.
- [x] Pages: replace `chatDock !== "center"` with `isChatDockedRight(chatDock)` in `app/page.tsx` and `app/patient/[id]/page.tsx` (the helper lives in `lib/chatDockPreference.ts`, not in `lib/chatDockLayout.ts`, which reads a constant of the panel module that page tests mock away); both pages pass `onDockChange={setChatDock}` and `allowRightDock={!splitActive}`; `lib/chatPanelMount.test.ts` stays green unchanged.
- [x] Patient page: remove the card at `app/patient/[id]/page.tsx:515-550` (breadcrumb, patient search, description) and its dead code (`handlePatientSelect`, four imports); keep `components/ui/PatientSearch.tsx`; "Back to patients" stays; Ctrl+K and the tab-strip search button remain the patient search, and a test pins that Quick Open finds a patient by id and opens it.
- [x] `CohortFilterBar`: one `Toolbar` row (four labelled controls with fixed widths, "Clear filters" while a filter is active, the "N of M patients" chip, no header text), props and the three callers unchanged; no "0 of 0 patients" while the list is empty (not loaded, or failed); component test in EN and TR.
- [x] Spacing so the first Patients row is above y = 300 (prototype measured 286, plan-literal edits alone about 340): `.sut-app-main` top padding 1rem, invoice table card `md` padding, `space-y-4` in `SUTPatients`, `SUTCompliance` and `SUTRevenue`, toolbar `py-2`, chat bar `py-1` and `mb-3`; the content width (`max-w-7xl`) is unchanged.
- [x] Tab label: `resolveTabInfo` returns `"Parent · Subtab"` as `label` (the same text as `fullTitle`); raise `WORKSPACE_TAB_MAX_PX` from 208 to 280 so none of the 22 labels is cut in EN or TR; update the 15 label assertions in `lib/workspaceSubtabs.test.ts` and add the 22-label matrix test with the real messages.
- [x] Messages (EN and TR): add `chat.actions.collapse`, `chat.actions.expand`, `chat.collapsed.prompt`, `chat.collapsed.working`; remove `cohort.filterBar.description` and the seven keys of the removed card (`patient.page.breadcrumbAria`, `workspace`, `patient`, `patientUnknown`, `searchEyebrow`, `searchPlaceholder`, `searchDescription`); keep `cohort.patientSearch.ageSuffix` and `patientDetails` (used by `lib/cohortFilter.ts`).
- [x] Tests: `navigationStore.test.ts` (default collapsed; only a user choice is remembered), `chatDockLayout.test.ts`, panel tests (collapsed markup EN/TR, split-view controls, no brief while collapsed, one brief on open, no abort on collapse, locale change while collapsed), patient page pane test (no search card, chat props), `WorkspaceQuickOpen.test.tsx`, `CohortFilterBar.test.tsx`, `chatDockPreference.test.ts`.
- [x] Gates: `npx tsc --noEmit`, `npx vitest run`, `npm run build`; `npx eslint` on the touched files shows nothing beyond the 8 existing problems; a full capture of the branch compared with `lanes/ui/baseline` using `--strict-multiplicity --strict-labels` ends in PARITY OK without warnings, and the line-by-line text diff shows only the expected lines removed and added.
- [x] Browser checks (probes in the spec appendix): 0 chat requests on load and exactly 1 after Open on the 5 home tabs a billing user sees (Rule Database is developer-only) and a patient page, the saved dock restored without hydration errors for collapsed, center, right and an unknown value, expand inside a split view, focus handoff, Quick Open by Ctrl+K and by the strip button in EN and TR, 390 px loads identical.

### Out of Scope
Phase 2 and later (summary row, next actions, Source drawer, collapsing secondary blocks), any backend, rule, amount, exactness or API change, deleting `components/ui/PatientSearch.tsx`, mobile and tablet layout (Phase 7), motion (Phase 6), a cookie so the server can render the saved dock, syncing the dock between browser tabs, the `/api/frontend-config` 404, the `0.00 TRY` values the API itself returns, committing screenshots or baselines.

### Review (2026-10-07)
What was built: the scout's verified prototype (`lanes/ui/phase-1/spec.md`, Appendix A) was read in full (all 1,723 lines) and applied with `git apply -p1`; the only change on top is that three test files lost a trailing blank line (`git diff --check` was not clean). 33 files under `frontend/src` (29 changed, 4 new: `lib/chatDockPreference.ts` and three new test files) plus this entry; no backend, `package.json`, lockfile, workflow or capture-tool file.

Gates (Node 22.16.0; CI uses Node 20 and stays the arbiter), on the final tree:
- `npx tsc --noEmit` exit 0; `npx vitest run` 91 files / 711 tests passed (baseline 88 / 684); `npm run build` exit 0 (`API_PROXY_TARGET=http://127.0.0.1:18001`).
- `npx eslint` on the 32 touched `.ts` and `.tsx` files: 7 problems, all pre-existing (`app/patient/[id]/page.tsx` 78, 295, 305, 375 and `CohortFilterBar.tsx` 47, `AppSidebar.tsx` 90, `PatientInvoiceTable.tsx` 136; the lines moved by 1 or 2 where imports were removed). The eighth known problem (`WorkspaceTabStrip.tsx:24`) is in a file this phase does not touch. `SutInlineAIPanel.tsx` is clean.

Acceptance, measured on a real `next build` and `next start` of this branch (backend 18001, frontend 13000, synthetic cohort of 50, chat endpoint stubbed because there is no LLM key):
- Full capture: 188 states in 645 s, no failed route, same 2 skipped states as the baseline (patient 0017 has no "Inspect clause" button).
- First Patients table row top: 286 at EN and TR, 1440x900 and 1280x800 (baseline 612, 612, 612, 630). First amount of the three patients: top 507 (baseline 852); headline amounts end at 552 to 589 (EN) and 552 to 559 (TR), inside both viewport heights. Compliance and Revenue first amount moves up 318 px; patient pages are 345 px shorter, Compliance and Revenue 318 px.
- No chat request without a user action: 0 `POST /api/chat` on load on the 5 home tabs and patient 0003, 0 after five client-side tab switches, exactly 1 after "Open chat", still 1 after collapse and reopen; a tab switch while open briefs the new tab once (2 in total, as today). Focus moves to "Collapse chat" after Open and to "Open chat" after Collapse.
- Saved dock (12 loads, 6 values x 2 pages): `bilun:chat-dock` restores collapsed, center and right; "left", "garbage" and no value give the collapsed bar; no React or hydration error. Saved right: panel fixed, `--chat-dock-inset-right` 412 px, sidebar rail 64 px, section `w-full`. Collapsed and center keep `mx-auto max-w-7xl` (width 1172 and 1012, no horizontal scroll). A split view shows "Open chat" and no "Dock right"; after Open one request, Collapse and Center buttons; a saved right dock is still `right` in storage after a split opens.
- Cohort filter: one toolbar row, 77 px high at 1440 and 1280, EN and TR, inactive and active (`?cohortSex=E`); at 1100 px it wraps to two rows (115 to 119 px), which the plan does not cover. No "0 of 0 patients": not in the server HTML, not while `/api/patients` is slow, not after a 500; "50 of 50 patients" when settled.
- Patient page: no search input, no combobox, no breadcrumb; "Back to patients" present (12 cells). Quick Open finds a patient by Ctrl+K and by the strip button in EN and TR and opens it. Tab labels: 22 of 22 equal "Parent · Subtab" in EN and TR, 0 cut at 280 px; the live strip shows "Compliance · Copay Rates". 390 px: no textarea, three loads of Patients, 0003 and 0017 have identical heights (1095, 9521, 7827); horizontal-scroll flags unchanged. Deep link `?section=claim-compliance&finding=...`: `found` true in 6 of 6 cells (offset unstable, as the baseline README says). Split view metrics (money overlaps 5, 7, 8, 9 and wraps) unchanged.

What the numbers guard compared and what it cannot see (do not read "PARITY OK: no number changed" as a claim about everything):
- `--compare lanes/ui/baseline <candidate> --strict-multiplicity --strict-labels` exit 0: 188 states, 0 failures, 0 warnings. It compared the set of amounts, counts, percents and uncertainty wording per state and the standalone amounts under their labels (about 10 percent of the amounts). Amounts inside table rows, bill chips and prose are compared as a set, so a swap between rows would not fail it; clipped text counts as visible; it does not see controls, order, the tab strip, layout, requests, the saved dock or hydration.
- Because of that, two extra checks were run: `diff -rq` of the numbers folders (188 of 188 files byte-identical) and the in-order text check `textdiff.py` (spec Appendix C): 376 text files, 2,680 expected lines removed (chat card, filter header, patient search card and breadcrumb), 0 files with an unexpected difference; one injected defect (two headline amounts swapped) made it exit 1. By hand (script, not by eye) the 30 headline label and value pairs (5 labels x patients 0003, 0017, 0029 x EN and TR, 1440x900, default view) are identical, including the two `0.00 TRY` / `₺0,00` recoverable values of 0017 and 0029 that the API returns itself. The default view holds 536 uncertainty-wording lines (partial, unavailable, not evaluated, could not be verified, estimated and the TR forms) before and after; the 188 lines that disappear are the chat stub answer "temporarily unavailable" (one per state; a collapsed chat does not brief), which is not billing wording.
- A reviewer must still compare the rows and columns of the bill picker, findings table, summary row and Patients table pages 1 to 5 by hand, and repeat the pairs for 0003, 0017 and 0029; the guard and my scripts are not a substitute.

Deviations from the plan (all taken from the scout's recommendations D-1 to D-4; the owner decided D1 to D5 of the plan, not these four):
- D-1 tab width: `WORKSPACE_TAB_MAX_PX` 208 to 280, because "Parent · Subtab" is cut in 12 (EN) and 13 (TR) of 22 tabs at 208 px. Fewer tabs fit before the strip scrolls.
- D-2 the plan range `page.tsx:515-550` also held the breadcrumb; it is removed with the search card ("Back to patients" and the header keep the information).
- D-3 the filter chip is hidden while the cohort list is empty (the old chip read "0 of 0 patients" for missing data). A genuinely empty cohort also shows no chip.
- D-4 the plan's own edits give a first row at about 340, not below 300; six extra spacing trims (global `.sut-app-main` top padding 1rem, invoice card padding `md`, `space-y-4` on three tabs, toolbar `py-2`, chat bar `py-1` and `mb-3`) reach 286. The content width is unchanged.
- The component default dock stays `center` (seven existing static-markup tests); the collapsed default lives in the store. `components/ui/PatientSearch.tsx` is kept (dead code, delete later).

Not run: Node 20 and GitHub CI; `npm run lint` over all of `src`; backend pytest (forbidden in this lane); a real LLM key (opening the panel with live answers and chat error states; the endpoint was stubbed); the developer identity; Wave A evidence (not rendered locally, so Phase 2 page-height targets cannot be judged); the split-pane Source drawer; Reference Tools Drugs and Materials past page 1; a pixel-by-pixel visual review (four screenshots were looked at: Patients, patient 0003, the split view, the deep link); the five injected-defect checks of the scout were not repeated (one was); the 390 px capture beyond the three-load height check.

Cleanup: backend (18001) and `next start` (13000) stopped by PID, both ports free; `frontend/.next`, `tsconfig.tsbuildinfo` and the scratch captures under `~/.cache/ui-capture-tmp/p1` removed. Known limits for the PR: a user with a saved non-default dock sees the collapsed bar between the server HTML and hydration (a cookie would avoid it); the dock does not sync between browser tabs; Quick Open returns at most 8 results and none before a character is typed (the removed card listed 20).

## Task: App UI overhaul, phase 1 fixer round: review findings (2026-10-07)

### Goal
Each blocking finding of the phase-1 review is either fixed with a measured result or answered with a measured reason, and the page-frame behaviour of the collapsed default (layout class, saved dock, split-view rule, sidebar first width) is pinned by tests that fail when it is broken.

### Subtasks
- [x] Verify each finding on a production build of `78f7b0f2` (backend 18001, frontend 13000, synthetic cohort): finding 2 (right dock header) and finding 3 (patient select) reproduced with the numbers of the review; finding 1 reproduced in the code, the API payload and the phase-0 baseline text; findings 4 and 5 reproduced by mutation.
- [x] `SutInlineAIPanel`: the header row wraps (`flex-wrap`), the control group sits at the end (`ml-auto`), so four controls beside "Patient: <id>" never run past the viewport edge; a test pins the markup.
- [x] `CohortFilterBar`: patient select 310 px with `pr-3`, sex 116 px (`min-w-0`), age 112 px, doctor 120 px, plus a `title` with the full label; a test pins widths, padding and title.
- [x] Tests for the default-state layout class: patient page (collapsed, center, right, embedded) in `page.panes.test.tsx`, new `app/page.test.tsx` (also the `allowRightDock` rule of the home page).
- [x] Tests for the restore half of the dock: new `navigationContext.test.tsx` (saved dock applied after the first render, never written back, unknown value gives the default, blocked storage), `WorkspaceSplitLayout.test.tsx` (right becomes centre without a write), `AppSidebar.test.tsx` (saved right dock gives the 64 px rail from the first paint).
- [x] Mutation checks of every new test (13 mutations, all caught); tsc, vitest, build.
- [x] Browser checks of the fixes on the final build in EN and TR at 1440 and 1280, single pane and split pane; pixel check that no filter control clips its own text; widths 360 to 1024 for horizontal scroll.
- [x] Full capture of the final tree (188 states) compared with the baseline and with the capture of `78f7b0f2`; it caught that a fixed 310 px select made 20 states scroll sideways at 390 px, so the patient select is `w-full` below 640 px.
- [ ] Finding 1 (frontend "0.00 TRY" from a sum of nulls) is NOT fixed in this phase; see Review.

### Out of Scope
Finding 1 (`complianceBilledAtRisk` / `audit_exposure_try ?? 0`, present on `main`, changes a shown amount, so it belongs to Phase 2 where the figures move into the summary row); the P3 items of the reviews (focus after Open, two tab stops in the bar, contrast, cookie for the saved dock, sidebar width of a saved right dock inside a split view, deep-link scroll margin); backend, rules, amounts, exactness, API shapes; Phase 2 and later.

### Review (2026-10-07, fixer round)
Findings, one by one (each re-run on a production build of `78f7b0f2`: backend 18001, frontend 13000, synthetic cohort of 50, Chrome 154):
- Honesty P2, `complianceBilledAtRisk` (`lib/workspaceViews.ts:90-96`, used at `ComplianceViewSection.tsx:72,95`, and `audit_exposure_try ?? 0` at :73): correct, and not caused by Phase 1. Live API for SENTETIK-HASTA-0003: the 4 `billing_strategy` compliance findings and the `drug_indication` finding all have `billed_try` and `audit_risk_try` null, so the card prints "Billed amount at risk 0.00 TRY" from a sum of nulls (`sum + (billed_try ?? 0)`); the phase-0 baseline `text/en/1440x900/patient-0003/default.visible.txt:113-114` already has the same pair. NOT fixed here, by decision: it changes an amount that is on screen (the baseline would no longer match, which is the proof this phase relies on), it is a calculation-level change in a figure Phase 2 moves into the new summary row anyway, and the owner limited this phase to the page frame. Phase 2 must show a dash or "unavailable" (not 0.00) for `complianceBilledAtRisk` when no at-risk action carries a billed amount, and for `audit_exposure_try` when it is null, with a test that feeds null amounts and asserts no "0.00".
- UX P2, right-dock header cut off on the patient page: correct. Before: "Dock right" at x 1420-1448 of a 1440 viewport (8 of 28 px outside) in EN, 1441 in TR, panel scrollWidth 387 > clientWidth 378. Fix: the header row wraps (`flex-wrap`, control group `ml-auto`, title block `min-w-0`), so the four controls take their own row when the subtitle is long. After, EN and TR, 1440 and 1280, patient page and home tab: the last button ends at 1419 (1259 at 1280), scrollWidth equals clientWidth (378), nothing outside. In a split pane (no right dock) the open card keeps its controls on the title row at 570 px (EN 1440) and 490 px (TR 1280), seen in screenshots.
- UX P2, patient select cuts its label: correct, and the suggested fix is not enough. The review's text widths are right (EN 219 px, TR 238 px, widest of the cohort 220 and 239 for SENTETIK-HASTA-0032), but Chrome's native select reserves room for its arrow on top of the CSS padding. A pixel compare of the control against a 250 px wider twin shows the Turkish label still cut at 290 px and at 300 px with the default `pr-8`, intact from about 310 px, and intact from about 288 px with `pr-3`. Chosen: 310 px with `pr-3` (about 22 px to spare), sex 116 px (`min-w-0`), age 112 px, doctor 120 px, so the row with "Clear filters" and the chip still fits one line at 1280 px; the select also gets a `title` with the full label. Below 640 px the patient select is `w-full` (a fixed 310 px made 20 states scroll sideways at 390 px; found by the capture metrics, not by the first probe). Checked: 96 controls (24 states: EN and TR, 1440 and 1280, Patients, Compliance and Revenue, patients 0003, 0032, 0040, 0006, with a patient and a sex filter active), 0 clipped, toolbar 77 px (one row) in all; a negative control with the select forced to 250 px is flagged in EN and TR; widths 360 to 1024: no horizontal page scroll. At 360 to 430 px the closed select is 214 to 284 px wide, so a long label is still cut there (tooltip only); phones are Phase 7.
- Regression P2, no test for the layout class of the default state: correct (mutations M1, M2 passed 711 tests). Added: patient page (collapsed, center, right, embedded) in `page.panes.test.tsx`; new `app/page.test.tsx` for the home page (also its `allowRightDock`).
- Regression P2, restore half of the dock and the split-view rule untested: correct (M4, M5, M6 passed). Added `stores/navigationContext.test.tsx` (the saved dock is applied after the first render and never written back; unknown value, empty value and blocked storage give the default), `components/shell/WorkspaceSplitLayout.test.tsx` (right becomes centre with no storage write; collapsed and centre untouched; no change without a split), `components/shell/AppSidebar.test.tsx` (a saved right dock gives the 64 px rail and `--shell-sidebar-width` 64px from the first paint; 220 px otherwise; the user's own collapse wins).
- Mutation checks (scratch edits of the source, restored from the index): M1 patient page `chatDock !== "center"`, M2 same on the home page, M4 provider ignores the saved dock, M5 split layout uses the persisting action, M6 sidebar ignores the saved dock, M10 and M11 `allowRightDock` always true (home and patient page), M12 header no longer wraps, M13 patient select 250 px, M14 no `title`, M15 fixed 310 px on phones, M16 default select padding, M17 sex select min width back: all 13 fail the new tests.

Results:
- Gates (Node 22.16.0; CI uses Node 20 and stays the arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 95 files / 737 tests passed (91 / 711 before: 4 new files, 26 new tests); `npm run build` exit 0; `npx eslint` on the 9 touched files: 1 problem, the existing `react-hooks/set-state-in-effect` at `CohortFilterBar.tsx:48` (and the jsx-ast-utils notice from the existing JSX comment inside `trailing`); `git diff --check` clean.
- Full capture of the final tree (`node scripts/capture-screens.mjs`, 188 states, no failed route, the same 2 skipped states): `--compare lanes/ui/baseline <run> --strict-multiplicity --strict-labels` exit 0, 188 states, 0 failures, 0 warnings. What that proves and what it does not: it compares the set of amounts, counts, percents and uncertainty wording per state, and the standalone amounts under their labels (about 10 percent of the amounts); amounts inside table rows, bill chips and prose are compared as a set, so a swap between rows would not fail it, clipped text counts as visible, and it does not see controls, order, the tab strip, width or the saved dock. Because of that: the `numbers` folder (188 files) and the `text` folder (376 files) are byte-identical to the capture of `78f7b0f2`, whose rows and columns the honesty review compared by hand against the baseline (patients 0003, 0017, 0029, every state, EN and TR). This round restructures no table, bill picker, findings row or summary row; it changes widths, one header row and tests.
- Metrics against the capture of `78f7b0f2`: all 96 files at 1440x900 and 1280x800 are identical (money wraps 838, overlaps 37, clipped 2,702, horizontal scroll flags 8, the same totals). At 390x844 the 20 filter-bar states (Patients, Compliance with its 7 sub-views and Revenue, EN and TR) are 69 or 70 px shorter, and no state changed its horizontal scroll flag; `deepLink.top` differs, as the capture README says it may.
- Browser probes are scratch scripts outside the repo (right-dock header, select pixel check, narrow widths 360 to 1024, split pane with the chat open, home tab with a split pane: toolbar 189 px high in a 610 px pane, no overflow).
- Not run: Node 20 and GitHub CI, `npm run lint` over all of `src`, backend pytest (forbidden in this lane), a real LLM key (chat stubbed), Wave A evidence, Safari and Firefox, Windows and macOS scrollbars, a phone or tablet device, the P3 items of the reviews.
- Cleanup: backend (18001) and `next start` (13000) stopped by PID, ports free; `frontend/.next` and the scratch captures under `~/.cache/ui-capture-tmp` removed.
