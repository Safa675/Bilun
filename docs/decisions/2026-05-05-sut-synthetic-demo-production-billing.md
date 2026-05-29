---
title: "SUT Synthetic Demo Production Billing"
aliases: ["synthetic SUT demo billing", "SUT demo production data", "synthetic claim demo mode"]
tags: [decision, sut, synthetic-data, billing, demo, exactness]
type: decision
status: provisional
source: "plans/synthetic-data-v2.md"
sources:
  - "plans/synthetic-data-v2.md"
  - "src/bilun/api/schemas.py"
  - "src/bilun/domain/claims/loader.py"
  - "src/bilun/cache/sut_context.py"
last_compiled: 2026-05-05
model: "gpt-5.5"
settled: false
llm_summary: "For demos before real hospital billing data exists, SUT billing should use exact synthetic claim-line data as a demo-production input, clearly labeled demo-scoped and designed to swap to real claim ingestion later."
llm_keywords: [sut, synthetic claims, demo production, billing, exactness, claim ingestion]
llm_questions:
  - "Should SUT billing use synthetic data in production demos?"
  - "How should synthetic SUT claim data be used before real billing data exists?"
  - "What is the migration path from synthetic SUT billing to real claim data?"
related: ["[[sut-dead-legacy-approximation-removal]]", "[[sut-rule-exact-no-approximation]]"]
---

# SUT Synthetic Demo Production Billing

## Context
- Current hospital clean clinical data is not suitable as a billing source because active SUT billing requires explicit claim/procedure/material/drug lines, not diagnosis-derived estimates.
- The synthetic SUT fixture now provides exact claim headers, procedure/material/drug lines, prescription linkage, lab billing linkage, and expected rule outputs.
- The near-term product goal is a rule-based demo. If a real contract is won, synthetic claim data should be replaced by real hospital billing claim data.

## Decision / Insight
- Synthetic SUT claim data is acceptable as the demo-production billing input only if the product labels it as demo/synthetic and does not present it as real hospital reimbursement.
- The runtime should treat synthetic and future real data through the same exact claim-line interface, so migration is a data-source swap rather than a rewrite.
- Clinical real data and synthetic billing data should not be silently blended as if they came from the same real patient record.

## Rationale
- Synthetic claim lines are more truthful for a rule-based demo than approximating billing from unsuitable clinical production data.
- Exact synthetic rows allow deterministic SUT rule demonstrations, golden tests, and product storytelling without PHI or unavailable hospital billing feeds.
- Demo credibility depends on transparency: exact rule behavior can be production-grade, but the sample billing data remains synthetic until real claims are integrated.

## Action Items
- Add an explicit SUT demo-data mode/data-source label in backend payloads and frontend copy.
- Route demo billing through `src/bilun/domain/claims/` exact claim loaders and keep missing real claims as unavailable, not estimated.
- Keep the claim schema stable enough that real hospital billing data can replace synthetic Parquets later.
- Expand synthetic scenarios for demo breadth only after the 5-patient fixture remains deterministic and validated.

## Source / Date
- Source: User input: "the reason off creating the syntethic data first place was acutally using in prodcution... our purpose here do a proper rule based system for demo. after demo if we can get a real contract then we are going to replace the synthetic data with the real hospital billing data"
- Date: 2026-05-05

## Phase 3 Provenance Contract Update

### Context
- SUT cache/API/frontend-config responses need a typed data-source contract so demo payloads cannot be mistaken for real hospital claim data.

### Decision / Insight
- SUT payloads that expose claim-derived totals, billing, optimization summaries, patient optimization, patient listings, or frontend config should carry `data_source`/`sut_data_source` metadata with `mode`, source labels, and `is_synthetic`.
- Missing or malformed provenance must be explicit `unavailable`, not treated as `real_claims`.

### Rationale
- Provenance is a product safety contract: exact SUT rules may run over synthetic demo claims, but API consumers must know when the underlying claim data is synthetic or unavailable.

### Action Items
- Keep frontend rendering copy aligned with the API metadata before presenting synthetic demo billing values.
- Preserve `real_claims` as `is_synthetic=false` only when configured real claim paths pass validation.

### Source / Date
- Source: User request: "Your scope is Phase 3 only: expose SUT data-source provenance in cache/API/frontend-config contracts."
- Date: 2026-05-05
