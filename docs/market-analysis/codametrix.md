---
title: "CodaMetrix (Autonomous Medical Coding)"
aliases: ["codametrix-coding"]
tags: [concept, market, competitor, rcm, status/provisional]
type: market-analysis
status: provisional
source: "external:https://www.prnewswire.com/news-releases/codametrix-chosen-by-health-systems-representing-180b-in-net-patient-revenue-302487502.html"
sources:
  - "external:https://www.prnewswire.com/news-releases/codametrix-chosen-by-health-systems-representing-180b-in-net-patient-revenue-302487502.html"
  - "external:https://www.fiercehealthcare.com/health-tech/himss24-codametrix-pockets-40m-series-b-build-out-ai-based-revenue-cycle-tools"
last_compiled: 2026-04-05
model: "claude-opus-4-6"
verified_at: 2026-04-13
llm_summary: "CodaMetrix — autonomous medical coding vendor (~$95M Series B, ~$600M Series C valuation, 220 hospitals = 12% US NPR). Closest functional analog to SUT optimization: rule + ML automation of reimbursement complexity."
llm_keywords: [codametrix, autonomous-coding, rcm, competitor, analog, funding, npr]
llm_questions:
  - "What is CodaMetrix?"
  - "How does CodaMetrix compare to ILAY SUT?"
  - "What's CodaMetrix's market share?"
  - "Is CodaMetrix a competitor?"
related: ["[[rcm-ai-market]]", "[[olive-ai-post-mortem]]", "[[rcm-pricing-models]]"]
---

# CodaMetrix (Autonomous Medical Coding)

## Summary

- **~$95M total funding** through Series B (2024), plus Series C ~$60M in 2026 at **~$600M valuation**
- **220 hospitals deployed**, representing **12% of US NPR ($180B)**
- Claims **70% denial reduction, 60% coding-cost reduction, 5-week faster cash** <!-- unverified: vendor marketing claims, no independent third-party validation found -->
- Claims **96%+ automation rate** on autonomous coding <!-- unverified: vendor self-reported metric -->
- Closest functional analog to SUT optimization (rule-driven + ML-driven automation of reimbursement complexity)

## Company facts

### Funding history
| Round | Amount | Date |
|---|---|---|
| Series A+B (cumulative) | ~$95M | Through HIMSS 2024 |
| Series B (lead tranche) | $40M | HIMSS 2024 |
| Series C | ~$60M | February 2026 |
| Valuation (Series C) | ~$600M | February 2026 |

### Customer traction
- **220 hospitals deployed**
- Customers represent **$180B in Net Patient Revenue (~12% of US NPR)**
- 50K+ providers served
- Partnerships with major academic medical centers

### Product and performance claims
- **96%+ automation rate** on autonomous medical coding <!-- unverified: vendor self-reported -->
- **70% denial reduction** claimed <!-- unverified: vendor marketing claim -->
- **60% coding-cost reduction** claimed <!-- unverified -->
- **5-week faster cash** from claim to payment <!-- unverified -->

### Technology positioning
- Autonomous medical coding (deep learning + NLP on clinical documentation)
- Targets the coding layer specifically (not full-stack RCM)
- ML models trained on clinical documentation → ICD/CPT codes
- Replaces or augments human coders

## Relevance to ILAY

- **Closest functional analog to SUT optimization**: both automate rule-heavy reimbursement complexity with ML
- **Series C valuation ($600M) is a defensible comp** for ILAY's future fundraising if ILAY executes on SUT + expands
- **Demonstrates specialist beats generalist in RCM**: CodaMetrix won by focusing on coding specifically, not by competing with Waystar/Optum on breadth
- **Traction model to replicate**: start with 1-2 marquee health systems (CodaMetrix started with Mass General Brigham), expand via referral
- **Pricing anchor**: CodaMetrix monetizes on coding volume — ILAY can monetize on claim volume or contingency on recovered revenue
- **Ceiling signal**: 220 hospitals after ~$95M raised means CAC is meaningful; ILAY's contingency model may scale faster if ROI is immediate

## Sources

- [CodaMetrix — 180B NPR customers](https://www.prnewswire.com/news-releases/codametrix-chosen-by-health-systems-representing-180b-in-net-patient-revenue-302487502.html)
- [CodaMetrix $40M Series B — Fierce Healthcare](https://www.fiercehealthcare.com/health-tech/himss24-codametrix-pockets-40m-series-b-build-out-ai-based-revenue-cycle-tools)
