# Rule-Encoding Gap Closure & Unified Claim Engine — Roadmap

**Status:** Approved (user sign-off via ExitPlanMode)
**Branch:** `rule-encoding-gap-closure` (created from `main` at HEAD = `a3e768c` + uncommitted RuleDatabaseSection work)
**Estimated effort:** ~10 weeks across 6 phases (the unified engine is the dominant cost; ~6 weeks without it)
**Risk profile:** HIGH — touches both validation paths, the shared coverage pipeline, and ~15 motors

> **Source of truth:** the canonical plan also lives at `tasks/todo.md` (checkbox form, updated as work progresses). This file is the long-form reference.

---

## VERIFIED BASELINE (captured 2026-07-05, post-`ec33851`)

> ⚠️ The diagnostic report's agents queried at `35a23bd` and reported 914 gaps / 3,954 implemented.
> Commit `ec33851` ("honest drug_indication partial status") then flipped `drug_indication_prose`
> from `implemented` → `partial` in `rule_registry.py:350`, roughly doubling the gap count.
> **All phase checkpoints use the CURRENT HEAD numbers below, not the report's stale figures.**

| Metric | Value (HEAD = post-ec33851) |
|---|---|
| Total in-force rows | 4,710 |
| `coverage_status = implemented` | 1,585 |
| `coverage_status = partial` | 2,422 |
| `coverage_status = non_algorithmic` | 703 |
| `has_rule_encoding = True` | 1,978 |
| `has_rule_encoding = False` | 2,732 |
| **`has_algorithmic_gap = True`** | **1,896** |
| `algorithmic_gap_pct` | 40.3% |
| Unencoded (impl OR partial) | 2,183 |

Top unencoded buckets (by primary_rule_id): `drug_indication_prose` 1,183 · `payment_method_package` 336 · `specialty_materials` 332 · `pricing_ek2b` 75 · `material_bundling_prose` 53 · `copay_rate_general` 45 · `surcharge_general` 42 · `drug_discount_prose` 38 · `drg_package_adequacy` 28 · `copay_rate_ek2c1` 21 · `pricing_ek2c` 7 · `dental_2_4_1` 5.

---

## Goal

Eliminate the "implemented/partial but not encoded" gap population (2,183 clauses) through three mechanisms:
1. **Honest reclassification** — clauses served by code/annex motors (price oracles, headings, amendments) move to `non_algorithmic` (~1,100+ clauses stop masquerading as encode-debt).
2. **Real encoding** — encodable decision rules get JSON rules + manifest wiring + (where needed) new prose evaluators.
3. **Unified claim engine** — collapse `validate_claim(dict)` and `compute_patient_billing_report(ctx)` into one core (`PatientClaimContext + analyze_claim()`).

Plus: the 4 hygiene fixes and a full drug Tier-C re-triage.

## Honest decomposition of the 2,183 (from Agent 3, still load-bearing)

- **821** structural (amendment=468, section_heading=353) → reclassify `non_algorithmic`
- **681** Tier-C-deferred drug → full re-triage
- **27** EMR-blocked drug → keep deferred (honest)
- **179** un-triaged real drug gaps → triage + encode
- **587** real decision-rule text → encode (~250 of these live in code-only/annex motors → reclassify)
- **66** pure annex lookups → reclassify `non_algorithmic`

## Decisions locked from Q&A

| Decision | Choice |
|---|---|
| Encoding scope | All 2,183 addressed (encode or reclassify) |
| Structural exclusions | Full drug Tier-C re-triage (~860 clauses) |
| Gap policy | Keep (A): unencoded-implemented = gap |
| Code-only motors | Build evaluators where feasible (~5); reclassify price oracles (~250) |
| Claim-line motors | **Unified claim engine** — `analyze_claim()` core, `validate_claim(dict)` = thin adapter |
| Plan granularity | Full roadmap, phased with checkpoints |

---

## Phase 0 — Hygiene fixes (~2 days, low risk)

