## Task: Rule Database tab — SUT rule catalog + clause-source drill-down (2026-06-13)

### Goal
A new top-level "Rule Database" tab that lists every SUT rule (catalog index, with honest coverage status) and drills each rule down into the actual extracted SUT clause text + regulatory sources, served by a purpose-built backend API.

### Design decisions (confirmed with Safa)
1. Layout = **catalog-as-index** (rule list → drill into source clauses).
2. Sources = **actual SUT clause text** (Turkish `text_tr` from the extracted corpus), not just section/annex labels.
3. **Full honesty** about coverage — expose `implemented` / `partial` / `missing` / `needs_claim_lines` / `non_algorithmic` openly.
4. Backend served **from the ground up** (new endpoints, not reusing existing optimizer routes).

### Architecture decisions (agent defaults — flag if you disagree)
- Promote the rule catalog into the production domain layer: canonical `src/bilun/domain/sut/rule_registry.py`; turn `scripts/sut/prose/rule_registry.py` into a thin re-export so existing golden tests keep passing. (API importing from `scripts/` is architecturally wrong.)
- Serve clause drill-down from the **precomputed** `data/gazette/sut_clause_coverage.parquet` (classify already ran offline), read with **Polars**, filtered by `matched_rule_ids` containing the rule_id (many-to-many, not just `primary_rule_id`).
- Reference data, **not** the DuckDB cache: module-level lazy load like `domain/materials/drugs.py`; never touch `startup.py` / `cache/builder.py`.
- New top-level tab (id `rule-database`), not a Reference Tools sub-section.

### Subtasks

#### Phase 0 — Data artifact prerequisite
- [x] Confirm/generate `data/gazette/sut_clauses.parquet` via `scripts/sut/extract_sut_prose.py` (8,180 clauses, 545 sections)
- [x] Generate `data/gazette/sut_clause_coverage.parquet` + `sut_registry_coverage.parquet` via `scripts/sut/build_sut_coverage.py`
- [x] Verify row counts and that every `RULE_REGISTRY.rule_id` resolves (26/27 map clauses; only `claim_validation` orchestrator = 0, expected)

#### Phase 1 — Backend domain layer
- [x] Create `src/bilun/domain/sut/rule_registry.py` (canonical `RULE_REGISTRY` + `RuleRegistryEntry`); re-export shim in `scripts/sut/prose/rule_registry.py`
- [x] Add path constants to `src/bilun/domain/constants.py`: `SUT_CLAUSES_PATH`, `SUT_CLAUSE_COVERAGE_PATH`, `SUT_REGISTRY_COVERAGE_PATH`
- [x] Create `src/bilun/domain/sut/rules_catalog.py`: lazy Polars loader + `list_rules()` + `get_rule_clauses(rule_id)` (drill-down via `matched_rule_ids`, primary-first), graceful-degrade if parquet missing
- [x] Unit tests: catalog completeness, clause join + pagination, missing-artifact degradation (`tests/unit/domain/sut/test_rules_catalog.py`)

#### Phase 2 — Backend API
- [x] Add schemas to `src/bilun/api/schemas.py`: `RuleCatalogResponse`, `RuleDetailResponse`, `RuleCatalogEntry`, `RuleClause`, `RuleSources`
- [x] Create `src/bilun/api/routes/rules.py`: `GET /api/rules` (index), `GET /api/rules/{rule_id}` (detail + paginated clauses); 404 unknown id, 400 bad pagination
- [x] Register router + re-export handlers in `src/bilun/api/routes/__init__.py`
- [x] API tests (`tests/unit/api/test_sut_rules_api.py`): index, detail drill-down, pagination, 404, 400, graceful degradation

