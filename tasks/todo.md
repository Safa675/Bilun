## Task: Patient profile per-bill redesign — Phase 6 segmented BillPicker

### Goal
Replace the claim dropdown with a segmented bill picker on `/patient/[id]` and default-select the highest-recoverable bill.

### Subtasks
- [x] Create `frontend/src/components/patient/BillPicker.tsx`
- [x] Replace `ClaimSelector` with `BillPicker` in patient page
- [x] Implement default selection (highest `recoverable_try`, tiebreak most recent)
- [x] Add EN/TR i18n keys
- [x] Verify frontend lint and build
- [x] Fix pre-existing patient-alert row-column test regression

### Verification
- `npm run lint`: no new errors (6 errors / 3 warnings pre-date this work)
- `npm run build`: succeeds
- `.venv/bin/python -m pytest -q`: `500 passed`

---

## Task: Claim-line wiring for SUT exactness

### Goal
Use the existing synthetic claim-line data consistently across SUT optimization, billing, API, and Rule Database explanations so claim-line rules become exact when invoices are available and remain honestly unavailable only when inputs are truly missing.

### Subtasks
- [x] Verify synthetic `SUTClaimDataset` loads procedure, drug, material, claim, and patient context rows end-to-end
- [x] Add regression tests proving claim-backed optimization summaries stay exact when `claim_dataset` is present
- [x] Audit API/cache response layers for false `missing_exact_inputs` degradation and fix patient-alert summary/row exactness overwrites
- [x] Implement missing drug-discount validation from `DrugClaimLine` data
- [x] Wire drug-discount output into cohort optimization summary without fabricating results when drug lines are absent
- [x] Verify billing report and cohort revenue recovery aggregation preserve exact claim-backed sections
- [x] Clarify `needs_claim_lines` vs runtime `missing_exact_inputs` by adding canonical `drug_discount_prose` Rule Registry metadata
- [x] Run focused unit/API tests and a synthetic-demo smoke check

### Results
- Existing claim-line plumbing was already healthy: synthetic demo loads 753 procedure lines, 336 drug lines, 151 material lines, and 134 claim headers; surcharge, EK-2/C-1 copay-rate, and DRG cohort summaries are exact with claim data.
- Added `src/bilun/domain/optimization/drug_discounts.py` and wired `drug_discount_validation` into `compute_optimization_summary`.
- Added canonical `drug_discount_prose` registry metadata and linked L2.7 fact-check metadata to it.
- Rule Database now reports `drug_discount_prose` as `needs_claim_lines` with 438 mapped clauses; runtime synthetic-demo summary reports exact validation over 336 drug lines with 0 violations.
- Fixed patient-alert false degradation: mixed exact/missing cohorts now produce `partial_exact`, preserve exact row outputs through DuckDB, and category filters only treat exact rows as flagged/clear.
- Added a cohort billing-flow regression proving `SUTClaimDataset` builds `PatientClaimContext` inside `compute_all_billing_reports` and propagates exact sections into `CohortRecoverySummary`.
- Verification: focused backend suite passed (`33 passed`), broader SUT backend slice passed (`73 passed`), patient-alert regression passed (`13 passed`), cohort billing-flow test passed, edited backend modules compile, and smoke summary confirmed exact drug-discount output.

### Out of Scope
Regenerating synthetic data, changing the meaning of the `needs_claim_lines` rule status, re-ingesting SUT DOCX/EK annexes, or building real Medula ingestion beyond the existing claim-loader path.

---

## Task: Localize Rule Database tab content for Turkish locale

### Goal
Make the Rule Database tab feel Turkish when the locale is TR by adding Turkish rule metadata to the backend and translating modality/category tokens in the frontend.

### Subtasks
- [x] Backend: add `description_tr` + `rule_category_tr` to `RuleRegistryEntry` and populate all 27 rules
- [x] Backend: surface new fields through `rules_catalog.py` and `schemas.py`
- [x] Backend tests: update schema/catalog tests for new fields
- [x] Frontend API types: add `description_tr` + `rule_category_tr` to `RuleCatalogEntry`
- [x] Frontend i18n: add deontic-modality keys to `messages/{en,tr}/sections.ts`
- [x] Frontend component: use locale-aware metadata + translate modality in `RuleDatabaseSection.tsx`
- [x] Run backend tests; frontend type-check pending (no Node runtime)

