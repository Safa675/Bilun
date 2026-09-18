# Rule Engine Surfacing Audit + Generic Finding Surface Implementation Plan

> **Implementer note:** This is an audit-first plan. Do not migrate additional detectors into `claim_compliance`, change financial totals, or add new medical/SUT rules until the inventory report in Phase 4 is generated and reviewed.

**Goal:** Produce an exact, reproducible answer to: “How many rule families/runtime detectors actually execute, how many are visible in patient/cohort UI, which are hidden, which are duplicate-surfaced, which are financial vs nonfinancial, and what is the exact hidden-rule list?” Then use that evidence to migrate only the appropriate hidden findings into a generic product surface.

**Architecture:** Treat BILUN as three related but different inventories: **registry rule families**, **runtime detectors/adapters**, and **user-facing finding kinds/surfaces**. Build a machine-readable coverage matrix across those layers. The SUT Rule Registry remains metadata; it must not be assumed to be a runtime dispatcher. Runtime truth comes from the canonical execution paths (`analyze_claim` and `compute_patient_billing_report`), while product visibility comes from report projection → cache/API → frontend rendering.

**Known baseline before the audit:** `RULE_REGISTRY` currently contains 47 entries (37 `implemented`, 4 `partial`, 6 `non_algorithmic`), but this is **not** the runtime-rule count. `claim_compliance` currently hard-codes only `icu_bundled_leakage_510090` and `tablo15_8_missing_diagnosis`. `analyze_claim` and `compute_patient_billing_report` execute many more detectors/adapters. The audit must derive the final counts instead of promoting any of these partial numbers to a headline metric.

---

## Why this audit comes before more rule work

PR87 proved the underlying product problem: K21 and K26 already existed as detectors, but users could not see them until a separate projection/cache/UI path was added. The same condition may exist for other detectors.

Adding more diagnosis/procedure logic before measuring current surfacing would increase hidden inventory and make the product harder to reason about. The first deliverable therefore is a **Rule Engine → Product Surface coverage matrix**, not another detector.

This plan also closes an older architectural gap left by the orphan-engine work: “runtime wired” and “user visible” are separate properties. A loader/registry/dispatch path can be correct while the finding is still absent from every product surface.

---

## Locked definitions

These definitions must be used by the script, report, tests, and later migration. Do not change them mid-audit to improve counts.

### 1. Inventory levels

1. **Registry rule family** — one `RuleRegistryEntry` in `src/bilun/domain/sut/rule_registry.py`.
2. **Runtime detector** — a concrete `check_*`, `detect_*`, `recommend_*`, `optimize_*`, `validate_*`, or equivalent evaluator that is reachable from a canonical production entrypoint.
3. **Finding kind** — a concrete emitted user-facing semantic row, normally identified by `rule_id`, `kind`, or a stable output category.

The audit reports all three counts separately. Never publish one as a substitute for another.

### 2. Runtime status

- `executed`: reachable from `analyze_claim(ctx)` and/or `compute_patient_billing_report(...)` and actually invoked when its declared inputs are present.
- `gated`: runtime-wired but only invoked when required inputs exist (`procedure_lines`, `drug_lines`, patient context, etc.). This is still runtime-wired.
- `registry_only`: metadata/catalog entry with no verified runtime invocation path.
- `artifact_only`: encoded JSON/YAML/data artifact with no verified production invocation path.

### 3. Visibility status

Rule Database metadata visibility does **not** count as finding visibility.

- `patient_visible`: a concrete finding can be rendered in the patient/bill workspace.
- `cohort_visible`: the finding can be rendered from a cohort/home API surface.
- `patient_and_cohort_visible`: both.
- `aggregate_only`: affects a KPI/total but has no row-level user-facing finding.
- `hidden_runtime`: the detector executes and can emit a meaningful finding, but that finding does not reach any product surface.
- `not_applicable`: metadata/non-algorithmic entry that is not supposed to emit findings.

### 4. Financiality

Do not infer “financial” merely because a rule could eventually cause a denial.

Use `money_semantics`:

- `priced_opportunity` — exact/reproducible recoverable amount is carried into a revenue total.
- `priced_exposure` — exact/reproducible billed/risk amount is carried into a compliance/audit monetary total.
- `unpriced_compliance` — operationally/financially important compliance risk, but the detector does not produce a trustworthy amount. K21/K26 currently belong here.
- `informational` — review/checklist/reference output with no direct money semantics.

