# Drug Indication Correctness, Canonicalization, and UX Implementation Plan

> **For the implementer:** Execute this plan on a new feature branch from the current `main` after merged PR #89. Use TDD, preserve financial invariants, and keep generated audit artifacts in a separate final commit so they do not bury the production diff.

**Date:** 2026-09-20
**Status:** Ready for implementation
**Priority:** Must complete before expanding the next rule-surfacing wave
**Depends on:** Merged PR #89 (`feat(compliance): complete generic rule surfacing loop`)
**Related plans:**
- `plans/billing/2026-09-18-rule-engine-surfacing-audit-plan.md`
- `plans/billing/r5-epic-4.2-drug-indication.md`
- `plans/billing/drug-indication-4.2.14.C-expansion-plan.md`
- `plans/billing/validate-claim-drug-indication-wiring-plan.md`

**Goal:** Make drug-indication findings medically and operationally intelligible: determine indication applicability correctly, stop generic no-ICD rules from masking diagnosis mismatches, evaluate the family through one canonical typed path, and show users observed diagnoses, eligible indication routes, the actual failure reason, uncertainty, and the next action.

**Architecture:** Separate diagnosis-based indication applicability from supplemental report/prescriber/duration/biomarker constraints. Introduce a typed canonical drug-indication evaluation batch shared by the analyzer and billing-report projections, while preserving the dedicated `drug_indication` product surface rather than forcing the 968-rule family into the narrow `claim_compliance` surface. Project structured data through patient report, recommended actions, cache/cohort API, and an explanation-first UI.

**Tech stack:** Python dataclasses/Pydantic, existing §4.2 YAML/JSON rule corpus, billing report JSON cache, React/TypeScript, Vitest, Pytest, PR #89 rule-surfacing audit generator.

---

## 1. Why this work comes before the next Wave A/B/C/D scope

PR #89 established the generic surfacing architecture and migrated the first three hidden Wave A findings. Drug indication is different:

- it is already visible to users;
- it covers 968 emitted rule identities;
- it can choose a semantically unjustified rule for an unrelated diagnosis;
- it currently reports `exact` even when applicability is ambiguous;
- its primary UI message is copied from regulatory prose rather than generated from the actual failure;
- its analyzer and patient-report paths independently execute the same family;
- the audit identifies drug indication as the largest remaining independent rerun relationship.

Expanding additional hidden rules before correcting this surface would increase product breadth while leaving a known user-facing correctness defect unresolved. This plan is therefore the prerequisite hardening step before the next bounded Wave A slice. Wave B and Wave D still require separate product scoping; Wave C currently has no accidental-duplicate candidate.

---

## 2. Confirmed current defects

### 2.1 Generic rules can mask indication mismatch

Current behavior in `src/bilun/domain/prose_rules/drug_indication.py`:

1. `_diagnosis_matches_rule()` returns `True` when a rule has neither `icd10_codes` nor `icd10_ranges`.
2. `_find_matching_rule()` puts those generic rules in `icd_matched`.
3. If a billed drug has an unrelated diagnosis, a generic report/prescriber rule can be selected before the engine decides whether any diagnosis-specific indication is eligible.

For abatacept/Orencia, the corpus contains diagnosis-specific routes including:

- `M05` / `M06` rheumatoid arthritis routes;
- `M08` juvenile arthritis routes;
- generic rheumatology/report constraints without an ICD selector.

An unrelated diagnosis must not be converted into a report-verification finding merely because a generic drug-name rule exists.

### 2.2 One arbitrary rule is used to explain a family-level mismatch

When no diagnosis-specific route matches, the current evaluator falls back to one drug-name candidate and emits its `rule_id`, `sut_section`, and `message_tr`. For a drug with multiple legitimate indication routes, this falsely implies that one route—such as an M08 ACR30 continuation rule—is the only expected indication.

### 2.3 `matched_icd10_codes` does not mean matched

`_collect_icd10_codes()` collects observed claim diagnoses. Those codes are returned as `matched_icd10_codes` even when none matched the selected rule. The contract must distinguish:

- observed diagnoses;
- diagnoses/routes eligible under the corpus;
- actually matched diagnoses;
- unmatched observed diagnoses.

### 2.4 Exactness is overstated

