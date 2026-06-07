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
      "noActionNeeded": "No action needed"
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
      "none": "None"
    },
    "savingsCategory": {
      "lab": "Laboratory",
      "copay": "Copay exemption",
      "strategy": "Billing strategy"
    },
    "flagType": {
      "hemogram_unbundling": "Hemogram unbundling"
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
