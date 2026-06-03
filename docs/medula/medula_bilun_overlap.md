---
title: "MEDULA vs BILUN: Overlap Analysis"
aliases: ["medula-bilun-overlap", "medula-overlap"]
tags: [analysis, medula, sut, bilun, overlap]
type: medula
status: provisional
related: ["[[medula_capabilities]]", "[[algorithms_reference]]"]
---

# MEDULA vs BILUN: Overlap Analysis

## What MEDULA Actually Is

MEDULA is the **SGK claims submission gateway**. Hospitals interact with it through SOAP web services in a three-stage workflow:

1. **Hasta Kabul (Patient Admission):** Creates a `takipNo` — checks patient entitlement, facility contract, sevk chain, biometric verification.
2. **Hizmet Kayıt (Service Registration):** Submits individual procedure/drug/material line items — MEDULA validates every DTO field, SUT code validity, quotas, and procedure presence rules.
3. **Fatura Kayıt (Invoice Registration):** Submits the final invoice — MEDULA computes payment, applies deductions, and returns a payable amount.

MEDULA is a **validator and calculator.** It says yes/no and computes a number. It never says "you could have billed this differently and made more money."

---

## Important: Abstraction Level Difference

**MEDULA operates at the web service DTO level.** It validates that SUT codes exist in EK-2/B and EK-2/C lists, that mandatory fields are filled, that procedure groups (ICU A/B/C) are present before allowing materials, and that quotas are not exceeded. It enforces SUT rules through **code lists, procedure presence logic, and ICU-group classification** — not through named annex enforcement.

**BILUN operates at the SUT annex level.** It loads annex catalogs (EK-1A, EK-4A, EK-3B-1, EK-2G, etc.) and performs pre-submission analytics on them.

**Critical finding:** The MEDULA manual never mentions SUT annex labels like EK-3B-1, EK-3B-2, EK-1A, or EK-2G by name. It references "SUT," "EK-2/B," "EK-2/C," and specific code lists. MEDULA's material blocking, for instance, is based on ICU group presence rules (A/B/C group present = materials allowed) and procedure presence ("no procedure in takip = no material invoicing"), not explicit EK-3B-1/3B-2 annex enforcement.

This means **there is no direct evidence in the manual that MEDULA explicitly enforces EK-3B-1 bundling or EK-3B-2 exclusion rules.** Those are SUT-level rules that may be encoded indirectly in MEDULA's validation logic, but the manual does not prove overlap.

---

## Overlap Analysis

### Category A: Clear Overlap — MEDULA and BILUN Do the Same Thing

| MEDULA Capability | BILUN Equivalent | Overlap Assessment |
|---|---|---|
| SUT code existence validation (code must be in EK-2/B list) | None — BILUN uses SUT codes for pricing lookups, not existence checks | Minimal. BILUN's catalog loader loads SUT codes for pricing, not to reject invalid ones. |
| Mandatory DTO field validation (doctor reg, branch, dates, quantities) | None | No overlap. BILUN doesn't replicate MEDULA's field-level DTO validation. |
| Drug barcode İTS validation | None | No overlap. BILUN looks up drugs by name for tier/substitution, doesn't validate barcodes. |
| Material UBB/UTS validation | None | No overlap. BILUN checks material reimbursability against SUT catalogs, not barcode registration. |
| ICD-10 code format validation | None | No overlap. BILUN uses ICD-10 codes for EK-1A exemption matching and chapter extraction, not format validation. |
| Quota enforcement (doctor daily max, eye surgery ratio, bed occupancy) | None | No overlap. BILUN doesn't track quotas. |
| Sevk chain enforcement | None | No overlap. BILUN has no referral chain logic. |
| Biometric verification (EKDS) | None | No overlap. |
| Copay calculation at invoice time | Copay savings calculator (Alg 3) | Different timing. MEDULA calculates copay at submission. BILUN identifies patients who should be exempt before submission. |

### Category B: Different Abstraction Levels — Related but Not Duplicative

