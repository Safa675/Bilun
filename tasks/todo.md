## Task: Phase 0 cleanup + Phase 1.1b (before 1.2)

### Goal
Close Phase 0 KPI gaps and harden session uplift before DRG uplift wiring.

### Subtasks
- [x] Wire `audit_exposure_try` from over-billing detectors (display-only)
- [x] Align cohort `total_strategy_savings` with `total_strategy_uplift`
- [x] Optimizer chart i18n for savings_by_category keys
- [x] Patient priority ranking on `sgk_uplift_try` only
- [x] Session section disclaimer (EN/TR)
- [x] `needs_clinical_review` heuristic; exclude from SGK headline
- [x] Integration test pin for SENTETIK-HASTA-0001 session uplift

### Review
- SENTETIK-HASTA-0001: 15 rule-calculated opportunities; 4 chart-review rows excluded → **3,245.90 TRY** SGK headline (was 16,573.83).
- `audit_exposure_try` ~8,755 TRY on 0001 (display-only); cohort `total_audit_exposure` added.
- Priority percentiles use `sgk_uplift_try` only; `total_opportunity_try` still SGK + copay for patient table display.

## Task: Phase 1.2 — DRG uplift wiring

### Goal
Surface legal `itemized_package_uplift_try` on the billing report and sum into `sgk_uplift_try` without double-counting strategy or session uplift.

### Subtasks
- [x] `DrgUpliftRecommendation` type + `claim_drg_uplift.py` wrapper
- [x] Orchestrator sum + cohort `total_drg_uplift` / `savings_by_category`
- [x] API serialize + frontend `DrgUpliftSection` (EN/TR)
- [x] `test_drg_uplift_wiring.py` (legal gate, strategy/session de-dupe, audit excluded)

### Review
- DRG uplift uses session-adjusted itemized vs package; skips `DRG_MANDATORY` compliant package claims.
- De-dupe: per-claim strategy uplift and session confirmed uplift subtracted before SGK headline.
- SENTETIK-HASTA-0001 claim 005 raw heuristic 341 TRY excluded (mandatory package); SGK headline unchanged at 3,245.90.

## Task: Phase 1.3 — Optional override surfacing

### Goal
Make §2.2.2(2) DRG_OVERRIDABLE uplift visible in SGK uplift UI, synthetic demo data, and cohort metrics.

### Subtasks
- [x] `savings_category` + recoverable-only `savings_try` on optional_override rows
- [x] `OptionalOverrideSection` UI (promoted out of strategy table)
- [x] Synthetic `sgk_optional_override_*` scenarios on demo patients
- [x] Cohort `n_optional_override_patients` + chatbot context

### Review
- `DRG_OVERRIDABLE` savings are zero when already on the higher legal method.
- Override rows carry `savings_category: sgk_uplift`; promoted to dedicated billing section.
- Demo patients 0002 (itemized higher, package billed) and 0003 (package higher, itemized billed) tagged — regenerate synthetic export + cache to see in UI.

## Task: Fix SGK uplift synthetic demos + integration pins

### Goal
Optional-override demo patients produce non-zero uplift after parquet regen; integration tests pin 0002/0003/0004.

### Subtasks
- [x] Fix `_pick_optional_override_demo_procedures` (payable_override, disable surcharges, pin 609270)
- [x] Add `test_sgk_uplift_synthetic_demos.py`
- [x] Regenerate synthetic parquet (`generate_sut_synthetic_data_v2.py`)
- [x] Rebuild DuckDB cache (uvicorn stopped; build `3c3a29c3-1808-430d-b895-cd41e39185b8`)
- [x] Verify integration tests pass on fresh parquet (3/3)

### Review
- 0002: optional override **1,750 TRY** (itemized > package, currently package-billed).
- 0003: optional override **5,000 TRY** (package 9,000 vs itemized 4,000, currently itemized-billed).
- 0004: blood uplift **310 TRY** unchanged.
- Root cause for 0003 failure: DRG-group package sampling picked starred mandatory code P610990; demos now pin overridable 609270.

## Task: Verdict follow-ups (DRG alignment, 0005, cohort surfacing, cache)

### Goal
Close remaining Phase 1.2–1.4 gaps from audit verdict.

### Subtasks
- [x] `resolve_package_total_try()` shared by strategy + DRG uplift (EK-2C / chapter fallback)
- [x] DRG uplift gate uses session-adjusted itemized vs resolved package total
- [x] Synthetic SENTETIK-HASTA-0005 (`sgk_drg_uplift_yatis`, `package_candidate=False`)
- [x] Cohort `n_drg_uplift_patients` / `n_blood_uplift_patients` + optimizer KPIs + chatbot lines
- [x] Roadmap regen docs (`generate_sut_synthetic_data_v2.py`, not `generate.py`)
- [x] Regenerate parquet + rebuild DuckDB cache (build `3c3a29c3-1808-430d-b895-cd41e39185b8`)

