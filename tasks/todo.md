## Task: Pipeline simplification (remaining phases)

### Goal
Complete remaining work from `plans/billing/pipeline-simplification-plan.md`: canonical manifests, compile_rules gate_b routing, coverage simplification, dead-code cleanup. `compile_rules.py --check` and pytest green at end.

### Subtasks
- [x] Phase 1 (finish): route `compile_rules` gate-B stages via `gate_b_section` + `gate_b_shim` — DONE (WIP)
- [x] Phase 2: emit `canonical-v1` from all writers + purge legacy fields + rewrite readers — DONE (WIP + 4 test fixes)
- [x] Phase 2b: migrate static manifests to `canonical-v1` shell via `build_canonical_encoded_shell` — DONE (WIP)
- [x] Phase 3: `deferral_table.yaml` wired — DONE (pre-existing)
- [x] Phase 4: parquet-derived corpus counts (`rules_catalog.py` L22) — DONE (WIP)
- [x] Phase 5: remove `xfail` — DONE (fixed latent `set - dict` TypeError; regen restored 0% drift; 22 cases pass)
- [x] Phase 6: simplify `coverage.py` (table-driven `_section_manifest_encode_override`) — DONE (711→695 ln)
- [x] Phase 7: delete 14 gate_b shim files + migrate 14 test files to `gate_b_shim`/`gate_b_audit` directly — DONE

### Review
- `compile_rules.py --check`: **PASS** (147 artifacts byte-identical)
- `audit_manifest_parity.py --drug-only`: **0 issues** across 23 manifests
- 14 per-section shim modules deleted (~940 lines); tests now call `shim_export_candidates("XXXX", ...)` / `gate_b_audit` directly; bespoke helpers (`is_421_proper`, `_combined_4210_batch_rules`, `audit_4227_gap_parity`, `_with_defer_themes`) co-located as test-local helpers
- Latent bug fixed: `test_manifest_derivation_invariants.py` had `set - {}` (dict) TypeError masked by xfail
- Status-honesty fix: old `inn_named_clause_count=536` was inflated vs its own traces (412); corrected
- 1378 tests pass across scripts + prose_rules + api

### Out of Scope
- Evaluator matching logic, extractor docx parsing, consolidating payment/material/copay gate_b modules, commit/push unless requested.

---

## Task: Phase 6 — Billing product IA v2 (premium-ui-enhancement-plan.md)

Branch `feat/frontend-billing-ia-v2`. Frontend-only; backend pipeline files in the working tree left untouched. 16 files changed (+394/−142).

### Subtasks
- [x] S1 — OriginalBillView line highlighting: `recommendedActionLineCodes()` helper + `selectedActionId` state + `highlightCodes` memo in `page.tsx`; `OriginalBillView` highlights matching rows; `RecommendedActionsPanel` rows selectable. Unit test added.
- [x] S2 — `?section=` URL write-back: `handleSelectAction` writes URL via `router.replace`; extended `RECOMMENDED_ACTION_SECTION_IDS` + added `id=` anchors to all 9 uplift `BillingSectionShell` calls.
- [x] S3 — Exactness: 3 inline `<p>` notices in `SutOptimizationSection` → `<ExactnessBlock>`. StatusChip → `Chip` across all 14 call sites via `chipVariantFromColor()`; `StatusChip` deleted.
- [x] S4 — Gold discipline: demoted 3 italic-gold violations (Diagnoses, Total billed, Rule-calculated opportunity) + dead ternary. Patient page = exactly 2 italic-gold (H1 `<em>` + primary recoverable Stat).
- [x] S5 — Wrapped `ProseInventoryPanel` raw `<table>` in `overflow-x-auto`; other dense tables already scroll-safe.
- [x] S6 — Empty states (subagent): DrugCatalog / RuleList (+onClearFilters) / ClauseBrowser / SectionBrowser → `<EmptyState>` + CTAs; EN+TR i18n.

### Review
- `tsc --noEmit` → 0. `vitest` → 159 passed (158 baseline + 1 new). `next build` → 0. `eslint` → 0 new problems vs baseline (proven via `git stash` A/B: 9 pre-existing in untouched data-fetching effects).
- Color→Chip mapping: gold-status chips collapse to `success` (design system reserves `gold` for actionable emphasis); informational blue → `outline`. Flagged for product review.
- Updated `billing/page.test.tsx` gold assertion to the demoted contract.

### Out of Scope
- `medula_playbook` line highlight (no code in action row — backend field fix needed); SUTOptimizerTab cohort `<td>` empty-states; pre-existing lint errors in page.tsx/rule-database effects; commit/push.

---

## Task: ICU İlave Oran (+100%) — Sınıf-3 facility surcharge (Phase 2 of icu_puani)

### Goal
Apply the EK-2/C-1 ilave oran (+100%, in-force) to intermediate ICU package (P55200x) days when the facility resolves to **3rd basamak**. Multiplies the intermediate puan × 2.0 for eligible facilities. `510090` day-rate is untouched (it is EK-2B hizmet-başı, not in EK-2/C-1).

