## Task: Synthetic Data v2 — Reimbursement Expansion

### Goal
Expand the synthetic SUT data generator from 5 patients / 5 claims to a rich, diverse dataset that eliminates every data-driven "Unavailable" state on the billing, alerts, and optimizer surfaces. (Backend-sanitized "Unavailable" states that require code changes in `optimization.py:48-55` and `alerts.py:48-82` are explicitly out of scope.) The generator must be parameterized — no hardcoded patient lists, no hardcoded prices.

---

### Current State (v1) — Deficiencies Found

| Area | v1 Status | Frontend Impact |
|------|-----------|-----------------|
| **Scale** | 5 patients, 5 claims, 15 procedure lines, 5 materials, 6 drugs, 10 diagnoses, 90 labs | No diversity for any feature |
| **Claim types** | 2 inpatient (003, 005); 3 outpatient/day-case with null admission/discharge dates | DRG pricing needs admission dates |
| **Surcharge eligibility** | `surcharge_applicable` = True for only 2 patients (003, 004) | Surcharge alerts tab: all rows show "Unavailable" |
| **Copay rate eligibility** | `copay_rate_applicable` = True only for outpatient claims (001, 002) | Copay rate compliance tab: all rows show "Unavailable" |
| **Materials** | 5 lines (patients 003-005), 3 unique codes | Billing materials section mostly unavailable |
| **Drugs** | 6 lines (patients 002, 004, 005), 2 unique drugs | Billing drug section shows "Unavailable" for patients 001, 003 |
| **Drug prices** | Hardcoded 120.0 / 185.0 TRY, NOT from EK-4A | Inaccurate drug pricing |
| **Lab results** | 90 rows, 3 test codes | Lab optimization limited to 3 test types |
| **Diagnoses** | 2 ICD-10 codes per patient, 10 diagnoses total | Limited disease diversity for exemption/DRG matching |
| **Catalog usage** | 16 gazette entries (6 EK-2B, 3 EK-2C, 3 EK-3, 2 EK-4A) | Doesn't exercise most catalog lookups |
| **Generator architecture** | Hardcoded patient list, hardcoded procedure specs, hardcoded prices | Impossible to scale without rewriting |

---

### Backend Hard-Blocks (Separate from Data)

These sections are **hardcoded to return "Unavailable"** in the backend via sanitization. Even perfect v2 data will NOT fix them:

| Feature | File | Line | Mechanism |
|---------|------|------|-----------|
| DRG Unbundling | `src/bilun/domain/optimization/unbundling.py` | 14-15 | Always returns `build_missing_exact_inputs_block()` |
| Drug Discount Validation | `src/bilun/domain/optimization/drugs.py` | ~1 | Always returns unavailable |
| Cohort Optimization Summary | `src/bilun/api/routes/optimization.py` | 48-55 | `_sanitize_optimization_summary` force-sanitizes surcharge, copay_rate, drg_unbundling, drug_discount to unavailable |
| Billing Strategy | `src/bilun/domain/billing/strategy.py` | 27-34 | Always returns unavailable |
| Surcharge Alert Summary | `src/bilun/api/routes/alerts.py` | 48-67 | `_sanitize_patient_alert_summary` overwrites surcharge exactness to unavailable |
| Copay Rate Alert Summary | `src/bilun/api/routes/alerts.py` | 68-82 | Same sanitization pattern for copay_rate |

These need backend implementation work — **not in scope of this synthetic data task**.

---

### Subtasks

#### Phase 0: Remove Hardcoded Limitations (DO THIS FIRST)

- [ ] **0.1 Replace hardcoded patient list** — generate patients programmatically from parameterized scenario templates. No `patients = [...]` literal with 5 dicts.
- [ ] **0.2 Replace hardcoded procedure/mapping dicts** (`procedure_by_patient`, `material_by_patient`, `drug_by_patient`) with scenario-driven generation that scales to N patients.
- [ ] **0.3 Remove hardcoded drug prices** (lines 486-487: `120.0`, `185.0`) — source `unit_price_try` from EK-4A `price_try` field.
- [ ] **0.4 Remove hardcoded fallback prices and names** in `_ek2b_lookup`, `_ek2c_lookup`, `_material_lookup`, `_drug_lookup` — fail explicitly if catalog is missing instead of silently using hardcoded values.
- [ ] **0.5 Add CLI parameters**: `--num-patients` (default 50), `--min-claims-per-patient` (default 1), `--max-claims-per-patient` (default 5), `--output-dir` (default `data/synthetic/sut`), `--seed` (default fixed for reproducibility).

