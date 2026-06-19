> **Note:** All completed tasks through 2026-06-16 are archived in `tasks/archive/todo-archive-2026-06-16.md`. This file contains only active work.

## Task: Demo Vignette feature'ını commit'le (dirty tree temizliği)

### Goal
Sohbet öncesi dirty kalan "SGK optional override showcase" işini commit'le. Önce 2 kırık test'i yeni fixture satır sayılarına ve senaryoya uydur. Co-author yok, push yok.

### Subtasks
- [x] Planı yaz, gerçek sayıları/senaryoyu doğrula
- [ ] test_loader.py:30 güncelle — procedure 520→501, material 115→110, drug 245→218, expected 433→394
- [ ] test_drg_claim_exact.py:51-66 — 0002-007 artık endocrinology_yatis (paketli); invariant test'ini SENTETIK-HASTA-0005/F-SENTETIK-HASTA-0005-019'a taşı (paket yok → missing)
- [ ] demo_vignette_lookup'un production'da no-op olduğunu doğrula (JSON yoksa None)
- [ ] .~lock çöp dosyasını sil
- [ ] pytest tam yeşil doğrula
- [ ] Tek feature commit: vignette dosyaları + claim_strategy + veri + test + docs

### Out of Scope
- Backend audit (sonraki)
- claim_strategy.py'deki "demo_vignette_hypothesis" mantığını değiştirme (feature'ın parçası)

---

## Task: Scripts Bug Fix — Dalga A-D (price_history, subprocess, atomicity, paths)

### Goal
`plans/frontend/scripts-bug-audit.md` raporundaki scripts bug'larını fixle. C1 (EK-2B kolon) en kritik. Co-author yok, push yok.

### Subtasks — Dalga A (pipeline bütünlüğü)
- [x] Planı yaz, dosyaları oku/doğrula
- [ ] C1: extract_ek2b output kolonu `package_code` → `code` (price_history.py:83,93,96,168)
- [ ] H2-kritik: price_history.py:145 broad except'e logging ekle (prose_drg_locked False olunca uyar)

### Subtasks — Dalga B (operasyonel)
- [ ] H1: ek4d_copay_exempt.py:80 LibreOffice subprocess'a timeout=300 ekle
- [ ] H1: generate_sut_synthetic_data_v2.py:80,84 validator/assert subprocess'a timeout=600 ekle
- [ ] H3: convert_xlsx_to_parquet.py:348-356 manifest write'a temp+os.replace atomic pattern

### Subtasks — Dalga C (path/leakage)
- [ ] M1: rebuild_baseline_metrics.py + export_material_bundling_clauses.py Path('data/...') → Path(__file__) resolve
- [ ] M2: validate_sut_synthetic_data.py:88 pd.ExcelFile → with context manager

