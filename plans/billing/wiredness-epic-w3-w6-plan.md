## Task: Wiredness Epic W3–W6 — Wire 68 More Rules (corrected)

### Goal
Wire 68 of the 337 remaining unwired rules via 4 proven patterns, on top of PR #7's W1–W2 baseline (which wired `gap_closing` + `gazette_repricing` + `material_uplift` into `analyze_claim`). Done = the wiredness matrix grows by 68 enforcement/traceability rules and `compile_rules.py --check` stays byte-identical.

### Starting state (verified 2026-07-06)
- Branch: `wiredness-epic`, PR #7 OPEN, CI green (backend SUCCESS, frontend SUCCESS), mergeable CLEAN.
- PR #7 W1–W2 **did** wire `gap_closing` into `engine.py:39-41,111-112` (`check_gap_closing_misc_for_context` / `check_gap_closing_treatment_for_context`). The earlier "gap_closing is orphaned" finding was branch-stale; it is live on this branch.
- Rule counts verified against JSON: treatment_pricing=182, drug_combination=53, payment_method=42, session_pricing=4, definitions_2_6=56 → **337 total, 68 wireable.**

### Evidence base (re-verified)
| Category | Total | Wireable | Pattern | Blocked |
|---|---|---|---|---|
| treatment_pricing_2_4 | 182 | 40 | Clone `gap_closing` loader + predicate engine + context builder | 142 need session counters / IVF cycles / temporal windows / clinical scores |
| drug_combination_4_2 | 53 | ~9–12 | Drug-name combo scan over `ctx.drug_lines` | 11 need drug-class map; 7 need pdl1/ecog; ~29 need EMR/clinical history |
| payment_method_2_2 | 42 | 12 | Secondary traceability pass | 30 need visit-sequence / temporal data |
| session_pricing_2_2_2_B | 4 | 4 | Read factor values from JSON | 0 |
| definitions_2_6 | 56 | 0 | Confirmed non-algorithmic reference | 56 |

---

### ⚠️ PREREQUISITE — W2.5: Fix the 3 Bugbot/Copilot issues in PR #7's W1–W2 before building on top

PR #7 shipped with **one HIGH and two MEDIUM** correctness bugs in the W1.3 gap_closing wiring that this epic builds on. Building W3–W6 on a foundation where gap_closing silently skips valid rules propagates the same defect into the clones. Fix these first, on the `wiredness-epic` branch, before W3.

- [ ] **W2.5a (HIGH) payment_method value mismatch** — `_build_gap_closing_context` (gap_closing.py ~L225-228) sets `payment_method` to `"package"/"itemized"` from `package_candidate`, but the 6 `gap_closing_treatment_2` rules that key on `payment_method` expect `"diagnosis_based"` (5 uses) / `"fee_for_service"` (1 use). **Verified: those 6 rules silently never fire.** Map the payment-method taxonomy correctly (derive `diagnosis_based`/`fee_for_service` from `claim_type` or `procedure_category`, not `package_candidate`).
- [ ] **W2.5b (MEDIUM) multi-procedure skips `_any` rules** — `_build_gap_closing_context` sets `procedure_category=None` when categories differ, but `_condition_matches` (gap_closing.py:85-89) reads the **base** field `procedure_category` (NOT `procedure_category_any`) for `procedure_category_any` predicates. `None` → honesty guard → skip. The builder writes a `procedure_category_any` key nothing reads. **Fix:** the predicate engine must read the `_any` key when present, OR the builder must keep the base field populated as a list.
- [ ] **W2.5c (MEDIUM) multi-claim context mishandled** — gazette_repricing + material_uplift wrappers pass `ctx.claims[0]` but all `ctx.procedure_lines`. Stale-price flags / pairing misses attribute to the wrong claim. Scope procedure lines to the passed header's `claim_id`.
- [ ] **W2.5d (LOW) Copilot doc nit** — `tasks/todo.md` in PR #7 was overwritten with frontend overhaul content unrelated to the PR's purpose. Revert `tasks/todo.md` on `wiredness-epic` to `main`'s version (the frontend content belongs on `feat/frontend-premium-ui`, not this branch).

Verification for W2.5: re-run the 6 treatment payment-method rules + multi-procedure fixture, confirm they now fire; `pytest tests/unit/ tests/smoke/` green.

---