#### Phase 1: Scale & Diversity

- [ ] **1.1 Scale to 50 patients** with varied age (0-90), gender, and cohort distribution. Realistic Turkish demographic profiles.
- [ ] **1.2 Scale to 2-5 episodes per patient** — some patients with single visits, some with multiple across time (for chronic disease scenarios).
- [ ] **1.3 Scale to 100-150 claims total** — mix of ayaktan, yatis, gunubirlik.
- [ ] **1.4 Ensure >= 30 inpatient claims have non-null admission_date and discharge_date** (currently only 2 of 5).
- [ ] **1.5 Scale procedure lines to 300+** (from 15). Use 50+ unique SUT procedure codes from EK-2B gazette (7,129 available).
- [ ] **1.6 Scale material lines to 50+** (from 5). Use 15+ unique material codes from non-empty EK-3 catalogs:
  - Non-empty catalogs available: ek3c2 (460 rows, orthotics), ek3c1 (506, medical suitability), ek3c4 (232, consumables), ek3f1 (342, arthroplasty), ek3f3 (184, tumor resection), ek3g (224, ophthalmology), ek3i (419, CV surgery), ek3n1 (102, allograft), ek3r (159, GI), ek3s (82, pulmonology), ek3p (35, nephrology), ek3o (18, hematology/oncology), ek3l (83, urology), ek3c3 (137, other prosthetics), ek3c5 (74, special cases).
  - Empty (skip): ek3h (cardiology), ek3e1 (spine), ek3e2 (cranial), ek3f2 (arthroscopy), ek3f4 (trauma), ek3m (radiology), ek3t (anesthesiology), ek3a (multibranch).
  - Total available EK-3 rows: 3,265 across 18 non-empty catalogs.
- [ ] **1.7 Scale drug claim lines to 60+** (from 6). Use 20+ unique drugs from EK-4A (8,428 available). Source `unit_price_try` from EK-4A `price_try`, NOT hardcoded values.
- [ ] **1.8 Scale lab results to 500+ rows** (from 90). Use 10+ unique lab test codes (1,954 lab SUT codes available in EK-2B with `L1*` prefix).
- [ ] **1.9 Scale diagnoses to 200+ rows** (from 10). Use 30+ unique ICD-10 codes spanning at least 8 ICD-10 chapters (letters) relevant to DRG group mapping (`_ICD10_CHAPTER_TO_EK2C_GROUP` in constants.py).

#### Phase 2: Reimbursement Logic

- [ ] **2.1 Set `surcharge_applicable` = True on a meaningful subset of procedures** — ~40% of procedure lines. Rule: surcharge is applicable for all procedures EXCEPT those listed in EK-2G (213 prohibited codes). Apply additional facility-tier restrictions (university hospitals have different surcharge rules than private).
- [ ] **2.2 Set `copay_rate_applicable` = True on a meaningful subset of procedures** — ~50% of procedure lines. Rule: copay rates apply to procedures listed in EK-2C-1 (465 procedures with explicit copay rate percentages from 20% to 100%). Outpatient claims generally have broader copay applicability.
- [ ] **2.3 Add `surcharge_rate` column to `procedure_claim_lines.parquet`** — a float column (null when surcharge_applicable=False). Generate varied rates (e.g., 0.10, 0.20, 0.30, 0.50, 0.75, 1.00) mapped from facility tier rules.
- [ ] **2.4 Add `copay_rate` column to `procedure_claim_lines.parquet`** — a float column (null when copay_rate_applicable=False). Source rate values from EK-2C-1 `copay_rate_pct` / 100.
- [ ] **2.5 Compute `expected_payable_try` correctly on procedure lines**:
  - If `is_package_included` = True: 0.0
  - If package itself (category = "paket"): `billed_amount_try` (full package price)
  - Otherwise: `billed_amount_try + (billed_amount_try * surcharge_rate) - (billed_amount_try * copay_rate)` where applicable, else `billed_amount_try`
- [ ] **2.6 Compute `expected_payable_try` correctly on drug lines**: `billed_amount_try * (1 - discount_tier)` — already the v1 formula, but now with EK-4A-sourced `unit_price_try` and real discount_tier values.
- [ ] **2.7 Compute `expected_payable_try` correctly on material lines**: `billed_amount_try` if not bundled, 0.0 if bundled. (Material price ceilings are a backend feature, not data generation.)
- [ ] **2.8 Set `discount_tier_expected` from EK-4A** `discount_tier_1` field (stored as decimal: 0.4, 0.28, 0.1, 0.0). Use multiple drugs across different discount tiers.
- [ ] **2.9 Set `equivalence_group` from EK-4A** `equivalence_group` field (2,107 groups available) instead of hardcoded "SENTETIK-ESDEGER".

