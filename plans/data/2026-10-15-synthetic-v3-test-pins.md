# Synthetic cohort test pins — P0 classification

Appendix to `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (P0, P6). Produced by a read-only analysis on 2026-10-15; the scratch artifacts listed at the end were temporary and are not kept.

Date: 2026-10-15. Tree: branch `claude/synthetic-v3-p0-p1`, HEAD `0a205223`. That commit, the P0/P1 work, landed during this analysis. It changed no test file in scope; it only added two reference tests, which are KEEP. Read-only: this analysis wrote nothing to the repo, and every pytest run was in a scratch copy.
Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`, P0 item "classify the test files" and P6.

## Method

1. **Static scan** of `tests/`, `frontend/src`, `frontend/scripts`, `scripts/`, `tools/` and `.github/`. It looks for:
   - SENTETIK ids, claim ids and line ids;
   - the 53 v2 `scenario_tag` values and 24 vignette faults;
   - golden and cohort amounts;
   - `data/synthetic` paths and the loader entry points.
   Then each hit was read by hand.
2. **Runtime trace.** The full suite ran in a scratch copy of the repo, without `.git`, `raw data/`, the two ILAY folders or `.env`. A pytest plugin recorded every test that opened `data/synthetic/**`, called the claims loader's cached reader, or opened `.cache/bilun.duckdb`.
3. **Four cohort mutations**, each run as a full suite in its own scratch copy:
   - **empty**: zero-row parquet files and empty manifests;
   - **relabel_ids**: the 50 patient ids are permuted, consistently across the parquet files and `demo_*.json`;
   - **rename_tags**: every `scenario_tag` gets a prefix;
   - **reseed**: today's generator, seed 777 instead of 20260504.

**Baseline:** 8,331 tests, 6 failures. All 6 come from the excluded `raw data/`, not from the cohort.

| Run | Tests that change outcome against the baseline |
|---|---|
| empty | 98 test cases in 30 files (91 fail or error, **7 skip silently**) |
| relabel_ids | 23 |
| rename_tags | 27 |
| reseed (same generator, other seed) | 21 |
| union of relabel, rename and reseed | **54 test cases in 17 files**. This is the measured minimum breakage of a regeneration. |

**Pin kinds:**
- **ID**: patient, claim or line id, or a patient index.
- **TAG**: a v2 `scenario_tag`.
- **AMT**: a TL amount from the cohort, or from the catalog price on the cohort's dates.
- **CODE**: a SUT, material or MEDULA code that belongs to one specific old bill.
- **CNT**: a count, floor, ceiling or shape (e.g. `len(ctx.claims) == 1`).
- **PATH**: a path to the data.

**Evidence codes:** R, T and S give the number of failing tests under relabel_ids, rename_tags and reseed.

## Totals

| Class | Files | Load-bearing pins | Note |
|---|---|---|---|
| RE-POINT (CI tests) | 15 | ≈206 | 4 of them fail under no mutation; they are weak (see below) |
| DROP (CI tests) | 5 | ≈30 | Test the v2 registry or generator that P3/P4 replace |
| DROP (generator post-check scripts, not CI) | 2 | ≈25 | `validate_sut_synthetic_data.py`, `assert_tier_a_post_regen.py` |
| RE-POINT (frontend live-app scripts, not CI) | 3 | 18 | Plus `frontend/scripts/RECORDING.md` text |
| KEEP: reads the real cohort, no ids | 11 | 4 (floors) | Implicit data-shape requirements are listed below |
| KEEP: incidental (API startup rebuilds the cache) | 5+ | 0 | No cohort assertions |
| KEEP: cosmetic literals in self-made fixtures | 31 (18 Python, 13 vitest) | ≈107 cosmetic | No P6 work needed |
| KEEP: strict lane (paused, deselected) | 8 | path pins only | Break only if `demo_vignettes.json` is deleted |

Work for P6: **25 files** (20 CI test files, 3 frontend scripts, 2 scripts) holding **≈280 load-bearing pins**. Together with ≈107 cosmetic literals this matches the earlier estimate of about 375.

## RE-POINT — CI tests