### Backend Review (Phase 0–2 complete, 2026-06-13)
- **Design deviation (intentional):** chose **graceful degradation + `artifacts_available` flag** over a hard 503 when clause artifacts are absent. The catalog still lists every rule (from the registry) with sources + coverage status; only clause text drops out. Matches the `domain/materials/drugs.py` empty-on-missing pattern and is more honest/robust for the UI (banner instead of dead tab).
- **Verification:** 34/34 new tests pass; live HTTP smoke (mounted router) returns 200 for `/api/rules` (27 rules) and `/api/rules/{id}` (62 clauses for `copay_rate_ek2c1`, paginated), 404 for unknown id, 400 for bad pagination.
- **Data note:** regenerating parquets produced byte-identical clause data (only pyarrow metadata differed), so committed parquets were kept to avoid a noisy binary diff.
- **Pre-existing failures (NOT introduced here):** `test_sut_cache_concurrency.py`, `test_sut_patient_alerts_api.py`, `test_sut_schema_exactness.py` all fail with `ModuleNotFoundError: No module named 'src.api'` (stale ILAY→BILUN import path); `test_material_bundling_golden.py[C001637]` is a pre-existing classify mismatch (fails on original committed parquets too).
- **PAUSED for review before Phase 3 (frontend)** per Safa's instruction.

#### Phase 3 — Frontend tab
- [x] `frontend/src/lib/constants.ts`: extend `SutHomeTab`, add `rule-database` to `SUT_HOME_TABS`, handle in `parseSutHomeTab`
- [x] `frontend/src/components/shell/AppTopBar.tsx`: add `rule-database` → `ruleDatabase` tabKey mapping
- [x] `frontend/src/app/page.tsx`: `dynamic()` import + render branch
- [x] `frontend/src/lib/api/sut.ts`: `getRuleCatalog()` + `getRuleDetail(ruleId)` types/fns via `requestJSON`
- [x] Create `SUTRuleDatabase.tsx` (thin shell) + `sut/sections/RuleDatabaseSection.tsx` (master-detail list + clause drill-down; reuses `EkAnnexChips`, `Section`, `Chip`, `Surface`; coverage chips use status tokens, gold reserved for active-row focus only)
- [x] i18n EN+TR: `homeTabs.ruleDatabase` in `messages/{en,tr}/constants.ts`; `sections.ruleDatabase.*` in `messages/{en,tr}/sections.ts`
- [x] Chat wiring: `defaultPrompts.ruleDatabase` in `messages/{en,tr}/chat.ts` + `resolvePromptKey` entry in `SutInlineAIPanel.tsx`; English `label` "Rule Database" matches the prompt-key map
- [x] Update `frontend/src/lib/constants.test.ts` for the new tab

#### Phase 4 — Verify
- [x] Backend: `pytest` new domain + api tests (34 pass); HTTP smoke via mounted router (200/404/400)
- [~] Frontend: IDE lints clean on all changed files; manual review of imports/props/exhaustiveness. **`vitest`/`tsc`/`next build` NOT run — no Node runtime in this environment.** Safa must run `cd frontend && npm install && npx tsc --noEmit && npx vitest run && npm run build` and load the tab in EN+TR.
- [ ] CI green before any push (AGENTS.md §10)

### Frontend Review (Phase 3 complete, 2026-06-13)
- **Tab:** new top-level `rule-database` ("Rule Database" / "Kural Veritabanı") after Reference Tools. Master-detail UI: searchable + coverage-status-filtered rule list on the left, clause drill-down on the right showing each rule's source SUT clauses (Turkish `text_tr`), section, EK annex chips, deontic modality, effective date, and Resmî Gazete amendment refs. Paginated (25/page).
- **Honesty surfaced:** coverage status chip on every rule (success/warning/danger/neutral status tokens — never gold), an `artifacts_available=false` banner, and an explicit "no clauses mapped" state.
- **Design adherence (lessons.md):** gold used only for active-row focus border; status uses separate tokens; no glassmorphism/glow/entry animation; reuses existing primitives + source chips.
- **LIMITATION:** Node toolchain unavailable in this environment, so type-check/tests/build were not executed here — verified by IDE linter + manual review only. Needs a local `tsc`/`vitest`/`build` pass before merge.