| MEDULA Mechanism | BILUN Algorithm | Relationship |
|---|---|---|
| Material blocking via ICU group rules (A/B/C group present → materials allowed; no procedure → no material invoice) | Bundling rules (EK-3B-1) + Exclusion rules (EK-3B-2) + §3.1 prose (`material_bundling_prose`, **22 rules**, partial) | MEDULA blocks via ICU-group and procedure-presence. BILUN adds annex + prose pre-check. **ADDITIVE** for EK-3B and prose; **PARTIAL_OVERLAP** for procedure pairing and TİTUBB/ÜTS flags. See `material_bundling_medula_boundary.md`. |
| Drug discount tier application at payment | Drug cost optimizer — generic substitution | MEDULA applies the discount. BILUN finds cheaper equivalents in the same equivalence group. Different functions. |
| Drug payment codes returned by `IlacAra` (1=Paid, 2=Paid with report, 3=Not paid) | Drug cost optimizer | MEDULA tells you if a drug is paid in a given context. BILUN could use this as a pre-check input but currently doesn't. Not duplicative. |
| Patient copay exemption flags (`katilimPayindanMuaf`) | Copay exemption checker (EK-1A) | MEDULA returns the exemption flag at admission. BILUN computes exemption eligibility from ICD-10 history. BILUN could feed its computed exemptions into MEDULA's flags but doesn't currently. |
| Material price calculation (facility-type-dependent markups) | Material pre-check (gazette ceilings) | MEDULA applies facility-type-dependent pricing (12% public, KDV only private, etc.). BILUN computes P90 price ceilings per specialty. Different analysis. |

### Category C: MEDULA Has No Equivalent — BILUN's Unique Value

| BILUN Algorithm | Why MEDULA Doesn't Do This |
|---|---|
| **Hemogram bundling (Alg 1)** | MEDULA validates individual SUT codes. It does not cross-reference a batch of lab tests and bundle CBC sub-components into one hemogram code. |
| **Duplicate test detection (Alg 1)** | MEDULA sees individual SUT codes. It does not detect that the same test was ordered multiple times for the same patient encounter. |
| **Generic drug substitution (Alg 2)** | MEDULA applies the EK-4A discount tier to whatever drug is submitted. It never compares drugs within an equivalence group and suggests cheaper alternatives. |
| **Drug passivation detection (Alg 2)** | MEDULA rejects passivated drugs at submission. BILUN detects them in advance. |
| **Package vs itemized strategy (Alg 4)** | MEDULA computes payment based on what's submitted. It never compares the two strategies and recommends the higher-paying one. |
| **DRG unbundling detection (Optimization 5)** | MEDULA processes whatever the hospital submits. It does not flag that items marked as package-included were billed separately. |
| **Copay exemption proactive discovery (Optimization 1)** | MEDULA checks exemption flags at submission. It does not scan a patient's ICD-10 history and proactively identify eligibility. |
| **Temporal price audit (Optimization 4)** | MEDULA has `guncelSutKodlari` for current prices only. It provides no historical price comparison across SUT amendments. |
| **Cohort-level aggregation with priority scoring** | MEDULA operates at the individual claim level. BILUN aggregates across thousands of patients, ranks them by recoverable amount, and produces cohort dashboards. |
| **Surcharge exposure analysis (Optimization 2)** | MEDULA applies ilave ücret rules per procedure. It does not analyze which departments or procedure types are systematically generating surcharge violations. |
| **EK-1A chronic disease precomputation** | MEDULA checks eligibility flags at submission. It does not scan historical diagnosis data proactively across a patient population. |
| **SUT catalog loading for analytics** | MEDULA provides `guncelSutKodlari` for real-time lookups. BILUN loads historical parquet catalogs for analytical queries across multiple amendment dates. |

---

## Category D: MEDULA Capabilities BILUN Could Leverage

These are MEDULA features that BILUN currently ignores but could use as pre-MEDULA optimization inputs:

| MEDULA Capability | Potential BILUN Feature | Value |
|---|---|---|
| Drug payment codes (`IlacAra`: 1=Paid, 2=Paid with report, 3=Not paid) | Pre-submission drug payment awareness — flag drugs that need reports or are not covered before the claim is submitted | Prevents rejections |
| Drug max dose fields (`IlacAra`: max usage period/dose) | Dose compliance pre-check — flag prescriptions exceeding EK-4A max dose limits | Prevents rejections |
| MR/CT 50% same-day rule | Imaging sequencing advisor — suggest optimal scheduling to avoid the 50% penalty | Revenue optimization |
| Sevk chain awareness | Referral route advisor — warn if a patient needs a sevk before treatment can be billed | Prevents workflow errors |
| Same-day package + exam conflict | Procedure conflict detector — flag incompatible procedure combinations | Prevents rejections |
| Drug report matching (`raporTakipNo` + active ingredient match) | Drug report readiness check — verify drug matches report before submission | Prevents rejections |
| Material ICU-group-dependent billing | ICU material eligibility pre-check — verify A/B/C group procedures exist before submitting materials | Prevents rejections |
| `barkodSutEslesmeSorgu` (barcode-SUT matching) | Material code validation — pre-verify that material barcodes map to billable SUT codes | Prevents rejections |
| `kisiGecmisIslemSorgu` (historical procedure query) | Procedure frequency pre-check — verify that repeat procedures haven't exceeded limits | Prevents rejections |

