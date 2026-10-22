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

/**
 * Where a patient stands on the copay exemption:
 * - `exempt`: at least one ground counts;
 * - `partial`: an EK-1/A diagnosis matched, but the chronic health report the waiver needs
 *   (SUT §1.8.5(7)) is not on file or not known, so no waiver is claimed;
 * - `none`: nothing matched.
 * Reads `partial_exempt` when the payload carries it, else the EK-1/A source that does not count.
 */
export type CopayExemptionState = "exempt" | "partial" | "none";

export function getCopayExemptionState(copay: {
  exempt?: boolean | null;
  partial_exempt?: boolean | null;
  exemption_sources?: ExemptionSource[] | null;
}): CopayExemptionState {
  if (copay.exempt) {
    return "exempt";
  }
  if (copay.partial_exempt) {
    return "partial";
  }
  const unmetEk1a = (copay.exemption_sources ?? []).some(
    (source) => source.category === "ek1a_chronic" && source.counts_toward_exempt === false,
  );
  return unmetEk1a ? "partial" : "none";
}

/**
 * The ground an exempt patient is exempt on: `primary_exemption_category` when the payload has it (the
 * patient-alerts rows do not), else the first source that counts, else EK-1/A for a legacy payload with
 * qualifying diagnoses only. Null when nothing exempts.
 */
export function getPrimaryExemptionGround(copay: {
  exempt?: boolean | null;
  n_qualifying?: number | null;
  primary_exemption_category?: string | null;
  exemption_sources?: ExemptionSource[] | null;
}): string | null {
  if (!copay.exempt) {
    return null;
  }
  if (copay.primary_exemption_category) {
    return copay.primary_exemption_category;
  }
  const counting = (copay.exemption_sources ?? []).find(
    (source) => source.category && source.counts_toward_exempt !== false,
  );
  if (counting) {
    return counting.category;
  }
  return (copay.n_qualifying ?? 0) > 0 ? "ek1a_chronic" : null;
}

export function formatExemptionBasisSummary(categories: string[], t: Translate = activeTranslate): string {
  if (categories.length === 0) {
    return "";
  }
  return categories.map((category) => formatExemptionCategory(category, t)).join(" · ");
}

export type { ExemptionSource };