### W3 — treatment_pricing evaluator (40 rules)
The highest-value batch. Clone the gap_closing pattern: a JSON loader + predicate engine + `_build_treatment_pricing_context(ctx)` that maps `PatientClaimContext` fields to the flat dict the evaluator consumes.

The 40 wireable rules use ONLY condition keys derivable from existing fields (verified frequencies):
- `procedure_category` (120) ← `ProcedureClaimLine.procedure_category`
- `procedure_code_any` (30) ← `ProcedureClaimLine.procedure_code`
- `provider_type` (11) ← `ClaimHeader.provider_type`
- `facility_not_in` / `facility_type_any` (18) ← `ClaimHeader.facility_tier`
- `diagnosis_any` / `diagnosis_in` (14) ← `ClaimDiagnosis.icd10_code`
- `health_board_report_present` (7) ← drug-line board-report flag

- [ ] W3.1 Create `src/bilun/domain/prose_rules/treatment_pricing.py`:
  - `load_treatment_pricing_rules()` — `lru_cache` JSON loader
  - `_condition_matches(condition, context)` — reuse gap_closing's predicate engine. **IMPORTANT (corrected): gap_closing's set-membership does NOT do ICD-10 prefix matching.** For `diagnosis_any`/`diagnosis_in` (14 uses), either (a) pre-expand billed ICD-10 codes into their prefix forms in the context builder, or (b) port `drug_indication._diagnosis_matches_rule`'s prefix logic (`drug_indication.py:493-515`). Do not claim gap_closing handles it — it does exact intersection only.
  - `_build_treatment_pricing_context(ctx)` — maps ClaimHeader + ProcedureClaimLine categories/codes + diagnoses + health_report_present to the flat dict
  - `check_treatment_pricing_for_context(ctx)` — iterates rules, calls `_condition_matches`, emits violations with `rule="treatment_pricing_2_4"`
  - Register in `rule_registry.py` (new entry, `coverage_status="implemented"`)
- [ ] W3.2 Wire `check_treatment_pricing_for_context(ctx)` into `engine.py` inside `if ctx.procedure_lines:` (same gate as the W1.3 motors)
- [ ] W3.3 Write tests: procedure-category-triggered rule fires; negative case; empty procedure_lines → no violations; **ICD-10 prefix match** (`diagnosis_in: ["E11"]` matches billed `"E11.9"`)

### W4 — drug_combination evaluator (~9–12 rules)
Cross-line drug combo detection. Scan `ctx.drug_lines` grouped by claim, test for concurrent drug pairs/triplets using INN name matching (the existing `_drug_name_matches` from `drug_indication.py:468`).

**Corrected wireability (was "9 today + 3 deferred"):** actual counts of blocked sub-sets are larger than first estimated:
- 11 rules touch `drug_class`/`drug_class_any`/`concurrent_drug_class_any` (not 3) → need a drug→class map (~50 INN table) → defer
- 7 rules need `pdl1_expression_pct`/`ecog_score` → EMR data, defer
- Several of the "9 wireable" carry keys the W4.1 predicate list must define or they silently no-op via the honesty guard: `concurrent`, `combination`, `formulation`, `treatment_phase`, `indication`, `two_distinct_agents_same_class_concurrent`, `two_distinct_active_ingredients_concurrent`

- [ ] W4.1 Create `src/bilun/domain/prose_rules/drug_combination.py`:
  - `load_drug_combination_rules()` — `lru_cache` loader
  - `_check_combo_condition(condition, drug_names_on_claim, diagnoses)` — evaluates `drug_name_any`, `drug_name_set_any_two` (≥2 listed drugs present on same claim), `diagnosis_any` (ICD-10 prefix match), AND define explicit semantics for `concurrent`/`combination`/`two_distinct_*` (treat as "≥2 distinct drugs on same claim" unless a rule needs otherwise). Any key without defined semantics → defer that rule, do not let it silently no-op.
  - `_collect_drug_names(ctx)` — extracts the set of drug names from `ctx.drug_lines` per claim
  - `check_drug_combination_for_context(ctx)` — groups by claim, evaluates combo rules, emits violations with `rule="drug_combination_4_2"`
  - Register in `rule_registry.py`