`validate_drug_indication_from_claims()` marks every non-empty drug-line context as `exact`, regardless of:

- missing diagnosis data;
- unresolved route arbitration;
- missing route discriminator fields;
- partial corpus coverage;
- rules that require manual/Tier C clinical inputs.

Input exactness and corpus coverage must remain separate:

- `exactness_status` describes whether the available claim inputs allowed a decisive evaluation;
- `coverage_scope` continues to describe the partial §4.2 corpus honestly.

### 2.5 Domain/API/frontend contracts are untyped bags

Current contracts use `list[dict[str, Any]]` and a small optional TypeScript shape. The UI cannot reliably know:

- which diagnoses were observed;
- which indication routes were eligible;
- why one route was selected;
- which inputs were missing;
- whether the result is a confirmed mismatch or manual review;
- what the user should do next.

### 2.6 Recommended-action projection drops useful data

`collect_billing_actions()` reads fields the detector does not emit:

- reads `detail`, while drug findings primarily emit `message_tr`;
- reads `sut_section_id`, while drug findings emit `sut_section`;
- reads `drug_code` or `inn`, which current findings may not contain.

The resulting cohort/recommended-action rows can have empty detail, drug code, and regulatory source.

### 2.7 The UI exposes implementation details instead of an explanation

`DrugIndicationReviewSection` currently presents:

- raw `violation_kind`;
- only the primary ICD-10;
- one internal rule ID;
- one SUT section;
- the raw regulatory summary as the main message.

The user instead needs:

1. what was found on the claim;
2. what eligible indication routes exist;
3. why the claim did not match or could not be decided;
4. the operational risk;
5. the corrective next step;
6. regulatory details only as expandable evidence.

---

## 3. Locked product and domain decisions

These decisions are acceptance constraints, not implementation suggestions.

### 3.1 Correctness precedes presentation

Do not implement a UI-only copy patch. The UI must not construct a stronger or more specific conclusion than the backend evaluation supports.

### 3.2 Indication applicability and supplemental constraints are separate stages

Evaluate in this order:

1. drug-name candidate discovery;
2. diagnosis-input availability;
3. diagnosis-specific indication applicability;
4. route arbitration when multiple diagnosis-matched routes remain;
5. report, duration, specialty, inpatient, biomarker, prior-therapy, response, and dose constraints;
6. structured finding construction.

A generic no-ICD rule must not establish that a drug is indicated for the observed diagnosis.

### 3.3 A mismatch is a family-level finding

When none of the observed diagnoses match any diagnosis-specific route:

- emit one stable `indication_mismatch` finding per drug claim line;
- do not attach one arbitrary candidate rule as the sole cause;
- return every relevant eligible route in deterministic order;
- return all observed claim diagnoses;
- return all relevant SUT sections/regulatory sources;
- keep candidate rule IDs as evidence, not as the finding identity.

### 3.4 Do not claim guaranteed rejection

Primary product language must be:

> Geri ödeme koşulu doğrulanamadı — MEDULA reddi riski.

Do not state “SGK kesin reddeder” unless a later, explicitly approved rule contract proves that stronger conclusion.

### 3.5 Missing data is not mismatch

If diagnosis data is unavailable, emit a missing-input/manual-verification evaluation. Do not emit `indication_mismatch`.

### 3.6 Preserve the dedicated product surface

Drug indication remains `surface="drug_indication"`. Reuse PR #89’s principles—stable identity, one canonical evaluation, pure projection, old-cache honesty—but do not force the broad family into `surface="claim_compliance"` merely to reuse the existing dataclass.

### 3.7 No hardcoded ICD disease names in the frontend

Disease labels may be shown only when supplied by a canonical backend/source mapping. The UI may always show ICD codes. It must not contain local mappings such as `E66.9 → Obezite` embedded in a component.

### 3.8 Existing financial behavior remains unchanged

Drug-indication findings remain nonfinancial:

- no SGK uplift;
- no savings/recovery amount;
- no audit-exposure amount inferred without an approved financial rule;
- no change to billing totals.

### 3.9 Old cache payloads must not crash or become falsely exact

The frontend/API must handle legacy drug-indication rows without the new structured fields. Legacy rows may use a reduced fallback presentation, clearly labeled as lacking structured explanation. A production cache rebuild is a rollout step, not a prerequisite for code safety.

