import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { translate } from "@/lib/i18n/translate";

function activeMessages() {
  return getModuleLocale() === "tr" ? trMessages : enMessages;
}

function t(key: string, params?: Record<string, string | number | undefined | null>): string {
  return translate(activeMessages(), key, params);
}

function toTitleCase(value: string | null | undefined): string {
  const normalized = value?.trim();
  if (!normalized) {
    return t("labels.sut.unknown");
  }

  return normalized
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function getSutAlertBadgeLabel(
  key: keyof typeof enMessages.labels.sut.alertBadge,
): string {
  return t(`labels.sut.alertBadge.${key}`);
}

export function getSutActionLabel(
  key: keyof typeof enMessages.labels.sut.action,
): string {
  return t(`labels.sut.action.${key}`);
}

const RECOMMENDED_ACTION_LABEL_KEYS: Record<string, keyof typeof enMessages.labels.sut.action> = {
  "Do not charge surcharge": "doNotChargeSurcharge",
  "Apply capped copay rate": "applyEk2c1ListedRate",
};

export function getSutRecommendedActionLabel(action: string | null | undefined): string {
  const trimmed = action?.trim();
  if (!trimmed) {
    return getSutActionLabel("noActionNeeded");
  }
  const key = RECOMMENDED_ACTION_LABEL_KEYS[trimmed];
  return key ? getSutActionLabel(key) : t("labels.sut.unknown");
}

export function getSutSeverityLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) {
    return t("labels.sut.severity.info");
  }

  const known = enMessages.labels.sut.severity[normalized as keyof typeof enMessages.labels.sut.severity];
  return known ? t(`labels.sut.severity.${normalized}`) : toTitleCase(value);
}

/**
 * Map a backend `payment_method_kind` (uppercase enum: DRG_MANDATORY,
 * DRG_OVERRIDABLE, ITEMIZED, MISSING_INPUTS, NOT_IN_SUT) to a localized label.
 */
export function getPaymentMethodKindLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) {
    return t("labels.sut.unknown");
  }

  const known = enMessages.api.paymentMethodKind[
    normalized as keyof typeof enMessages.api.paymentMethodKind
  ];
  return known ? t(`api.paymentMethodKind.${normalized}`) : toTitleCase(value);
}

export function getSutRiskTierLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) {
    return t("labels.sut.unknownRisk");
  }

  const known = enMessages.labels.sut.riskTier[normalized as keyof typeof enMessages.labels.sut.riskTier];
  if (known) {
    return t(`labels.sut.riskTier.${normalized}`);
  }
  return t("labels.sut.dynamicRisk", { value: toTitleCase(value) });
}

function lookupDomainLabel(
  group: keyof Pick<
    typeof enMessages.labels.sut,
    "priority" | "actionType" | "savingsCategory" | "flagType" | "paymentMethod"
  >,
  normalized: string,
): string | null {
  const map = enMessages.labels.sut[group] as Record<string, string>;
  if (normalized in map) {
    return t(`labels.sut.${group}.${normalized}`);
  }
  return null;
}

export function getSutPriorityLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase().replace(/\s+/g, "_");
  if (!normalized) {
    return t("labels.sut.unknown");
  }

  const known = lookupDomainLabel("priority", normalized);
  if (known) {
    return known;
  }
  return toTitleCase(value);
}

export function getSutDomainLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase().replace(/\s+/g, "_");
  if (!normalized) {
    return t("labels.sut.unknown");
  }

  if (normalized === "unknown") {
    return t("labels.sut.unknown");
  }

  for (const group of ["savingsCategory", "actionType", "flagType", "paymentMethod", "priority"] as const) {
    const known = lookupDomainLabel(group, normalized);
    if (known) {
      return known;
    }
  }

  return toTitleCase(value);
}

/** @deprecated Use getSutAlertBadgeLabel — kept for tests importing constants */
export const SUT_ALERT_BADGE_LABELS = enMessages.labels.sut.alertBadge;
export const SUT_ACTION_LABELS = enMessages.labels.sut.action;
export const SUT_RISK_BUCKET_LABELS = enMessages.labels.sut.riskBucket;
export const SUT_RISK_TIER_LABELS = enMessages.labels.sut.riskTier;
export const SUT_SEVERITY_LABELS = enMessages.labels.sut.severity;
