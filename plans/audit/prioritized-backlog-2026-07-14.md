# Bilun — Prioritized Backlog (2026-07-14)

Whole-codebase audit: 9 parallel subagents across claims/rules, prose evaluators (×2), billing orchestration, api/chatbot/auth, SUT pipelines, synthetic data, frontend, tests/docs/CI. ~70 findings consolidated; de-duplicated across agents. Sorted by **Value × (1/Effort)**.

---

## Backlog table

| Rank | Module | Finding | Type | Sev | Effort | Value | file:line | Proposed action |
|---:|---|---|---|---|---:|---:|---|---|
| 1 | chat/auth | Client-controlled `user_role: "dev"` in request body → unlocks dev repo-read tools + full payloads. No server-side role source. | security | P0 | S | 5 | `api/routes/chat.py:93-96,553`; `chatbot/tools.py:409,822-826` | Derive role server-side (HMAC token claim or username→role map); never trust `req.user_role`. |
| 2 | auth | No login rate limit — single shared password brute-forceable. Chat endpoint IS rate-limited; login is not. | security | P0 | S | 5 | `api/routes/auth.py:41-62` (cf `chat.py:47-56,532`) | Apply per-IP rate limit + exponential lockout using the existing `_check_rate_limit` pattern. |
| 3 | billing/priority | `assign_priority_by_percentile` IndexError when >25% of reports have zero uplift (the common case — most patients have no recoverable ₺). Crashes every cohort run. | bug | P0 | S | 5 | `billing/priority.py:10-15`; caller `cohort_runner.py:125,183` | Index `recoverables` by `len(recoverables)`, not `len(reports)`. Add a >25%-zero-cohort test. |
| 4 | gap_closing + treatment_pricing | `_suffix_len` bug: `"procedure_code_not_any"` matches `_any` suffix first → base computed as `"procedure_code_not"` → 4 rules that use `*_not_any` predicates never fire (incl. ENF-3 anti-ENA bundling gate). | bug | P1 | S | 5 | `gap_closing.py:180-184`; `treatment_pricing.py:166-171` | Reorder tuple to longest-first: `("_not_any","_not_in","_any","_in")` or `max(..., key=len)`. Fix in one shared place. |
| 5 | fatura_inceleme | `_build_fatura_inceleme_context` reads `header.procedure_specialty_code` — field doesn't exist on `ClaimHeader` (it's on `ProcedureClaimLine`). `getattr(header, ...)` always returns `""`, so branch routing only works via `department` keyword overlap. ~28 branch-specific rules silently mis-route. | bug | P1 | S | 4 | `fatura_inceleme.py:165`; `claims/models.py:23-42` vs `:82` | Read `procedure_specialty_code` from the first procedure line (where it actually lives). |
| 6 | material_uplift + gazette_repricing | `check_*_for_context` evaluate ONLY `ctx.claims[0]` — multi-claim PatientClaimContext silently drops findings on claims [1..n]. Sibling adapters (`procedure_addon_uplift`, `drg_package_adequacy`) correctly iterate `ctx.claims`. Silent data loss. | bug | P1 | S | 5 | `material_uplift.py:265`; `gazette_repricing.py:307` (cf `procedure_addon_uplift.py:304-307`) | Lift both bodies into `for claim in ctx.claims:` loops (line-filtering code already exists). |
| 7 | exclusions cache | Mutable module-global caches (`_EK3B1_CACHE`/`_EK3B2_CACHE`) mutated from worker threads under `ThreadPoolExecutor` with no lock → race on first-load during parallel cohort runs. | bug | P1 | S | 4 | `exclusions.py:18-19,28-30,59`; `cohort_runner.py:117` | Replace hand-rolled globals with `@lru_cache(maxsize=1)` (already used in `catalog_lookup.py:106+`). |
| 8 | synthetic gen | `procedure_specialty_code` NEVER generated — parquet column absent. Keeps 3 detectors fully dormant (temporal_anomaly overlap, duplicate_exam_10day, session_specialty) and weakens 4 more rule files (16 references). | gap | P0 | M | 5 | `claims/models.py:82`; gen `claim_lines.py:246-271` (no specialty key); `temporal_anomaly.py:130` | Generate by joining each procedure's EK-2/B `group`/branch via catalog membership. Emit in procedure row dict + exporter schema. |
| 9 | synthetic gen | `sag_sol` (Medula laterality) NEVER generated → both laterality detectors (#6 imaging, #17 surgery) ship 100% dormant behind a B-guard. Field exists, parser reads it, generator never writes it. | gap | P0 | S | 4 | `claims/models.py:83`; `laterality_validation.py:176,227`; gen `claim_lines.py:246-271` | Emit `sag_sol ∈ {"1","2"}` for paired-organ/cataract codes; leave `""` for ~30% to create violation candidates. |
| 10 | billing types | 7× duplicated `confirmed_uplift_try` / `total_uplift_try` / `review_uplift_try` properties across uplift dataclasses. Single copy-paste fix point for the `included_in_sgk_total` default inconsistency. | debt | P2 | M | 3 | `types.py:296-318,367-383,521-537,552-568,619-639,753-781,796-812` | Introduce `UpliftBlockMixin` (or `_sum_opportunity_try` helper); 7 dataclasses delegate. |
| 11 | cohort_summary | `_savings_by_category` dict literal defines `lab`/`copay`/`strategy` keys TWICE (lines 147-149 then 154-156) → 6 dead entries, Python silently keeps last. Frontend-facing shape is misleading. | bug | P1 | S | 3 | `cohort_summary.py:133-157` | Delete the 3 duplicate entries; one canonical mapping only. |
| 12 | recovery_summary | `patient_recovery_summary_from_payload(dict)` builds savings from only 7 keys, but `_get_top_action_type(report)` considers 13. Same patient gets different `top_action_type` from live object vs cached JSON → UI shows wrong top action when served from cache. | bug | P1 | S | 3 | `recovery_summary.py:90-125` vs `:34-58` | Extract one `_savings_dict_from_report(report_or_dict)` helper used by both paths. |
| 13 | icu_puani + yatak_puani | `recoverable_uplift_try = total_try` unconditionally — never nets out what the hospital already billed (`510090`/`510010`). Correctly-billed ICU stay still emits full-sized "recoverable" opportunity, inflating SGK-uplift total. Sibling detectors (`material_uplift`, `procedure_addon_uplift`) correctly do `ceiling - billed`. | bug | P1 | M | 4 | `icu_puani.py:332`; `yatak_puani.py:170` | Sum actual billed amounts from `procedure_lines`; emit `actual_billed_try`; `recoverable = max(0, expected - actual)`. |
| 14 | drg_unbundling | `analyze_claim_unbundling(same_incision=None)` default means session-violation detector is NEVER called unless caller passes the kwarg. Reads as "auto-detect" but means "skip." Session overbilling (§2.2.2.B) is the highest-value unbundling finding. | dormant | P1 | S | 4 | `drg_unbundling.py:228,255-260` | Default `same_incision=True` (matches every real call site). |
| 15 | report_totals + cohort_summary | Registry-block rollup (14 `cohort_total_field`s + 7 counters) tested with ALL-ZERO values. A typo in `uplift_field`/`block_scalar` wiring would pass every test. The 21-spec `BILLING_BLOCK_SPECS` loop has 2 hand-built tests only. | test | P0 | M | 5 | `cohort_summary.py:64-88`; `report_totals.py:35-85`; `test_orchestrator_grand_total.py:60-155` | Parametrized "spec integrity" test: for each spec, set one block's field to a sentinel, assert it rolls up. |
| 16 | report_exactness | `finalize_report_exactness` + `finalize_summary_exactness` (the 3-branch exactness rollup driving every "missing data" badge) have ZERO direct tests. The class-name fallback branch (synthesizing `required_inputs_missing`) is completely untested. | test | P0 | M | 5 | `report_exactness.py:56-122` | Tests: all-exact→exact; all-missing→missing_inputs; mix→PARTIAL; class-name fallback. |
| 17 | sut_fetch | Zip-slip: `zf.extractall(target_dir)` on zip from SGK website with no member-name sanitization. URL parsed from remote HTML by regex. | security | P1 | S | 5 | `sut_fetch.py:96-99` (via `:61,116`) | Iterate `zf.infolist()`, resolve each against `target_dir.resolve()`, assert containment before writing. Add traversal test. |
| 18 | catalog | `_sorted_codes` global stale after `force_reload=True` on a new asof date — only invalidated by length check, not by date. Prefix searches can return codes from the wrong catalog version. | bug | P2 | S | 3 | `catalog.py:408,458-459` | Key `_sorted_codes` per-asof alongside `_catalog_cache_by_asof`, or invalidate on `force_reload`. |
| 19 | rules_catalog | `_corpus_row_count_from_parquet` does a FULL parquet read (potentially 100s of MB) per section prefix, per API request, with no cache. 4 reads of the same file in one `coverage_summary` request. Bare `except` silently returns 0. | perf | P1 | S | 4 | `rules_catalog.py:307-321`; callers `:324,345,405` | Read parquet once per process with mtime invalidation (pattern exists at `:87-88`); single `group_by` pass. |
| 20 | SutInlineAIPanel | 663-line component, 15 refs, dual streaming state machines, locale-reset + debounce + abort interactions — ZERO tests. The most complex stateful frontend component. | test | P1 | L | 5 | `SutInlineAIPanel.tsx` (whole file) | Component tests: locale switch reset, debounce+abort on patientId change, SSE frames, unmount during streaming. |
| 21 | PatientInvoiceTable | Fetch effect has NO AbortController (cancelled boolean only), `t` in dep array triggers refetch on locale switch, errors silently swallowed via `.catch(() => null)` → empty table with no error UI. | bug | P1 | M | 5 | `PatientInvoiceTable.tsx:151-223` | Add real AbortController; remove `t` from deps (use tRef); render error path instead of empty table. |
| 22 | treatment_pricing context | `facility_type` is derivable (gap_closing already derives it from `provider_type` at `:437-449`) but treatment_pricing + dental don't surface it → 7 dental + 8 treatment_pricing rules stay dormant despite the derivation existing next door. | dormant | P2 | M | 4 | `treatment_pricing.py:418`; `dental_2_4_1.py`; `gap_closing.py:437-449` | Port the `facility_type` derivation from gap_closing into treatment_pricing + dental context builders. |
| 23 | sut_monitor | Writes Turkish `new_tebliğ` key on error paths but ASCII `new_teblig` on success. CI reads ASCII. Turkish key is dead state; anyone reading the obvious name gets wrong data. | bug | P1 | S | 4 | `sut_monitor.py:88,98,106` vs `:113-118` | Standardize on ASCII `new_teblig` in all 5 sites. |
| 24 | BILUN_AUTH_OPTIONAL | `=1` disables session gate globally with no environment guard. Misconfigured `.env` silently exposes entire API unauthenticated. `/health` leaks build IDs unauthenticated. | security | P2 | S | 3 | `api/__init__.py:88-110`; `auth.py:88-98` | Refuse to honor the flag outside explicitly local hosts, or require an `I_UNDERSTAND_THIS_IS_INSECURE` confirm var. |
| 25 | claim_strategy | DRG_MANDATORY compliance savings (over-billed itemized) reported with `savings_category=None` — excluded from SGK headline AND from compliance-adjustment bucket. `SAVINGS_CATEGORY_COMPLIANCE` exists in types but is never assigned. | bug | P2 | S | 3 | `claim_strategy.py:228-231,457-461` | Tag with `SAVINGS_CATEGORY_COMPLIANCE` so it rolls into the compliance bucket. |
| 26 | deploy.yml | Cache-rebuild wait loop (90×10s) silently succeeds on timeout → deploy "succeeds" while backend serves stale/no cache. The DuckDB-lock failure mode already documented as real. | ci | P2 | S | 3 | `deploy.yml:110-124` | After loop, check final `READY`; if not `true`, `exit 1` before the sed reset. |
| 27 | CI backend job | No linter, no type-checker, no coverage gate on Python. Frontend job has `tsc + vitest + build`; backend has `pytest` only. Type errors ship to prod. | ci | P1 | S | 4 | `.github/workflows/ci.yml:22-34` | Add `ruff check .` (+ optionally `mypy src/bilun`) to the backend job. |
| 28 | docs | Architecture docs describe "5-6 optimization algorithms"; code has 21 billing blocks. 16 engines added since docs written are undocumented. Orchestrator description is stale. | docs | P1 | M | 4 | `algorithms_reference.md:96,323`; `README.md:36,58` | Auto-generate the engine table from `BILLING_BLOCK_SPECS` (single source of truth). |
| 29 | dead dependency | `scikit-learn==1.7.2` pinned in pyproject + requirements but ZERO imports anywhere in src/scripts/tests. ~150MB transitive deps for nothing. | config | P2 | S | 3 | `pyproject.toml:26`; `requirements.txt:18` | Remove from both files; run CI to confirm. |
| 30 | dep manifests drift | `requirements.txt` missing `pyyaml`, `requests`, `jsonschema` (all imported in src/scripts). Anyone installing from it gets a broken runtime. `dev` extra lacks `ruff`, `pytest-cov`, `pytest-asyncio`. | config | P2 | S | 3 | `pyproject.toml:14-37`; `requirements.txt`; `deploy.yml:73` | Delete `requirements.txt` (single source = pyproject) or auto-generate it. Add missing dev deps. |

---

## TOP 10 expansions

### #1 — Client-controlled `dev` role escalation (P0, S, Value 5)
**What's wrong:** `api/routes/chat.py:93-96` reads `user_role` from the JSON request body and returns `"dev"` if the string is `"dev"`. The session token (`auth.py:171-186`) carries only `username + expires_at` — no role claim. Anyone who passes `"user_role":"dev"` in the body unlocks `read_repo_file`/`grep_repo` dev tools and full unredacted billing payloads.
**Why it matters:** Concrete exploitable privilege escalation. Distinct from the known "no authz model" — this is the specific path. A billing officer can read source code and full patient payloads via the chatbot.
**Minimal fix:** Add a `role` claim to the HMAC token at login (server-side map from username), or a `username→role` server-side lookup. Strip `req.user_role` from the chat request schema. Add a test asserting a non-dev session cannot get repo tools.

### #2 — No login rate limit (P0, S, Value 5)
**What's wrong:** The chat endpoint uses `_check_rate_limit` (`chat.py:47-56,532`), but `/api/auth/login` (`auth.py:41-62`) has no rate limiting. Auth is a single shared password (`auth.py:1-6`). PBKDF2 (310k iters) slows each attempt but doesn't prevent unbounded online brute force.
**Why it matters:** The login endpoint is the one place where an unauthenticated attacker has a direct crack at the credential. No backoff = dictionary attack viable.
**Minimal fix:** Reuse the existing `_check_rate_limit` pattern keyed by client IP on `/login`. Add exponential lockout after N failures. Test the lockout triggers.

### #3 — `assign_priority_by_percentile` IndexError on clean cohorts (P0, S, Value 5)
**What's wrong:** `priority.py:10-15` builds `recoverables` from positive-uplift reports only, then indexes it with `recoverables[min(n-1, int(n*0.75))]` where `n = len(reports)` (ALL reports). When >25% of reports have `sgk_uplift_try == 0` (the common case — most patients have no recoverable uplift), `int(n*0.75) >= len(recoverables)` → `IndexError`. Reproduced with `[0,0,0,100,200,300]`.
**Why it matters:** Crashes the entire analytics-cache build on any cohort with mostly-clean claims. Called from `cohort_runner.py:125,183` — every cohort run.
**Minimal fix:** Use `n = len(recoverables)` for the percentile index. One-line fix + a test with a >25%-zero cohort.

### #4 — `_suffix_len` bug breaks `*_not_any` predicates (P1, S, Value 5)
**What's wrong:** `_SET_PREDICATE_SUFFIXES = ("_any","_in","_not_in","_not_any")` is iterated in order; `_suffix_len` returns on the first `endswith` match. `"procedure_code_not_any".endswith("_any")` is `True` → returns `len("_any")==4` → base = `"procedure_code_not"` (wrong). The engine looks up a non-existent key → honest-skip. 4 rules can never fire, including ENF-3 "anti-ENA without ANA is no-pay" — a real bundling gate auditors expect.
**Why it matters:** A real billing rule is silently inert due to a string-ordering bug. The condition looks correct to any reader. Duplicated in both `gap_closing.py:180` and `treatment_pricing.py:166`.
**Minimal fix:** Reorder to longest-first: `("_not_any","_not_in","_any","_in")`. Or use `max((s for s in SUFFIXES if key.endswith(s)), key=len)`. Fix once, both files benefit (after the predicate-engine consolidation).

### #5 — `provider_specialty` reads non-existent header field (P1, S, Value 4)
**What's wrong:** `fatura_inceleme.py:165` does `getattr(header, "procedure_specialty_code", "")` — but `ClaimHeader` has no such field; it lives on `ProcedureClaimLine` (`models.py:82`). Always returns `""`. Branch routing for ~28 branch-specific fatura inceleme rules only works via `department` keyword overlap; any claim with `department=""` or a generic value loses all branch routing.
**Why it matters:** Branch-specific rules (KBB, KVC, Göz, etc.) silently mis-route or no-op. This is a routing defect, not an honest skip.
**Minimal fix:** Read `procedure_specialty_code` from `ctx.procedure_lines[0]` (where it lives). Add a fixture with `department=""` + non-empty specialty to lock the fix.

### #6 — Multi-claim context adapters drop findings (P1, S, Value 5)
**What's wrong:** `material_uplift.py:265` and `gazette_repricing.py:307` do `claim = claims[0]` then scope lines to that one `claim_id`. For a `PatientClaimContext` with 2+ claims, findings on claims [1..n] are silently never emitted. Sibling adapters (`procedure_addon_uplift.py:304-307`, `drg_package_adequacy.py:252`) correctly iterate `ctx.claims`.
**Why it matters:** Silent data loss on multi-claim contexts — the patient report underreports recoverable material uplift and gazette repricing opportunities. The asymmetry across 4 structurally identical adapters is the smoking gun.
**Minimal fix:** Lift both bodies into `for claim in ctx.claims:` loops. The line-filtering code already exists; it just runs once.

### #7 — Race on mutable global exclusion caches (P1, S, Value 4)
**What's wrong:** `_EK3B1_CACHE`/`_EK3B2_CACHE` (`exclusions.py:18-19`) are module-level mutable globals populated on first access, with no lock. `cohort_runner.py:117` calls `map_parallel` → worker threads → concurrent first-load can double-read or observe a half-built list.
**Why it matters:** Under parallel cohort runs (the production path), the race is live. GIL makes dict writes atomic but doesn't protect the read-check-write sequence.
**Minimal fix:** Replace with `@lru_cache(maxsize=1)` (the pattern already used in `catalog_lookup.py:106+`). Thread-safe by design.

### #8 — Generate `procedure_specialty_code` (P0, M, Value 5)
**What's wrong:** `ProcedureClaimLine.procedure_specialty_code` (`models.py:82`) defaults to `""`. The parser reads it (`row_parsers.py:247`). No generator writes it — the synthetic parquet has no such column. This keeps 3 detectors fully dormant (`temporal_anomaly.procedure_time_overlap`, `common_billing_errors.tablo15_2_duplicate_exam_10day`, `session_specialty`) and weakens 4 more rule files (16 references).
**Why it matters:** Specialty is a core billing dimension — without it, duplicate-exam detection (same specialty, 10-day window) can't work, and procedure-time-overlap detection skips every line. The EK-2/B catalog already carries the branch/group, so the data exists upstream.
**Minimal fix:** In `gen/claim_lines.py:246`, join each procedure's code to its EK-2/B `group` via `catalog_membership.normalize_procedure_code` + the catalog's specialty column. Emit it in the procedure row dict + exporter schema.

### #9 — Generate `sag_sol` (laterality) (P0, S, Value 4)
**What's wrong:** `ProcedureClaimLine.sag_sol` (`models.py:83`) defaults to `""`. Both laterality detectors (`laterality_validation.py:176,227`) short-circuit `return []` when no line carries a non-empty `sag_sol`. Zero synthetic claims populate it. Detectors #6 (imaging) and #17 (surgery) ship 100% dormant.
**Why it matters:** Laterality is a real SGK audit point (bilateral organ procedures must specify side). The detectors are wired and tested — they just have no data.
**Minimal fix:** For paired-organ imaging codes (801xxx/803xxx) and 516xxx cataract codes, emit `sag_sol ∈ {"1","2"}` randomly; leave `""` for ~30% to create violation candidates. One generator change, two detectors activate.

### #10 — 7× duplicated uplift properties in types.py (P2, M, Value 3)
**What's wrong:** `confirmed_uplift_try`, `total_uplift_try`, and `review_uplift_try` are copy-pasted across 7 uplift dataclasses (`types.py:296-318, 367-383, 521-537, 552-568, 619-639, 753-781, 796-812`). Each re-implements `sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities if row.get("included_in_sgk_total", True))`. The `included_in_sgk_total` default inconsistency lives in 7 places.
**Why it matters:** Any change to uplift-sum logic (e.g. fixing the default, adding rounding) must be patched in 7 places. Silent drift otherwise.
**Minimal fix:** Introduce a `UpliftBlockMixin` with the 3 properties implemented once. The 7 dataclasses inherit. Behavior-preserving; `tsc`/tests catch regressions.

---

## Cross-cutting observations (not ranked — for context)

- **~70% of encoded prose rules are dormant.** Of ~1,943 rules across audited JSONs, only ~580 (≈30%) can fire on current data. ~1,360 are dormant inventory. Some dormancy is fixable bugs (#4 `_suffix_len`, #5 specialty field); most is genuine data-model gaps (biomarkers, board composition, `bmi` in context, e-nabız, `provision_type`). The single highest-leverage data fix is `procedure_specialty_code` (#8).
- **Two money-math correctness bugs inflating SGK-uplift totals:** #13 (ICU/yatak don't net out actuals) and #14 (session-violation detector skipped by default). Both make the "recoverable ₺" headline overstated.
- **The validation motor (`analyze_claim`) is not wired into the billing report.** 50+ validation detectors surface only via `/validate-claim`, not in `BillingActionReport` or `recommended_actions`. The two-engine split is intentional, but the seam is undocumented and untested — a strategic decision worth making explicitly.
- **No audit log / export of billing decisions.** For a health-billing engine subject to SGK audit, the lack of a deterministic `rule_id → patient → ₺` provenance table is a compliance gap. `recommended_actions` is the only trace, and it collapses to one string.
- **Test coverage on money-math paths is systematically weak.** The registry-driven aggregation (`BILLING_BLOCK_SPECS` → `report_totals` → `cohort_summary` → `report_exactness`) is tested with all-zero values. A typo in any spec field would pass every test. Items #15-16 are the same shape — one parametrized "spec integrity" test suite would close both.

---

## Corrections (2026-07-14 — post-evaluation)

An independent evaluation verified all 30 findings against the code. 22 confirmed, 3 wrong (false positives), 3 partially right. The 3 false positives are **RETRACTED**:

| # | Original claim | Verdict | Evidence |
|---|---|---|---|
| ~~#3~~ (P0) | `assign_priority_by_percentile` IndexError on clean cohorts | **WRONG** | `priority.py:13` uses `n = len(recoverables)`, not `len(reports)`. Reproduced with `[0,0,0,100,200,300]` → no crash. Subagent misread the variable. |
| ~~#11~~ (P1) | `_savings_by_category` has 3 duplicate dict keys → 6 dead entries | **WRONG** | AST confirms 22 unique keys, 0 duplicates. `lab`/`compliance`, `copay`/`copay_waiver` are intentional aliases (same source, different consumers). |
| ~~#14~~ (P1) | Session detector "NEVER called" due to `same_incision=None` default | **WRONG** | Both production callers pass `same_incision=True` explicitly (`unbundling.py:65`, `claim_audit_exposure.py:23`). The detector fires. |

**Root cause of the 3 false positives:** subagents read function bodies but didn't execute/trace them or grep call sites. A 5-second runtime check would have killed #3; an AST key-count would have killed #11; a grep for callers would have killed #14.

**Lesson recorded in tasks/lessons.md:** audit findings claiming "this crashes" or "this is never called" require execution or call-site proof — not just reading the function body.

## Implemented fixes (2026-07-14)

| # | Fix | Status | Verification |
|---|---|---|---|
| #1 | `user_role` derived server-side from session token + `BILUN_DEV_USERNAMES` env var; `req.user_role` ignored | ✅ Shipped | `resolve_user_role()` unit-tested |
| #2 | Login rate limiting: per-IP failure counter, 10 failures → 5-min lockout | ✅ Shipped | `_check_login_lockout` unit-tested |
| #4 | `_SET_PREDICATE_SUFFIXES` reordered longest-first in gap_closing + treatment_pricing | ✅ Shipped | `_suffix_len` + `_condition_matches` verified |
| #5 | `procedure_specialty_code` read from `ProcedureClaimLine` not `ClaimHeader` | ✅ Shipped | Context builder verified |

**Test suite:** 1726 passed (domain + chatbot, excluding API tests blocked by Cursor DuckDB lock — pre-existing environment issue).
