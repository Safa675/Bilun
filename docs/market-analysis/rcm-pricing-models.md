---
title: "RCM and Claims Intelligence Pricing Models"
aliases: ["rcm-pricing", "claims-ai-pricing"]
tags: [concept, market, commercial, pricing, status/provisional]
type: market-analysis
status: provisional
source: "external:https://www.getmonetizely.com/articles/procurement-guide-how-hospital-revenue-cycle-management-rcm-systems-are-priced-for-enterprises"
sources:
  - "external:https://www.getmonetizely.com/articles/procurement-guide-how-hospital-revenue-cycle-management-rcm-systems-are-priced-for-enterprises"
  - "external:https://www.vozohealth.com/blog/the-ultimate-guide-to-healthcare-software-pricing-models"
last_compiled: 2026-04-05
model: "claude-opus-4-6"
verified_at: 2026-04-13
llm_summary: "Pricing reference for RCM and claims-intelligence — percent-of-NPR for enterprise RCM platforms (Waystar/Optum), per-claim or per-provider for point-solutions, tiered SaaS for coding-automation AI."
llm_keywords: [pricing, rcm, claims-intelligence, percent-of-npr, per-claim, enterprise-contracts]
llm_questions:
  - "How is RCM priced?"
  - "What's percent-of-NPR pricing?"
  - "How do coding-AI vendors charge?"
  - "What's the RCM procurement playbook?"
related: ["[[rcm-ai-market]]", "[[waystar]]", "[[codametrix]]"]
---

# RCM and Claims Intelligence Pricing Models

## Summary

- **Three dominant pricing structures**: contingency (% of recovered revenue), per-claim, SaaS tiers
- **Contingency: 2-9%, typically 3-5%** of recovered revenue — outcome-aligned model hospitals prefer
- **Per-claim: $3-25/claim** volume-based
- **Point tools: $50K-$500K/year** SaaS; enterprise deals $1M-$10M+ ARR
- **Volume discounts**: 15-25% above 250 beds
- **Mid-size hospital typical contingency**: 4-7% with volume discounts

## Pricing model detail

### 1. Contingency (% of collections)
- **Range**: 2-9%
- **Typical mid-market**: 3-5% for full RCM services
- **ILAY-relevant**: 3-4% for specific claim scrubbing/denial recovery
- **How it works**: vendor takes percentage of recovered/collected revenue attributable to their intervention
- **Why hospitals prefer it**: outcome-aligned, no upfront risk, self-funding from recovered dollars
- **Why vendors prefer it**: deepens customer alignment, creates expansion pressure for vendor (recover more = earn more)
- **Contract cadence**: 3-year renewal typical

### 2. Per-claim pricing
- **Range**: $3-$25 per claim
- **Typical**: $5-15/claim for specialty tools, $3-8 for volume platforms
- **Variable cost model**: aligns vendor compensation with volume served
- **Volume discounts**: 15-25% reduction above 250-bed equivalent throughput
- **Contract cadence**: annual or multi-year

### 3. Per-user / per-provider SaaS
- **Common for**: coding tools, denial management point tools
- **Range**: $100-$500/user/month typical
- **Enterprise tier**: $50K-$500K/year
- **Feature-based tiering**: base/pro/enterprise packages

### 4. Enterprise contracts
- **Large health system deals**: $1M-$10M+ ARR
- **Waystar precedent**: serves 18 of 22 U.S. News top hospitals — enterprise contracts dominate
- **Multi-module bundling**: eligibility + claims + denials + analytics
- **Deal cycles**: 6-18 months

## Pricing by product category

| Product category | Typical model | Price range |
|---|---|---|
| Full RCM service | Contingency | 3-5% of collections |
| Claim scrubbing | SaaS per-bed OR contingency | $50K-$250K/year OR 2-3% contingency |
| Denial prediction/management | Per-claim OR contingency | $5-$15/claim OR 3-5% on recoveries |
| Coding automation | Per-claim OR subscription | $3-$8/claim OR $200K-$1M enterprise |
| Underpayment detection | Contingency | 10-25% of recovered underpayments |

## Mid-size hospital economics (250-500 beds)

| Metric | Typical |
|---|---|
| Annual claims volume | 100K-300K claims |
| Revenue per claim | $800-$2,500 average |
| Denial rate | 8-15% |
| Recoverable denial share | ~60% |
| Typical vendor contract size | $100K-$500K ARR |
| Contingency rate | 4-7% |

## Olive AI pricing lesson

- Olive used aggressive contingency + fixed-fee hybrid <!-- unverified: Olive's exact contract structure was never publicly documented; this is a plausible reconstruction from secondary post-mortem coverage -->
- Overcommitted to recovered-revenue claims that didn't materialize
- Hospitals stopped renewing when delivered ROI fell short
- **Lesson for ILAY**: be conservative in contingency promises; structure contracts to prove value before expanding

## Relevance to ILAY

### Recommended pricing model for ILAY

**Turkey Year 1 pricing (hybrid)**:
- **Wedge pricing (SUT claim validation)**: Contingency 3-4% of recovered revenue from claim-level optimization
  - 500-bed hospital with ₺50M annual SGK claims, 3% recovery = ₺1.5M potential, ILAY takes ₺45K-60K
  - Scales with customer value
- **Retention pricing (IHS + platform)**: Annual SaaS ₺200K-400K per hospital
  - Predictable revenue
  - Justifies ongoing gazette maintenance + rule-engine updates

**Chain-wide enterprise pricing**:
- ₺2M-5M/year for full chain deployment (60+ hospital groups like MLP Care)
- Covers: SUT optimization + IHS clinical intelligence + continuous gazette updates
- 3-year terms with annual price escalation (lira protection)

### Pricing discipline per Olive lesson
- **Contingency rates documented with audit trails**: recovered revenue must be independently verifiable
- **Customer sign-off required on attributed recovery**: no disputed ROI claims
- **Conservative initial commitments**: start at 3% contingency, negotiate up with proof of delivery
- **Avoid shared-savings overreach**: don't promise savings ILAY can't measure

### Mid-term commercial model evolution
- Year 1: Contingency wedge (easy buy for CFOs, self-funding)
- Year 2: Expand into SaaS retention (adds IHS, platform features)
- Year 3: Enterprise chain-wide deals (full platform, multi-module)
- Year 4+: Pursue US/MENA markets with adapted pricing

## Sources

- [Monetizely — Hospital RCM Pricing Guide](https://www.getmonetizely.com/articles/procurement-guide-how-hospital-revenue-cycle-management-rcm-systems-are-priced-for-enterprises)
- [Vozo Health — Pricing Models](https://www.vozohealth.com/blog/the-ultimate-guide-to-healthcare-software-pricing-models)