---

## 4. Target domain contract

Create typed models for a canonical drug-indication evaluation. Exact names may follow repository conventions, but the information content is required.

### 4.1 Route evidence

```python
@dataclass(frozen=True)
class DrugIndicationRouteEvidence:
    rule_id: str
    sut_section: str | None
    icd10_codes: tuple[str, ...]
    icd10_ranges: tuple[str, ...]
    regulatory_summary_tr: str
    report_required: bool
    report_duration_months: int | None
    report_specialties: tuple[str, ...]
    prescriber_specialties: tuple[str, ...]
```

Optional label fields may be added only when sourced from canonical rule metadata:

```python
indication_label_tr: str | None
```

### 4.2 Finding

```python
@dataclass(frozen=True)
class DrugIndicationFinding:
    finding_id: str
    patient_id: str
    claim_id: str
    drug_claim_line_id: str
    drug_name: str
    drug_code: str | None
    finding_kind: str
    severity: str
    applicability_status: str
    evaluation_status: str
    observed_icd10_codes: tuple[str, ...]
    matched_icd10_codes: tuple[str, ...]
    unmatched_icd10_codes: tuple[str, ...]
    eligible_routes: tuple[DrugIndicationRouteEvidence, ...]
    selected_rule_id: str | None
    explanation_tr: str
    recommended_action_tr: str
    required_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
```

Required applicability states:

- `eligible`
- `indication_mismatch`
- `missing_diagnosis`
- `ambiguous_route`
- `not_in_encoded_corpus`

Required evaluation states should reuse existing vocabulary where possible:

- `evaluated`
- `missing_inputs`
- `unavailable`

### 4.3 Evaluation batch

```python
@dataclass(frozen=True)
class DrugIndicationEvaluationBatch:
    findings: tuple[DrugIndicationFinding, ...]
    evaluations: tuple[DrugIndicationLineEvaluation, ...]
    legacy_violations: tuple[dict[str, Any], ...]
```

`legacy_violations` is a temporary compatibility projection for `analyze_claim` and `/validate-claim`. It must be generated from the canonical typed result; it must not rerun the detector.

### 4.4 Stable finding identity

Use the drug line and finding kind, not an arbitrarily selected candidate rule:

```text
drug_indication:<patient_id>:<claim_id>:<drug_claim_line_id>:<finding_kind>
```

URL-quote every component as PR #89 does for claim-compliance identities. The same ID must survive patient report, cache, cohort index, deep link, and UI.

---

## 5. Target evaluation algorithm

### 5.1 Candidate discovery

For each drug claim line:

1. normalize and collect all claim diagnoses from header and normalized `ClaimDiagnosis` rows;
2. collect every rule matching the drug/INN/commercial name;
3. partition candidates into:
   - diagnosis-specific routes: have `icd10_codes` and/or `icd10_ranges`;
   - supplemental constraints: no ICD selector;
4. preserve deterministic corpus order or an explicit stable sort.

### 5.2 No drug candidate

If no encoded drug-name rule exists:

- do not fabricate a violation;
- record `applicability_status="not_in_encoded_corpus"`;
- preserve honest partial coverage;
- expose a review state only if product requirements call for it.

### 5.3 Diagnosis unavailable

If diagnosis-specific routes exist but no diagnosis input is available:

- do not select a route;
- do not emit `indication_mismatch`;
- record `missing_diagnosis` / `missing_inputs`;
- set block exactness according to the aggregate rules in Section 6.

### 5.4 No diagnosis-specific route matches

If observed diagnoses exist and none match any diagnosis-specific candidate:

- emit one `indication_mismatch` finding for the drug line;
- include all observed diagnoses;
- include all eligible diagnosis-specific routes;
- include zero matched diagnoses;
- do not evaluate report duration, specialty, ACR/DAS28, biomarker, prior therapy, or dose as the primary issue;
- do not select a generic no-ICD rule as the explanation.

### 5.5 One or more routes match

If diagnosis-specific candidates match:

1. restrict the route pool to those matched candidates;
2. use available structured fields to resolve duration/specialty/biomarker/prior-therapy/dose distinctions;
3. if exactly one route is deterministically applicable, evaluate its supplemental constraints;
4. if multiple routes remain and required discriminators are missing, emit `ambiguous_route` / review—not an arbitrary violation;
5. evaluate generic no-ICD constraints only after diagnosis applicability is established and only when their drug/family applicability is justified by existing metadata.