| File | Tests on cohort / total | Pins by kind | Evidence | What it needs from the cohort |
|---|---|---|---|---|
| `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py` | 22/22 | TAG 32, AMT 10, CODE 22, CNT 11 (=75), plus 10 indices in test names | R0 T22 S2 | One fault each, every one on a **single-bill patient**: (1) override, billed as package while itemised is higher (0 savings; `:72-73` 3500/3038.16); (2) override, billed itemised while package is higher; (3) DRG uplift on a non-package inpatient bill; (4) package materials unbundled (`:140` 667.01); (5) colonoscopy add-on missing (701450→701460); (6) 10 MEDULA rejections, one event each (1688, 0612, 1205, 0521, 0315, 0901, 0704, 0320, 0411, 1102); (7) package adequacy (609270 billed, 609300 candidate); (8) performed but not billed, with a performed line; (9) günübirlik care-setting review; (10) blood line under a same-session package (`:394-401` P611720, 101019.30); (11) UTS checklist without a MEDULA event; (12) KDV ceiling exceeded (OP1592); (13) procurement screen incomplete. Patients are already looked up through the vignette registry (`:15-27`), which is why the ids survive relabelling. The **tags, amounts and codes do not survive**: the reseed alone gave 3038.16→2025.44 and P611720→P619460. |
| `tests/unit/domain/billing/test_billing_actions.py` | 4/12 (`:30-165`) | ID 11, AMT 3, CODE 9, CNT 7 (=30) | R3 S3 | (a) An outpatient exam bill for an exemption-eligible patient. It has one package-mandated procedure billed itemised (§2.2.1.B-1.a; 613080) and 3 exam documentation items (ORTAK-5). (b) The "package higher, billed itemised" override bill: inpatient orthopaedic EK-2/C surgery with 2 lines of one uplift material. It also gates the checklist refs ORTAK-17/27 and ORTOPEDİ-6. Amounts 4625.48, 2350 and 6975.48 (`:144-149`). (c) Any patient. Claim numbers are a **global sequence**, so F-…-0003-011 and -015 moved under the reseed. |
| `tests/unit/synthetic/test_vignette_golden.py` | 9/9 | ID 10, IDX 12, TAG 5, CNT 1, plus 6 golden bands read from `demo_vignettes.json` | R5 T4 S2 | **Mixed.** Drop 6 tests: the manifest and tier checks (`:35-77`), and the ghost-package and presentation checks (`:153-205`), which become P5 plausibility tests. Re-point 3: golden bands for the two override faults, taken from the injection log (`:86-122`); and the blanking test (`:124-150`), which should iterate **all** patients, not 6 ids. |
| `tests/unit/domain/claims/test_loader.py` | 15/15 (2 to re-point; 13 use the cohort as a valid fixture) | ID 3, CNT 17 | S7 | A role "patient with a bill, a procedure line and a drug line" (today 0001, `:41-52`). At least one material line with a prose flag (`:64-73`). Floors should become registry counts. `expected_outputs ≥ 300` (`:35`) breaks once the answer rows cover only injected faults (P3). `claims ≥ 80` already failed under the reseed (77 claims). |
| `tests/unit/api/test_medula_rejection_queue_api.py` | 9/9 | ID 4, CODE 7, CNT 3 (=14) | R2 | The MEDULA rejection set: one patient and claim per event, its code (at least 1688 and 0612, `:10-41`), its stage, and the rebill flag. The floors ≥10, ≥9 and ≥8 (`:16,55,63`) should become equalities with registry counts. |
| `tests/unit/domain/billing/test_claim_materials_precheck.py` | 1/12 (`:444-474`) | ID 6, CODE 1 | R1 S1 | One bill with two lines of the same EK-3 code (GHC1220): one needs pre-authorisation, one is bundled, and both trigger §3.1 prose bundling. Separately, a self-made test (`:315-361`) reuses the ids cosmetically (10 literals); keep it. |
| `tests/unit/domain/billing/test_claim_strategy_sut.py` | 1/13 (`:519-548`) | ID 4, AMT 2 | R1 S1 | A clean control: a DRG-mandatory package bill, correctly billed as a package, with its package total (7218.58). |
| `tests/unit/domain/test_billing_strategy_exactness.py` | 1/4 (`:30-52`) | ID 3 | R1 S1 | The "package higher, billed itemised" override bill. |
| `tests/unit/domain/billing/test_session_uplift_patient_0013.py` | 1/1 | ID 1, CODE 1 | R1 | The session-underbilling fault and its secondary code (610070). |
| `tests/unit/domain/billing/test_lab_optimizer_sentetik_0001_002.py` | 1/1 | ID 3, PATH 2 (paths relative to cwd, `:23-25`) | R1 S1 | A bill with billed lab lines and several raw `lab_clean` results per code. |
| `tests/unit/cache/test_copay_outcome_kind.py` | 1 of 4 is pinned (`:24-71`); 1 more uses no ids | ID 2 | R1 S1 | An exempt patient (by profile or diagnosis) and a patient with an EK-2C-1 rate-capped procedure. It was already re-targeted once after generator drift (`:27`). |
| `tests/unit/domain/billing/test_session_uplift_patient_0001.py` | 1/1 | ID 1, plus 4 `== 0` asserts | none (**weak**) | A **clean control**: surgery billed at the full EK-2B list price, with no session or DRG uplift. |
| `tests/unit/domain/billing/test_drg_uplift_wiring.py` | 1/8 (`:330-343`) | ID 2 | none (**weak**) | The same clean control. |
| `tests/unit/domain/billing/test_claim_integration.py` | 2/3 | ID 2 | none | Any patient with bills; the id is arbitrary. |
| `tests/unit/domain/optimization/test_copay_rate_exposure.py` | 2 of 6 read the cohort (1 to re-point, 1 to keep) | CNT 2, PATH 1 (`:98`, relative to cwd) | none (**weak**) | The number of injected EK-2C-1 copay-rate faults. The ceilings ≤2 and ≤1 (`:110-111`) pass on zero, so they should become equality. |