- [ ] **0.1 Orphan ref reconciliation.** 61 orphan `gate_b_sources` across 32 drug rules (all §4.2.13/14/16/17/6/9) point to struck clauses (`had_struck_content=True`, filtered by `_IN_FORCE_ONLY` at `coverage.py:16`). Re-attach via `amendment_refs` in `sut_clauses.parquet` using orchestrator-only `_apply_source_patches` (`compile_rules.py:833-850`) — never edit `drug_indication_prose.json` directly.
- [ ] **0.2 Delete dead schema.** `data/gazette/prose_rules/schemas/base_rule_set.schema.json` (0 code references). Final-grep confirm → delete → verify `compile_rules.py --check` passes.
- [ ] **0.3 Soften brittle test locks.** `test_rule_sources.py:79-80,86,113,129`, `test_drug_indication_gate_b.py:18,20`, the `==131/282/832` tests. Replace `==` with `>=` floors (precedent: `test_rule_interaction_graph.py:24-30` uses ±15% relative).
- [ ] **0.4 Extract the `implemented ∧ ¬has_rule_encoding` predicate.** Re-derived as raw polars masks in 5+ scripts (`build_sut_coverage.py:73`, `close_algorithmic_gaps.py:97`, `extract_tier_c_drug_rules.py:122`, `prose_rules/drug_indication.py:344`). Add `is_implemented_but_unencoded(row)` next to `_is_structural_gap_excluded` (`coverage.py:118`).
- [ ] **Checkpoint 0:** `pytest tests/unit/scripts/test_rule_sources.py tests/unit/scripts/test_sut_coverage.py` green; `build_sut_coverage.py` reproduces HEAD baseline (1,896 gaps / 1,978 encoded) ±0; orphan count == 0.

## Phase 1 — Honest reclassification (~1 week)

Most of the headline gap-count reduction comes from here, at lowest risk.

- [ ] **1.1** Reclassify the 821 structural clauses via `_has_actionable_signal` (`coverage.py:79-93`): structural-only signal → `non_algorithmic` at classification time (not just gap-suppressed).
- [ ] **1.2** Reclassify ~66 pure annex-lookup clauses (`pricing_ek2b`/`pricing_ek2c`/`copay_rate_ek2c1`/`copay_exemption_ek1a`/`material_preauth_ek3c1`/`specialty_materials`-legacy where `text_tr` is essentially `(EK-2/B)`).
- [ ] **1.3** Reclassify ~250 decision-rule clauses in price-oracle/code-only motors (`pricing_ek2b`=39, `pricing_ek2c`=7, `copay_rate_ek2c1`=16, `copay_exemption_ek1a`=1, `drug_discount_prose`=38, `specialty_materials` legacy pricing subset) via an explicit, auditable, reversible `RECLASSIFY_AS_NON_ALGORITHMIC` set keyed by `(primary_rule_id, clause_id)`.
- [ ] **Checkpoint 1:** `non_algorithmic` count up ~1,100–1,200; `algorithmic_gaps` drops materially (target TBD from run).

## Phase 2 — Unified claim engine (3–4 weeks, HIGHEST RISK)

Leaf primitives (`evaluate_drug_indication_line`, `check_material_bundling_prose`, `check_specialty_materials_prose`) are already shared; the impedance is at orchestration + adapter layers.