Do not silently infer that every no-ICD rule is universal. If applicability cannot be justified, retain it as review evidence rather than a confirmed violation.

### 5.6 Explanation generation

The primary explanation must be generated from the structured result. For `indication_mismatch`, the Turkish template should be semantically equivalent to:

> Faturada {observed_codes} tanıları bulundu. {drug_name} için kodlanmış SGK geri ödeme yolları {eligible_codes_or_ranges} tanılarını kapsıyor. Mevcut tanılar bu yollarla eşleşmiyor.

Recommended action:

> Tanı kodunu, ilaç–hasta/fatura eşleşmesini ve ilgili sağlık kurulu raporunu kontrol edin. Endikasyon dışı veya istisnai kullanım varsa manuel değerlendirin.

Regulatory `message_tr` remains evidence under the route, not the primary error explanation.

---

## 6. Block exactness rules

Update `validate_drug_indication_from_claims()` projection semantics:

| Situation | Block status |
| --- | --- |
| No drug lines | `not_applicable` |
| Every drug line decisively evaluated | `exact` |
| Some lines evaluated; others missing/ambiguous | `partial_exact` |
| Drug lines exist but none can be evaluated due missing required input | `missing_exact_inputs` |
| Required source/corpus unavailable | existing unavailable semantics |

Keep corpus status separate in `coverage_scope`:

- `prose_engine_status="partial"` may coexist with input `exactness_status="exact"` for a line that is decisively evaluated against encoded routes;
- the UI must not imply complete §4.2 corpus coverage.

---

## 7. Implementation tasks

### Task 1 — Lock cross-rule shadowing regressions

**Objective:** Reproduce the current false route selection using the complete rule corpus before changing production behavior.

**Files:**
- Modify: `tests/unit/domain/prose_rules/test_drug_indication.py`
- Modify or create focused test: `tests/unit/domain/prose_rules/test_drug_indication_4201.py`
- Modify: `tests/unit/domain/billing/test_claim_drug_indication.py`

**Required RED scenarios:**

1. Orencia/abatacept + `E66.9` with complete corpus:
   - must become `indication_mismatch`;
   - must not become `needs_report_verification`;
   - eligible routes include M05/M06 and M08 evidence.
2. Orencia/abatacept + `T13.2`:
   - same protection against generic-rule shadowing.
3. Orencia/abatacept + missing diagnosis:
   - must be missing-input/review;
   - must not be mismatch.
4. Multiple diagnoses where one matches M06:
   - must not emit indication mismatch.
5. The result’s observed codes must not be described as matched codes.
6. Complete-corpus tests must be used; do not inject a single isolated rule and thereby hide cross-rule arbitration defects.

**RED command:**

```bash
/opt/Bilun/.venv/bin/python -m pytest -o addopts='' -q \
  tests/unit/domain/prose_rules/test_drug_indication.py \
  tests/unit/domain/prose_rules/test_drug_indication_4201.py \
  tests/unit/domain/billing/test_claim_drug_indication.py
```

Expected before implementation: new regressions fail for route selection, exactness, or missing structured fields.

**Suggested commit:**

```text
test(drug-indication): lock cross-rule applicability regressions
```

---

### Task 2 — Introduce typed canonical evaluation models

**Objective:** Replace the unstructured result bag as the source of truth while retaining temporary legacy serialization.

**Files:**
- Create: `src/bilun/domain/billing/drug_indication_findings.py`
- Modify: `src/bilun/domain/billing/types.py`
- Test: `tests/unit/domain/billing/test_drug_indication_findings.py`

**Steps:**

1. Add route evidence, line evaluation, finding, and batch dataclasses.
2. Implement stable URL-quoted finding identity.
3. Add deterministic serialization helpers.
4. Add compatibility projection to the current violation dict shape.
5. Prove identity differs by drug line and finding kind.
6. Prove every financial field remains absent/null and excluded from totals.
7. Prove route lists and diagnosis lists serialize deterministically.

**Important boundary:** Do not generalize PR #89’s `RuleFinding` into an all-purpose platform unless required by a failing test. Mirror its invariants without destabilizing the already-merged claim-compliance contract.