### Review
- 0005: DRG uplift **2,500 TRY** (`package_candidate=False`); strategy override **0** on demo claim.
- DRG gate/amount both use `resolve_package_total_try()` + session-adjusted itemized.
- Optimizer + chatbot cohort lines include DRG/blood patient counts and TRY totals.

## Task: Phase 2.1 — Missing billable materials

### Goal
Detect inverse EK-3B-1 pairing gaps (procedure billed, expected material missing) and sum priced uplift into `sgk_uplift_try`.

### Subtasks
- [x] `material_pairing_uplift.json` + `material_uplift.py` detector
- [x] `claim_material_uplift.py` + `MaterialUplift` type + orchestrator sum
- [x] API + `MaterialUpliftSection` UI (EN/TR) + cohort/chatbot KPIs
- [x] Synthetic SENTETIK-HASTA-0006 (`sgk_material_uplift_yatis`)
- [x] Unit + synthetic integration tests
- [x] Regenerate parquet + rebuild cache (build `26efe11d-9b60-49fd-a77e-033c67bbe774`)

### Review
- Pairing rule: procedure **600150** → expected material **OR2640** (~**667 TRY** KDV ceiling).
- SENTETIK-HASTA-0006: procedure billed, no material lines → uplift in SGK headline.
- Priced-only: no TRY emitted when EK-3 catalog price missing.
- Expanded catalog (7 rules): `pairing_mode: specialty_annex` for EK-3H/I/F-1 stent, valve, ICD, EVAR, hip.

### Out of Scope
- L4.4 specialty batch expansion beyond pilot pairing rule

## Task: Phase 2.2 — Care-setting optimizer (advisory)

### Goal
Flag ambiguous inpatient/outpatient coding where an alternate legally plausible care setting yields higher recoverable TRY — advisory only, excluded from SGK headline.

### Subtasks
- [x] Enhance `infer_care_setting` + `detect_care_setting_ambiguity()` in `claim_utils.py`
- [x] `care_setting_review.py` detector + `claim_care_setting_review.py` wrapper
- [x] `CareSettingReview` type + orchestrator wire (NOT in `_sum_sgk_uplift_try`)
- [x] API serialize + `CareSettingReviewSection` UI (EN/TR)
- [x] Synthetic SENTETIK-HASTA-0007 (`sgk_care_setting_review_gunubirlik`)
- [x] Unit + synthetic integration tests
- [x] Regenerate parquet + rebuild cache

### Review
- Ambiguous patterns: `gunubirlik`, same-day `yatis`, `poliklinik` with multi-day stay.
- `gunubirlik` at tier-3: outpatient DRG_MANDATORY vs alternate inpatient DRG_OVERRIDABLE.
- SENTETIK-HASTA-0007 demo claim: review uplift excluded from `sgk_uplift_try` (`included_in_sgk_total: false`).
- Cache rebuild: `6d466431-7de1-4a20-8730-8a03522c9f8d`.

### Out of Scope
- Auto-flipping Y↔G claim types
- Counting review TRY in `sgk_uplift_try` headline

## Task: Phase 2.3 — Procedure pairing & add-on rules

### Goal
Detect missing same-session add-on procedures when a trigger procedure is billed; estimate uplift from EK-2B price × add-on factor and sum into `sgk_uplift_try`.

### Subtasks
- [x] `procedure_pairing_prose.json` + `procedure_addon_uplift.py` detector
- [x] `claim_procedure_addon_uplift.py` + `ProcedureAddonUplift` type + orchestrator sum
- [x] De-dupe vs session under-billing uplift on same code/date
- [x] API + `ProcedureAddonUpliftSection` UI (EN/TR) + optimizer KPI
- [x] Synthetic SENTETIK-HASTA-0008 (`sgk_procedure_addon_kolonoskopi`)
- [x] Unit + synthetic integration tests; regen parquet + cache

### Review
- Pilot rules: colonoscopy/OGD triggers → polypectomy add-ons at 30% EK-2B factor.
- SENTETIK-HASTA-0008: 701450 billed, 701460 missing → **primary_billed × 30%** in SGK headline.
- Session under-billing on same code/date de-duped; no TRY without EK-2B catalog price.
- Cache rebuild: `dcb25d89-a5e2-415c-8a83-d9e93c7ed157`.

### Out of Scope
- Full L4.4 / all EK-2B modifier catalog batch
- EMR procedure capture completeness (Phase 3.1)

## Task: Phase 2 audit hardening

