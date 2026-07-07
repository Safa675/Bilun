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