## DROP

| File | Pins | Evidence | Why it goes |
|---|---|---|---|
| `tests/unit/synthetic/test_cohort_tiers.py` | ID 4, CNT 3 (8/16/26), dataset id and seed 2 | R1 | It tests the v2 tier report: the landing patient is 0003, and 0011 is tier C (`:24-40`). Replace it with the registry self-test. 2 of its 3 tests pass with empty manifests (see Weak tests). |
| `tests/unit/synthetic/test_vignettes_registry.py` | IDX 2, TAG 1 (plus 9 cosmetic) | R1 T1 | It tests the v2 `vignettes.py`. `:46-50` reads the real JSON. Rewrite it for the P3 fault registry. |
| `tests/unit/scripts/test_synthetic_data_integrity.py` | seed and size tied to the manifest | R1 | It tests the v2 generator. Through the generator it reads `demo_vignettes.json`, so relabelling broke it. |
| `tests/unit/scripts/test_synthetic_material_prose_flags.py` | CNT 14 (flag coverage) | R2 | It tests the v2 flag rotation. Its check of the committed parquet (`foreign_facility.any()`) becomes a P5 coverage check. |
| `tests/unit/scripts/test_synthetic_specialty_prose_flags.py` | CNT 2 | R2 | It tests the v2 generator. |
| `scripts/synthetic/validate_sut_synthetic_data.py` (post-check run by the generator) | ID 13 (`:307-334,945`), TAG 7, ≥90 claims | — | Replace it with the P5 tests and the registry self-test. It already rejects the seed-777 v2 cohort (77 claims, below 90). |
| `scripts/synthetic/assert_tier_a_post_regen.py` | registry-driven, no literal ids | — | Replace it with the registry self-test. |

## RE-POINT — frontend live-app scripts (not in CI)

| File | Pins | What it needs |
|---|---|---|
| `frontend/scripts/capture-screens.mjs` | ID 9 (`:110, :520-523, :550-559`) | The default landing patient; a patient with a material pre-check; and a patient with at least one claim-compliance finding. Without that finding the script aborts (`:523`). |
| `frontend/scripts/lib/recording-kit.mjs` (used by `record-workflows.mjs`) | ID 2 (`:4`) | The landing patient, with a ranked action and its clause source; and a material pre-check patient. |
| `frontend/scripts/verify-workspace-views.mjs` | ID 1, CNT 4, AMT 2 (`:51, :69-72, :89, :114, :137`) | A patient with compliance findings, revenue actions and a document checklist. The badge regexes `/18/` and `/\b4\b/` match any such digit, so they are weak. |

## KEEP — reads the real cohort but pins no ids (these are its data-shape requirements)