- [x] **2.1 Write `check_bundling_violations_for_context` / `check_exclusion_violations_for_context`** (Risk 1 — biggest unknown). AUDIT OUTCOME: thin-wrapper parity was IMPOSSIBLE (CSV `is_bundled` is a broader pricing-bundle concept, not a stale EK-3B-1 label). User chose Option A (additive derivation): new `is_ek3b1_bundled` + `is_excluded` fields on `MaterialClaimLine`, populated at build time by `_enrich_material_regulatory_flags` from the canonical `match_bundled_material` / `is_material_reimbursable` matchers. Parity test `tests/unit/domain/rules/test_parity_context_wrappers.py` (7 tests) clears the gate structurally.
- [x] **2.2 Build canonical dict→`PatientClaimContext` adapter** — `src/bilun/domain/claims/adapter.py:build_context_from_material_dict`. `billed_amount_try = unit_price × quantity` when `billed_amount` absent (mirrors legacy compute at `rule_engine.py:52`).
- [x] **2.3 `analyze_claim(ctx) -> list[dict]`** in `src/bilun/domain/billing/engine.py`. Validation-only core (5 motors); the broader ~15-motor billing-optimization pipeline stays in `compute_patient_billing_report`.
- [x] **2.4 `validate_claim(dict)` thin adapter** — builds ctx, calls `analyze_claim`, projects to `ClaimValidationResult`. Legacy body preserved as `_validate_claim_legacy` for the parity test (`tests/unit/domain/test_validate_claim_adapter_parity.py`, 6 tests across 5 fixture shapes).
- [x] **2.5 Caller migration** — `/validate-claim` and chatbot unchanged (contract preserved); the 7 aggregation tests in `test_rule_engine_validate_claim.py` migrated to call `_validate_claim_legacy` directly (they patch its internals).
- [~] **2.6 `compute_patient_billing_report` facade — N/A (different scope).** `analyze_claim` is the validation seam (5 regulatory motors); `compute_patient_billing_report` is the broader billing-optimization report (~15 motors including copay, billing strategy, uplifts). They're complementary, not facade/inner. Forcing a facade would either drop billing-report functionality or double-count violations. Documented as a scope clarification, not a regression.
- [x] **Checkpoint 2:** 1732 passed, 0 failed across domain/scripts/chatbot/api suites. The pre-existing §3.1/§3.3 `risk_amount` divergence (legacy per-unit vs context total) is documented as an accepted correctness improvement in the parity test.

## Phase 3 — Build new prose evaluators (~1 week, gated on Phase 2)

- [ ] **3.1 `dental_2_4_1`** (EASIEST) — evaluator `check_dental_2_4_1_prose` already exists, material-dict-based. 5-line wire into `analyze_claim`.
- [ ] **3.2 `drg_package_adequacy`** — already JSON-driven (`drg_package_adequacy_prose.json`); after unification runs for all callers. Encode the 28 unencoded §2.2.1.B clauses.
- [ ] **3.3 `procedure_pairing`** — already JSON-driven; wire into unified core.
- [ ] **3.4 `material_preauth_ek3c1`** (EASY) — convert `_get_ek3c1_preauth()` list to JSON rules + membership check. Encode 2.
- [ ] **3.5 `material_miat_ek3c2`** (EASY) — convert `_get_ek3c2_miat()` to JSON rules + interval math. Encode 3.
- [ ] **3.6 SKIP (per Q&A):** `pricing_ek2b/ek2c`, `copay_rate_ek2c1`, `copay_exemption_ek1a`, `drug_discount_prose`, `surcharge_general`, `specialty_materials` legacy, `copay_rate_general`, `drg_unbundling`, `lab_billing`, `payment_method_*`. Each gets a `// CODE-ONLY BY DESIGN — see roadmap` comment.
- [ ] **Checkpoint 3:** each evaluator has a unit test; encoded count +~40.

## Phase 4 — Encode decision-rule clauses in prose-evaluable motors (~2 weeks)

Uses the **safe subagent pattern** from `tasks/lessons.md` (2026-06-29): subagents produce self-contained `*_patches.py` + dedicated manifest JSONs; orchestrator does ALL shared-file writes SEQUENTIALLY. Batches ≤60 clauses per subagent (timeout-tail-loss lesson).