- [ ] W4.2 Wire `check_drug_combination_for_context(ctx)` into `engine.py` (gated on `ctx.drug_lines`, like drug_indication)
- [ ] W4.3 Write tests: claim with two anti-TNF drugs → combo violation; single drug → no violation; empty drug_lines → no violations
- [ ] W4.4 **Re-derive the final wireable count after W4.1** — report the exact number of rules that genuinely fire, split out the deferred-with-reason list. Do not headline "12" if the predicate gaps reduce it.

### W5 — payment_method secondary traceability pass (12 rules)
The hardcoded `_classify_payment_method_kind` (`payment_method.py:93`) makes the primary decision. The JSON rules add no-pay/mandatory-billing nuances whose conditions are derivable (`provider_type`, `care_setting`, `procedure_in_annex`). Run them as a secondary pass that emits traceability violations.

- [ ] W5.1 Create `check_payment_method_traceability_for_context(ctx)` in `payment_method.py`:
  - Reuse `gap_closing._condition_matches` against a context built from ClaimHeader (provider_type, claim_type→care_setting, package_candidate→payment_method) — **after W2.5a fixes the payment_method taxonomy**, so the traceability pass inherits correct values.
  - Iterate the 42 rules from `payment_method_2_2.json`; the honest-skip guard handles the ~30 with unavailable keys.
  - Emit violations with `rule="payment_method_traceability"`, `severity="info"` (traceability, not enforcement — the primary decision is already correct).
- [ ] W5.2 Wire into `engine.py` — **anchor point now exists** after W1.3 wired gap_closing (lines 111-112). Insert after the gap_closing `_for_context` calls, before the procedure-gated block.
- [ ] W5.3 Write tests: claim with provider_type matching a no-pay rule → traceability violation; mismatched provider_type → no violation

### W6 — session_pricing factor-read refactor (4 rules)
Make the JSON the single source of truth for factor values (currently hardcoded `0.25/0.5/0.3` at `session_pricing.py:72,74,171,206`). The selection logic (which of the 4 rules applies) is already computed via `same_session`/`same_incision`/`all_in_ek2c`/`mixed_ek2c_ek2b` — just read the factor VALUES from the JSON instead of literals.

- [ ] W6.1 Refactor `session_pricing.py::compute_session_point_factors`:
  - After computing `(same_session, same_incision, all_in_ek2c, mixed_ek2c_ek2b)`, look up the matching rule from `session_pricing_2_2_2_B.json` by condition match.
  - Read `action.highest_procedure_factor`, `action.other_procedure_factor`, `action.ek2c_procedure_factor`, `action.ek2b_procedure_factor` from the matched rule.
  - Fall back to the hardcoded defaults if JSON is absent or no rule matches (backward compatibility).
  - This makes the JSON DRIVE the decision, not just document it.
- [ ] W6.2 No new `_for_context` wrapper needed — session_pricing runs via the orchestrator, not `analyze_claim` (it needs procedure-line grouping logic). The refactor makes it JSON-driven; the wiring to `analyze_claim` is a separate concern (the orchestrator already calls it).
- [ ] W6.3 Write test: verify factors come from JSON; verify fallback when JSON absent.

