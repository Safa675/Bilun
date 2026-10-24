---
title: "BILUN Algorithm Reference"
aliases: ["algorithms-reference", "algorithms"]
tags: [core-system, algorithms, sut, billing, optimization]
type: core-system
status: provisional
related: ["[[sut]]", "[[gazette]]"]
---

# BILUN Reimbursement Intelligence: Algorithm Reference

## Overview

BILUN is a healthcare reimbursement intelligence system for Turkish public hospitals. It analyzes claims against the official SGK/SUT (Sağlık Uygulama Tebliği — Health Implementation Communique) regulations. The system has three layers of algorithmic logic:

1. **Claim Validation Rules** — pre-submission compliance check (is this claim legally billable?)
2. **Revenue Optimization Rule Engines** — post-hoc cohort analysis for revenue recovery
3. **Billing Optimization Algorithms** — proactive per-patient billing strategy recommendations

All algorithms are grounded in the official Turkish gazette annexes (EK-1A through EK-4A). Nothing is invented — every rule traces back to a specific gazette publication.

---

## Layer 1: Claim Validation Rules

These rules answer: **Is this claim compliant with SUT, or will SGK reject/underpay it?**

They run *before* claim submission to SGK. The inputs are the claim's material line items.

### Architecture

```
claim materials → [Bundling Rules] + [Exclusion Rules] → ClaimValidationResult
```

### 1.1 EK-3B-1 Bundling Rule

**Gazette anchor:** EK-3/B-1 — 54 consumable items bundled into procedure prices.

**What it does:** Detects consumables that were billed as separate line items but should have been included in the procedure fee. These are simple, low-cost items (syringes, gloves, scalpel tips, antiseptic solutions, etc.) grouped into ~7 categories that the SUT explicitly says the hospital must supply at its own expense. SGK will not pay for them as separate items.

**How it works:**
1. Loads the 54 EK-3B-1 bundled consumable categories from the curated parquet catalog.
2. For each material in the claim, Turkish-normalizes its name and checks against the bundled list using two matching strategies:
   - **Substring match (both directions):** The material name contains the bundled category name, or vice versa.
   - **Fuzzy match:** If substring matching fails, applies a fuzzy string distance check with an 80% similarity threshold.
3. Each match is flagged as a violation. The billed amount for the matched material line becomes potential savings.
4. Violations where billed amount > 50 TRY are classified as "error" severity; below that, "warning."

**Business meaning:** If a hospital bills antiseptic solution at 5 TRY per unit in a procedure line, and the EK-3B-1 says antiseptics are bundled, that 5 TRY is unrecoverable and should be removed from the claim before submission. Otherwise SGK may reject the entire claim or claw it back in an audit.

### 1.2 EK-3B-2 Exclusion Rule

**Gazette anchor:** EK-3/B-2 — 13 entries of non-reimbursable materials (curated `ek3b2_non_reimbursable.parquet`).

**What it does:** Detects materials in the claim that SGK will *never* reimburse, regardless of how they're billed. These are items like viscosupplementation products, sports prostheses, stem cell materials, etc.

**How it works:**
1. Loads the EK-3B-2 non-reimbursable catalog.
2. For each material in the claim, checks if it matches any exclusion entry via Turkish-normalized substring matching.
3. If direct match fails, applies fuzzy matching at 80% threshold.
4. Matched items are flagged as "exclusion" violations with "error" severity.
5. The billed amount becomes the **risk amount** — money the hospital will lose if the claim is submitted as-is.

**Business meaning:** This is the strongest SUT enforcement rule. If a material is in EK-3B-2, SGK simply will not pay. The hospital must either absorb the cost or bill the patient directly (if legally permissible). The rule catches these *before* submission so the hospital can decide whether to proceed.

### 1.4 §3.1–3.2 Material Bundling Prose (PARTIAL)

**Registry:** `material_bundling_prose` — status **partial** (`data/gazette/prose_rules/material_bundling_prose.json`).

SUT §3.1–3.2 contains hundreds of material payment and non-separate-billing clauses. BILUN runs a wired prose engine (`prose_engine_status: implemented`, `prose_coverage_tier: partial`) with keyword and claim-field rules — not the full 301+ clause engine. Product surfaces show a coverage version string; long tail is in `plans/billing/material-bundling-prose-p2-plan.md`.