### Out of Scope
- Editing/authoring rules from the UI (read-only catalog)
- Surfacing the full raw clause corpus as a browser (only clauses matched to a rule)
- Resmi Gazete amendment-history timeline per clause (could be a later enhancement)
- Re-running the prose extractor as part of API runtime (artifacts built offline)
- Replacing the existing `/bundled-consumables` coverage-scope blobs

---

## Task: L3.1 §2.2.2.B session fractions (2026-06-11)

### Goal
Close L3.1-hemo PARTIAL gap: apply §2.2.2.A(5) session point factors per lab encounter in normative costing and compliance flags.

### Subtasks
- [x] Refactor `lab.py`: per-encounter code list → `compute_session_point_factors`
- [x] `LabOptimization.session_fraction_savings` + `total_savings` rollup
- [x] Unit tests (single visit, cross-visit, hemogram+labs combo)
- [x] Frontend: combined savings display + `session_fraction_overbilling` label
- [x] Update L3.1 doc + FIX_BACKLOG; run tests

### Review
- L3.1-hemo verdict: COMPLIANT (was PARTIAL on §2.2.2.B gap).
- `same_incision=True` default for same-visit labs (§2.2.2.A(5) 30% secondary).
- 5/5 `test_lab_session_fractions.py` pass.

### Out of Scope
- Claim-line billed amount comparison (lab path has test names only)
- `cross_specialty` auto-detect (no specialty on lab lists)
- `same_incision=False` param (default True until kesi metadata)

---

## Task: L2.4 EK-2C-1 polish (2026-06-11)

### Goal
Close L2.4 polish: synthetic reconcile, demo-scoped violations, package-line exclusion, i18n, cache.

### Subtasks
- [x] Synthetic: normalized EK-2C-1 keys + `_reconcile_ek2c1_procedure_lines` + 3 demo violations
- [x] `copay_rate_evaluable_line` — skip package-included / zero-billed from rate checks
- [x] EN/TR i18n: "copay rate" / "katılım payı oranı" (not "add-on rate" / "ilave oran")
- [x] Update `L2.4_copay_rate_ek2c1.md`
- [x] Regenerate synthetic; tests pass; rebuild cache

### Review
- Synthetic: ≤2 rate + ≤1 flag demo violations; SGK share >100% = 0.
- Package-included EK-2C-1 lines excluded via `copay_rate_evaluable_line`.
- Cache rebuilt: `6c5e8030-805a-443c-9f69-5d19576149a2`.

---

## Task: L4.4 specialty §3.3 prose — finish integration (2026-06-11)

### Goal
Close L4.4 Phase 2: synthetic claim flags, coverage scope, UI surfacing, golden tests, registry sync.

### Subtasks
- [x] `specialty_coverage_scope.py` + `MaterialPreCheck.specialty_coverage_scope`
- [x] Synthetic: L4.4 flag columns + coverage + keyword demo rows (generators/exporters/validate)
- [x] Orchestrator action counts + `claim_materials` rule_source + chat context
- [x] Frontend: `specialty_prose_violations` + scope notice (EN/TR)
- [x] Golden tests + `test_sut_coverage` + synthetic flag tests
- [x] Registry `specialty_materials_prose` → implemented; update L4.4 plan
- [x] Regenerate synthetic parquets; run tests

### Review
- 49 §3.3 rules wired end-to-end: validate_claim, precheck, synthetic flags (37 claim fields), UI table + scope notice.
- Runtime wiring: validation API + ClaimValidator/BundledConsumables scope notices; cache rebuilt (`6bff5ee5`).
- Synthetic reconcile fix: L4.4 demo rows update claim header + expected outputs.
- Patient `SENTETIK-HASTA-0001`: exact materials precheck, **5** specialty violations; **17/50** patients flagged.

### Out of Scope
- L4.4 Phase 4 catalog alignment (code-first EK-3 price lookup)
- Full §3.3 long-tail encode beyond existing 49 rules
