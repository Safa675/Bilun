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
    "severity": {
      "error": "Error",
      "warning": "Warning",
      "info": "Info"
    }
  }
} as const;

export default labels;