**Suggested commit:**

```text
refactor(drug-indication): add canonical typed finding contract
```

---

### Task 3 — Separate applicability from supplemental constraints

**Objective:** Correct rule arbitration in the §4.2 evaluator.

**Files:**
- Modify: `src/bilun/domain/prose_rules/drug_indication.py`
- Modify as needed: `data/gazette/prose_rules/drug_indication_prose.schema.json`
- Test: existing `tests/unit/domain/prose_rules/test_drug_indication*.py`

**Steps:**

1. Extract helpers for:
   - observed diagnosis collection;
   - drug-name candidate collection;
   - diagnosis-specific route detection;
   - route evidence construction;
   - matched-route selection;
   - supplemental-constraint evaluation.
2. Remove the semantic use of “no ICD selector means diagnosis matched.”
3. Ensure no-ICD rules cannot mask mismatch.
4. Return all eligible diagnosis-specific routes on mismatch.
5. Resolve one route only when structured inputs justify the selection.
6. Return an ambiguous/manual-review result when multiple routes remain unresolved.
7. Preserve existing successful biomarker, prior-therapy, dose, duration, specialty, and report tests.
8. Keep existing legacy `evaluate_drug_indication_line()` callers working through a compatibility projection until Task 4 rewires them.

**Do not:**

- delete generic no-ICD rules;
- rewrite the 968-rule corpus;
- add hardcoded Orencia-specific branching;
- use file order as a medical applicability decision;
- convert missing diagnosis to mismatch.

**Suggested commit:**

```text
fix(drug-indication): separate indication routes from report constraints
```

---

### Task 4 — Establish one canonical family evaluator and pure projections

**Objective:** Remove the independent analyzer→patient-adapter execution relationship recorded by the PR #89 audit.

**Files:**
- Modify: `src/bilun/domain/billing/drug_indication_findings.py`
- Modify: `src/bilun/domain/billing/engine.py`
- Modify: `src/bilun/domain/billing/claim_drug_indication.py`
- Modify: `src/bilun/domain/billing/patient_report.py`
- Test: `tests/unit/domain/billing/test_drug_indication_findings.py`
- Test: `tests/unit/domain/billing/test_claim_drug_indication.py`
- Test: `tests/unit/domain/test_rule_engine_validate_claim.py`

**Target flow:**

```text
PatientClaimContext
  → evaluate_drug_indication_findings()
  → DrugIndicationEvaluationBatch
      ├─ legacy analyzer projection
      ├─ DrugIndicationReview projection
      ├─ recommended-action projection
      └─ cache/cohort projection
```

**Steps:**

1. Add one canonical evaluator for the family.
2. Make `analyze_claim()` consume the canonical batch’s legacy projection instead of calling `check_drug_indication_for_context()` directly.
3. Make `validate_drug_indication_from_claims()` a pure projection from a supplied batch.
4. Have `compute_patient_billing_report()` evaluate the family once and pass the batch to the projection.
5. Preserve standalone callers by allowing a projection wrapper to evaluate only when no batch is supplied; add tests proving the billing path evaluates once.
6. Preserve `/validate-claim` compatibility.
7. Remove direct duplicate detector execution from the patient billing path.

**Acceptance:** A spy test must prove one drug-indication family evaluation per billing-report computation.

**Suggested commit:**

```text
refactor(drug-indication): reuse one canonical evaluation batch
```

---

### Task 5 — Type the billing and API response

**Objective:** Carry structured applicability evidence without relying on permissive dictionaries.

**Files:**
- Modify: `src/bilun/domain/billing/types.py`
- Modify: `src/bilun/api/schemas.py`
- Modify: `src/bilun/api/routes/billing.py` if serialization changes require it
- Modify tests under: `tests/unit/api/`

**Steps:**

1. Replace `DrugIndicationReview.violations: list[dict]` with a typed serializable finding list, or introduce a typed parallel field with a bounded compatibility period.
2. Add Pydantic models for finding, route evidence, and evaluation state.
3. Preserve unknown legacy fields only where old-cache compatibility requires it.
4. Include both `sut_section` compatibility and structured `regulatory_sources` during the transition.
5. Deprecate `matched_icd10_codes` as the observed-code field; serialize `observed_icd10_codes` explicitly.
6. Keep a temporary alias only if an existing consumer test proves it is necessary.
7. Validate old cached payloads without fabricating structured routes or `exact` status.