| File | Requirement | Evidence |
|---|---|---|
| `tests/unit/domain/claims/test_config.py` | ≥80 bills and ≥40 patients (`:159-180`). v3's 100–150 bills are fine; registry counts would be better. | S2 |
| `tests/unit/domain/billing/test_bill_billing_report.py` | At least one patient with ≥2 bills. It runs the whole cohort (about 68 s). | **skipped on empty** |
| `tests/unit/api/test_bill_optimization_api.py` | Any patient with a bill. | **skipped on empty** |
| `tests/unit/domain/billing/test_orchestrator_claim_cohort_flow.py` | A patient with procedure lines; the MEDULA events file must exist. | — |
| `tests/unit/domain/claims/test_ingestion_dates.py` | All 7 claim tables, including non-empty rejection and performed tables. | — |
| `tests/unit/domain/claims/test_ingestion_optional_fields.py` | At least 3 drug lines and 3 material lines. | — |
| `tests/unit/domain/claims/test_patient_context_slice.py` | Any patient with a bill. | — |
| `tests/unit/domain/optimization/test_cohort_claim_integration.py` | The **first 5 patients in sorted order** must include a drug line and an EK-2G procedure. | — |
| `tests/unit/domain/test_optimization_claim_context.py` | At least one patient with an EK-2G procedure and one with an EK-2C-1 procedure. | — |
| `tests/unit/cache/test_sut_patient_alerts_exactness.py` | A patient with procedure lines. | — |
| `tests/unit/api/test_sut_cache_concurrency.py` | None. It loads the cohort only as a side effect of asking for patient "P1". | — |

**Incidental readers.** `test_auth.py`, `test_health.py`, `test_sut_chat.py`, `test_sut_patient_claims_api.py`, `tests/smoke/test_sut.py` and the other `api_client` users all depend on the cohort the same way. With no `.cache/bilun.duckdb` present, as in a fresh CI checkout, the `TestClient` lifespan rebuilds the full cache from the cohort (`src/bilun/api/startup.py:117-119`). A broken cohort only logs an error, and these tests do not assert on cohort data.

**Cosmetic, no change needed.** These use v2 ids or tags only as labels in self-made fixtures:
- `test_claim_copay_scope.py` (ID 4);
- `test_yatak_puani.py` (ID 1);
- 7 billing `test_*_wiring.py` files and `test_optional_override_surfacing.py`, plus 8 `prose_rules` tests (one v2 tag label each);
- 13 vitest files, about 55 literals in mocks (e.g. `CohortFilterBar.test.tsx`, `SutBillingReportSections.test.tsx`, `numbers-parity.test.mjs`).

**Strict lane (paused).** The roster lists `data/synthetic/demo_vignettes.json` (`scripts/deploy/generate_candidate_source_roster.py:28`). The same path appears in `test_generate_candidate_source_roster.py:64,118` and `tests/integration/deploy/test_signed_transition_startup.py:528`. That roster entry has been stale since #247 removed the runtime read. These tests break only if v3 deletes the file, and changing them is strict-lane work.

## Weak tests: they pass on an empty or changed cohort

- **Silent skip on an unloadable cohort (measured):**
  - `test_bill_billing_report.py:19-28` (5 tests);
  - `test_bill_optimization_api.py:12-21` (2 tests);
  - `tests/smoke/test_sut.py` uses `_skip_if_unavailable`.
  In each case CI stays green while the tests do not run.
- **Vacuous on an empty cohort (measured as passing):**
  - `test_medula_rejection_queue_api.py::test_queue_filters_by_sonuc_kodu` (`:44`, `all()` over no rows);
  - `::test_queue_pagination_bounds_rows` (`:97`, `len <= 1`);
  - `test_vignette_golden.py::test_manifest_tier_lists_match_vignette_tiers` and `::test_scenario_by_index_matches_vignette_tags` (loops over an empty manifest);
  - `test_cohort_tiers.py::test_render_markdown_includes_tier_c_ids` and `::test_write_cohort_tier_artifacts` (whose `or` makes the id check always true).
- **Vacuous by construction.** These failed on the empty run only because the loader rejects empty tables. A loader that accepts empty tables would make them pass:
  - `test_copay_rate_exposure.py`: ceilings (`:110-111`) and the `for line` invariant (`:84-90`);
  - `test_vignette_golden.py::test_tier_a_showcase_claims_have_no_ghost_package_lines`: it loops over tier A and skips any non-override tag.
- **The pinned id does not carry the test (still passes after relabelling):**
  - the negative controls `test_session_uplift_patient_0001.py` and `test_drg_uplift_wiring.py:330`;
  - `test_claim_integration.py`;
  - `test_billing_actions.py::test_count_matches_collect`.
  `test_lab_optimizer_sentetik_0001_002.py` uses only `== 0` assertions, so it would pass on a bill with no lab lines.