---

## Key Questions the Manual Cannot Answer

The MEDULA manual is a web service DTO reference, not a SUT rule repository. Several questions BILUN needs answers to are not in the manual:

1. **Does MEDULA explicitly enforce EK-3B-1 (bundled consumables)?** The manual describes material blocking via ICU group rules and procedure presence, not consumable bundling categories. EK-3B-1 enforcement likely happens, but the manual doesn't document it as a named rule.

2. **Does MEDULA explicitly enforce EK-3B-2 (non-reimbursable materials)?** Same problem — the manual documents material validation via UTS/UBB barcode rules and ICU-group logic, not by matching against EK-3B-2 exclusion categories.

3. **Where exactly are EK-3B-1 and EK-3B-2 enforced in the SGK pipeline?** They may be enforced at the audit/inspection stage (after MEDULA submission), at the SUT regulation level (embedded in code lists), or within MEDULA's business rules layer (not documented in the web service manual).

4. **Does MEDULA perform hemogram bundling (multiple CBC sub-components → single hemogram code)?** The manual defines hemogram tahlil type codes (HEM102, HEM103, HEM104) but does not describe a bundling algorithm.

**Bottom line:** The web service manual documents the API contract. It does not document MEDULA's internal business rule engine. The absence of EK-3B-1/3B-2 mentions in the manual does not prove MEDULA doesn't enforce them — it just means they're not part of the API specification.

---

## Summary and Recommendation

| Layer | Module | Verdict | Reason |
|---|---|---|---|
| Layer 1 | Bundling rules (EK-3B-1) | **KEEP — ADDITIVE** | Phase 5: manual has no EK-3B-1 by name; pre-MEDULA analytics (`medula_overlap_gaps.md`). |
| Layer 1 | Exclusion rules (EK-3B-2) | **KEEP — ADDITIVE** | Same; ÜTS/UBB DTO ≠ EK-3B-2 category match. |
| Layer 1 | §3.1 prose material bundling (L1.4) | **KEEP — ADDITIVE** | 17-rule partial engine; do not claim MEDULA-guaranteed savings from prose hits. |
| Layer 1 | `validate_claim()` orchestrator | **KEEP — ADDITIVE** | Third pass: bundling + exclusion + prose. |
| Layer 2 | All 6 optimization engines | **KEEP** | No MEDULA web service overlap. These are analytics/strategy, not validation. |
| Layer 3 | Lab optimizer (Alg 1) | **KEEP** | Hemogram bundling + duplicate detection have no MEDULA equivalent. |
| Layer 3 | Drug optimizer (Alg 2) | **KEEP** | Generic substitution is procurement optimization. |
| Layer 3 | Copay savings (Alg 3) | **KEEP** | EK-1A proactive discovery has no MEDULA equivalent. |
| Layer 3 | Billing strategy (Alg 4) | **KEEP** | Package vs itemized comparison has no MEDULA equivalent. |
| Layer 3 | Material pre-check (Alg 5) | **KEEP with reframe** | ICD-10→specialty mapping and gazette ceiling analysis have no MEDULA equivalent. Pre-auth/MIAT catalog mirroring should be verified against actual MEDULA enforcement before relying on. |
| Layer 3 | Billing orchestrator | **KEEP** | Cohort aggregation has no MEDULA equivalent. |
| Catalog | SUT catalog loader | **KEEP** | MEDULA's `guncelSutKodlari` is real-time lookup; BILUN's parquet catalogs enable historical queries and batch analysis. Different purpose. |
| New | Pre-MEDULA compliance checks | **CONSIDER** | 9 potential features in Category D above — drug payment awareness, dose checks, MR/CT sequencing, sevk awareness, procedure conflicts, drug report matching, ICU material eligibility, barcode-SUT matching, procedure frequency. |

**Bottom line (2026-06-02, Phase 5):** Do not delete Layer 1. Classify EK-3B-1/2 and L1.4 prose as **ADDITIVE** vs MEDULA ICU/procedure/ÜTS blocking — see [`material_bundling_medula_boundary.md`](material_bundling_medula_boundary.md) and [`medula_overlap_gaps.md`](../../reports/sut-fact-check/medula_overlap_gaps.md). Keep Layers 2–3; optional Category D integrations (ICU-group pre-check, `barkodSutEslesmeSorgu`) remain backlog.
