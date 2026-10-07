import type {
  CopayExemptionResult,
  ExemptionSource,
  PatientAlertCopay,
} from "@/lib/domains/sut";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { translate } from "@/lib/i18n/translate";

type Translate = (key: string) => string;

function activeTranslate(key: string): string {
  return translate(getModuleLocale() === "tr" ? trMessages : enMessages, key);
}

export function formatExemptionCategory(category: string, t: Translate = activeTranslate): string {
  const key = category.trim().toLowerCase();
  const messageKey = `optimizer.exemptionCategories.${key}`;
  const label = t(messageKey);
  return label !== messageKey ? label : category.replaceAll("_", " ");
}

export function getExemptionCategories(
  copay: CopayExemptionResult | PatientAlertCopay,
): string[] {
  const sources = copay.exemption_sources ?? [];
  if (sources.length > 0) {
    return sources
      .map((source) => source.category)
      .filter((category): category is string => Boolean(category));
  }
  if (copay.exempt && (copay.n_qualifying ?? 0) > 0) {
    return ["ek1a_chronic"];
  }
  if (copay.exempt && copay.primary_exemption_category) {
    return [copay.primary_exemption_category];
  }
  return [];
}

export function hasEk1aExemption(categories: string[]): boolean {
  return categories.includes("ek1a_chronic");
}

export function formatExemptionBasisSummary(categories: string[], t: Translate = activeTranslate): string {
  if (categories.length === 0) {
    return "";
  }
  return categories.map((category) => formatExemptionCategory(category, t)).join(" · ");
}

export type { ExemptionSource };