**Implemented today (23 rules):**
- Keyword rules: §3.1.3(7)–(9), §3.1.2(c)/(ç)/(d), barcode mismatch, lost/stolen MIAT, non-reimbursed procedure materials, device consumable, branch-unlisted, etc.
- Claim-field rules: missing code, `not_in_ek3c` / `not_in_ek3`, procedure pairing, TİTUBB/ÜTS incomplete, procurement screen, foreign facility, facility restriction, diagnosis-bundled MEDULA, **`3.1.1.(15).separate_billing_not_authorized`** (§3.1.1(13), C002751), etc.
- **KDV pricing (tail):** `src/bilun/domain/pricing/material_kdv.py` — §3.1.1(10), C002748; `kdv_price_reviews` on `precheck_materials_from_claims()`.
- **EK-3 allow-list (tail):** `ek3_separate_billing_allowed_codes()` in `catalog_lookup.py` — C001823 catalog scan.
- Synthetic demo ingest: prose flag columns on `material_claim_lines.parquet` (2026-06-03).
- `validate_claim()` third pass; `precheck_materials_from_claims()` → `prose_bundling_violations` (separate from EK-3B-1 `is_bundled`).
- **MEDULA:** classified **additive** for prose + EK-3B paths (`docs/medula/material_bundling_medula_boundary.md`). Prose hits are pre-submission risk flags, not guaranteed SGK recovery.

**What remains:** full §3.1–3.2 corpus (beyond 23 encoded rules); tier/care-setting in prose evaluator; optional MEDULA ICU-group / barcode API integration.

### 1.3 Claim Validation Orchestrator

**Entry point:** `rule_engine.py` — `validate_claim()`