### Goal
Fix pricing/demo/test gaps from Phase 2 audit before Phase 3.

### Subtasks
- [x] Procedure-addon: primary_billed × session factor; suppress when add-on line exists
- [x] Demo patients 0006–0008: single-episode isolation; 0008 catalog pricing
- [x] Material: foreign_facility inference; partial billing; per-claim dedupe; message_tr
- [x] Integration tests: SGK sum includes procedure_addon; session/addon de-dupe
- [x] Remove duplicate TR careSettingReview i18n key
- [x] Regenerate parquet + cache

### Review
- Procedure-addon uses `primary_billed_x_session_factor`; zero-billed add-on lines suppressed.
- 0007/0008 isolated (1 claim); 0007 `sgk_uplift_try == 0`; 0008 uplift pinned to trigger×0.3.
- Material partial gaps, per-claim pairing dedupe, procedure-linked billing only.
- Cache: `824760dc-adea-4c6d-ae15-7737335ce74c`.

### Out of Scope
- specialty_annex clinical guards; care-setting fee schedule differentiation

## Task: Phase 3.1 — Procedure capture completeness (EMR vs claims)

### Goal
Ingest optional EMR/OR performed-procedure log, detect performed-not-submitted gaps priced from EK-2B/EK-2C, expose `capture_gap_try` separate from `sgk_uplift_try`, and de-dupe vs procedure-addon uplift.

### Subtasks
- [x] `PerformedProcedureLine` model + optional `performed_procedure_lines.parquet` loader
- [x] Extend `PatientClaimContext` + synthetic export
- [x] `procedure_capture_gap.py` detector + `claim_procedure_capture_gap.py`
- [x] `ProcedureCaptureGap` type + `capture_gap_try` on report (exclude from SGK headline)
- [x] Orchestrator de-dupe vs `procedure_addon_uplift` on same claim/code/date
- [x] API + `ProcedureCaptureGapSection` UI (EN/TR)
- [x] Synthetic SENTETIK-HASTA-0009 (`sgk_procedure_capture_kolonoskopi`)
- [x] Unit + synthetic integration tests; regen parquet + cache

### Review
- EMR log `performed_procedure_lines.parquet` optional at load; empty patients stay exact with no gap.
- Pricing: EK-2B list price (EK-2C fallback); `included_in_sgk_total: false`; `capture_gap_try` on summary.
- 0009: colonoscopy billed, polypectomy in EMR → capture gap TRY; add-on de-duped; `sgk_uplift_try == 0`.
- Cache rebuild: `638b97fa-f33b-4bc9-acb7-a4201fe93e7f`.

### Out of Scope
- Full hospital EMR connector (parquet contract only)
- gazette repricing (3.3), MEDULA playbook (3.4)

## Task: Phase 3.2 — DRG / package code adequacy review

### Goal
Advisory `documentation_review` when billed EK-2/C package is under-coded vs clinical procedure footprint; expose `package_adequacy_review_try` outside `sgk_uplift_try`.

### Subtasks
- [x] `drg_package_adequacy_prose.json` footprint rules + detector
- [x] `DrgPackageAdequacyReview` + `claim_drg_package_adequacy.py` + orchestrator
- [x] API + `DrgPackageAdequacyReviewSection` UI (EN/TR)
- [x] Synthetic SENTETIK-HASTA-0010 (`sgk_package_adequacy_undercoded`)
- [x] Unit + synthetic tests; regen parquet + cache

### Review
- Footprint rules in `drg_package_adequacy_prose.json` (609270 vs 609300); strict superset only.
- `recommendation_kind: documentation_review`; `included_in_sgk_total: false`; `package_adequacy_review_try` on summary.
- 0010: package 609270 billed with 600150+600160 → candidate 609300 review; excluded from `sgk_uplift_try`.
- Cache rebuild: `3821ccf1-bf27-4834-b9e9-c61b3b0c4f3c`.

### Out of Scope
- Auto package switching; highest-price-wins upcoding
- MEDULA playbook (3.4)

## Task: Phase 3.3 — Gazette repricing opportunity (prospective)

### Goal
Flag claim lines priced at pre-amendment EK-2B/EK-2C gazette rates when a later tebliğ increased list price; expose `gazette_repricing_try` outside `sgk_uplift_try`.

### Subtasks
- [x] `gazette_repricing_prose.json` rebill gate + `gazette_repricing.py` detector
- [x] `GazetteRepricingOpportunity` + `claim_gazette_repricing.py` + orchestrator
- [x] API + `GazetteRepricingSection` UI (EN/TR)
- [x] Synthetic SENTETIK-HASTA-0011 (`sgk_gazette_repricing_600150`)
- [x] Unit + synthetic tests; regen parquet + cache

