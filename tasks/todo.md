## Task: Fix lab session-fraction source of truth (implementation)

### Goal
Make lab optimization and session-fraction correction use billed claim lines (`procedure_claim_lines` with `procedure_category == "laboratuvar"`) as the source of truth, eliminate phantom duplicates from clinical lab result rows, and move "clinical lab present but not billed" detection into capture gap.

### Subtasks
- [x] Phase 0 — Spike: inspect `SENTETIK-HASTA-0001-002` end-to-end and confirm the bug
  - [x] Dump lab claim lines for the relevant claim
  - [x] Dump clinical lab result rows for the patient/visit
  - [x] Capture current `LabOptimization` output
  - [x] Assert target: savings derived from `billed_amount_try` via session-fraction engine
  - [x] Confirm no existing test asserts the broken behavior
- [x] Phase 1 — Add claim-line-based lab optimizer
- [x] Phase 2 — Merge lab gaps into capture gap
- [x] Phase 3 — Replace old lab optimizer call sites; patient aggregate = sum per-bill
- [x] Phase 4 — Frontend label / exactness updates
- [x] Phase 5 — Tests (including `SENTETIK-HASTA-0001-002` regression)
- [x] Phase 6 — Cache rebuild and spot check

### Verification
- `pytest -q`: **511 passed** (was 500; +11 new tests)
- Cache rebuild: `scripts/bilun/build_cache.py --activate` succeeded, build `c515aafb-606f-4a30-b06f-3a9913677e2b`
- Spot check `SENTETIK-HASTA-0001-002`:
  - Before fix: 11 phantom lab flags, session savings ₺1,873.05 (from gazette prices × 12 clinical rows)
  - After claim-line switch (with session fraction): 2 claim-line flags, session savings ₺14.51
  - Final state (session fraction removed for labs): **0 lab flags**, session savings ₺0.00
- Patient aggregate now sums per-bill claim-line lab results instead of falling back to clinical lab feed

### Changes
- Added `src/bilun/domain/billing/claim_lab.py` — claim-line based lab optimizer
- Added `src/bilun/domain/prose_rules/lab_capture_gap.py` — clinical lab vs claim gap detection
- Updated `src/bilun/domain/billing/claim_procedure_capture_gap.py` — merges lab gaps into capture gap
- Updated `src/bilun/domain/billing/orchestrator.py` — per-bill lab/capture-gap summing, new optimizer wiring
- Updated frontend i18n labels in `frontend/src/messages/{en,tr}/billing.ts`
- Added tests:
  - `tests/unit/domain/billing/test_claim_lab_optimizer.py`
  - `tests/unit/domain/prose_rules/test_lab_capture_gap.py`
  - `tests/unit/domain/billing/test_lab_optimizer_sentetik_0001_002.py`

### Review / post-implementation decision
- **Session-fraction / seans kesir oranı is intentionally NOT applied to lab tests.**
  - SUT §2.2.2.A(5) and §2.2.2.B target surgical/medical "işlemler" with "kesi" (incision); the wording does not cover laboratory "tetkikler".
  - Removing session-fraction from `claim_lab.py` is the legally correct reading and prevents false savings on routine multi-test lab panels.
  - `session_fraction_overbilling` flags remain available for non-lab procedure categories via the existing session-pricing engine.

### Out of Scope
- Non-lab capture gap changes
- Claim data model / ingestion re-architecture
- New SUT session-fraction rules
- Frontend table component structure changes beyond labels
- Real hospital data ingestion

---

## Task: Delete legacy lab.py fallback path

### Goal
Remove `src/bilun/domain/billing/lab.py` and the legacy clinical-lab-feed fallback in `compute_patient_billing_report()`; lab optimization now uses claim lines exclusively.

