---
title: "SUT Regulatory Engine"
aliases: ["sut-engine", "sut-module", "sut-pricing"]
tags: [module, sut, turkish-healthcare, compliance, status/provisional]
type: core-system
status: provisional
source: "src/bilun/domain/__init__.py"
last_compiled: 2026-04-16
model: "claude-opus-4-6"
llm_summary: "SUT engine encodes Turkish healthcare billing rules from 37 curated gazette parquets (115K rows) into queryable pricing, copay, and billing audit APIs — no PHI required."
llm_keywords: [sut, sgk, gazette, pricing, copay, billing, reimbursement, turkish-healthcare]
llm_questions:
  - "What does SUT do?"
  - "What data does SUT need?"
  - "How many SUT codes are there?"
  - "Does SUT require patient data?"
  - "What is the SUT wedge strategy?"
related: ["[[acibadem-primary-strategy]]", "[[gazette]]", "[[sgk-sut-regulatory-context]]"]
---

# SUT Regulatory Engine

## Key Facts

- **Data**: 37 curated parquets, 115,568 rows from 393 unique gazette documents (444 manifest entries). No PHI — public regulatory data only.
- **EK-2B procedures**: 7,129 codes with point-based pricing. EK-3 materials: 3,265 items across 27 specialties (8 annexes empty).
- **EK-4A drugs**: 8,428 entries with tier classification, generic substitution, reimbursability.
- **Value proposition**: Revenue recovery from under-coding (2-5% of SUT-eligible revenue left on table). Not price tracking (that's solved).
- **API**: 15+ endpoints under `/api/` — pricing, copay simulation, billing audit, optimization.

The SUT module (`src/bilun/domain/`) is ILAY's rules engine for the **Saglik Uygulama Tebligi** (Health Implementation Communique) — the master regulation published by Turkey's Social Security Institution (SGK) that governs healthcare pricing, reimbursement ceilings, copayment rates, and billing rules for every service delivered to publicly insured patients. It encodes the gazette-published tariff schedules into queryable, patient-level cost estimates and normative billing recommendations.

This module is ILAY's **standalone commercial wedge** (see [[acibadem-primary-strategy]]): it requires **no PHI**, ships against committed gazette data, and solves an acute pain point for every Turkish private hospital that bills SGK.

## Key capabilities

- **Procedure pricing (EK-2B)** — 7,129 SUT procedure codes with point-based pricing and katsayi (coefficient) multiplication.
- **Material pricing (EK-3)** — 3,265 specialty materials across 27 discipline catalogs (cardiology, CV surgery, orthopedics, etc.) with reimbursability checks and gazette price ceilings. 8 annex files are empty (0 rows).
- **Drug tier pricing (EK-4A)** — Drug lookup, generic substitution recommendations, tier classification, and passivated drug detection.
- **DRG package costing (EK-2C)** — Median-based package prices by ICD-10 chapter with Turkish clinical keyword matching for chapter-specific narrowing.
- **Copay optimization** — EK-1A exemption detection, EK-2C-1 rate corrections, EK-2G no-surcharge validation.
- **Billing audit** — Hemogram bundling, duplicate test detection, DRG unbundling detection, temporal price auditing, drug discount tier validation.

> [!important]
> Active runtime exactness policy: see [[2026-05-03-sut-rule-exact-no-approximation]]. The current direction is that active `src/bilun/domain/` product surfaces must be exact-rule-only; approximate or simulated findings must be rewritten exactly or surfaced as unavailable.

> [!note]
> Phase 1 exactness classification is captured in [[sut-phase-1-exactness-audit-2026-05-03]].

> [!note]
> Phase 2 canonical historical pricing is captured in [[sut-phase-2-canonical-pricing-2026-05-03]].

> [!note]
> Phase 3 DRG analytics exactness is captured in [[sut-phase-3-drg-exactness-2026-05-03]].

> [!note]
> Phase 4 billing strategy provenance gating is captured in [[sut-phase-4-billing-gate-2026-05-03]].

> [!note]
> Phase 6 contract/cache/type alignment is captured in [[sut-phase-6-contract-cache-ui-2026-05-03]].

> [!note]
> Phase 7 frontend exactness rendering is captured in [[sut-phase-7-frontend-exactness-2026-05-03]].

> [!note]
> Current Patient SUT search/runtime gaps are captured in [[sut-patient-runtime-gap-diagnosis-2026-05-11]].

## Submodules

| Submodule | Role |
|-----------|------|
| `constants` | Tariff maps, code crosswalks (`ILAY_TO_SUT_CODE`), ICD-10-to-EK-2C group mappings, default prices, file paths |
| `utils` | Turkish-locale string normalization (`turkish_lower`) and safe type coercion helpers |
| `catalog` | Unified catalog loader with 3-tier fallback strategy (curated parquet, JSON cache, raw parse); all price-lookup APIs for EK-2A visits, EK-2B procedures, labs |
| `loaders` | Raw gazette parsing (`parse_ek2b`, `parse_ek2c`), curated parquet loading by as-of date, JSON export |
| `materials` | EK-3 specialty material catalogs, EK-4A drug catalog, reimbursability and bundling checks, drug tier classification |
| `estimators` | Dataclasses (`PatientSUTEstimate`, `SUTCostBreakdown`, `CopaymentEstimate`) and per-component cost estimators (lab, visit, procedure, Rx, copay) |
| `pricing` | Patient-level and cohort-level cost orchestration; DRG package price computation with ICD-10 keyword filtering |
| `analytics` | Reimbursement gap analysis, DRG episode summarization, material cost estimation |
| `billing` | 5-algorithm normative engine: lab billing, drug cost, copay savings, package-vs-itemized, material pre-check; cohort aggregation |
| `optimization` | Rule-level checks: copay exemptions, surcharge exposure, temporal price audits, DRG unbundling detection, drug discount tier validation |

> [!note] Ten items, eight conceptual groups
> `billing` and `optimization` form the core billing-audit subsystem. Their package `__init__.py` files are the stable import surfaces for route and analytics callers.

## Data sources

The engine runs against **37 curated gazette parquet files** committed to the repository under `data/gazette/curated/`. These are cleaned extracts from official SGK Resmi Gazete publications covering the 2025 and 2026 SUT editions. See [[gazette]] for the full inventory and the raw/curated/snapshot directory layout.

Key datasets:
- EK-2B procedure catalog (curated by as-of date)
- EK-2C DRG package catalog (curated by as-of date)
- EK-3 specialty material catalogs (27 discipline-specific parquets)
- EK-4A drug reference list
- EK-1A exemption lists, EK-2C-1 copay rate tables, EK-2G no-surcharge lists

## API endpoints

All routes are served under `/api/`:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/validate-claim` | Validate a claim against bundling and coverage rules |
| GET | `/api/procedure/{code}` | Procedure price lookup (EK-2B) |
| GET | `/api/material/{code}/pricing` | Material search across EK-3 catalogs |
| GET | `/api/optimization-summary` | Aggregated 6-engine optimization findings |
| GET | `/api/patient/{id}/optimization` | Per-patient SUT optimization report |
| GET | `/api/patient-alerts` | Patient-level billing alerts |
| GET | `/api/revenue-recovery` | Revenue recovery opportunities |
| GET | `/api/billing-report/{id}` | Full billing report for a patient |
| GET | `/api/bundled-consumables` | List of bundled (non-separately-billable) consumables |

## Commercial value

The SUT engine is ILAY's **standalone commercial wedge** for Turkish private hospitals:

1. **No PHI required** — operates entirely on gazette-published regulatory data, eliminating data-sharing barriers.
2. **Immediate pain point** — hospitals currently look up SUT prices manually from 300+ page gazette PDFs; this engine makes every code queryable in milliseconds.
3. **Revenue recovery** — the billing optimizer surfaces concrete TRY-denominated savings from hemogram bundling, generic substitution, copay exemption capture, and DRG package selection.
4. **Compliance de-risking** — temporal price auditing and unbundling detection reduce SGK audit clawback exposure.

SUT sits alongside [[ihs]] as one of two product surfaces in the [[acibadem-primary-strategy]]: IHS is the institutional path (Acıbadem clinical partnership), SUT is the commercial path (direct sale to Turkish private hospitals, no data partnership required).

## Data inventory — 115,568 rows across 37 parquet files

The complete SUT curated dataset, broken down by annex. All volumes come from `data/gazette/curated/` and `src/bilun/domain/constants.py` which registers the file paths.

| Annex | Rows | Purpose |
|---|---:|---|
| EK-2B (procedure history) | 76,600 | Full temporal history of SUT procedure prices and point values across gazette versions |
| EK-2B (flat / as-of snapshot) | 7,129 | The flat current procedure catalog used for fast price lookups |
| EK-2C (DRG package history) | 26,412 | Temporal history of DRG package prices by ICD-10 chapter |
| EK-4A (drug reference) | 8,428 | Drug catalog with tier classification, generic substitution pointers, reimbursability status |
| EK-2C-1 (copay rate ceilings) | 465 | Procedures with copay-rate ceilings (20%, 40%, 50%, 70%, 75%) |
| EK-2G (no-surcharge procedures) | 213 | Procedures for which patients cannot be charged any additional fee beyond SGK payment |
| EK-1A (copay exemptions) | 98 | Chronic disease ICD-10 ranges that exempt patients from copay entirely |
| EK-2A (visits) | 87 | Visit-code catalog with point values and katsayi multipliers |
| EK-3 (materials, 25 annexes) | 3,265 | Specialty-specific material catalogs (cardiology, CV surgery, orthopedics, etc.). 8 annexes are empty (0 rows). |
| Check-up JSON | 64 | 41 labs + 23 procedures with katsayi 0.593 for standard check-up packages |

**Total curated rows:** **115,568 rows across 37 parquet files**. Derived from **393 unique SGK gazette source documents** (444 manifest entries) tracked in `version_manifest.parquet`. The 2026.01.17 SUT Değişiklik Tebliği (Change Communiqué) is the latest major update incorporated.

This is the quantitative moat for any SUT-coding-copilot pitch: **115K curated rows is the regulatory knowledge base** ILAY has compiled and keeps current. No HBYS vendor publicly positions themselves as having this — most embed SUT compliance inside their transaction flow without exposing the underlying knowledge as a product. See [[turkish-his-white-space]] for the wedge ranking and [[sgk-sut-regulatory-context]] for the regulatory cadence context.

## Dual-engine framing: "one learns, one enforces"

A key pitch framing that emerged during the Harvard-Koç hackathon preparation: **IHS and SUT are complementary engines, not competitors for the same pitch narrative.**

- **IHS** = probabilistic ML engine. It learns patterns from historical data and predicts future clinical risk with calibrated probabilities. It is uncertain by construction because the future is uncertain.
- **SUT** = deterministic rule engine. It enforces the current gazette-published billing rules against submitted claims and produces yes/no compliance verdicts with specific rule citations.

**Slogan for external material:** "One learns, one enforces." This pre-empts the judge question "why not one model?" — the answer is that clinical deterioration prediction and regulatory compliance are **fundamentally different problem shapes**. Deterioration is a probabilistic inference problem; compliance is a deterministic rule-application problem. Conflating them produces a system that is bad at both.

**Pitch copy that goes with the framing:** "Compiled from 393 unique SGK gazette documents, full 2013-2026 temporal history — every pre-bill validated as-of the admission date." This communicates three things simultaneously: (1) the data volume, (2) the temporal depth, and (3) the fact that claims are validated against the rule version that was in effect on the date of service, not the current rule version. The temporal-as-of semantics matters because SGK audits retrospectively — a claim made under the 2024 rule version is evaluated against the 2024 rules, not the 2026 rules, and mixing them up creates audit liability.

## EK-2G: the phantom flag rate (chapter-level ICD matching bug)

> [!note] Unverifiable
> The specific patient counts below (192,919 / 210,606 patients, 91.6%, 36.3M flag occurrences) are from an analysis whose code is not committed to the repository. The qualitative description of the EK-2G chapter-level matching bug remains accurate.

**The observation:** the EK-2G surcharge-compliance check historically flagged an extremely high percentage of patients due to chapter-level ICD matching. Every rational intuition says this is wrong — most patients are not committing surcharge violations.

**Root cause:** the EK-2G rule matching happens at the **ICD-10 chapter letter level**, not at the procedure level. A patient with diagnosis code `I10` (essential hypertension) matches chapter `I` (circulatory system diseases), which triggers all **~188 EK-2G rules under chapter I** as potential violations, even though those rules are actually about specific *procedures* in circulatory care, not about every patient who has ever had a circulatory diagnosis.

**The fundamental problem:** EK-2G is a **procedure-based** regulation ("you cannot charge additional fees for these specific procedures"), but ILAY's current data is **diagnosis-based** (we have ICD codes from the patient's visit history, not procedure codes from their billed items). Chapter-level ICD matching is a rough approximation that produces dramatically inflated flag counts.

**This is the "SUT synthetic data gap" and should be framed honestly in pitches.** ILAY cannot do true EK-2G compliance without procedure codes, which Acıbadem's current data extract does not contain. The real production use case requires the hospital to supply procedure-level billing data as part of the integration.

**In pitch material, this constraint must be disclosed rather than hidden.** Saying "we flag 91.6% of patients as at-risk" is technically true but profoundly misleading. The honest framing is: "procedure-level SUT compliance requires procedure codes from your HIS; the current ILAY demo uses diagnosis codes as a stand-in and is therefore overfit to chapter-level matches. Once connected to your actual billing data, the flag rate drops to the true positive rate for EK-2G violations, which we estimate to be in the low single-digit percent range based on published audit rates."

**Design rule:** whenever an ILAY SUT check flag rate exceeds ~10-15% of the cohort, the check is almost certainly matching at the wrong granularity. Real SUT violations are rare; high flag rates are a sign of rule matching that is too permissive.

## Copay exemption gaps — ILAY only covers EK-1A (66.6% of exempt patients)

**The observation:** ILAY's copay exemption detector only checks against **EK-1A**, the chronic disease ICD-10 exemption list (98 ICD-10 ranges). This correctly identifies **140,332 / 210,606 = 66.6% of patients as exempt**, which is the fraction of the Acıbadem cohort carrying at least one EK-1A-eligible chronic diagnosis.

**What ILAY is missing:** Turkish SUT has **seven other exemption categories** beyond EK-1A, and these are **status-based** rather than diagnosis-based:

| Exemption category | Description | Data requirement |
|---|---|---|
| **Şehit / gazi / yakınları** | Veterans, combat-wounded, and their relatives | Government ID linkage |
| **Vatani hizmet erleri** | Those who served in certain national-service capacities | Government ID linkage |
| **2022 sayılı kanun** (65 yaş aylığı) | Elderly allowance beneficiaries aged 65+ | Age + SGK benefit status |
| **Yeşil kartlılar** | "Green card" holders (income-based healthcare benefit) | SGK benefit status |
| **İş kazası / meslek hastalığı** | Work accident / occupational illness | Employment and diagnosis data |
| **Acil servis başvuruları** | Emergency service visits (copay waived during emergency) | Visit type from HIS |
| **Koruyucu sağlık** | Preventive health services | Visit type / encounter code |

None of these are encoded in ICD-10. All of them require **status information** that ILAY does not currently receive — either because the hospital doesn't have it (government ID linkage) or because it's not being piped through to ILAY's data extract (emergency-vs-routine visit type, SGK benefit status flags).

**EK-2C-1 is different from copay exemption — don't conflate them.** EK-2C-1 is a **copay rate ceiling list** (465 procedures with explicit copay rates of 20%, 40%, 50%, 70%, or 75%). EK-2C-1 does not exempt patients from copay; it *caps* the copay rate. The ILAY copay module handles EK-2C-1 separately from EK-1A, and the two should not be mixed in analytical summaries.

**Honest pitch framing:** "ILAY covers the largest single exemption category (EK-1A chronic diseases, ~67% of exempt patients in the Acıbadem cohort). Full SUT exemption coverage requires status-based data that varies by hospital and by integration scope. For a production deployment, we map the additional categories to whichever data fields your HIS exposes."

**Do not claim** that ILAY produces complete copay exemption analysis. It doesn't. The 66.6% figure is a real but partial result.

## Gazette prices are uniformly +10/+20% — the real value is coding, not pricing

A counter-intuitive finding from a price-change audit across the 2024 → January 2026 gazette updates:

> [!note] Unverifiable
> The specific numbers below (14,110 codes, 14,108 increased, 2 decreased) are from an analysis whose code is not committed to the repository. The qualitative description of the price audit pattern (uniform +10/+20% increases) remains accurate.

| Statistic | Value |
|---|---:|
| Codes compared | ~14,000 |
| Codes that increased | ~100% |
| Codes unchanged | ~0 |
| Codes decreased | ~0 |
| Median increase | **+20%** |
| P10 increase | +10% |
| P50-P95 range | +20% |
| Max increase | +247.6% (on a small number of outlier codes) |

Within January 2026 alone, a small percentage of codes changed mid-month. Amendment frequency:

- **2024:** ~9 gazette amendments (roughly one every 5-6 weeks)
- **2025:** 8 gazette amendments
- **2026:** 4 amendments already by January 31

**The strategic insight:** Turkish SUT price-update complexity is **embarrassingly uniform**. Most updates are flat +10% or +20% across the board with a few code-specific adjustments layered on top. Any competent HBYS vendor can ship those pricing updates by running a simple percentage multiplier across their price catalog. **MEDULA already rejects non-compliant claims in real-time** — so if you bill at the wrong price, you get rejected at submission, not at audit, and the feedback loop is fast.

**Conclusion: the real SUT value is not tracking prices.** Price tracking is table stakes, already solved, and not a wedge. **The real SUT value is catching revenue leakage from under-coding** — when a hospital coder uses a simpler code than the procedure actually warrants, and the hospital gets paid less than they were entitled to. This leakage is invisible because it never triggers a rejection at submission (the bill was compliant — just sub-optimal), and it compounds across thousands of visits.

**Business model implication:** a SUT *pricing* copilot is a weak business because pricing is a solved problem. A SUT *coding* copilot is a strong business because coding is where the revenue leakage hides. The typical take-rate on recovered delta from under-coding is **3-5% of the recovered amount**, which is enough to sustain a SaaS subscription model without being so large it triggers hospital procurement caution.

**Pitch rule:** never lead with "we track price updates for you." Lead with "we catch the 2-5% of SUT-eligible revenue your hospital is currently leaving on the table from under-coding." The first framing is a commodity; the second is a CFO pain point.

## See also

- `src/bilun/domain/__init__.py` — root package (no re-exports by design)
- `src/bilun/domain/billing/__init__.py` — billing package entrypoint
- [[acibadem-primary-strategy]] — current strategic framing
- [[gazette]] — gazette parquet inventory
- [[sgk-sut-regulatory-context]] — regulatory background