### Changes
- `src/bilun/domain/sut/rule_registry.py`: `RuleRegistryEntry` now has `rule_category_tr` and `description_tr`; all 27 rules populated with Turkish category labels and descriptions.
- `src/bilun/domain/sut/rules_catalog.py`: `_rule_summary()` surfaces the new TR fields.
- `src/bilun/api/schemas.py`: `RuleCatalogEntry` schema accepts the new fields.
- `frontend/src/lib/api/sut.ts`: TypeScript `RuleCatalogEntry` type updated.
- `frontend/src/messages/{en,tr}/sections.ts`: Added `sections.ruleDatabase.deontic.*` translations for `MUST_BILL`, `MAY_BILL`, `MUST_NOT_BILL`, `NO_PAY`, `NO_COPAY`, `COPAY_REQUIRED`.
- `frontend/src/components/tabs/sut/sections/RuleDatabaseSection.tsx`: Added `useLocalizedRule` hook (switches description/category to TR when locale is `tr`), `useDeonticLabel` hook (translates modality tokens), `RuleDescription` component, and displays the localized category in the detail header.

### Verification
- `tests/unit/domain/sut/test_rules_catalog.py`: added assertions that every rule exposes non-empty `description_tr` and `rule_category_tr`.
- `tests/unit/api/test_sut_rules_api.py`: added assertions that `copay_exemption_ek1a` returns the expected Turkish fields.
- Full Python suite: `478 passed in 39.88s` (was 466 before).
- Schema exactness + prose golden tests pass.
- Frontend: Node v22.16.0 / npm 10.9.2 are installed at `/home/safa/.local/node-v22.16.0-linux-x64/bin` (not on PATH). With PATH exported:
  - `npx tsc --noEmit`: 5 pre-existing errors in unrelated files (`SutBillingReportSections.tsx`, `SyntheticDemoProvenance.test.tsx`, `SUTOptimizerTab.test.tsx`). `RuleDatabaseSection.tsx` is clean.
  - `npx vitest run`: 4 pre-existing failures in unrelated test files (`SutBillingReportSections.test.tsx`, `PatientSection.test.tsx`, `page.test.tsx`). All other 110 tests pass.

### Limitations
- The pre-existing frontend TypeScript errors and test failures are not introduced by this change; they appear in patient/billing components unrelated to the Rule Database tab.

---

---

## Task: Evaluate Rule Database tab — Turkish i18n gaps and design divergence

### Goal
Explain why the Rule Database tab appears mostly English under Turkish locale and why its design differs from the other tabs, with actionable recommendations.

### Subtasks
- [x] Inspect Rule Database frontend component + i18n files
- [x] Trace backend data sources (rule registry, clause corpus, fact-check audit)
- [x] Compare layout/interaction model with other home tabs / Reference Tools sub-sections
- [x] Identify every untranslated or English-only data surface
- [x] Document recommendations

### Findings

#### 1. It looks English in Turkish settings because the *content* is English data, not translated UI text
The UI chrome **is** fully translated in `frontend/src/messages/tr/sections.ts` (title, subtitle, search placeholder, status chips, pagination, error messages, etc.) and `frontend/src/messages/tr/constants.ts` (tab label "Kural Veritabanı").

What remains English is the **rule catalog data itself**, which comes from the backend and has no localization layer:

| Field | Example | Source |
|-------|---------|--------|
| `rule_id` | `copay_exemption_ek1a`, `material_bundling_prose` | `src/bilun/domain/sut/rule_registry.py:51` |
| `rule_category` | `copay_exemption`, `bundling`, `material_exclusion` | `rule_registry.py:52` |
| `description` | `"EK-1A chronic disease copay exemptions"` | `rule_registry.py:62` |
| `keywords` | `"katılım payı alınmaz"` (TR) mixed with English tokens | `rule_registry.py:61` |
| `domain_modules` | `src/bilun/domain/optimization/copay_exemptions.py` | `rule_registry.py:55` |
| `fact_check_units` | `P0.1`, `L1.4` | `src/bilun/domain/sut/fact_check_audit.py:53` |
| `fact_check_note` | `"IVF §1.8.4 rates fixed 2026-06-02"` | `fact_check_audit.py:72` |
| `clause.section_title` | mixed / English depending on DOCX extraction | `src/bilun/domain/sut/rules_catalog.py:39` |
| `clause.deontic_modality` | `MUST_BILL`, `MAY_BILL`, `COPAY_REQUIRED` | rendered raw at `RuleDatabaseSection.tsx:511` |
| `clause.text_tr` | Turkish prose — the only localized content | `rules_catalog.py:43` |

So the tab *chrome* is Turkish, but the rule descriptions, categories, module paths, audit notes, and clause modality tokens are stored and served in English.

#### 2. It is designed differently because it was intentionally built as a master-detail catalog, not a table lookup
The previous implementation plan (`tasks/todo.md` 2026-06-13) records the confirmed design decisions:

- **Layout = catalog-as-index** (rule list → drill into source clauses).
- Promoted to a **new top-level tab** (`rule-database`) rather than a Reference Tools sub-section.
- Sources = actual extracted SUT clause text (`text_tr`), not just section/annex labels.
- Full coverage-honesty UI with status chips and `artifacts_available` banner.

Concrete differences from other tabs:

| Aspect | Rule Database | Other Reference Tools (e.g. Lab Prices, Checkup) |
|--------|---------------|--------------------------------------------------|
| Layout | 2-column master-detail (`340px + 1fr`) | single `Surface` + `DataTable` |
| Navigation | searchable + status-filtered selectable list | none (static table) |
| Detail | paginated clause cards with provenance | none |
| Interaction | click rule → drill into clauses | none |
| Primitives | custom list items, `Chip`, `Surface`, pagination buttons | `DataTable` |

#### 3. Why it was made a top-level tab instead of living under Reference Tools
The prior plan explicitly chose a top-level tab because the Rule Database is not a calculator/validator like the other Reference Tools; it is a **source-of-truth catalog** of every extracted SUT rule with coverage status and clause provenance. That is a different mental model from "Billing & Gazette Tools" (`sections.tools.dividerLabel`).

### Recommendations
1. **Add localized rule metadata** — either store `description_tr` / `category_tr` in `rule_registry.py` or add a display-name mapping in the frontend. This is the biggest reason the tab feels English.
2. **Translate `deontic_modality` tokens** in the UI (`MUST_BILL` → "Faturalandırılmak zorunda", `MAY_BILL` → "Faturalandırılabilir", etc.) via a key map + i18n strings.
3. **Consider mapping `rule_category` slugs** to Turkish labels in `sections.ts` (e.g. `copay_exemption` → "Katılım Payı Muafiyeti").
4. **Keep the top-level tab** — the decision is documented and defensible; moving it under Reference Tools would collapse a catalog into a toolbox.
5. **Keep the master-detail layout** — it matches the task requirement to "drill into source clauses"; a single table would not work for clause text.

### Out of Scope for this evaluation
- Actually implementing the localization fixes above.
- Changing the tab placement or layout.

---

## Task: Add invoice/claim selector to patient billing page

### Goal
Let users choose a specific invoice/claim on `/patient/[id]` and view its raw claim-line details.

### Plan
See `plans/frontend/patient-claim-invoice-selector-plan.md`.

### Subtasks
- [x] Phase 1: backend API to list patient claims
- [x] Phase 2: backend API to get single claim detail
- [x] Phase 3: frontend API client + types
- [x] Phase 4: ClaimSelector component
- [x] Phase 5: ClaimDetailPanel component
- [x] Phase 6: wire selector + panel into patient page
- [x] Phase 7: i18n EN+TR
- [x] Phase 8: verify tests + type-check

### Verification
- Python: `484 passed`
- Frontend lint: no new errors introduced (remaining 6 errors / 3 warnings pre-date this task)
- Frontend build: `next build` succeeds

### Also fixed while verifying
- `RuleDatabaseSection.tsx`: moved `useLocalizedRule` before early returns to fix React hooks-order runtime error (`RuleDetailPanel`).

### Out of Scope
- Claim-scoped billing report (re-running billing algorithms per claim)
- Editing/creating claims from UI

---

## Task: Fix all Python test failures (23 failed + 22 errors)

### Goal
Restore a green Python test suite: `0 failed, 0 errors` when running `.venv/bin/python -m pytest`.

### Plan
See `plans/testing/fix-all-test-failures-plan.md`.

### Subtasks
- [x] Phase 1: fix stale `src.api.*` imports + missing `api_client` fixture
- [x] Phase 2: make billing orchestrator defensive against partial material stubs
- [x] Phase 3: fix claims config messages + loader mode handling + fixture counts
- [x] Phase 4: fix `validate_claim` tests against prose side effects
- [x] Phase 5: fix billing strategy recommendation kind mismatch
- [x] Phase 6: fix patient recovery summary payload mapping
- [x] Phase 7: resolve `C001637` material bundling golden mismatch
- [x] Phase 8: full-suite verification + task close-out

### Verification
```
.venv/bin/python -m pytest -q
466 passed in 34.14s
```

### Out of Scope
- Frontend type-check/test/build failures
- CI workflow addition (follow-up after suite is green)

### Notes
- Supersedes the narrower `plans/testing/fix-pre-existing-test-failures-plan.md` (4 failures only).
- Phase 7 decision: chose Option A (update golden expectation to `3.1.2.(2).not_in_ek3c`).

---

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