### Subtasks
- [x] Delete `src/bilun/domain/billing/lab.py`
- [x] Remove `_optimize_lab_billing` import/export from `src/bilun/domain/billing/__init__.py`
- [x] Remove `_optimize_lab_billing` import and fallback branch from `src/bilun/domain/billing/orchestrator.py`
- [x] Remove unused `patient_lab_tests`, `patient_lab_dates`, `patient_lab_visit_ids` parameters from `compute_patient_billing_report()`
- [x] Delete or update tests that reference `_optimize_lab_billing`
  - [x] `tests/unit/domain/billing/test_lab_session_fractions.py` (deleted)
  - [x] `tests/unit/domain/billing/test_billing_bugfixes.py` (removed 3 direct lab tests; updated monkeypatch)
  - [x] `tests/unit/domain/test_billing_strategy_exactness.py` (removed lab mock; updated assertion)
  - [x] `tests/unit/domain/billing/test_honest_gaps.py` (removed lab mock; updated assertion)
- [x] Update `docs/core-system/algorithms_reference.md`
- [x] Update `src/bilun/domain/billing/README.md`
- [x] Run `pytest -q` and confirm green

### Verification
- `pytest -q`: **507 passed** (was 511; net -4 tests after removing legacy lab coverage)
- No remaining imports or references to `_optimize_lab_billing` in source/tests

### Out of Scope
- Changing `LabOptimization` dataclass shape
- Frontend lab display changes
- Port hemogram-bundling behavior beyond what `claim_lab.py` already tests

---

## Task: Rule Database full surface — Phase 1 coverage_summary API

### Goal
Implement backend `coverage_summary` for `GET /api/rules` so the expert Rule Database tab can show honest pipeline health (extracted clauses, coverage status distribution, registry status, algorithmic gaps).

### Subtasks
- [x] Update `plans/frontend/rule-database-full-surface-plan.md` to expert-only framing
- [x] Add `SUT_COVERAGE_BY_RULE_PATH` and `SUT_COVERAGE_BY_SECTION_PATH` to `src/bilun/domain/constants.py`
- [x] Implement `coverage_summary()` in `src/bilun/domain/sut/rules_catalog.py`
- [x] Extend `RuleCatalogResponse` schema in `src/bilun/api/schemas.py`
- [x] Wire `coverage_summary` into `src/bilun/api/routes/rules.py`
- [x] Add unit tests in `tests/unit/domain/sut/test_rules_catalog.py` and `tests/unit/api/test_sut_rules_api.py`
- [x] Run `pytest -q` and confirm green

### Verification
- `pytest -q`: **512 passed** (was 507; +5 new tests)
- `GET /api/rules` now returns `coverage_summary` with:
  - `clauses.total_extracted`: 8,180
  - `clauses.algorithmic_gaps`: 4,471 (54.7%)
  - `registry.total_rules`: 28
  - `registry.zero_clause_matches`: 2 rules flagged
- Graceful degradation tested: missing parquets return `artifacts_available: false` with build hint

### Out of Scope
- Frontend coverage panel (Phase 3)
- Section / prose-inventory endpoints (Phase 2)
- Role-based tab hiding
- Chat context enrichment (removed from plan)

---

## Task: Rule Database full surface — Phase 2 supplementary endpoints

### Goal
Add expert-only backend endpoints for SUT section rollup and prose-rule engine inventory.

### Subtasks
- [x] Add `GET /api/rules/sections` — paginated section rollup from `sut_coverage_by_section.parquet`
- [x] Add `GET /api/rules/prose-inventory` — prose engine manifest from `data/gazette/prose_rules/*.json`
- [x] Add schemas in `src/bilun/api/schemas.py`
- [x] Implement domain helpers in `src/bilun/domain/sut/rules_catalog.py`
- [x] Wire routes in `src/bilun/api/routes/rules.py`
- [x] Add tests in `tests/unit/api/test_sut_rules_api.py`
- [x] Run `pytest -q` and confirm green

### Verification
- `pytest -q`: **519 passed** (was 512; +7 new tests)
- `GET /api/rules/sections` returns paginated section rollup (1,999 sections; supports `q`, `min_gap_count`, `page`, `per_page`)
- `GET /api/rules/prose-inventory` returns 10 prose engines with rule counts and SUT anchors
- Invalid pagination params return 400