Runs both annex list rules in sequence and aggregates results into a single `ClaimValidationResult` (not full §3.1–3.2 prose — see §1.4):
- `is_valid`: False if any violation has "error" severity.
- `total_savings_try`: Sum of bundling violation amounts (money being billed that shouldn't be).
- `total_risk_try`: Sum of exclusion violation amounts (money SGK will not cover).
- Also computes material cost estimates against gazette prices for each line item.

---

## Layer 2: Revenue Optimization Rule Engines (20 Billing Blocks)

These rules operate at the **cohort level** and answer: **How much money is the hospital leaving on the table across all patients?**

They are designed for revenue recovery dashboards — they scan patient populations to find systematic billing opportunities.

The billing report (`BillingActionReport`) is composed of 20 billing blocks, each driven by a
dedicated detector. The canonical list lives in `src/bilun/domain/billing/block_registry.py`
(`BILLING_BLOCK_SPECS`) — that tuple is the single source of truth and includes: lab optimization,
copay exemption, billing strategy (package vs itemized), session uplift, DRG uplift, blood
component uplift, yatak/icu/yenidogan/refakatci/anestezi puanları, material uplift, procedure
addon uplift, care-setting review, DRG package adequacy, procedure capture
gap, MEDULA rejection playbook, claim submission checklist, and drug indication review.

### Architecture

```
patient ICD-10 diagnoses + claim dataset → 20 billing block detectors → BillingActionReport → cohort summary
```

There is a critical runtime concept: **exactness.** Each rule engine declares what inputs it needs. If the data is available (exact claim lines from the hospital's billing system), the output is tagged `exact`. If only gazette catalogs are available without patient-specific claim data, the output is tagged `missing_exact_inputs` and the result is intentionally minimal. This prevents the system from fabricating numbers.

### 2.1 Copay Exemption Checker (EK-1A)

**Gazette anchor:** EK-1A — chronic disease copayment exemption. SUT clause 1.8.1.

**What it does:** Identifies patients who should be exempt from outpatient copayment (katılım payı) because they have a qualifying chronic disease. Turkish law waives copays for patients with specific chronic conditions.

**How it works:**
1. Loads the EK-1A exemption catalog: 98 ICD-10 ranges (32 multi-code ranges + 66 single-code entries) covering diseases like diabetes, hypertension, COPD, cancer, etc.
2. **Pre-indexing optimization:** Groups the 98 ranges by ICD-10 chapter letter (A-Z) for O(1) lookup — only ranges matching the first letter of a diagnosis code are checked.
3. **Per-patient evaluation:** For each patient, their diagnoses are checked against the letter-indexed EK-1A catalog. The letter filter narrows the search to only the ranges matching each diagnosis code's chapter letter, then numeric range comparison determines a match.
4. **ICD-10 range matching:** Uses a structured algorithm that compares numeric portions of codes within the same letter family. For example, range "A15-A19" matches codes A15, A16, A16.2, A17, A17.9, A18, A19. Single codes (e.g., "C34") match the exact code and all sub-codes (C34.1, C34.9, etc.).
5. Per-patient: if any of the patient's diagnoses match, the patient is marked `exempt = True`.

**Business meaning:** Hospitals may be collecting copayments from patients who are legally exempt. This is both a patient-experience issue and a potential compliance liability. The algorithm identifies these patients so the hospital can stop charging them and potentially refund past charges.

### 2.2 Surcharge Eligibility (EK-2G)

**Gazette anchor:** EK-2G — procedures where additional surcharge fees are prohibited.

**What it does:** Identifies procedures where the hospital is prohibited from charging the patient any additional fee (ilave ücret) above the SGK base rate.

**How it works:**
1. Loads EK-2G: 213 procedures with surcharge prohibitions.
2. Requires exact claim lines to operate (cannot be inferred from ICD-10 codes alone — needs procedure codes and service dates).
3. When exact claim lines are available: joins procedure codes to EK-2G via `optimization/catalog_join.py` (catalog-authoritative prohibition list) and compares against the `surcharge_applicable` flag on each line.
4. When exact data is unavailable: returns a structured "missing exact inputs" payload with the specific reason and what's needed.

**Business meaning:** Many hospitals add surcharges to certain procedures to increase revenue. But EK-2G bans this for 213 specific procedures. Billing a surcharge on a prohibited procedure can trigger SGK audit penalties. The algorithm identifies exposure so the hospital can correct its billing.

### 2.3 Copay Rate Eligibility (EK-2C-1)

**Gazette anchor:** EK-2C-1 — 465 procedures with explicit copayment rate percentages.

**What it does:** Identifies procedures that have a gazette-mandated copay rate (ranging from 20% to 100%) and validates whether the billed amounts match the expected rates.

**How it works:**
1. Loads EK-2C-1: 465 procedures with their mandated copay rate percentages.
2. Like surcharge, requires exact claim lines with `copay_rate_applicable` flags and billed/payable amounts.
3. When exact data is available: joins billed procedure codes to EK-2C-1 via `catalog_join.py`, validates `copay_rate_applicable` flags and billed/payable ratios against gazette rates.
4. Computes a cohort-level mean copay rate and distribution histogram.

**Business meaning:** SUT mandates specific copay percentages for specific procedures. If a hospital bills a different copay rate, SGK may reject or adjust the payment. This rule engines identifies mismatches at scale.

### 2.4 Temporal Price Validation (EK-2B/2C History)

**Gazette anchor:** EK-2B (fee-for-service procedure pricing) and EK-2C (DRG package pricing) across all historical amendment dates.

**What it does:** Tracks how procedure prices have changed over time across gazette amendments. This is a system-level audit, not per-patient.

**How it works:**
1. Loads the full temporal history of EK-2B and EK-2C catalogs — every effective date and price for every code.
2. For each code in EK-2B (fee-for-service procedures): compares the first published price to the last published price across all amendment dates. Computes delta percentage.
3. For each package code in EK-2C (diagnosis-based packages): same comparison on package prices.
4. Produces statistics: number of codes with price changes, mean delta percentage, top 10 price increases and decreases, change rate per code.

**Business meaning:** This is an audit/strategic tool. If SGK's price for a high-volume procedure dropped by 15% in a recent amendment, the hospital's revenue projections are now wrong. The temporal audit identifies which codes to worry about and which amendments caused the shift.

### 2.5 DRG Unbundling Detection (EK-2C Package Rules)

**Gazette anchor:** EK-2C — diagnosis-related group package pricing.

**What it does:** Detects when a hospital bills procedures individually (itemized) that should be grouped into a single DRG package payment — or the reverse, when a package is being billed but itemized billing would yield higher revenue.

**How it works:**
1. Requires exact claim lines (needs `package_candidate` flags, `is_package_included` flags, `procedure_category` classifications, and `expected_payable_try` amounts).
2. For each claim flagged as a package candidate:
   - **Bundled-line violations:** Identifies procedure lines marked `is_package_included` that were billed separately with a positive billed amount. These are services that the package price already covers. Savings = billed amount - expected payable.
   - **Package vs itemized comparison:** Computes the total expected payable if billed itemized vs. if billed as a package. If itemized > package, the hospital is losing money by staying itemized. If package > itemized, the hospital is over-billing and at audit risk.
3. **Same-session point factors (§2.2.2.B / §2.2.2.A(5)):** Flags secondary procedures billed above allowed fractions. Each line is priced by how it was billed: lines billed as packages (`paket` or a `P` code) take §2.2.2.B(3)(a)/(b) 25%/50%; hizmet başı lines take §2.2.2.A(5) 30%/50%, even when the code is also an EK-2/C package; package plus hizmet başı lines take §2.2.2.B(3)(c)/(ç), with the A(5) fallback when the EK-2/B line has the highest puan. A session holds procedures only (`session_scope.py`, #261): EK-2/B §6 operations (600000–629999), every EK-2/C package with an işlem grubu (A1–E) and the EK-2/B code with the same number (catheter angiography and PCI, pacemaker/ICD, ERCP, RFT, transplants), and the §7/§8 codes SGK's Fatura İnceleme guide prices under A(5) (GİS endoscopy, interventional radiology). Beds, visits, ER and general interventions, anaesthesia, labs, diagnostic imaging, blood and the per-day EK-2/C care packages are never session lines; other interventional EK-2/B codes (e.g. incisional §3 codes) await the include list. `cross_specialty` adds +25 percentage points to secondary factors; it is auto-detected when two operations carry different known branches (`procedure_specialty_code`); a line without a branch neither adds nor cancels a specialty. The EK-2/C işlem grubu is not a specialty (`session_specialty.py`, #264). A secondary's expected amount is its factor times its list price in force on its procedure date (`line_gazette_list_billed_try`): the EK-2/C package price for a package line, +30% for a starred package at the tiers C000678 names (training and research hospitals, university hospitals with a medical faculty), and the EK-2/B price for the rest; never the bill's unit price, since MEDULA returns an operation's amount after the reduction, so a unit price may already hold it (#300). A code without a list price that day is not assessed.
4. Aggregates findings by ICD-10 chapter; `patient_icd10_chapters` from diagnoses union claim chapters for `n_chapters_analyzed`.
5. Returns per-patient: unbundling risk, sourced vs heuristic savings split, and chapter breakdown.

**Business meaning:** DRG packages are the SUT's way of controlling costs. The hospital gets a fixed payment for everything related to a diagnosis episode — no matter how many individual services were performed. If the hospital itemizes things that should be in the package, SGK rejects the extra lines. If the hospital uses the package when individual billing would pay more, they're losing revenue. This algorithm tells hospitals which direction to go.

### 2.6 Cohort Aggregator (`compute_optimization_summary`)

**Entry point:** `optimization/aggregator.py`

Runs all 5 features across a patient cohort in a single pass and produces a unified optimization summary:
- **Copay exemptions:** Exemption rate, top diseases triggering exemptions.
- **Surcharge exposure:** Total EK-2G procedures, surcharge application rate, patients with flags.
- **Copay rate exposure:** Total EK-2C-1 procedures, procedure rate distribution, mean rate.
- **Temporal prices:** Full EK-2B/2C price change audit (cached).
- **DRG unbundling:** Patients with risk, total potential savings, riskiest ICD-10 chapters.

**Note:** EK-4A remains a catalog reference (`materials/drugs.py`, `/api/drugs`). Drug copay rules live in §1.8 + EK-4/D on claim lines — not a separate optimizer.

---

## Layer 3: Billing Optimization Algorithms (4 Algorithms)

These algorithms produce actionable, per-patient recommendations. They answer: **What should this specific hospital do differently for this specific patient?**

They run on the billing pipeline and feed into the revenue recovery dashboard.

### Architecture

```
patient data (labs, diagnoses, claim lines) → 4 parallel algorithms → BillingActionReport → CohortRecoverySummary
```

The orchestrator also assigns a **priority** (high/medium/low) to each patient based on their total recoverable amount relative to the cohort's P50 and P75 percentiles. Patients above P75 get "high" priority.

### 3.1 Algorithm 1: Lab Billing Optimizer

**What it does:** Finds over-billing in lab tests through hemogram (CBC) bundling.

**How it works:**

**Hemogram (CBC) bundling:**
1. The SUT gazette defines a complete blood count (hemogram) as a single billable code (L107020) regardless of how many sub-components are reported (hemoglobin, WBC, RBC, platelets, hematocrit, MCV, etc.).
2. The algorithm maintains a set of 13 known CBC sub-component test names (`HEMOGRAM_TESTS`).
3. It scans a patient's lab tests grouped by encounter (visit_id preferred, date fallback). If multiple CBC sub-components appear in the same encounter, only one hemogram is reimbursable.
4. The bundling savings = (total sub-components across all encounters - number of encounters with any sub-component) × hemogram gazette price.
5. If the hospital billed each sub-component separately, the savings are flagged with the exact math: "X CBC subtests across Y encounter(s) should be billed as Y hemograms."

**Non-hemogram tests:**
The algorithm resolves each test name to its exact SUT gazette price using a lookup cascade: if the test name is an L-code, it uses the 3-tier procedure code lookup; otherwise it checks a pre-built gazette price dictionary, falling back to a default price.

**Claim-line input (source of truth):**
1. Algorithm 1 now reads `procedure_claim_lines` where `procedure_category == "laboratuvar"`.
2. Each claim line is treated as one billed lab test; clinical lab result rows are only used for capture-gap detection ("performed but not billed").
3. This eliminates phantom duplicates from raw clinical lab feeds.

**Session fractions:**
Session-fraction / seans kesir oranı rules are **not** applied to laboratory tests. SUT §2.2.2.A(5) targets surgical/medical "işlemler" with "kesi" (incision), not laboratory "tetkikler". Therefore `session_fraction_savings` remains zero for lab optimization.

**Output:** `LabOptimization` with hemogram bundling savings, zero session-fraction savings, and flagged tests (hemogram unbundling only).

### 3.2 Algorithm 2: Copay Savings Calculator

**What it does:** Computes the actual copayment savings achievable if an EK-1A-exempt patient's copays are correctly waived.

**How it works:**

**Heuristic mode (no claim lines):**
1. Takes the pre-computed copay exemption result from the EK-1A checker (Algorithm 2.1).
2. If the patient is exempt, records which disease and ICD-10 range triggered the exemption.
3. Does not compute monetary savings — just flags eligibility.

**Exact mode (with claim lines):**
1. Reads every procedure line where `copay_rate_applicable` is true.
2. Computes the copay component: `billed_amount - expected_payable`. This is the portion of the billed amount that represents patient copayment.
3. If the patient is exempt and the copay component is positive, that amount is recoverable.
4. Does the same for drug lines.
5. Separates visit copay savings from prescription copay savings.
6. Builds a list of rate corrections: one entry per procedure showing the billed amount, payable amount, and copay component.

**Output:** `CopayOptimization` with exemption status, exemption disease/range, visit copay savings, drug copay savings, total copay savings, and procedure-level rate corrections.

### 3.3 Algorithm 3: Package vs. Itemized Billing Strategy

**What it does:** Determines the **legally mandated** payment method (DRG package vs. itemized fee-for-service) for each claim per SUT §2.2, using EK-2/B and EK-2/C catalog membership, facility tier, and EK-2/C star markers. Savings are **corrective** (wrong method today) or **optional** (tier-3 §2.2.2(2) override only) — never pure price minimization.

**How it works (when exact claim lines are available):**

1. **Per procedure line** — `resolve_payment_method()` in `prose_rules/payment_method.py`:
   - EK-2/C only or EK-2/C + tier-2 / starred (*) → `DRG_MANDATORY` (package)
   - EK-2/B only → `ITEMIZED`
   - EK-2/C + tier-3 + non-star + also in EK-2/B → `DRG_OVERRIDABLE` (§2.2.2(2)) unless `prose_drg_locked` on catalog (§2.2.2 proviso list)
   - Uses `ClaimHeader.facility_tier` via `prose_rules/facility_tier.py`, `has_star`, and `procedure_prose_drg_locked()` from curated EK-2C + `ek2c_prose_drg_locked_codes.json`

2. **Per claim** (when `package_candidate` is true):
   - Computes **itemized total** via `compute_session_adjusted_itemized_total()` (§2.2.2.B / §2.2.2.A(5) session point factors on same-day operations); exposes `itemized_raw_try` and `itemized_price_methodology` (`session_adjusted` vs `claim_lines`)
   - When the package is mandated (`DRG_MANDATORY`) on a package-candidate claim but the bill is itemized, the itemized total is the part of the bill the package replaces: every itemized procedure, drug and package-included material line at its billed amount, with no compliance filter and no session re-pricing (`package_replaced_total_try`, `itemized_price_methodology = billed_lines`; `itemized_raw_try` keeps everything billed). Materials marked outside the package (SUT §3.1.4) and the blood-component share billed next to the package (C000694) drop out of both sides. A package that pays more is reported as package-billing uplift (`savings_category = sgk_uplift`); a higher itemized bill is a compliance saving, which is never counted as SGK uplift (`included_in_sgk_total = false`). When the package pays at least the bill, the must-package lines and the session factors on that claim are not audit exposure; `mandated_package_gap_try` is the shared gate, so a claim without a strategy row keeps its risk (#269)
   - Computes **package total** from `paket` category lines, or DRG chapter price lookup when no package lines exist
   - Aggregates claim kind (strictest wins): `DRG_MANDATORY` > `DRG_OVERRIDABLE` > `ITEMIZED`
   - Emits recommendation with `recommendation_kind`:
     - `mandatory_compliance` — only one legal method; `savings_try` > 0 only if currently billed the wrong way
     - `optional_override` — tier-3 §2.2.2(2); recommends the **higher-paying legal option**; `savings_try = abs(package − itemized)`

3. **Compliance violations** — lines billed contrary to mandated method are flagged separately (`type: compliance_violation`) with `payment_method_kind` and `sut_section_id`.

**Heuristic mode (no claim lines):** Returns chapter-level review flags with `missing_exact_inputs` status — line-level pricing and catalog membership are required.

**Output:** `BillingStrategyRecommendation` with per-claim fields: `recommendation`, `recommendation_kind`, `payment_method_kind`, `sut_section_id`, `rule_id`, both totals, corrective/override `savings_try`, and `current_billing`.

### 3.4 Algorithm 4: Material Reimbursability Pre-Check

**What it does:** Flags material reimbursement risks based on the patient's diagnosis profile, including pre-authorization requirements and minimum interval restrictions.

**How it works:**

**Diagnosis-to-specialty mapping:**
1. Maps ICD-10 chapter letters to relevant EK-3 specialty material catalogs. For example:
   - Chapter "I" (circulatory) → cardiology (EK-3H, EK-3I) and radiology (EK-3M)
   - Chapter "M" (musculoskeletal) → orthopedics (EK-3F-1 through EK-3F-4)
   - Chapter "C" (neoplasms) → hematology-oncology (EK-3O)
2. This narrows the material risk surface from 25 specialty catalogs to the 2-4 catalogs relevant to the patient's condition.

**Partial mode (no material claim lines):**
1. Maps ICD-10 chapters to relevant EK-3 specialty annex ids only.
2. Surfaces **P90 price benchmarks** per annex as `gazette_ceiling_by_specialty` — a heuristic, not EK-3C-1/2 coverage.
3. Does **not** load EK-3C-1 or EK-3C-2 in this path (`partial_exact` status).

**Pre-authorization checks (EK-3C-1) — exact mode only:**
1. Loads the EK-3C-1 catalog: materials requiring **tıbbi uygunluk** (§3.1.2) before SGK payment.
2. Flags each billed line whose code is in EK-3C-1 or has `requires_pre_auth`.

**MIAT checks (EK-3C-2) — exact mode only:**
1. **Catalog advisory:** codes on EK-3C-2 with no prior use in patient material history → `miat_restricted`.
2. **Interval violation:** compares `material_date` to prior uses of the same code; parses Turkish `miat_period` strings → `miat_interval_violations`.

**Bundling (EK-3B-1):**
1. `is_bundled` lines with positive billed amount → `bundled_separate_billing` (not the MIAT bucket).
2. L1.4 prose engine may add `prose_bundling_violations`.

**Output:** `MaterialPreCheck` with pre-auth list, MIAT catalog/interval lists, bundled-separate list, prose hits, and (partial mode) P90 benchmarks by specialty.

### 3.6 Billing Orchestrator

**Entry point:** `billing/orchestrator.py` — `compute_all_billing_reports()`

1. Collects all patient data from the pipeline cache: lab tests, prescriptions, copay exemptions, ICD-10 chapters, and exact claim contexts.
2. For each patient, calls `compute_patient_billing_report()` which runs all 21 billing block detectors (see `BILLING_BLOCK_SPECS`).
3. If exact claim data exists, routes to claim-line-aware variants (e.g., `optimize_copay_from_claims` instead of `_optimize_copay`).
4. Assemblies a `BillingActionReport` per patient with the sum of all algorithm savings as `total_recoverable_try`.
5. Computes cohort-wide statistics and assigns priority levels:
   - **High:** Total recoverable ≥ P75 of cohort
   - **Medium:** Total recoverable ≥ P50
   - **Low:** Everything else
6. Computes a `CohortRecoverySummary` with total savings broken down by category (lab, drug, copay, strategy), top 10 patients ranked by recovery potential, and priority distribution.
7. Parallelizes per-patient computation using `ThreadPoolExecutor` when `max_workers > 1`.

---

## Shared Foundations

### ICD-10 Range Matching (`shared.py`)

Used by copay exemptions (EK-1A). Matches a diagnosis code against gazette-defined ranges:
- Range "A15-A19": matches any code A15 through A19 (including sub-codes like A16.2).
- Single code "C34": matches C34 and all sub-codes (C34.0, C34.1, etc.).
- Sub-code "C49.5": matches only C49.5 exactly.
- Comparison is numeric within same letter: extracts the numeric portion after the letter and does integer range checking.

### 3-Tier Procedure Code Lookup (`catalog.py`)

Used throughout the system for resolving SUT procedure codes to prices:
1. **Exact match:** Direct hash lookup in the EK-2B by-code index.
2. **P-prefix stripped:** Hospitals often prefix codes with "P" (MEDULA convention). Strips leading P/p and retries.
3. **Prefix search:** If input is ≥3 characters, uses binary search (`bisect`) on sorted codes for prefix matching, returning up to 10 candidates.

### Exactness System (`exactness.py`)

A metadata discipline applied across all optimization and billing outputs:
- Every result carries `exactness_status`: `"exact"`, `"partial_exact"`, or `"missing_exact_inputs"`.
- Non-exact results carry `unavailable_reason` (human explanation) and `required_inputs_missing` (list of specific inputs needed).
- Orchestrators propagate exactness: if any component is non-exact, the aggregate report carries `"partial_exact"`.
- This prevents the system from presenting estimate-based numbers as if they were verified against actual claims.

---

## Gazette Annexes Used

| Annex | Content | Used By |
|-------|---------|---------|
| EK-1A | Chronic disease ICD-10 exemptions | Copay exemption checker, Copay savings alg |
| EK-2A | Outpatient visit pricing | Visit price lookups |
| EK-2B | Fee-for-service procedure pricing | All price lookups, temporal audit |
| EK-2C | DRG package pricing | DRG unbundling, billing strategy, temporal audit |
| EK-2C-1 | Copay rate mandates | Copay rate eligibility |
| EK-2G | Surcharge prohibitions | Surcharge eligibility |
| EK-3B-1 | Bundled consumables | Bundling rule |
| EK-3B-2 | Non-reimbursable materials | Exclusion rule |
| EK-3C-1 | Pre-authorization materials | Material pre-check |
| EK-3C-2 | MIAT-restricted materials | Material pre-check |
| EK-3A through EK-3T | Specialty material pricing | Material pre-check (gazette ceilings) |
| EK-4A | Drug reimbursement catalog | Drug optimization, drug discount validation |