- **Lucky data shape:** `test_cohort_claim_integration.py` (first 5 patients), `test_optimization_claim_context.py`, and the loader and config floors (9 tests failed on the reseed alone).

## Fixture strategy

**Generator output, in the same run as the parquet: `data/synthetic/cohort_registry.json`.** It contains:
- `dataset_id`, `seed`, and `files_sha256` for every parquet file, so a stale registry is detected.
- `counts`: patients, claims, and every line table, expected outputs, MEDULA events and performed lines.
- `roles`: stable name → `{patient_id, claim_id}`. Examples: `default_landing`, `clean_full_list_surgery`, `drg_mandatory_package_ok`, `multi_bill_patient`, `lab_bill_repeated_results`, `copay_exempt_patient`, `copay_rate_capped_patient`, `material_precheck_patient`, `claim_compliance_finding_patient`, `ek2g_surcharge_patient`, `ek2c1_rate_patient`.
- `faults`: the P3 injection log, one row per injected fault. Each row has `fault_id` (stable and semantic, e.g. `optional_override.package_higher_billed_itemized`), `patient_id`, `claim_id`, `line_ids`, `sut_section`, `engine_rule`, `detectable`, `expected` (the detection fields plus the TL effect) and `tier`. MEDULA rejections are rows here too, with `sonuc_kodu`, `medula_stage`, `rebill_permitted` and `playbook_key`.

**Test helper: `tests/fixtures/synthetic_cohort.py`.** It provides `registry()`, `dataset()`, `role(name)`, `fault(fault_id)`, `faults(prefix)` (for parametrize) and `counts()`. It fails (`pytest.fail`), never skips, when a file, role or fault is missing.

**Rules:**
- **No literals in tests:** no SENTETIK ids, claim numbers, v2 tags or TL amounts.
- **Amounts:** compare with `fault.expected`, with a tolerance.
- **Counts:** replace floors with equality to `counts()`.
- **Empty parametrization:** set `empty_parameter_set_mark = "fail_at_collect"` in `pyproject.toml`. Today it is unset, so an empty parametrize skips silently.
- **Imports:** drop the `sys.path` imports of `demo_config` (`test_sgk_uplift_synthetic_demos.py:15-19`, `test_vignette_golden.py:10-21`).

**Registry self-test (`tests/unit/synthetic/test_cohort_registry.py`).** It checks that:
- the file hashes match;
- every id resolves;
- each fault's lines exist;
- the counts are equal.
A mutation test deletes one fault line and expects a failure.

**Users of the registry:**
- all 15 RE-POINT tests, through `fault()` or `role()`;
- the 11 KEEP data-shape tests, through roles and counts, so their requirements are declared instead of lucky;
- the 3 frontend scripts, which read the JSON with `fs` and use role names.

## Riskiest tests

1. `test_sgk_uplift_synthetic_demos.py`: 22 tests and about 75 pins. All 22 failed under tag renaming; 2 failed under a mere reseed (catalog price on a new date, a random same-session package code). It needs a fault-by-fault decision on which v2 faults v3 keeps (10 of them are MEDULA cases).
2. `test_billing_actions.py`, `test_billing_strategy_exactness.py` and the golden bands. They pin the bill numbers of patient 0003, which come from a global sequence. They also pin documentation-checklist refs that come from incidental generator choices. They failed under relabelling and under the reseed.
3. `test_loader.py` and `test_config.py` floors: 9 failures on the reseed alone. P3's answer-key change will break `expected_outputs ≥ 300`.
4. The silent skips and vacuous MEDULA queue tests above.
5. Engine coupling, not a test pin. `traffic_accident_billing.py:84-90,122-129` and `treatment_pricing.py:603-608` still read `scenario_tag` substrings (`kaza`, `trafik`, `ykm`). A v3 tag such as `is_kazasi` would change engine output, and the blanking test samples only 6 patients.

## Artifacts (scratch)

All in `…/scratchpad/test_pins/`:
- scanner: `scan_pins.py` (output `scan.tsv`);
- tracer plugin: `plugin/pin_tracer.py`;
- mutation script: `mutate_cohort.py`;
- comparison script: `compare_runs.py` (output `compare.txt`);
- `junit_{baseline,empty,relabel_ids,rename_tags,reseed}.xml`;
- `runtime_deps_baseline.tsv`.