For the requested binary rollup, the first two are **financial**; the latter two are **nonfinancial**. Preserve `money_semantics` in the detailed matrix so the binary label does not erase meaning.

### 5. Duplicate surfacing

`duplicate_surface` means the same semantic finding identity (`rule_id/kind + patient + claim + line/material/procedure identity`) is independently surfaced more than once.

Classify duplicates as:

- `intentional_cross_view` — same canonical finding intentionally linked from more than one view without double-counting.
- `accidental_duplicate` — independently constructed rows or repeated detector execution can present/count the same issue twice.
- `financial_double_count_risk` — duplicate representation can alter monetary totals. This is merge-blocking.

---

## Target coverage matrix

The machine-readable artifact must contain at least these fields for every runtime detector/finding family:

```text
inventory_level
registry_rule_id
runtime_id
callable
entrypoint
gating_condition
required_inputs
emitted_rule_ids_or_kinds
report_field
recommended_action_surface
finding_type
cohort_api_surface
patient_ui_surface
cohort_ui_surface
money_semantics
money_fields
included_in_totals
visibility_status
duplicate_group
duplicate_status
hidden_reason
regulatory_source
evidence_files
```

Human report columns should be compact:

```text
runtime/family | emitted rule/kind | patient UI | cohort UI | financiality | visibility | duplicate | notes
```

---

## Phase 0 — Freeze the taxonomy and baseline

**Objective:** Make the audit reproducible before changing any runtime behavior.

### Tasks

1. Record the current commit/branch and current `RULE_REGISTRY` count/status breakdown.
2. Record the current canonical execution entrypoints:
   - `src/bilun/domain/billing/engine.py::analyze_claim`
   - `src/bilun/domain/billing/patient_report.py::compute_patient_billing_report`
3. Record the current product projection entrypoints:
   - `billing_actions.py::collect_billing_actions`
   - `claim_compliance.py::project_claim_compliance`
   - `cohort_compliance.py`
4. Freeze the definitions above in the audit script/tests.

**Gate:** No runtime/UI code changes before the first full matrix is generated.

---

## Phase 1 — Build the static runtime inventory

**Objective:** Enumerate every detector/adapter production can invoke without relying on naming assumptions or the registry alone.

**New file:** `scripts/audits/build_rule_surfacing_inventory.py`

### 1.1 Parse `analyze_claim`

Extract every direct evaluator call, including calls nested behind input gates. Record:

- callable/module;
- gate (`ctx.patient_id`, `ctx.procedure_lines`, `ctx.drug_lines`, etc.);
- whether output is appended to the flat violation list;
- expected emitted `rule_id`/kind where statically discoverable.

Do not collapse all `check_*` calls into one “validation engine” row. The user needs the exact hidden-detector list.

### 1.2 Parse `compute_patient_billing_report`

Extract every report adapter assignment and post-processing step, including:

- lab/capture;
- copay;
- billing strategy;
- session/DRG/blood/yatak/ICU/newborn/refakatçi/anesthesia/material/add-on/care-setting/repricing engines;
- MEDULA playbook;
- submission checklist;
- drug indication;
- material precheck;
- `claim_compliance`.

Record the destination `BillingActionReport` field and the input gate.

### 1.3 Reconcile with Registry and prose inventory

Join runtime rows against:

- `RULE_REGISTRY` / `RULE_BY_ID`;
- prose inventory/catalog metadata;
- rule-set JSON/YAML artifacts where relevant.

The report must explicitly list:

- runtime detector with no registry family;
- registry family with no runtime invocation;
- one registry family mapping to multiple runtime detectors;
- one runtime detector emitting multiple rule IDs.

**Gate:** Every canonical runtime call has a row in the matrix. A detector cannot disappear because it lacks a registry mapping.

---

## Phase 2 — Trace backend surfacing end to end

**Objective:** Determine exactly what each runtime output becomes after execution.

### 2.1 Patient report trace

For each runtime row, trace one of these outcomes:

1. report field → `collect_billing_actions` → user-facing action;
2. report field → dedicated patient section, outside `recommended_actions`;
3. `claim_compliance` → dedicated nonfinancial finding/evaluation block;
4. contributes only to totals/summary;
5. discarded/not projected.

The fifth category is a primary hidden-rule candidate.

### 2.2 `recommended_actions` trace

Enumerate every explicit surface created by `billing_actions.py` and join it back to its source report block/runtime detector.

Current examples include `materials`, `drug_indication`, `lab`, `billing_strategy`, `session_uplift`, `drg_uplift`, `blood_uplift`, `yatak_puani`, `material_uplift`, `procedure_addon_uplift`, `procedure_capture_gap`, `drg_package_adequacy`, `gazette_repricing`, `care_setting_review`, `copay`, `medula_playbook`, and `claim_checklist`.

Do not assume an engine is visible merely because its report field exists.

### 2.3 Dedicated projection trace

Trace `claim_compliance` separately. Today it re-runs only two detectors. Flag this hard-coded allowlist as architectural debt, not as the desired final inventory.

### 2.4 Totals trace

Trace monetary inclusion through `finalize_report_totals` and related reconciliation. Record every field that changes:

- SGK uplift/recovery;
- compliance savings/exposure;
- billed-at-risk or audit totals;
- nonfinancial/null money.

This is the evidence for `money_semantics`; do not classify from detector names.

---

## Phase 3 — Trace API and frontend visibility

**Objective:** Prove that a backend projection is actually reachable by users.

### 3.1 API/cache

Trace each surface through:

- report serialization/schema;
- billing cache tables/payloads;
- cohort index projections;
- patient/cohort API routes and filters;
- old-cache/unavailable behavior.

### 3.2 Patient UI

Trace each surface to concrete components/routes, including:

- `frontend/src/lib/recommendedActions.ts`;
- patient workspace views/sections;
- dedicated billing report sections;
- deep-link section mapping.

### 3.3 Cohort/home UI

Trace each cohort-visible surface to:

- Compliance dashboard;
- alerts/other cohort tabs;
- Red Kuyruğu where relevant;
- any other native product list.

### 3.4 Rule Database is metadata only

Record Rule Database presence as `catalog_visible=true`, but do not use it to satisfy `patient_visible` or `cohort_visible`.

**Gate:** A rule is only “visible” when an emitted finding can be reached through a real API/report path and rendered by a real UI component.

---

## Phase 4 — Generate the exact audit outputs

**Objective:** Produce the numbers and lists that motivated this work.

**Generated outputs:**

- `reports/rule-engine-surfacing/2026-09-18-rule-surfacing-matrix.json`
- `reports/rule-engine-surfacing/2026-09-18-rule-surfacing-audit.md`

The Markdown report must start with exact counts for:

1. registry rule families;
2. runtime detectors/adapters;
3. distinct emitted rule IDs/kinds;
4. patient-visible findings;
5. cohort-visible findings;
6. hidden runtime findings;
7. aggregate-only findings;
8. duplicate-surfaced findings;
9. financial findings;
10. nonfinancial findings.

Then include complete lists for:

- **Hidden runtime findings** — exact detector + emitted rule/kind + why hidden + required inputs.
- **Duplicate groups** — every surface involved and whether duplication affects money.
- **Registry-only/artifact-only entries** — kept separate from hidden runtime rules.
- **Unknown/ambiguous mappings** — must remain explicit; no forced classification.

### Verification

Add `tests/unit/scripts/test_rule_surfacing_inventory.py` with fixtures asserting:

- all canonical runtime calls are captured;
- `claim_compliance` current two-rule allowlist is captured;
- registry-only rows are not mislabeled runtime;
- a new unmapped runtime call causes the test to fail.

**Audit review gate:** Review the generated hidden/duplicate list before implementing Phase 5+. The report is the decision document for migration scope.

---

## Phase 5 — Define one canonical finding contract

**Objective:** Stop adding one-off K21/K26-style wiring for every hidden nonfinancial detector.

**Proposed new domain type:** `RuleFinding` (exact filename decided during implementation after the audit).

Minimum contract:

```text
finding_id
patient_id
claim_id
line_id
rule_id
kind
finding_type
severity
detail
sut_section_id / regulatory_source
surface
money_semantics
money fields (nullable)
required_inputs / evaluation_status
source_engine
```