#### Phase 3: Column Completeness & Schema

- [ ] **3.1 `claim_headers.parquet`** — ensure all columns populated: `claim_type` (enum: ayaktan/yatis/gunubirlik), `facility_tier` (enum: 2_3_basamak_ozel/3_basamak/2_basamak_kamu/1_basamak), `provider_type` (enum: Ozel/Universite/Kamu), `admission_date`, `discharge_date`, `claim_start_date`, `claim_end_date`, `primary_icd10`, `package_candidate`, `expected_total_billed_try`, `expected_total_payable_try`, `expected_denial_reason`, `scenario_tag` — none null where semantically required.
- [ ] **3.2 `procedure_claim_lines.parquet`** — ensure all columns: `surcharge_applicable` (bool), `surcharge_rate` (float, null if not applicable), `copay_rate_applicable` (bool), `copay_rate` (float, null if not applicable), `is_package_included`, `package_code`, `expected_payable_try` — properly populated.
- [ ] **3.3 `material_claim_lines.parquet`** — ensure all columns: `procedure_line_id`, `requires_pre_auth`, `expected_payable_try` — properly populated.
- [ ] **3.4 `drug_claim_lines.parquet`** — ensure all columns: `drug_name`, `drug_code`, `barcode`, `equivalence_group`, `discount_tier_expected`, `expected_payable_try` — properly populated from EK-4A.
- [ ] **3.5 `claim_diagnoses.parquet`** — ensure all columns: `is_primary`, `diagnosis_role`, `exemption_eligible` — properly populated. `exemption_eligible` = True when ICD-10 code falls within an EK-1A exemption range (98 ranges in `ek1a_chronic_exemptions.parquet`).
- [ ] **3.6 `expected_rule_outputs.parquet`** — scale proportionally: one expected output per claim (claim-level validation) AND one per procedure/material/drug line that triggers a rule. Target: 500+ rows (from 20). Covers: `drg_paket_ayristirma`, `faturalama_stratejisi`, `ilac_indirimi`, `fatura_dogrulama`.

#### Phase 4: Scenario Diversity

- [ ] **4.1 Distribute patients across 8+ medical specialties**: cardiology (non-EK-3), orthopedics, oncology, endocrinology, gastroenterology, pulmonology, neurology, nephrology. Match specialty to available EK-3 material catalog.
- [ ] **4.2 Add patients with multiple comorbidities** (diabetes + hypertension + cardiac disease, etc.) — multi-ICD10 per episode.
- [ ] **4.3 Add emergency admission scenarios** with varied urgency levels.
- [ ] **4.4 Add chronic disease patients** with recurring visits over time — for temporal analysis and exemption eligibility (EK-1A).
- [ ] **4.5 Add package-eligible episodes** (DRG) with proper procedure-to-package mapping from EK-2C. Ensure `package_candidate` = True and `package_code` is populated on relevant procedure lines.
- [ ] **4.6 Add bundled procedure scenarios** — procedures that are `is_package_included` = True, with `expected_payable_try` = 0.0 and `denial_reason_expected` set.
- [ ] **4.7 Add material pre-authorization scenarios** — `requires_pre_auth` = True for some materials, False for others.
- [ ] **4.8 Add drug discount scenarios across multiple EK-4A discount tiers** (0.0, 0.1, 0.28, 0.4, and others from actual catalog).

#### Phase 5: Validation & Verification