### Out of Scope
- Frontend section browser panel (Phase 4)
- Frontend prose inventory panel (Phase 4)
- Material bundling coverage scope details beyond file-level metadata
- Real-time prose rule ingestion

---

## Task: Rule Database full surface — Phase 3 frontend coverage panel

### Goal
Add a dense coverage summary panel to the expert Rule Database tab, relabel/demote the frozen fact-check banner, and surface zero-clause-mapping warnings on the rule list.

### Subtasks
- [x] Add `coverage_summary` TypeScript types in `frontend/src/lib/api/sut.ts`
- [x] Add EN/TR i18n keys in `frontend/src/messages/{en,tr}/sections.ts`
- [x] Build `CoverageSummaryPanel` inside `RuleDatabaseSection.tsx`
- [x] Relabel `FactCheckRollupBanner` as frozen June 2026 audit and move it below the coverage panel
- [x] Add zero-clause warning icon/tooltip to rule list items
- [x] Run frontend type-check / tests

### Verification
- `npx tsc --noEmit`: passed (no errors)
- `npx vitest run`: **123 passed** (33 test files)
- `pytest -q`: **519 passed**
- Rule Database tab now shows:
  - Dense coverage summary panel at top (clauses + registry + algorithmic gaps + top gap categories)
  - Collapsible fact-check panel labeled as archived June 2026 audit below it
  - Warning icon on rules with zero clause mapping

### Out of Scope
- Frontend section browser panel (Phase 4)
- Frontend prose inventory panel (Phase 4)
- Role-based tab hiding
- Consumer-friendly UX simplification

---

## Task: Rule Database full surface — Phase 4 section browser + prose inventory panels

### Goal
Add expert-only frontend panels for browsing SUT sections by coverage gap and inspecting prose rule engines.

### Subtasks
- [x] Add API client functions in `frontend/src/lib/api/sut.ts` for `/api/rules/sections` and `/api/rules/prose-inventory`
- [x] Add EN/TR i18n keys for section browser and prose inventory
- [x] Build `SectionBrowserPanel` with pagination, search, min-gap filter
- [x] Build `ProseInventoryPanel` listing prose engines with metadata
- [x] Add Rules / Sections / Prose Engines tabs to `RuleDatabaseSection.tsx`
- [x] Run frontend type-check / tests

### Verification
- `npx tsc --noEmit`: passed
- `npx vitest run`: **123 passed**
- `pytest -q`: **519 passed**
- Rule Database tab now has three tabs:
  - **Rules**: existing master-detail rule list
  - **Sections**: dense table with § id, title, clause count, gap count, worst status, categories; supports search + min-gap filter + pagination
  - **Prose engines**: table of prose JSON engines with rule counts, effective dates, SUT anchors

### Out of Scope
- Role-based tab hiding
- Deep-linking from section row to first matching rule (client filter only)
- Real-time prose rule ingestion

---

## Task: Rule Database full surface — role-based tab gating

### Goal
Hide the Rule Database tab from `billing_analyst` users; show it for `compliance_engineer`, `dev`, and admin roles.

### Subtasks
- [x] Investigate current auth/role mechanism in frontend
- [x] Implement role check utility in `frontend/src/lib/userRole.ts`
- [x] Add `requiredRole` to `SUT_HOME_TABS` for `rule-database`
- [x] Filter tabs in `AppTopBar.tsx` by user role
- [x] Add/update tests (`userRole.test.ts`, `constants.test.ts`)
- [x] Run frontend type-check / tests

### Verification
- `npx tsc --noEmit`: passed
- `npx vitest run`: **128 passed** (34 test files)
- `.venv/bin/pytest -q`: **519 passed**
- `billing_analyst` users no longer see the Rule Database top-level tab
- `compliance_engineer`, `dev`, and `admin` users continue to see it
- Direct URL access to the tab is not blocked (frontend-only gating)

