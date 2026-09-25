const labels = {
  "sut": {
    "unknown": "Unknown",
    "unknownRisk": "Unknown risk",
    "dynamicRisk": "{value} risk",
    "alertBadge": {
      "exempt": "Exempt",
      "notExempt": "Not exempt",
      "flagged": "Flagged",
      "clear": "Clear",
      "unavailable": "Unavailable"
    },
    "action": {
      "noActionNeeded": "No action needed",
      "doNotChargeSurcharge": "Do not charge surcharge",
      "applyEk2c1ListedRate": "Apply EK-2C-1 listed rate"
    },
    "riskBucket": {
      "atRisk": "At risk",
      "noRisk": "No risk"
    },
    "riskTier": {
      "low": "Low risk",
      "medium": "Medium risk",
      "high": "High risk"
    },
    "priority": {
      "low": "Low",
      "medium": "Medium",
      "high": "High",
      "very_high": "Very High"
    },
    "actionType": {
      "lab": "Laboratory",
      "copay": "Copay exemption",
      "strategy": "Billing strategy",
      "none": "None",
      "session_uplift": "Session uplift",
      "drg_uplift": "DRG uplift",
      "yatak_puani": "Bed-day score",
      "materials": "Materials pre-check",
      "billing_strategy": "Billing strategy"
    },
    "savingsCategory": {
      "lab": "Laboratory",
      "copay": "Copay exemption",
      "strategy": "Billing strategy",
      "session_uplift": "Session uplift",
      "drg_uplift": "DRG uplift",
      "yatak_puani": "Bed-day score"
    },
    "ruleCategory": {
      "surcharge": "Surcharge (ilave ücret)",
      "copay_exemption": "Copay exemption",
      "copay_rate": "Copay rate",
      "payment_method": "Payment method",
      "pricing": "Pricing",
      "bundling": "Bundling",
      "material_exclusion": "Material exclusion",
      "material_preauth": "Material pre-auth",
      "material_miat": "Material MIAT",
      "specialty_materials": "Specialty materials",
      "drug_reimbursement": "Drug reimbursement",
      "drug_indication": "Drug indication",
      "drug_discount": "Drug discount",
      "lab_billing": "Lab billing",
      "drg_coding": "DRG coding",
      "procedure_pairing": "Procedure pairing",
      "material_pairing": "Material pairing",
      "drg_unbundling": "DRG unbundling",
      "claim_validation": "Claim validation",
      "billing_admin": "Billing admin",
      "medula_rejection": "MEDULA rejection",
      "administrative": "Administrative",
      "gap_closing": "Gap closing",
      "dental": "Dental",
      "treatment_pricing": "Treatment pricing",
      "drug_combination": "Drug combination",
      "fatura_inceleme": "Invoice review"
    },
    "flagType": {
      "hemogram_unbundling": "Hemogram unbundling",
      "session_fraction_overbilling": "Session fraction over-billing"
    },
    "paymentMethod": {
      "package": "Package",
      "itemized": "Itemized",
      "overridable": "Overridable"
    },
    "severity": {
      "error": "Error",
      "warning": "Warning",
      "info": "Info"
    }
  }
} as const;

export default labels;
