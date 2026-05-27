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

**Gazette anchor:** EK-3/B-1 — 54 categories of consumables bundled into procedure prices.

**What it does:** Detects consumables that were billed as separate line items but should have been included in the procedure fee. These are simple, low-cost items (syringes, gloves, scalpel tips, antiseptic solutions, etc.) that the SUT explicitly says the hospital must supply at its own expense. SGK will not pay for them as separate items.

**How it works:**
1. Loads the 54 EK-3B-1 bundled consumable categories from the curated parquet catalog.
2. For each material in the claim, Turkish-normalizes its name and checks against the bundled list using two matching strategies:
   - **Substring match (both directions):** The material name contains the bundled category name, or vice versa.
   - **Fuzzy match:** If substring matching fails, applies a fuzzy string distance check with an 80% similarity threshold.
3. Each match is flagged as a violation. The billed amount for the matched material line becomes potential savings.
4. Violations where billed amount > 50 TRY are classified as "error" severity; below that, "warning."

**Business meaning:** If a hospital bills antiseptic solution at 5 TRY per unit in a procedure line, and the EK-3B-1 says antiseptics are bundled, that 5 TRY is unrecoverable and should be removed from the claim before submission. Otherwise SGK may reject the entire claim or claw it back in an audit.

### 1.2 EK-3B-2 Exclusion Rule

**Gazette anchor:** EK-3/B-2 — 13 categories of non-reimbursable materials.

**What it does:** Detects materials in the claim that SGK will *never* reimburse, regardless of how they're billed. These are items like viscosupplementation products, sports prostheses, stem cell materials, etc.

**How it works:**
1. Loads the EK-3B-2 non-reimbursable catalog.
2. For each material in the claim, checks if it matches any exclusion entry via Turkish-normalized substring matching.
3. If direct match fails, applies fuzzy matching at 80% threshold.
4. Matched items are flagged as "exclusion" violations with "error" severity.
5. The billed amount becomes the **risk amount** — money the hospital will lose if the claim is submitted as-is.

**Business meaning:** This is the strongest SUT enforcement rule. If a material is in EK-3B-2, SGK simply will not pay. The hospital must either absorb the cost or bill the patient directly (if legally permissible). The rule catches these *before* submission so the hospital can decide whether to proceed.

### 1.3 Claim Validation Orchestrator

**Entry point:** `rule_engine.py` — `validate_claim()`