### Architectural constraints

1. **Do not turn `RULE_REGISTRY` into the runtime dispatcher.** It can supply display/regulatory metadata, but execution stays in the domain engines.
2. **Do not re-run the same detector in multiple projection layers.** Canonical runtime output should be projected once, then reused by patient/cohort/UI surfaces.
3. **Stable finding identity is mandatory** so cross-view rendering does not become duplicate counting.
4. **Money stays nullable and explicit.** Generic surfacing must not manufacture amounts for unpriced compliance findings.
5. **Existing financial engines keep their current monetary semantics** unless the audit proves a concrete double-counting bug.

### Metadata source

After the audit, decide whether display/surface metadata belongs in an extension of `RuleRegistryEntry` or a separate presentation registry. The decision must follow the actual mapping cardinality found in Phase 4. Do not assume one registry entry = one emitted finding.

---

## Phase 6 — Migrate findings in evidence-based waves

**Objective:** Surface hidden rules without destabilizing existing financial/revenue paths.

### Wave A — Hidden + nonfinancial validation findings

First migration target:

- `visibility_status == hidden_runtime`;
- `money_semantics == unpriced_compliance`;
- deterministic claim/line identity exists;
- required inputs are available in current claim context.

Route these through the generic claim-compliance/finding projection and existing patient/cohort Compliance UX.

This is the direct generalization of PR87.

### Wave B — Hidden informational/audit findings

Route appropriate rows to the audit/review surface, not automatically to Compliance. Preserve the existing distinction between compliance, revenue opportunity, and document/review work.

### Wave C — Duplicate visible findings

For every `accidental_duplicate`:

- choose one canonical finding producer;
- make other views reference/project that finding;
- preserve deep links;
- prove counts and totals do not double-count.

Financial duplicate-risk fixes block broader migration until their regression tests pass.

### Wave D — Aggregate-only or special-purpose engines

Decide explicitly whether aggregate-only outputs need row-level surfacing. Do not create rows just to maximize the visibility percentage.

---

## Phase 7 — Make hidden-rule regressions impossible

**Objective:** A newly wired runtime rule cannot silently disappear from the product again.

### CI/test gates

1. Every runtime detector discovered from the canonical entrypoints must have a surfacing classification.
2. Every `hidden_runtime` row requires an explicit allowlisted reason or a migration owner.
3. New nonfinancial validation detectors must declare a finding surface or an explicit `internal_only` rationale.
4. New financial detectors must declare their money semantics and total inclusion.
5. Stable finding IDs must be unique across surfaces.
6. Cross-view duplication must not change monetary totals.

### Regression tests

- patient-level generic finding projection;
- cohort index/API pagination/filtering;
- frontend Compliance rendering and deep links;
- old-cache unavailable behavior;
- financial totals before/after migration remain identical for nonfinancial waves;
- duplicate finding identities render once per intended view and count once globally where required.

---

## Phase 8 — Rollout and cache compatibility

1. Keep new response fields additive where possible.
2. Old caches must remain `unavailable`, never fake zero.
3. Cache rebuild is required only when the migrated finding projection becomes part of cached cohort artifacts.
4. Compare pre/post rebuild counts using the active cache build ID only.
5. Spot-check at least one positive and one negative patient for every migrated rule family before deployment.

---

## Definition of done

The work is complete only when:

1. the audit script deterministically produces the matrix from the current tree;
2. the report gives exact counts and the complete hidden-rule/duplicate lists;
3. every runtime detector has a documented surface classification;
4. the first approved hidden nonfinancial migration wave is surfaced through one generic finding contract, without one-off rule-ID wiring;
5. nonfinancial migration does not change financial totals;
6. CI fails if a future runtime detector is added without a surfacing classification.

---

## Out of scope

- Adding new SUT/Fatura İnceleme/El Kitabı medical logic.
- Adding the proposed diagnosis→procedure medical-necessity rule.
- Reclassifying rule-coverage status merely to improve coverage percentages.
- Changing existing price/recovery formulas without a separately evidenced bug.
- Treating Rule Database metadata presence as product finding visibility.
- Forcing every informational or aggregate-only engine into Compliance.
- Deploying/rebuilding production cache as part of the audit-only phases.