### Subtasks — Dalga D (drift/cosmetic)
- [ ] M4: raw_data/generate_readmes.py:12 TODAY → date.today().isoformat()
- [ ] Diğer broad except'ler (convert_xlsx, build_curated, build_clause_embeddings) — değerlendir, log ekle
- [ ] L1 (nested ternary), L2 (banker's rounding) — değerlendir

### Doğrula + commit (dalga dalga)
- [ ] pytest yeşil, scripts import'ları sağlam

### Out of Scope
- Backend `src/bilun/` audit
- merge_drug_indication_phase1.py supersession kararı

---

## Task: Frontend Bug Fix — Dalga 3 (chat panel race + null guards)

### Goal
H2 (auto-brief debounce/locale double-fire), H5 (auto-brief + follow-up stream race), M4 (OriginalBillView null guard) düzelt. Co-author yok.

### Subtasks
- [x] Planı yaz, SutInlineAIPanel + OriginalBillView doğrula
- [ ] H2: locale effect'inin `force:true` ateşlemeden önce pending debounce'u temizle
- [ ] H5: auto-brief stream ederken textarea `disabled` yap (isAutoLoading || isResponding)
- [ ] M4: OriginalBillView episode/claim_type/icd10 null guard (filter Boolean join)
- [ ] Doğrula + commit

### Out of Scope
- H4 (health status flash) — Dalga 4
- M1, M2, M3, M6, L1-L5 — Dalga 4

---

## Task: Frontend Bug Fix — Dalga 4 (UX jank + i18n + cosmetic)

### Goal
Kalan MEDIUM/LOW bug'lar: M1 (chat message key), M2 (BillPicker null date), M3 (variance guard), M6 (AppTopBar poll), H4 (health flash), L1 (hardcoded strings).

### Subtasks
- [ ] M1: chat message key → stabil id (role + index yerine monoton counter/ref)
- [ ] M2: BillPicker defaultSelectedClaimId + sortedClaims null-safe date sort
- [ ] M3: OriginalBillView variance için guard (negatif/NaN)
- [ ] M6: AppTopBar ingest status'e interval + AbortController
- [ ] H4: app/page.tsx health effect `setHealthStatus(null)`'ı kaldır
- [ ] L1: "Thinking" hardcoded → t() key (chat.ts'ye ekle, en+tr)
- [ ] Doğrula + commit

---

## Task: Frontend Bug Fix — Dalga 2 (patient page fetch/race + locale churn)

### Goal
Tek kök nedeni (`t` callback dep'lerinde) ortadan kaldırarak 4 bug'ı birden çöz: C2 (locale switch selectedClaimId sıfırlar), H1 (workspace loading reset eksik), H3/M7 (`t`-dep churn). Ayrıca C1 (scoped report loading guard) ve C3 (useParams memo) düzelt. Co-author yok.

### Subtasks
- [x] Planı yaz, page.tsx + RuleDatabaseSection + useTranslations'i doğrula
- [ ] `tRef` pattern: her render'da `tRef.current = t`, callback'ler `tRef.current` okusun
- [ ] 4 callback'in dep array'inden `t`'yi çıkar (loadWorkspace:185, loadClaims:235, loadClaimDetail:269, loadScopedReports:345)
- [ ] C1: scoped report effect'inden `loading` guard'ını kaldır (349)
- [ ] C3: `useParams` useMemo'yu kaldır, direkt hesapla
- [ ] M7: RuleDatabaseSection detail effect'inden `t`'yi çıkar (1007) — tRef pattern
- [ ] Doğrula: tsc, vitest, build
- [ ] Commit (push yok)

### Out of Scope
- H2, H5 (chat panel double-fire) — Dalga 3
- M1-M6, L1-L5 — Dalga 4
- Registry drift (3a), stale rakam (3b)

---

## Task: Frontend Dead-Code & Stale Cleanup — Dalga 1

### Goal
Frontend audit raporundaki (`plans/frontend/frontend-deadcode-bug-audit.md`) Dalga 1 kalemlerini sil: orphaned/superseded dosyalar, ölü CSS sınıfları, kullanılmayan npm dependency'ler, ölü barrel export'lar. Bug'ler Dalga 2'de. Co-author yok.

### Subtasks
- [x] Planı yaz, dead dosyaları grep ile doğrula
- [ ] 5 ölü dosyayı sil: `components/tabs/SUTAnalytics.tsx`, `components/patient/ClaimSelector.tsx`, `components/patient/ClaimDetailPanel.tsx`, `components/tabs/SUTOptimizer.tsx`, `components/home/SutWorkspaceLanding.tsx`
- [ ] `components/home/SutWorkspaceLanding.test.tsx`'i sil (S3 testi)
- [ ] `app/page.tsx`'ten `SutWorkspaceHeader` import+2 usage'ı kaldır (`:9,130,189`)
- [ ] `components/shell/SutWorkspaceHeader.tsx`'i sil (artık unimported)
- [ ] `legacy.css`'ten 4 ölü kuralı sil: `.sut-filter-control` (`:200-205`), `.loading-state,` grubu (`:253`), `.loading-spinner` + `@keyframes spin` (`:271-282`), `.app-main` (`:35-42`)
- [ ] `package.json`'dan 5 ölü dependency çıkar: `@radix-ui/react-collapsible`, `@radix-ui/react-select`, `@radix-ui/react-slot`, `@tanstack/react-virtual`, `class-variance-authority`
- [ ] `npm install` (lockfile güncelle)
- [ ] Ölü export'ları kaldır: `getNestedMessage` (`lib/i18n/index.ts:3` + `translate.ts`), `Messages` type (`lib/i18n/index.ts:5`), `useClearSutChatSession` (`stores/uiStateContext.tsx:56`)
- [ ] Doğrula: `npx tsc --noEmit`, `npx vitest run`, `npm run build` hepsi yeşil
- [ ] Sadece kendi dosyalarımı stage'le + commit (push yok)

### Out of Scope
- Bug fix'ler (C1,C2,H3 vs.) — Dalga 2
- `components/primitives/index.ts` type export'ları (14 adet) — ayrı değerlendirme, risk
- Backend audit

---

## Task: Exact billing only — Phase A: policy & wiring (block legacy paths)

### Goal
Make `SUTClaimDataset` required for all billing surfaces in demo and production modes, remove every `claim_context is None` fallback that calls estimate-based helpers, and delete or hard-fail the legacy `billing/strategy.py` stub.

### Subtasks
- [x] Add `SUT_REQUIRE_CLAIM_LINES: bool = True` default in `src/bilun/domain/constants.py` (or appropriate config module) and read it in the billing orchestrator.
- [x] Audit `src/bilun/domain/billing/orchestrator.py` for every `if claim_context is not None` / `else` branch.
  - [x] Remove `else` branches that call `_precheck_materials`, `_recommend_billing_strategy`, or `_optimize_copay`.
  - [x] When `claim_context` is missing and `SUT_REQUIRE_CLAIM_LINES` is true, return a report whose relevant blocks have `pricing_status = "missing_exact_inputs"` / `exactness = "missing"` and zero fabricated ₺ amounts.
  - [x] Keep the report shape intact so frontend tables do not crash.
- [x] Update `src/bilun/cache/build_expensive.py` and `src/bilun/cache/context.py` (or `sut_context.py`) so every expensive compute path attaches `SUTClaimDataset` before calling billing/analytics functions.
- [x] Audit `src/bilun/domain/billing/__init__.py` exports: remove `_recommend_billing_strategy` and `_optimize_copay` legacy re-exports if they are no longer used.
- [x] Delete `src/bilun/domain/billing/strategy.py` or replace its body with a function that raises `NotImplementedError("Legacy ICD-chapter strategy estimator removed; use recommend_billing_strategy_from_claims")`.
- [x] Add unit tests:
  - [x] `compute_patient_billing_report(..., claim_context=None)` with `SUT_REQUIRE_CLAIM_LINES=true` returns `missing_exact_inputs` blocks and no heuristic savings.
  - [x] `compute_patient_billing_report(..., claim_context=...)` continues to return exact claim-backed blocks.
  - [x] Cache build path raises or attaches claims when claim dataset is absent (depending on mode).
- [x] Run `.venv/bin/python -m pytest -q` and confirm green.
- [x] Run frontend checks: `npx tsc --noEmit`, `npx vitest run`, `npm run build`.

### Verification
- [x] `.venv/bin/python -m pytest -q`: **529 passed** (no regressions)
- [x] `npx tsc --noEmit`: passed
- [x] `npx vitest run`: **132 passed**
- [x] `npm run build`: succeeded
- [x] Grep shows no product-path calls to `_recommend_billing_strategy`, `_optimize_copay`, or `_precheck_materials` outside tests.

### Review (2026-06-16)
- Fixed `_set_missing_inputs_report` NameError by importing all block-level unavailable/required constants from `types.py`.
- Report- and cohort-level exactness now propagate `missing_exact_inputs` when every block/report lacks claim lines (was incorrectly `partial_exact`).
- Rewrote stale tests that imported deleted `billing.strategy` module; added cache-path test for absent `sut_claim_dataset`.

### Out of Scope
- ~~Removing the actual `_optimize_copay` / `_precheck_materials` source files yet~~ — **done 2026-06-16** (`copay.py` deleted; `materials.py` trimmed to EK-3C loaders only).
- Updating material-validation API (`/api/validate-claim`) — Phase D.
- Removing heuristic savings from UI totals — Phase E.

---

## Task: Exact billing only — Phase C: pricing module cleanup

### Goal
Remove median DRG package-price helpers and hardcoded default LOS constants from product paths after the DRG claim-exact rewrite.

### Subtasks
- [x] Grep all imports of `get_drg_package_price` / `get_drg_package_price_for_date` in `src/bilun` outside `domain/pricing/drg.py` and `tests/`.
- [x] Delete `SUT_ICD10_PROCEDURE_COSTS` from `src/bilun/domain/constants.py` if truly unused.
- [x] Delete `_DEFAULT_INPATIENT_LOS` and `_DEFAULT_ICU_LOS` from `src/bilun/domain/constants.py` once no product code references them.
- [x] In `src/bilun/domain/estimators.py`, remove cohort-mean visit-price enrichment; require claim-header facility tier + specialty or return `None` / unavailable.
- [x] Update any tests that relied on the deleted constants / cohort-mean behavior.
- [x] Run `.venv/bin/python -m pytest -q` and confirm green.

### Verification
- [x] `.venv/bin/python -m pytest -q`: **532 passed**
- [x] Grep confirms `_DEFAULT_INPATIENT_LOS`, `_DEFAULT_ICU_LOS`, `SUT_ICD10_PROCEDURE_COSTS`, and `get_drg_package_price_for_date` are absent from product paths (`api`, `cache`, `chatbot`, `domain/billing`, `domain/analytics`, `domain/optimization`).

### Review (2026-06-16)
- Deleted unused `SUT_ICD10_PROCEDURE_COSTS` and default LOS constants from `constants.py`.
- Replaced `_enrich_visit_prices_from_ek2a` cohort-mean fallback with `enrich_visit_prices_from_claim_header` (exact EK-2A tier row only).
- Added `tests/unit/domain/test_estimators.py`; corrected stale chapter-median docstring in `claim_strategy.py`.
- Median DRG helpers remain in `domain/pricing/drg.py` (deprecated, out of scope for deletion).
- **Follow-up (2026-06-16):** Removed median DRG exports from `pricing/__init__.py` to block accidental product imports.

### Out of Scope
- Removing the definition files in `domain/pricing/drg.py` entirely (deprecate first; delete in a later phase if zero callers remain).
- Replacing fuzzy catalog code resolution for free-text hospital names.

---

## Task: Exact billing only — Phase D: materials & validation API

### Goal
Replace `estimate_material_costs` with claim-line material pricing and update `validate_claim` plus `/api/validate-claim` to require coded material lines.

### Subtasks
- [x] Audit `src/bilun/domain/analytics/materials.py` and `estimate_material_costs`; design a claim-line replacement that prices from `billed_amount_try` or exact EK-3 code lookup.
- [x] Update `src/bilun/domain/rule_engine/validate_claim.py` to use the new claim-line material pricing and drop the fuzzy name-match path.
- [x] Update `src/bilun/api/routes/validation.py` contract: rename `material_estimates` to `material_lines` (or equivalent) and document the change.
- [x] Add/update tests for material-line pricing and validation.
- [x] Run `.venv/bin/python -m pytest -q` and confirm green.

### Verification
- [x] `.venv/bin/python -m pytest -q`: **535 passed**
- [x] `/api/validate-claim` returns material data sourced from claim lines, not fuzzy EK-3 name matches.

### Review (2026-06-16)
- Replaced `estimate_material_costs` with `price_material_lines` (`MaterialLinePricing`); fuzzy EK-3 name index removed.
- `validate_claim` / API now expose `material_lines` with `exactness_status`; `total_claim_amount` sums exact lines only.
- Frontend Claim Validator updated (EN/TR copy: "Material Lines", missing-input notice).

### Out of Scope
- Re-ingesting SUT EK-3 annexes.
- Building a hospital HIS adapter.

---

## Task: Exact billing only — Phase E: savings honesty

### Goal
Ensure cohort/patient totals use only claim-backed (`sourced`) savings, remove or expert-gate heuristic savings buckets, and update EN/TR copy so "recoverable" means claim-backed only.

### Subtasks
- [x] In `src/bilun/domain/prose_rules/drg_unbundling.py`, keep violation flags but stop summing `heuristic_savings_try` into UI-facing totals.
- [x] In `src/bilun/domain/billing/claim_drg_uplift.py`, narrow `savings_basis` to `sourced` / `optional_override`; drop `heuristic` basis.
- [x] In `src/bilun/domain/optimization/unbundling.py`, remove `total_heuristic_savings` from optimizer KPIs or hide it behind an expert flag.
- [x] In `src/bilun/domain/prose_rules/session_uplift.py`, keep `needs_clinical_review` as a review flag, not a ₺ savings amount.
- [x] Update frontend copy in `frontend/src/messages/{en,tr}/{optimizer,billing,patient}.ts` to clarify that recoverable amounts are claim-backed.
- [x] Run `.venv/bin/python -m pytest -q`, `npx tsc --noEmit`, `npx vitest run`.

### Verification
- [x] `.venv/bin/python -m pytest -q`: **536 passed**
- [x] `npx vitest run`: **132 passed**
- [x] Optimizer/patient UI no longer displays totals derived from `heuristic_savings_try`.

### Review (2026-06-16)
- `potential_savings_try` / cohort `total_potential_savings` now equal sourced prose violations only; heuristic amounts stay in `chapter_analysis` audit fields.
- Removed `total_heuristic_savings` / `has_heuristic_savings` from optimizer API payload.
- Session uplift clinical-review rows expose `review_uplift_try` with `recoverable_uplift_try = 0`.
- DRG uplift skips non-sourced claim kinds; UI copy updated EN/TR.

### Out of Scope
- Removing heuristic flags entirely from audit-only surfaces.
- Rebuilding fact-check audit metadata (only note the change).

---

## Task: Exact billing only — Phase F: verification & kill-list grep

### Goal
Prove no product API field presents a ₺ amount derived from ICD chapter median, default LOS, fuzzy material match, or hardcoded fallback.

### Subtasks
- [x] Run kill-list grep across `src/bilun` and `frontend/src`:
  - `chapter_median`
  - `get_drg_package_price`
  - `_DEFAULT_INPATIENT`
  - `_DEFAULT_ICU`
  - `_precheck_materials`
  - `estimate_material_costs`
  - `_FALLBACK_LAB`
  - `heuristic_savings`
  - `SUT_ICD10_PROCEDURE_COSTS`
- [x] For each hit, classify as test/deprecated/non-product vs product. Fix any product hits.
- [x] Run full test pyramid:
  - [x] `.venv/bin/python -m pytest -q`
  - [x] `npx tsc --noEmit`
  - [x] `npx vitest run`
  - [x] `npm run build`
- [x] Rebuild cache (`scripts/bilun/build_cache.py --activate`) and spot-check a patient with yatış + paket line and one without.
- [x] Update `src/bilun/domain/sut/fact_check_audit.py` notes where surfaces became exact.

### Verification
- [x] All kill-list terms are confined to tests, deprecated helpers, or clearly marked non-product files.
- [x] Full test/build suite green.
- [x] Cache rebuild succeeds; spot-check patients show `exact` only when claim lines support it.

### Review (2026-06-16)
- Added `tests/unit/domain/test_phase_f_kill_list.py` (15 grep assertions) — durable guard for product paths.
- Removed dead `chapter_median_heuristic` UI branch from `SutBillingReportSections.tsx`.
- Updated fact-check notes: L1.3, L3.4–L3.6, L4.3, P0.4.
- Kill-list classification: median DRG in `pricing/drg.py` (deprecated); `_FALLBACK_*` in orphaned `estimators.py`; `heuristic_savings` audit-only in `prose_rules/drg_unbundling.py`.
- `.venv/bin/python -m pytest -q`: **551 passed**
- `npx vitest run`: **132 passed**; `npm run build`: succeeded
- Cache build `b11658d7` activated; `SENTETIK-HASTA-0001` DRG episode with package line `exact`, without package line `missing_exact_inputs`.

### Out of Scope
- Full SUT prose coverage (54% algorithmic gaps remain a separate workstream).
- Hospital grouper / auto package-code assignment.
- MEDULA live integration.

---

## Task: Rule Database Section Polish & Subtabs Fix

### Goal
Fix the broken "Bölümler" (Sections) and "Prose Motorları" (Prose) subtabs in the Rule Database tab by resolving the Radix unmount/API abort conflict, and apply visual polish to clean up inline styles, viewport sizing, disabled states, and spacing issues.

### Subtasks
- [x] Fix Radix `TabsContent` unmount bug in `RuleDatabaseSection.tsx` using `forceMount` and `data-[state=inactive]:hidden`.
- [x] Replace inline `style={{ minWidth: 220, maxWidth: 360 }}` in toolbars with Tailwind classes `min-w-[220px] max-w-[360px]`.
- [x] Fix duplicate labeling/eyebrow in `CoverageSummaryPanel`'s `Stat` components.
- [x] Change fixed `maxHeight: 620` scroll box on `RuleList` to a responsive class like `max-h-[60vh]`.
- [x] Change fixed `maxHeight: 520` scroll box on `Clause Cards` list to a responsive class like `max-h-[55vh]`.
- [x] Add `disabled:opacity-50 disabled:cursor-not-allowed` styles to all pagination buttons.
- [x] Add `overflow-x-auto` container to status filters in the toolbar to prevent wrapping.
- [x] Simplify excessive padding/nesting in main tab structure (`Section` padding none / single `Surface` wrapper).
- [x] Verify that all typescript checks, linting, and build paths are green.
- [x] Fix FastAPI route shadowing bug in backend `src/bilun/api/routes/rules.py` that was causing `404 Not Found` API errors for the `sections` and `prose` tabs.

### Verification
- [x] Run typescript type checks: `npx tsc --noEmit --pretty` - Passed with 0 errors
- [x] Run eslint checks on `RuleDatabaseSection.tsx` - Passed with 0 warnings/errors
- [x] Verify build is successful: `npm run build` - Passed successfully (compiled Next.js application)
- [x] Verified FastAPI routes are correctly ordered to avoid parameter shadowing.

### Out of Scope
- Redesigning the entire API responses or data schemas.
- Modifying backend endpoints.