### Review
- 600150 billed at **449.73** (2024-06-01 service); post-2026 tebliğ list **539.68** → **89.95 TRY** prospective delta (display-only, not in `sgk_uplift_try`).
- Fixed 0011 diagnosis date alignment (`visit_date` pinned with episode).
- Cache rebuild: `f5415ad7-0ffc-4cfb-b7ca-983c07ba3db2`.

### Out of Scope
- Automatic rebill submission; MEDULA playbook (3.4)

## Task: Phase 3.4 — MEDULA rejection → corrective rebill playbook

### Goal
Ingest MEDULA rejection events, map to SUT-anchored corrective rebill templates (not auto-rebill), expose `medula_playbook_entry_count` outside `sgk_uplift_try`.

### Subtasks
- [x] `data/medula/*.json` knowledge base + `rejection_playbook.json`
- [x] Optional `medula_rejection_events.parquet` + loader + `MedulaRejectionEvent`
- [x] `medula_rejection.py` detector + `claim_medula_rejection.py` + orchestrator
- [x] API + `MedulaRejectionPlaybookSection` UI (EN/TR) + chatbot KB extension
- [x] Synthetic SENTETIK-HASTA-0012 (`medula_rejection_1688_molecular_microbiology`)
- [x] Unit + synthetic tests; regen parquet + cache

### Review
- Code **1688** (moleküler mikrobiyoloji rapor eksik) at `fatura_kayit` → 4-step corrective template; `medula_playbook_entry_count=1`, not in `sgk_uplift_try`.
- Chat: `search_playbook_entries` + `build_medula_context` playbook block.
- Cache rebuild: `e509a07c-9941-4952-b522-89716778710d`.

### Out of Scope
- Automatic MEDULA rebill submission; live MEDULA SOAP ingest

## Task: Phase 3 hardening (post-audit)

### Goal
Fix optional-ingest semantics, adequacy false-positive guard, locale/cohort polish from Phase 3 audit.

### Subtasks
- [x] `not_applicable` exactness for optional EMR/MEDULA ingest; exclude from report rollup
- [x] Unknown package guard + skip zero-delta adequacy rows
- [x] Capture runs when EMR present without procedure lines; addon de-dupe date normalization
- [x] MEDULA steps locale (EN/TR); optional-ingest UI shells
- [x] Cohort TS types, optimizer KPIs, savingsCategory i18n; remove medula count from pie
- [x] Tests: unknown package, not_applicable wiring, stronger 0010 delta pin

## Task: Phase 1.4 — Blood component uplift

### Goal
Detect §2.2.2.B-1.e blood component under-billing and sum into `sgk_uplift_try`.

### Subtasks
- [x] `detect_blood_component_underbilling_opportunities()` in `blood_uplift.py`
- [x] `BloodComponentUplift` + `claim_blood_uplift.py` + orchestrator/cohort wiring
- [x] Frontend `BloodComponentUpliftSection` (EN/TR)
- [x] Synthetic demo on SENTETIK-HASTA-0004 (`sgk_blood_uplift_yatis`)
- [x] Unit tests (detector + wiring; over-billing stays audit-only)

### Review
- 705371 at 50 TRY billed vs 1000 TRY reference → **310 TRY** recoverable (36% cap = 360).
- Over-billed lines excluded from uplift; `detect_blood_component_violations` unchanged for audit.

## Task: Fact-check + evidence relocation

**Plan:** `plans/docs/fact-check-evidence-relocation.md`

### Goal
Move `reports/sut-fact-check/` → `docs/core-system/fact-check/` and root `evidence/` → `data/gazette/prose_{manifests,corpus}/`; eliminate orphan directories.

### Subtasks
- [x] Phase 0 — create target dirs; baseline `rg` file list
- [x] Phase 1 — `git mv` pipeline data; update `coverage_scope.py` + 8 scripts
- [x] Phase 2 — `git mv` fact-check docs; fix internal markdown paths
- [x] Phase 3 — update plans + medula doc links
- [x] Phase 4 — `reports/README.md` stub; archive WORKSTREAMS; migrate FIX_BACKLOG P2 rows
- [x] Phase 5 — `rg` clean; `rebuild_baseline_metrics.py`; material bundling tests

### Review
- Relocated 2026-06-07: `docs/core-system/fact-check/`, `data/gazette/prose_{manifests,corpus}/`, `docs/medula/medula_overlap_gaps.md`.
- `coverage_scope.py` uses `PROSE_MANIFESTS_DIR` from `constants.py` (repo-root anchored).

### Out of scope
Re-auditing algorithms, L1.4 corpus expansion, `algorithms_reference.md` sync (separate plan).
