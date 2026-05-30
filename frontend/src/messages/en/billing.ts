const billing = {
  "summary": {
    "title": "Patient billing report",
    "description": "Normative SUT rule review across labs, drugs, copay policy, billing strategy, and materials controls.",
    "partialExact": "Partial exact",
    "ruleCalculatedOpportunity": "Rule-calculated opportunity",
    "recommendedActions": "Recommended actions",
    "reviewSections": "Review sections",
    "priorityTier": "Priority tier",
    "partialTotalsNotice": "Section totals are exact where marked; review section-level exactness before treating the aggregate as fully exact.",
    "totalsUnavailableNotice": "Billing totals remain unavailable until every billing section is exact."
  },
  "lab": {
    "title": "Lab optimization",
    "unavailable": "Lab optimization findings are unavailable until the billing input contract is exact.",
    "test": "Test",
    "sutCode": "SUT code",
    "gazettePrice": "Gazette price",
    "flag": "Flag",
    "savings": "Savings"
  },
  "drug": {
    "title": "Drug optimization",
    "unavailable": "Drug optimization savings require exact dispensed drug claim lines and billed drug amounts.",
    "drug": "Drug",
    "issue": "Issue",
    "alternative": "Alternative",
    "savings": "Savings",
    "tierCorrection": "Tier correction",
    "tierCorrectionSameDrug": "Tier correction on same drug"
  },
  "copay": {
    "title": "Copay optimization",
    "unavailable": "Copay optimization totals remain unavailable until both visit and prescription claim inputs are exact.",
    "exempt": "Exempt",
    "notExempt": "Not exempt",
    "visitSavings": "Visit copay savings",
    "rxSavings": "Rx copay savings",
    "totalSavings": "Total copay savings",
    "procedure": "Procedure",
    "billed": "Billed",
    "payable": "Payable",
    "copayComponent": "Copay component",
    "gazetteRate": "Gazette rate",
    "correction": "Correction"
  },
  "strategy": {
    "title": "Billing strategy",
    "unavailable": "Billing strategy recommendations require exact billed procedure lines.",
    "claim": "Claim",
    "recommendation": "Recommendation",
    "chapter": "Chapter",
    "group": "Group",
    "strategy": "Strategy",
    "packageTotal": "Package total",
    "itemizedTotal": "Itemized total",
    "savings": "Savings"
  },
  "materials": {
    "title": "Materials pre-check",
    "unavailable": "Material ceiling estimates remain unavailable until this section is fully exact.",
    "preAuth": "Pre-authorization required",
    "miat": "MIAT restricted",
    "sutCode": "SUT code",
    "material": "Material",
    "gazettePrice": "Gazette price",
    "note": "Note",
    "miatPeriod": "MIAT period",
    "ceilingEyebrow": "Gazette ceiling (p90) by specialty"
  },
  "sutOptimization": {
    "title": "SUT optimization findings",
    "copayEyebrow": "Copay exemption",
    "ek1aQualifying": "{count} EK-1A qualifying diagnoses",
    "exemptStatusVisit": "Exempt on status or visit-type grounds",
    "noWaiver": "No waiver grounds matched",
    "surchargeEyebrow": "Surcharge compliance",
    "flags": "{count} flags",
    "copayRateEyebrow": "Copay rate compliance",
    "cappedProcedures": "{count} capped procedures",
    "noRateCaps": "No rate caps applicable",
    "drgEyebrow": "DRG unbundling risk",
    "potentialSavings": "Potential savings: {amount}",
    "surchargeUnavailable": "Surcharge compliance needs exact billed procedure codes and procedure dates.",
    "copayRateUnavailable": "Copay rate compliance needs exact billed procedure codes and procedure dates.",
    "drgUnavailable": "DRG unbundling risk needs exact itemized billed procedure lines and package eligibility context."
  }
} as const;

export default billing;