- [ ] **4.1 `material_bundling_prose`** — 44 real unencoded. §3.1.3/3.1.4 list-of-criteria `bent` clauses. ~2 batches. New condition flags → `material_bundling.py:227-278` claim_flags + `_rule_evaluation_priority`.
- [ ] **4.2 `specialty_materials_prose`** — ~190 real unencoded. §3.3 wound-care/oxygen/specialty criteria. ~4 batches. New flags → `specialty_materials.py:26-63`.
- [ ] **4.3 `copay_rate_general`** — 34 real. **Requires paired refactor** of `copay_general.py:30,42,58,86` hardcoded rule_id lookups → iterate. ~1 batch + refactor.
- [ ] **4.4 `drg_unbundling`** — 4 clauses. Decision deferred to Phase 4 entry.
- [ ] **Per-batch workflow (MANDATORY — prevents clobbering):** subagent writes own `scripts/sut/prose/<motor>_<batch>_patches.py` + own manifest `data/gazette/prose_manifests/<motor>_<batch>_manifest.json` → returns → orchestrator runs `compile_rules.py --target <batch>` sequentially → orchestrator wires manifests into `coverage.py` in one pass → `build_sut_coverage.py` verifies encoded +N, gap −N.
- [ ] **Checkpoint 4:** per-batch monotonic encoded↑/gap↓; `algorithmic_gaps` in the low hundreds (residual = Tier-C drug).

## Phase 5 — Full drug Tier-C re-triage (~1.5 weeks)

The 681 `tier_c_deferred` + 179 un-triaged + 441 fikra/bent/numbered_item candidates (rivaroksaban dosing, somatropin criteria, anti-VEGF protocols).

- [ ] **5.1** Build triage worklist (~860 clauses with text_tr, sut_section, manifest_status, defer_themes).
- [ ] **5.2** Per-section triage subagents (≤60 clauses). For each: PROMOTE (clean drug_name+indication → encode) / KEEP DEFERRED (refine `defer_reason`) / EMR-BLOCKED (move lists).
- [ ] **5.3** Encode PROMOTE set — drug rules are parametric, `evaluate_drug_indication_line` already reads flat fields, no evaluator change.
- [ ] **5.4** Update 23 drug manifests; `reconcile_drug_manifests` re-derives bucket lists from traces.
- [ ] **Checkpoint 5:** each drug section `manifest_coverage_pct` ≥ 95%; PROMOTE rules have unit tests (sample 10%); `drug_indication_prose` gaps <100.

## Phase 6 — Final verification (~3 days)

- [ ] **6.1** Full fresh pipeline: `extract_sut_prose` → `build_sut_coverage` → cache rebuild (`BILUN_STARTUP_POLICY=rebuild`).
- [ ] **6.2** Gap reconciliation — expected `algorithmic_gaps` <150 (down from 1,896).
- [ ] **6.3** Dashboard audit (`CoverageSummaryPanel`, `GapCompositionBanner`, `SectionBrowserPanel`).
- [ ] **6.4** Full test suite green.
- [ ] **6.5** Update `tasks/lessons.md` with new patterns.
- [ ] **Checkpoint 6 (FINAL):** staff-engineer review.

---

## Out of Scope

- No gap-policy change (A retained). No new rule categories. No frontend rewrite. No DB schema changes. No `_STATUS_RANK` change. `payment_method`/`copay_rate_general`/`surcharge_general`/`lab_billing` stay code-only. No synthetic cohort regen unless 6.1 surfaces a latent bug.

## Top-5 risk register

1. **HIGH — bundling/exclusion parity** (Phase 2.1 hard gate).
2. **HIGH — dict→Context adapter** (Phase 2.2 per-motor gating).
3. **MED-HIGH — double-counting** (Phase 2.4 before/after totals).
4. **MED — serialization contract** (Phase 2.4 + chatbot monkeypatch path).
5. **MED — encoding clobbering recurrence** (Phase 4 orchestrator-only shared-file writes).

## Recommended execution order

Phase 0 → 1 first (safe, fast gap-count win, ~1.5 weeks). Then **decide whether to commit to the Phase 2 unified engine** before proceeding. The plan currently commits to it per the Q&A choice.