### Subtasks
- [x] S1 — Add helper `_resolve_ilave_oran(claim, intermediate_code) -> (oran_pct: float, reason: str)` in `icu_puani.py`:
  - Resolve tier via `normalize_facility_tier(claim.facility_tier, provider_type=claim.provider_type)` (matches `care_setting_review.py:140` convention — NOT `tier_context_from_claim`, which is test-only)
  - `not tier.resolved` → `(0.0, "tier_unresolved")`
  - `not tier.is_third_tier` → `(0.0, "not_sinif_3")`
  - Else look up `get_ek2c1_copay_rates().get(f"P{intermediate_code}")` and extract `float(row.get("copay_rate_pct", 0.0))` — **NOT** the raw dict (B1 fix). Key MUST be P-prefixed (B2 fix).
  - Return `(oran_pct, "sinif_3_uplift_applied")`
- [x] S2 — In `detect_icu_puani_opportunities`, after `intermediate_code` is selected (`icu_puani.py:224-226`), call `_resolve_ilave_oran(claim, intermediate_code)` once. Compute `intermediate_puan_uplifted = intermediate_puan * (1 + oran/100)` and same for price_try. Use uplifted values in `total_puan`/`total_try` sums. Leave `first_last_count * day_rate_*` unchanged.
- [x] S3 — Enrich opportunity dict with: `ilave_oran_pct`, `ilave_oran_eligible` (bool), `ilave_oran_reason`, `intermediate_puan_base`, `intermediate_puan_uplifted`. Keep existing `intermediate_puan` key = **base** (unchanged downstream contract; only unit tests read it).
- [x] S4 — Rewrite `detail` string (lines 256-263) to reflect uplift status (safe — verified zero production consumers; only the docstring TODO mentions it).
- [x] S5 — Remove the Phase-2 TODO from module docstring (lines 28-31).
- [x] S6 — Update `tests/unit/domain/prose_rules/test_icu_puani.py`:
  - Change `_make_claim_header` default `facility_tier` from `"devlet"` (unresolved) to `"3_basamak"` (resolves cleanly, is_third_tier=True). This makes the 9 existing tests exercise the uplift path.
  - Update existing `total_puan`/`total_try` assertions in the 3 existing multi-day tests to reflect the ×2.0 intermediate uplift.
  - Add 3 NEW tests: (a) explicit 2nd-basamak (`"2_basamak_kamu"`) → oran=0, totals unchanged; (b) unresolved tier (`"devlet"`) → oran=0, reason=`tier_unresolved`; (c) assert the new `ilave_oran_*` fields are populated correctly on the Sınıf-3 path.
- [x] S7 — Run the full ICU + billing test suite; verify `confirmed_icu_try` (via `total_try`) flows correctly.

### Review
- `pytest tests/unit/domain/prose_rules/test_icu_puani.py -v` → **14 passed** (11 original + 3 new ilave-oran tests).
- `pytest tests/unit/domain/billing/ tests/unit/domain/prose_rules/ -q` → **1126 passed, 0 failed**. Integration tests (`test_claim_integration.py`, `test_orchestrator_grand_total.py`) that read `confirmed_icu_try` all still pass — no downstream total shifted, meaning the integration/wrapper tests do not construct Sınıf-3 ICU claims (so no totals were invalidated).
- Both warnings in the run are pre-existing and unrelated (`jsonschema.RefResolver` deprecation, class-scoped fixture in `test_bill_billing_report.py`).
- No causation check needed — zero test failures.
- Math sanity (Sınıf-3 path): 3-day/P552003 `15400.73 → 28296.90` (intermediate doubled); 4-day/P552001 `8948.14 → 15391.74`; 1-day/2-day unchanged (0 intermediate days).

### Decisions (verified)
- **Predicate = `is_third_tier`** (not `is_university_eah`). Web search confirms the gate is "3. basamak sağlık hizmeti sunucularınca yapılması halinde" — any 3rd-basamak facility, including non-university özel. `is_third_tier` (`basamak==3`) is correct and broader; `is_university_eah` would under-apply.
- **oran = 100** (in-force as of 2026-01-31 per parquet). The docstring's "+60% or +100%" was historical (rates revised upward repeatedly); +60% is stale. Drop it.
- **Tier resolver = `normalize_facility_tier`** (not `tier_context_from_claim`). Matches the convention in `care_setting_review.py` / `payment_method.py`; `tier_context_from_claim` has zero production callers.

### Out of Scope
- e-nabız +60 TL/day (§2.4.4.H.(10)) — needs data-submission signal not on ClaimHeader
- §2.2.2.B.(5) +30% star rule disabling — no other motor touches P55200x today (grep-clean), so no double-count risk. Document as inline TODO.
- Exact EK-2/A-1 facility classification (U1/U2/A1/A2) — `TierContext.is_third_tier` is the available proxy
- Reconciliation of the historical +60% rate (stale, dropped deliberately)
- Frontend/UI changes (the IA-v2 plan covers display; this task is backend-only)