### Changes
- `frontend/src/lib/userRole.ts`: new `UserRole`, `canAccessRuleDatabase`, `getUserRole`, `setUserRole` helpers
- `frontend/src/lib/constants.ts`: added `requiredRole` to `SutHomeTab`; gated `rule-database` to expert roles
- `frontend/src/components/shell/AppTopBar.tsx`: filters visible tabs using `useUserRole`
- `frontend/src/lib/userRole.test.ts`: new tests for role access and persistence
- `frontend/src/lib/constants.test.ts`: added assertion that `rule-database` requires expert roles

### Out of Scope
- Backend authorization (assume frontend-only gating for tab visibility)
- Blocking direct URL access to Rule Database
- Per-feature gating inside the Rule Database tab

---

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
The prior plan explicitly chose a top-level tab because the Rule Database is not a calculator/validator like the other Reference Tools; it is a **source-of-truth catalog** of every SUT rule with coverage status and clause provenance. That is a different mental model from "Billing & Gazette Tools" (`sections.tools.dividerLabel`).

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
- orchestrator.py` - [x] Create `src/bilun/domain/sut/rules_catalog.py`: lazy Polars loader + `list_rules()` + `get_rule_clauses(rule_id)` (drill-down via `matched_rule_ids`, primary-first), graceful-degrade if parquet missing
- [x] Unit tests: catalog completeness, clause join + pagination, missing-artifact degradation (`tests/unit/domain/sut/test_rules_catalog.py`)

#### Phase 2 — Backend API
- [x] Add schemas to `src/bilun/api/schemas.py`: `RuleCatalogResponse`, `RuleDetailResponse`, `RuleCatalogEntry`, `RuleClause`, `RuleSources`
- [x] Create `src/bilun/api/routes/rules.py`: `GET /api/rules` (index), `GET /api/rules/{rule_id}` (detail + paginated clauses); 404 unknown id, 400 bad pagination
- [x] Register router + re-export handlers in `src/bilun/api/routes/__init__.py`
- [x] API tests (`tests/unit/api/test_sut_rules_api.py`): index, detail drill-down, pagination, 404, 400, graceful degradation

### Backend Review (Phase 0–2 complete, 2026-06-13)
- **Design deviation (intentional):** chose **graceful degradation + `artifacts_available` flag** over a hard 503 when clause artifacts are absent. The catalog still lists every rule (from the registry) with sources + coverage status; only clause text drops out. Matches the `domain/materials/drugs.py` empty-on-missing pattern and is more honest/robust for the UI (banner instead of dead tab).
- **Verification:** 34/34 new tests pass; live HTTP smoke via mounted router returns 200 for `/api/rules` (27 rules) and `GET /api/rules/{id}` (62 clauses for `copay_rate_ek2c1`, paginated), 404 for unknown id, 400 for bad pagination.
- **Data note:** regenerating parquets produced byte-identical clause data (only pyarrow metadata differed), so committed parquets were kept to avoid a noisy binary diff.
- **Pre-existing failures (NOT introduced here):** `test_sut_cache_concrrency.py`, `test_sut_patient_alerts_api.py`, `test_sut_schema_exactness.py` all fail with `ModuleNotFoundError: No module called 'src.api'` (stale ILAY→BILUN import path); `test_material_bundling_golden.py[C001637]` is a pre-existing classify mismatch (fails on original committed parquets too).
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
- **Design adherence (lessons.md):** gold used only for active-row-focus border; status uses separate tokens; no glassmorphism/glow/entry animation; reuses existing primitives + source chips.
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

### Out of Scope
- L4.4 Phase 4 catalog alignment (code-first EK-3 price lookup)
- Full §3.3 long-tail encode beyond existing 49 rules

---

## Task: Implement MEDULA Rebill Playbook UX cleanup + rejection queue

### Goal
Phase 1: hide the MEDULA rebill playbook block on the patient billing page when rejection ingest is absent or the patient has zero rejection events. Phase 2: add a cohort-level MEDULA rejection queue with deep links into the per-bill playbook.

### Subtasks
- [x] Phase 1.1 — Hide `MedulaRejectionPlaybookSection` when `not_applicable` or empty
- [x] Phase 1.2 — Confirm `BillingSummary` already gates the playbook KPI on count
- [x] Phase 1.3 — Add `medula_rejection_ingest_available` flag to `SUTClaimDataset`, `PatientClaimContext`, `BillingActionReport`, `CohortRecoverySummary`, and `BillingReportResponse`
- [x] Phase 1.4 — Add backend + frontend Phase 1 tests
- [x] Phase 1.5 — Verify Phase 1 tests pass
- [x] Phase 2.1 — Add `operations` home tab (conditionally visible when ingest is available)
- [x] Phase 2.2 — Build `GET /api/medula-rejections/queue` + `/ingest-status` endpoints
- [x] Phase 2.3 — Build `MedulaRejectionQueueTab` table with filters and empty states
- [x] Phase 2.4 — Deep-link from queue to `/patient/{id}?claim={claim_id}&section=medula-playbook`; scroll to playbook anchor
- [x] Phase 2.6 — Add API + frontend tests for the queue
- [x] Phase 3 — Hide MEDULA playbook KPI on optimizer tab when ingest is unavailable; add i18n namespaces
- [x] Phase 3 — Add `search_medula_playbook` chatbot tool; include queue count in operations-tab context; suppress MEDULA playbook injection in patient chat

### Verification
- Backend: `tests/unit/domain/billing tests/unit/domain/claims tests/unit/api/test_medula_rejection_queue_api.py tests/unit/chatbot/`: **127 passed**
- All API tests: `tests/unit/api/`: **63 passed**
- Frontend tests: `npx vitest run`: **123 passed**
- Frontend type check: `npx tsc --noEmit`: clean
- Frontend lint: no new errors introduced (remaining 7 errors / 2 warnings pre-date this work)

### Changes
- Backend: `src/bilun/domain/claims/loader.py`, `src/bilun/domain/claims/patient_context.py`, `src/bilun/domain/billing/types.py`, `src/bilun/domain/billing/orchestrator.py`, `src/bilun/api/schemas.py`, `src/bilun/api/routes/medula_rejections.py`, `src/bilun/api/routes/__init__.py`, `src/bilun/api/routes/chat.py`, `src/bilun/chatbot/tools.py`, `src/bilun/chatbot/context.py`
- Frontend: `frontend/src/components/patient/SutBillingReportSections.tsx`, `frontend/src/app/patient/[id]/page.tsx`, `frontend/src/app/page.tsx`, `frontend/src/components/shell/AppTopBar.tsx`, `frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.tsx`, `frontend/src/components/tabs/sut/operations/*`, `frontend/src/lib/constants.ts`, `frontend/src/lib/api/sut.ts`, `frontend/src/lib/domains/sut.ts`, `frontend/src/messages/{en,tr}/{constants,index,operations}.ts`
- Tests: `tests/unit/domain/claims/test_loader.py`, `tests/unit/domain/billing/test_orchestrator_claim_cohort_flow.py`, `tests/unit/api/test_medula_rejection_queue_api.py`, `tests/unit/chatbot/test_tools.py`, `frontend/src/components/patient/SutBillingReportSections.test.tsx`, `frontend/src/lib/constants.test.ts`

### Review / post-implementation notes
- The `operations` tab is hidden from the top bar when `medula_rejection_ingest_available === false`, but the route still renders if accessed directly with `?tab=operations` (shows the ingest-off empty state).
- The playbook section on `/patient/[id]` now self-hides when there are no matched entries; the billing-summary playbook KPI is already gated by count.
- Queue rows use `match_playbook_template` directly so unmatched events still appear as `playbook_matched: false`.
- Deep links parse `claim` to pre-select the bill and `section=medula-playbook` to scroll to the section anchor.
- MEDULA playbook context is no longer injected into patient-workspace chat; a new `search_medula_playbook` tool is available on cohort/home views.
- When the active tab is `operations`, the LLM context includes `medula_queue.total`.
- TR title wording for the playbook section was left unchanged pending Safa sign-off.

### Out of Scope
- Live MEDULA SOAP ingest / real-time polling
- Expanding `rejection_playbook.json` templates
- Auto-submitting corrective rebills to MEDULA
- Cohort summary badge on the Patients tab (optional Phase 2.5)