**API acceptance cases:**

- structured mismatch payload;
- structured missing-input payload;
- structured matched-route/report violation;
- old cache payload;
- no drug-line not-applicable payload.

**Suggested commit:**

```text
fix(api): expose structured drug indication evidence
```

---

### Task 6 — Repair recommended-action and cohort projection

**Objective:** Ensure the cohort/index view receives meaningful detail and stable identity.

**Files:**
- Modify: `src/bilun/domain/billing/billing_actions.py`
- Modify: `src/bilun/domain/billing/cohort_compliance.py` only if the generic action projection cannot carry required fields
- Modify: `tests/unit/domain/billing/test_cohort_compliance.py`
- Modify relevant billing-action tests

**Steps:**

1. Use the canonical `finding_id` as `action_id`.
2. Populate:
   - drug code/name;
   - `detail` from `explanation_tr`;
   - SUT/regulatory source from structured route evidence;
   - severity and evaluation status;
   - claim and drug line identity.
3. Preserve null money fields.
4. Preserve deep links from cohort row to the exact patient drug finding.
5. Ensure multiple drug lines in one claim do not collapse into one action.
6. Ensure old-cache rows remain readable but are not falsely enriched.

**Suggested commit:**

```text
fix(compliance): preserve drug indication evidence in projections
```

---

### Task 7 — Build explanation-first Drug Indication UI

**Objective:** Replace the raw implementation table with an actionable user explanation.

**Files:**
- Modify: `frontend/src/lib/domains/sut.ts`
- Modify: `frontend/src/components/patient/SutBillingReportSections.tsx`
- Modify: `frontend/src/components/patient/SutBillingReportSections.test.tsx`
- Modify: `frontend/src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx` if cohort detail needs structured rendering
- Modify: `frontend/src/messages/tr/billing.ts`
- Modify: `frontend/src/messages/en/billing.ts`
- Modify related compliance-dashboard tests

**Primary presentation:**

For every finding, show:

1. **Title:** e.g. `Tanı–ilaç eşleşmesi bulunamadı`
2. **Drug:** commercial name/INN and available code
3. **Observed diagnoses:** every code evaluated, not only primary ICD
4. **Eligible routes:** ICD code/range + optional sourced label + SUT section
5. **Explanation:** structured reason, not raw regulatory prose
6. **Next action:** claim/diagnosis/report verification instruction
7. **Risk label:** `Geri ödeme koşulu doğrulanamadı — MEDULA reddi riski`
8. **Evaluation certainty:** exact, partial, missing input, or manual review

**Expandable technical details:**

- candidate and selected rule IDs;
- regulatory summaries (`message_tr`);
- report duration/specialties;
- missing inputs;
- source/coverage scope;
- raw technical kind only for debugging/advanced review.

**Remove from primary view:**

- untranslated `indication_mismatch`;
- a single internal rule ID as the explanation;
- raw ACR/DAS28 prose unrelated to the actual failure;
- guaranteed rejection wording;
- “matched” terminology for merely observed diagnoses.

**Legacy fallback:**

If structured fields are absent, render the existing message under a clearly labeled legacy/technical detail state. Do not crash and do not infer eligible diagnoses in the browser.

**Required frontend cases:**

1. structured indication mismatch with multiple eligible routes;
2. missing diagnosis/manual verification;
3. matched route with missing board report;
4. ambiguous route;
5. legacy cache row;
6. empty/not-applicable block;
7. partial-exact block shows exactness notice;
8. deep link selects the exact drug-line finding.

**Suggested commit:**

```text
feat(ui): explain drug indication findings and next actions
```

---

### Task 8 — Full-corpus, integration, and financial-invariance verification

**Objective:** Prove the fix does not regress the existing 4.2 corpus or financial outputs.

**Files:**
- Modify/add tests only as required by failures
- Do not modify rule corpus merely to make tests green unless a source-backed corpus defect is separately identified

**Backend focused suite:**