Runs both rules in sequence and aggregates results into a single `ClaimValidationResult`:
- `is_valid`: False if any violation has "error" severity.
- `total_savings_try`: Sum of bundling violation amounts (money being billed that shouldn't be).
- `total_risk_try`: Sum of exclusion violation amounts (money SGK will not cover).
- Also computes material cost estimates against gazette prices for each line item.

---

## Layer 2: Revenue Optimization Rule Engines (6 Features)

These rules operate at the **cohort level** and answer: **How much money is the hospital leaving on the table across all patients?**

They are designed for revenue recovery dashboards — they scan patient populations to find systematic billing opportunities.

### Architecture

```
patient ICD-10 diagnoses + claim dataset → 6 parallel rule engines → cohort optimization summary
```

There is a critical runtime concept: **exactness.** Each rule engine declares what inputs it needs. If the data is available (exact claim lines from the hospital's billing system), the output is tagged `exact`. If only gazette catalogs are available without patient-specific claim data, the output is tagged `missing_exact_inputs` and the result is intentionally minimal. This prevents the system from fabricating numbers.

### 2.1 Copay Exemption Checker (EK-1A)

**Gazette anchor:** EK-1A — chronic disease copayment exemption. SUT clause 1.8.1.

**What it does:** Identifies patients who should be exempt from outpatient copayment (katılım payı) because they have a qualifying chronic disease. Turkish law waives copays for patients with specific chronic conditions.

**How it works:**
1. Loads the EK-1A exemption catalog: 98 ICD-10 ranges (32 multi-code ranges + 66 single-code entries) covering diseases like diabetes, hypertension, COPD, cancer, etc.
2. **Pre-indexing optimization:** Groups the 98 ranges by ICD-10 chapter letter (A-Z) for O(1) lookup — only ranges matching the first letter of a diagnosis code are checked.
3. **Precomputation phase:** Before running on the cohort, the system collects all unique ICD-10 codes across all patients and pre-matches them against EK-1A. The result is a lookup map: diagnosis code → (disease name, range). This means each unique code is checked exactly once, not once per patient.
4. **ICD-10 range matching:** Uses a structured algorithm that compares numeric portions of codes within the same letter family. For example, range "A15-A19" matches codes A15, A16, A16.2, A17, A17.9, A18, A19. Single codes (e.g., "C34") match the exact code and all sub-codes (C34.1, C34.9, etc.).
5. Per-patient: if any of the patient's diagnoses match, the patient is marked `exempt = True`.

**Business meaning:** Hospitals may be collecting copayments from patients who are legally exempt. This is both a patient-experience issue and a potential compliance liability. The algorithm identifies these patients so the hospital can stop charging them and potentially refund past charges.

### 2.2 Surcharge Eligibility (EK-2G)

**Gazette anchor:** EK-2G — procedures where additional surcharge fees are prohibited.

**What it does:** Identifies procedures where the hospital is prohibited from charging the patient any additional fee (ilave ücret) above the SGK base rate.

**How it works:**
1. Loads EK-2G: 213 procedures with surcharge prohibitions.
2. Requires exact claim lines to operate (cannot be inferred from ICD-10 codes alone — needs procedure codes and service dates).
3. When exact claim lines are available: iterates through each patient's procedure lines, checks the `surcharge_applicable` flag encoded on each claim line, and tallies which procedures carry surcharge exposure.
4. When exact data is unavailable: returns a structured "missing exact inputs" payload with the specific reason and what's needed.

**Business meaning:** Many hospitals add surcharges to certain procedures to increase revenue. But EK-2G bans this for 213 specific procedures. Billing a surcharge on a prohibited procedure can trigger SGK audit penalties. The algorithm identifies exposure so the hospital can correct its billing.

### 2.3 Copay Rate Eligibility (EK-2C-1)

**Gazette anchor:** EK-2C-1 — 465 procedures with explicit copayment rate percentages.

**What it does:** Identifies procedures that have a gazette-mandated copay rate (ranging from 20% to 100%) and validates whether the billed amounts match the expected rates.

**How it works:**
1. Loads EK-2C-1: 465 procedures with their mandated copay rate percentages.
2. Like surcharge, requires exact claim lines with `copay_rate_applicable` flags and billed/payable amounts.
3. When exact data is available: computes per-procedure the actual payable-to-billed ratio and compares it against the gazette-mandated rate, producing a rate distribution across the cohort.
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
3. Aggregates findings by ICD-10 chapter for chapter-level risk analysis.
4. Returns per-patient: whether there's unbundling risk, total potential savings, and chapter-level breakdown.

**Business meaning:** DRG packages are the SUT's way of controlling costs. The hospital gets a fixed payment for everything related to a diagnosis episode — no matter how many individual services were performed. If the hospital itemizes things that should be in the package, SGK rejects the extra lines. If the hospital uses the package when individual billing would pay more, they're losing revenue. This algorithm tells hospitals which direction to go.

### 2.6 Drug Discount Validation (EK-4A)

**Gazette anchor:** EK-4A — drug reimbursement catalog with discount tier bands.

**What it does:** Validates that drug claim lines reflect the correct SGK discount tiers and computes the correct payable amounts.

**How it works:**
1. Requires exact drug claim lines (dispensed drug codes, billed amounts, expected discount tiers, expected payable amounts).
2. For each drug line: verifies that `expected_payable = billed_amount × (1 - discount_tier_expected)`. Flags lines where the difference exceeds 0.02 TRY as mismatches.
3. Computes tier distribution: what percentage of drugs fall in each discount band (e.g., 10%, 20%, 28%, 41%, 54%).
4. Tracks total discount savings (billed - payable) and mean discount tier across the cohort.
5. Samples up to 10 drugs with their tier details for inspection.

**Business meaning:** SGK applies mandatory discounts to drugs based on their EK-4A classification. If the pharmacy or billing system applies the wrong tier, the hospital either under-recovers (discount too high) or faces audit risk (discount too low). This validation catches systematic tier errors.

### 2.7 Cohort Aggregator (`compute_optimization_summary`)

**Entry point:** `optimization/aggregator.py`

Runs all 6 features across a patient cohort in a single pass and produces a unified optimization summary:
- **Copay exemptions:** Exemption rate, top diseases triggering exemptions.
- **Surcharge exposure:** Total EK-2G procedures, surcharge application rate, patients with flags.
- **Copay rate exposure:** Total EK-2C-1 procedures, procedure rate distribution, mean rate.
- **Temporal prices:** Full EK-2B/2C price change audit (cached).
- **DRG unbundling:** Patients with risk, total potential savings, riskiest ICD-10 chapters.
- **Drug discounts:** Tier distribution, tier mismatch count, sample drugs.

---

## Layer 3: Billing Optimization Algorithms (5 Algorithms)

These algorithms produce actionable, per-patient recommendations. They answer: **What should this specific hospital do differently for this specific patient?**

They run on the billing pipeline and feed into the revenue recovery dashboard.

### Architecture

```
patient data (labs, drugs, diagnoses, claim lines) → 5 parallel algorithms → BillingActionReport → CohortRecoverySummary
```

The orchestrator also assigns a **priority** (high/medium/low) to each patient based on their total recoverable amount relative to the cohort's P50 and P75 percentiles. Patients above P75 get "high" priority.

### 3.1 Algorithm 1: Lab Billing Optimizer

**What it does:** Finds over-billing in lab tests through two mechanisms — hemogram bundling and duplicate test detection.

**How it works:**

**Hemogram (CBC) bundling:**
1. The SUT gazette defines a complete blood count (hemogram) as a single billable code (L107020) regardless of how many sub-components are reported (hemoglobin, WBC, RBC, platelets, hematocrit, MCV, etc.).
2. The algorithm maintains a set of ~20 known CBC sub-component test names (`HEMOGRAM_TESTS`).
3. It scans a patient's lab tests grouped by date. If multiple CBC sub-components appear on the same date, only one hemogram is reimbursable.
4. The bundling savings = (total sub-components across all dates - number of dates with any sub-component) × hemogram gazette price.
5. If the hospital billed each sub-component separately, the savings are flagged with the exact math: "X CBC subtests across Y dates should be billed as Y hemograms."

**Duplicate test detection:**
1. For non-hemogram tests, the algorithm counts how many times each test appears for a given patient.
2. SUT rules typically allow one billing per test per encounter. Duplicates beyond the first are non-reimbursable.
3. Duplicate savings = test price × (count - 1) for each duplicated test.
4. The algorithm resolves each test name to its exact SUT gazette price using a 3-tier lookup (direct name match → SUT code lookup → fallback default).

**Output:** `LabOptimization` with normative cost (what the hospital should have billed), hemogram bundling savings, duplicate test savings, and a list of specific flagged tests with SUT codes and savings amounts.

### 3.2 Algorithm 2: Drug Cost Optimizer

**What it does:** Identifies cheaper generic alternatives for prescribed drugs and detects passivated (discontinued) drugs.

**How it works:**

**Equivalence group indexing:**
1. Loads the EK-4A drug catalog and indexes all active drugs by their equivalence group — a gazette-defined grouping of therapeutically equivalent drugs.
2. Filters out passivated drugs (drugs with a `passivation_date` — meaning SGK no longer reimburses them).

**Generic substitution:**
1. For each drug prescribed to the patient, looks up its EK-4A record.
2. If the drug's equivalence group has other active members, checks if any are cheaper. Two criteria qualify an alternative as cheaper:
   - **Status "ESDEGER":** The alternative is classified as a generic equivalent while the current drug isn't.
   - **Higher discount tier:** The alternative's discount_tier_1 is more than 5 percentage points higher than the current drug's (meaning SGK covers more of it).
3. Estimates savings using tier midpoints: basic drugs ≈ 25 TRY, moderate ≈ 95 TRY, specialty ≈ 475 TRY. The savings estimate = current tier midpoint - alternative tier midpoint.

**Passivation detection:**
1. If a drug has a non-empty `passivation_date`, it's flagged. The algorithm searches the same equivalence group for active alternatives.
2. The passivated count is tallied but carries no direct savings — it's a compliance alert.

**Exact mode (when claim lines are available):**
1. If exact drug claim lines exist, the algorithm computes actual savings from billed amounts vs. expected payable amounts per line.
2. Discount tier savings (billed - payable on each line) are added as recommendations alongside generic substitution savings.
3. Takes the maximum of heuristic-estimated savings and line-level computed savings.

**Output:** `DrugOptimization` with generic substitution savings estimate, count of generics available, passivated drug count, and a list of specific drug recommendations (current drug → suggested alternative with estimated savings).

### 3.3 Algorithm 3: Copay Savings Calculator

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

### 3.4 Algorithm 4: Package vs. Itemized Billing Strategy

**What it does:** Compares DRG package billing against itemized (fee-for-service) billing for each claim and recommends the strategy that maximizes reimbursement.

**How it works (when exact claim lines are available):**

1. For each claim flagged as a package candidate:
   - Computes the **itemized total** from non-package, non-bundled procedure lines.
   - Computes the **package total** from procedure lines with category "paket."
   - If no package total exists but an admission date is available, falls back to gazette DRG price lookup by ICD-10 chapter and date.

2. Comparison:
   - If `itemized_total > package_total`: recommends **itemized** billing. Savings = itemized - package.
   - If `package_total > itemized_total`: recommends **package** billing. Savings = package - itemized.

3. Each claim gets a recommendation entry with the recommended strategy, both totals, and the dollar savings.

**Heuristic mode (no claim lines):** Returns an empty recommendation with `missing_exact_inputs` status — this algorithm fundamentally requires line-level pricing data to be meaningful.

**Output:** `BillingStrategyRecommendation` with per-claim recommendations (claim ID, strategy, package total, itemized total, savings).

### 3.5 Algorithm 5: Material Reimbursability Pre-Check

**What it does:** Flags material reimbursement risks based on the patient's diagnosis profile, including pre-authorization requirements and minimum interval restrictions.

**How it works:**

**Diagnosis-to-specialty mapping:**
1. Maps ICD-10 chapter letters to relevant EK-3 specialty material catalogs. For example:
   - Chapter "I" (circulatory) → cardiology (EK-3H, EK-3I) and radiology (EK-3M)
   - Chapter "M" (musculoskeletal) → orthopedics (EK-3F-1 through EK-3F-4)
   - Chapter "C" (neoplasms) → hematology-oncology (EK-3O)
2. This narrows the material risk surface from 25 specialty catalogs to the 2-4 catalogs relevant to the patient's condition.

**Gazette price ceilings:**
1. Computes P10, P50, P90, and max price statistics for each specialty catalog.
2. The **P90 price** is surfaced as the "gazette ceiling" — materials priced above this are likely flagged by SGK as excessive.
3. This is a heuristic, not a hard rule, hence the `partial_exact` status when materials claim lines are absent.

**Pre-authorization checks (EK-3C-1):**
1. Loads the EK-3C-1 catalog: materials that require medical board (sağlık kurulu) approval before SGK will reimburse.
2. Summarizes the top 5 pre-auth materials by price.

**MIAT period checks (EK-3C-2):**
1. Loads the EK-3C-2 catalog: materials with minimum inter-application time (MIAT) restrictions — e.g., a specific implant that SGK will only reimburse once every 90 days.
2. Summarizes the top 5 MIAT-restricted materials with their minimum periods.

**Exact mode (when material claim lines are available):**
1. Instead of diagnosis-based catalog association, directly checks every billed material line against the EK-3C-1 and EK-3C-2 catalogs.
2. Adds checks for `is_bundled` flags on material lines — if a bundled material was billed separately, flags it.
3. Uses actual billed amounts instead of catalog list prices.

**Output:** `MaterialPreCheck` with pre-auth required list, MIAT-restricted list, and gazette ceiling prices by specialty.

### 3.6 Billing Orchestrator

**Entry point:** `billing/orchestrator.py` — `compute_all_billing_reports()`

1. Collects all patient data from the pipeline cache: lab tests, prescriptions, copay exemptions, ICD-10 chapters, and exact claim contexts.
2. For each patient, calls `compute_patient_billing_report()` which runs all 5 algorithms.
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
