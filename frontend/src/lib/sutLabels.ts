function toTitleCase(value: string | null | undefined): string {
  const normalized = value?.trim();
  if (!normalized) {
    return "Unknown";
  }

  return normalized
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export const SUT_ALERT_BADGE_LABELS = {
  exempt: "Exempt",
  notExempt: "Not exempt",
  flagged: "Flagged",
  clear: "Clear",
  unavailable: "Unavailable",
} as const;

export const SUT_ACTION_LABELS = {
  noActionNeeded: "No action needed",
} as const;

export const SUT_RISK_BUCKET_LABELS = {
  atRisk: "At risk",
  noRisk: "No risk",
} as const;

export const SUT_RISK_TIER_LABELS = {
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
} as const;

export const SUT_SEVERITY_LABELS = {
  error: "Error",
  warning: "Warning",
  info: "Info",
} as const;

export function getSutSeverityLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) {
    return SUT_SEVERITY_LABELS.info;
  }

  return SUT_SEVERITY_LABELS[normalized as keyof typeof SUT_SEVERITY_LABELS] ?? toTitleCase(value);
}

export function getSutRiskTierLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) {
    return "Unknown risk";
  }

  return SUT_RISK_TIER_LABELS[normalized as keyof typeof SUT_RISK_TIER_LABELS] ?? `${toTitleCase(value)} risk`;
}