```bash
/opt/Bilun/.venv/bin/python -m pytest -o addopts='' -q \
  tests/unit/domain/prose_rules/test_drug_indication*.py \
  tests/unit/domain/billing/test_drug_indication_findings.py \
  tests/unit/domain/billing/test_claim_drug_indication.py \
  tests/unit/domain/test_rule_engine_validate_claim.py
```

**Billing/API projection suite:**

```bash
/opt/Bilun/.venv/bin/python -m pytest -o addopts='' -q \
  tests/unit/domain/billing/test_cohort_compliance.py \
  tests/unit/api/test_claim_compliance_pipeline.py \
  tests/unit/api/test_compliance_index_api.py
```

**Financial invariance:**

Add explicit before/after assertions proving drug-indication findings do not modify:

- `sgk_uplift_try`;
- `compliance_adjustment_try`;
- `audit_exposure_try`;
- `total_recoverable_try`;
- existing material, copay, or pricing totals.

**Frontend:**

```bash
cd /opt/Bilun/frontend
npx vitest run \
  src/components/patient/SutBillingReportSections.test.tsx \
  src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx \
  src/lib/workspaceViews.test.ts
npx tsc --noEmit
```

**Static checks:**

```bash
cd /opt/Bilun
/opt/Bilun/.venv/bin/python -m compileall -q \
  src/bilun/domain/prose_rules/drug_indication.py \
  src/bilun/domain/billing/drug_indication_findings.py \
  src/bilun/domain/billing/claim_drug_indication.py
/opt/Bilun/.venv/bin/ruff check \
  src/bilun/domain/prose_rules/drug_indication.py \
  src/bilun/domain/billing/drug_indication_findings.py \
  src/bilun/domain/billing/claim_drug_indication.py \
  src/bilun/domain/billing/billing_actions.py
git diff --check
```

**Suggested commit:**

```text
test(drug-indication): verify full-corpus and financial invariants
```

---

### Task 9 — Refresh PR #89 surfacing audit in a separate commit

**Objective:** Prove the 968-ID independent rerun relationship is removed or accurately reclassified without burying the production review.

**Files:**
- Modify: `scripts/audits/build_rule_surfacing_inventory.py` only if the canonical drug evaluator requires discovery metadata
- Regenerate:
  - `reports/rule-engine-surfacing/2026-09-18-rule-surfacing-matrix.json`
  - `reports/rule-engine-surfacing/2026-09-18-rule-surfacing-audit.md`
- Modify tests: `tests/unit/scripts/test_rule_surfacing_inventory.py`

**Requirements:**

1. The audit discovers the canonical drug-indication evaluator.
2. Analyzer and patient/cohort projections reference the same canonical family output.
3. The 968-ID direct rerun relationship is removed or replaced by an explicit canonical-evaluator relationship.
4. Patient and cohort visibility remain intact.
5. Financial semantics remain `unpriced_compliance` and excluded from totals.
6. Generated artifacts are committed separately from production code.

**Commands:**

```bash
cd /opt/Bilun
/opt/Bilun/.venv/bin/python -m pytest -o addopts='' -q \
  tests/unit/scripts/test_rule_surfacing_inventory.py
/opt/Bilun/.venv/bin/python scripts/audits/build_rule_surfacing_inventory.py --write
/opt/Bilun/.venv/bin/python scripts/audits/build_rule_surfacing_inventory.py --check
git diff --check
```

**Suggested commit:**

```text
docs(audit): refresh drug indication surfacing inventory
```

---

## 8. Required regression matrix

| Scenario | Expected applicability | Expected finding |
| --- | --- | --- |
| Orencia + E66.9 | no eligible route | `indication_mismatch`, M05/M06/M08 evidence |
| Orencia + T13.2 | no eligible route | `indication_mismatch`, no generic report-rule shadowing |
| Orencia + M06.9 | RA route matched | evaluate RA report/prior-therapy constraints |
| Orencia + M08.x | JIA route matched | evaluate JIA route; do not show RA requirements |
| Orencia + M06.9 + M08.x | multiple routes matched | resolve from structured fields or `ambiguous_route` |
| Orencia + no diagnosis | unknown | missing-input review, not mismatch |
| Drug with no encoded corpus candidate | not in corpus | honest noncoverage/manual state, not clean compliance |
| Correct route + report absent | eligible indication | `missing_board_report` |
| Correct route + report status unknown | eligible indication | `needs_report_verification` |
| Correct route + wrong report duration | eligible indication | `report_duration_mismatch` |
| Correct route + wrong prescriber specialty | eligible indication | `prescriber_specialty_mismatch` |
| Multiple diagnoses, one eligible | eligible | no indication mismatch |
| Old cached violation dict | legacy | safe fallback UI, no crash |
| No drug lines | not applicable | no section/finding |