- [ ] **5.1 Update validation script** (`scripts/synthetic/validate_sut_synthetic_data.py`) to match new scale: 50 patients, 100+ claims, 300+ procedure lines, 50+ material lines, 60+ drug lines, 500+ lab rows.
- [ ] **5.2 Add validation for surcharge coverage**: at least 40% of procedure lines have `surcharge_applicable` = True AND `surcharge_rate` is non-null when applicable.
- [ ] **5.3 Add validation for copay coverage**: at least 40% of procedure lines have `copay_rate_applicable` = True AND `copay_rate` is non-null when applicable.
- [ ] **5.4 Add validation for drug pricing**: all drug `unit_price_try` values must be sourced from EK-4A (not hardcoded 120.0/185.0). Verify no hardcoded prices remain.
- [ ] **5.5 Add cross-reference validation**: material `procedure_line_id` references exist in procedure_claim_lines; drug `prescription_id` references exist in recete_clean; lab `islem_satiri_id` references exist in procedure_claim_lines.
- [ ] **5.6 Add validation for `expected_rule_outputs`**: one claim-level row per claim + one line-level row per bundled/rejected line.
- [ ] **5.7 Verify ALL generated Parquet files pass the updated validator without errors.**
- [ ] **5.8 Rebuild DuckDB cache** (`python -m src.bilun.cache.builder` or equivalent cache build command) and verify cache tables reflect new data.
- [ ] **5.9 Verify frontend shows data (not "Unavailable")** for all sections where claim data is the dependency:
  - Billing → Lab Optimization (should have data from lab_clean + procedure lines)
  - Billing → Drug Optimization (should have data from drug_claim_lines with real prices)
  - Billing → Copay Optimization (should have data from procedure_claim_lines with copay flags)
  - Billing → Materials Pre-Check (should have data from material_claim_lines)
  - Patient Alerts → **Per-row** surcharge/copay rate alerts (individual row values NOT sanitized by `_sanitize_patient_alert_rows`)
  - Patient Outcome → DRG pricing for episodes with admission dates
  - Optimizer → Compliance Alerts **per-row** data (surcharge/copay flags on individual claims)
  - Optimizer → Revenue Recovery → per-claim breakdowns
- [ ] **5.10 Document which sections remain "Unavailable"** despite v2 data (the 6 backend hard-blocks listed above) so there is no confusion.

---

### Out of Scope (Separate Backend Tasks)

1. **DRG Unbundling Implementation** — `src/bilun/domain/optimization/unbundling.py`
2. **Drug Discount Validation Implementation** — `src/bilun/domain/optimization/drugs.py`
3. **Billing Strategy Implementation** — `src/bilun/domain/billing/strategy.py`
4. **Cohort-Level Optimization Summary sanitization removal** — `src/bilun/api/routes/optimization.py:48-55`
5. **Surcharge/Copay Alert Summary sanitization removal** — `src/bilun/api/routes/alerts.py:48-82`
6. **Temporal Price Validation** — verification needed with proper admission-dated data

---

### Definition of Done

1. Generator produces 50 patients, 100+ claims, 300+ procedure lines, 50+ material lines, 60+ drug lines, 500+ lab rows, 200+ diagnoses, 500+ expected rule outputs
2. All generation is parameterized — no hardcoded patient lists, procedure specs, or prices
3. CLI accepts `--num-patients`, `--max-claims-per-patient`, `--seed`, `--output-dir`
4. 30+ unique ICD-10 codes spanning 8+ ICD-10 chapters relevant to DRG group mapping
5. 50+ unique SUT procedure codes from EK-2B, 15+ unique material codes from non-empty EK-3 catalogs, 20+ unique drugs from EK-4A
6. 30+ inpatient claims with non-null admission/discharge dates
7. `surcharge_applicable` = True on >= 40% of procedure lines, with valid `surcharge_rate` values
8. `copay_rate_applicable` = True on >= 40% of procedure lines, with valid `copay_rate` values from EK-2C-1
9. All drug `unit_price_try` values sourced from EK-4A (no hardcoded 120.0/185.0)
10. Drug `equivalence_group` values sourced from EK-4A (no hardcoded "SENTETIK-ESDEGER")
11. All Parquet files pass updated validation script
12. DuckDB cache rebuild succeeds and data appears in cache tables
13. Frontend sections that depend ONLY on claim data (not backend hard-blocks) show actual values:
    - Billing: Lab Optimization, Drug Optimization, Copay Optimization, Materials Pre-Check
    - Patient Alerts: individual surcharge and copay rate rows (per-row, not summary)
    - Patient Outcome: DRG pricing for inpatient episodes
    - Optimizer → Compliance Alerts: per-row surcharge/copay data
    - Optimizer → Revenue Recovery: per-claim breakdowns
14. Sections that remain "Unavailable" are ONLY those blocked by the 6 backend hard-blocks in "Out of Scope"

---

### Demo credibility cohort (Tier A/B)

Showcase sentetik hastalar, claim line semantiği (sunulan vs optimizasyon alternatifi), post-regen doğrulama ve manifest:

- [`data/synthetic/README.md`](../../data/synthetic/README.md)
- [`plans/data/synthetic-demo-credibility-plan.md`](synthetic-demo-credibility-plan.md)

After regenerating parquet, run `validate_sut_synthetic_data.py` and `assert_tier_a_post_regen.py`; rebuild cache with `scripts/bilun/build_cache.py --activate` when billing surfaces look stale.
