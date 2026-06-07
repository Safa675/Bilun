import type { ExactnessStatus } from "./domains/sut";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { translate } from "@/lib/i18n/translate";
import {
  formatRequiredInputsLocalized,
  translateApiText,
  translateUnavailableReason,
} from "@/lib/apiMessages";

export interface ExactnessLike {
  exactness_status?: ExactnessStatus | null;
  pricing_status?: ExactnessStatus | null;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[] | null;
}

function activeMessages() {
  return getModuleLocale() === "tr" ? trMessages : enMessages;
}

function t(key: string, params?: Record<string, string | number | undefined | null>): string {
  return translate(activeMessages(), key, params);
}

export function isExactOutput(block: ExactnessLike | null | undefined): boolean {
  return block?.exactness_status === "exact" || block?.pricing_status === "exact";
}

export function isOptionalIngestPending(
  block: ExactnessLike | null | undefined,
): boolean {
  return block?.exactness_status === "not_applicable";
}

export function hasRecoverableBillingTotals(
  block: ExactnessLike | null | undefined,
): boolean {
  return (
    isExactOutput(block) ||
    block?.exactness_status === "partial_exact"
  );
}

export function formatRequiredInputs(inputs: string[] | null | undefined): string {
  return formatRequiredInputsLocalized(inputs);
}

export function getUnavailableMessage(
  block: ExactnessLike | null | undefined,
  fallback: string,
): string {
  const reason = block?.unavailable_reason?.trim();
  const inputs = formatRequiredInputsLocalized(block?.required_inputs_missing);
  const localizedReason = reason ? translateUnavailableReason(reason) : "";
  if (localizedReason && inputs) {
    return t("api.exactness.reasonWithInputs", {
      reason: localizedReason,
      inputs,
    });
  }
  if (localizedReason) {
    return localizedReason;
  }
  if (inputs) {
    return t("api.exactness.missingInputs", { inputs });
  }
  return translateApiText(fallback) || fallback;
}