### W7 — Verification
- [ ] `compile_rules.py --check`: artifacts byte-identical
- [ ] `pytest tests/unit/ tests/smoke/`: full suite green
- [ ] Re-run the wiredness matrix: confirm the exact number of newly-wired rules, **reported split by enforcement vs traceability** (so the headline isn't inflated by info-severity noise)
- [ ] Update the plan/lessons with the revised wiredness count
- [ ] Check CI green **before** every push (AGENTS.md §10 — never push on red CI)

### Out of Scope (the 269 genuinely blocked — confirmed absent from claim models)
- 29 drug_combination rules needing EMR/clinical history (PD-L1, ECOG, prior therapy, recurrence windows) — keys verified 0 hits in `claims/models.py`
- 142 treatment_pricing rules needing session counters / IVF cycle history / temporal windows / clinical scores (BMI, testosterone, risk scores) — keys verified 0 hits
- 30 payment_method rules needing visit-sequence / temporal data
- 56 definitions_2_6 rules confirmed non-algorithmic reference data (registry already `non_algorithmic`)
- 11 drug_combination rules needing a drug→class map (~50 INN classification table — separate data-modeling task; was "3" in the original plan, corrected upward)

These require data-model extensions or EMR integration — future epic territory.

### Execution order
W2.5 (prerequisite fixes) → W3 (treatment_pricing, highest value) → W4 (drug_combination) in parallel with W5 (payment_method) → W6 (session_pricing, smallest) → W7 (verification). W3 and W4 can be built by parallel subagents (different modules, no shared-file conflicts); W5 reuses gap_closing's predicate engine (import, not edit) and depends on W2.5a; W6 is a contained refactor in `session_pricing.py`.

### Review (filled in after implementation — 2026-07-07)

**Branch:** `feat/wiredness-w3-w6` (forked from `feat/frontend-premium-ui` @ `2735b5f`, which already contained the merged PR #7 W1–W2 + W2.5a–m baseline). W2.5 prerequisite was **already satisfied** — no W2.5 work needed.

**Implemented via 4 parallel subagents** (one focused vertical slice each, no shared-file conflicts) + serial orchestrator wiring of `billing/engine.py` + `rule_registry.py`.

#### Honest wired-rule counts (the plan's estimates were optimistic; runtime analysis is authoritative)

| Batch | Plan estimate | Actual wireable (runtime) | Honest-skip | Notes |
|---|---|---|---|---|
| W3 treatment_pricing | ~40 | **17** of 182 | 165 | Blocked by session counters / IVF cycles / temporal windows / clinical scores (BMI, testosterone, risk scores). |
| W4 drug_combination | ~9–12 | **6** of 53 | 47 | Blocked by drug→class map (~18), PD-L1/ECOG/Child-Pugh (~14 oncology), EMR prior-therapy timelines (~15). |
| W5 payment_method traceability | 12 | **2** of 42 | 40 | Primary `_classify_payment_method_kind` unchanged; traceability emits `info`-severity nuances. 40 honest-skip via gap_closing's predicate guard. |
| W6 session_pricing | 4 | **4** of 4 | 0 | JSON now drives factor values (was hardcoded literals); behavior identical, fallback preserved. |
| **Total** | **~68** | **29 newly wired** | 252 honest-skip | Split: 25 enforcement (W3+W4) + 2 traceability (W5, info-severity) + 4 JSON-driven refactor (W6). |

The headline "~68" was inflated by static-key analysis; runtime evaluation against the real `PatientClaimContext` fields yields **29**. The honesty guard (rules with unavailable condition keys simply don't fire) is working as designed — no false positives.

#### Verification (W7)
- `compile_rules.py --check`: **PASS** — 147 rule/manifest/corpus artifacts byte-identical.
- `pytest tests/unit/ tests/smoke/`: **1910 passed, 0 failed**, 9 skipped, 22 xfailed (up from 1844 baseline; +66 new tests across the 4 batches).
- Inventory integrity: `treatment_pricing_2_4` + `drug_combination_4_2` **graduated from "orphan" to "wired"** — `_ORPHAN_RULE_SETS` is now empty; `test_wired_engines_present` updated to assert both are listed.
- End-to-end smoke: `analyze_claim` fires the new motors on matching fixtures (W3 `robotic_rehab` rule, W4 `cinacalcet+etelcalsetid` combo, W5 `private_daily_visit_cap` traceability).

#### Key findings (worth flagging to gazette curators)
1. **Gazette drug-name spelling inconsistency (W4):** the `4.2.15.D-1` DOAC rule lists INN names in Turkish phonetic transliteration (`apiksaban`, `rivaroksaban`, `edoksaban`) while real claim data uses international INN (`apixaban`, `rivaroxaban`, `edoxaban`). The W4 evaluator faithfully matches what the JSON says, so the DOAC rule won't fire on real claims until the gazette is normalized. **Not patched here** — gazette curation is a separate task. Other W4 rules (cinacalcet, MS-DMT) use consistent INN and fire correctly.
2. **`procedure_category_any` predicate (W3, W2.5b lesson):** the W3 evaluator correctly reads the `_any` key for multi-category claims, avoiding the W2.5b bug where the base scalar was `None`.
3. **Honest deferral (W4.4):** `_check_combo_condition` returns a reason (`skipped_no_data` / `skipped_unknown_key` / `not_matched`) so deferred rules are auditable, not silently no-op'd.

#### Scope discipline
Only 11 backend files touched (5 modified + 6 new). No frontend, no `data/gazette/` artifacts, no manifests. The `feat/frontend-premium-ui` rebrand work and an unrelated `pipeline-simplification` workstream were explicitly excluded from the commit.