Add at least one complete-corpus regression for every drug family where the same name has both diagnosis-specific and no-ICD generic rules. Isolated single-rule fixtures are insufficient for arbitration coverage.

---

## 9. Merge gates

Do not merge until all are true:

### Domain correctness

- [ ] No-ICD generic rules cannot establish diagnosis applicability.
- [ ] Unrelated diagnosis + abatacept produces structured mismatch, not report verification.
- [ ] Missing diagnosis is distinguished from mismatch.
- [ ] All observed diagnoses are evaluated.
- [ ] Multiple eligible routes are represented without arbitrary file-order selection.
- [ ] Existing biomarker, prior-therapy, dose, duration, specialty, and report behavior remains green.

### Canonical architecture

- [ ] Drug indication has one canonical typed evaluator.
- [ ] Billing report does not execute the family twice.
- [ ] Analyzer compatibility is a projection from canonical results.
- [ ] Stable finding identity survives patient/cohort/deep-link paths.
- [ ] PR #89 audit no longer records the old 968-ID independent direct rerun.

### API/cache

- [ ] Typed route and diagnosis evidence is serialized.
- [ ] Legacy cache payloads remain readable.
- [ ] Legacy payloads are not falsely upgraded to structured/exact findings.
- [ ] No database schema migration is required unless independently justified.

### UI

- [ ] Primary message states observed vs eligible diagnoses.
- [ ] User sees a corrective next action.
- [ ] Risk language is bounded and does not guarantee rejection.
- [ ] Raw rule IDs/prose are secondary expandable evidence.
- [ ] Partial/missing-input states are visually distinct from confirmed mismatch.
- [ ] No hardcoded ICD disease labels are introduced in React components.

### Financial and regression safety

- [ ] Financial totals are unchanged.
- [ ] Full drug-indication corpus suite passes.
- [ ] Billing/API integration suite passes.
- [ ] Frontend focused tests and TypeScript pass.
- [ ] Ruff, compileall, audit generator check, and `git diff --check` pass.

---

## 10. Non-goals

This implementation must not:

- add new §4.2 rules merely to increase corpus count;
- complete the R5 §4.2 encoding tail;
- implement the next Wave A detector slice;
- implement Wave B taxonomy;
- manufacture Wave C work where no accidental duplicates exist;
- expose Wave D aggregate-only financial rows;
- change SGK uplift/recovery calculations;
- add a frontend-only diagnosis dictionary;
- claim the partial §4.2 corpus is complete;
- guarantee MEDULA rejection;
- rebuild or deploy the production cache without a separate rollout decision;
- mix the generated 8k+ audit matrix into the production-code commit.

---

## 11. Recommended commit structure

1. `test(drug-indication): lock cross-rule applicability regressions`
2. `refactor(drug-indication): add canonical typed finding contract`
3. `fix(drug-indication): separate indication routes from report constraints`
4. `refactor(drug-indication): reuse one canonical evaluation batch`
5. `fix(api): expose structured drug indication evidence`
6. `fix(compliance): preserve drug indication evidence in projections`
7. `feat(ui): explain drug indication findings and next actions`
8. `test(drug-indication): verify full-corpus and financial invariants`
9. `docs(audit): refresh drug indication surfacing inventory`

Keep commits reviewable and do not squash during implementation. The final PR may be squash-merged after review if desired.

---

## 12. Work after this plan

After this PR is merged and verified:

1. select the next bounded Wave A slice of three to five exact-ID nonfinancial detectors;
2. use the PR #89 generic transport rather than adding surface-specific allowlists;
3. scope remaining independent rerun families separately, beginning with material precheck families;
4. write a Wave D product/financial decision memo;
5. rescope Wave B by product meaning;
6. leave Wave C closed unless a refreshed audit finds an actual accidental duplicate or financial double-count risk.

The immediate next implementation is this drug-indication correctness plan—not broad rule expansion.
