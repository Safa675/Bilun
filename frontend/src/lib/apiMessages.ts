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

function snakeToCamel(value: string): string {
  return value.replace(/_([a-z0-9])/g, (_, char: string) => char.toUpperCase());
}

const UNAVAILABLE_REASON_CODE_KEYS: Record<string, string> = {
  exact_claim_dataset_unavailable: "api.unavailableReason.exactClaimDatasetUnavailable",
  exact_claim_lines_missing_for_patient: "api.unavailableReason.exactClaimLinesMissingForPatient",
  exact_claim_patient_totals_missing: "api.unavailableReason.exactClaimPatientTotalsMissing",
  bilun_data_source_metadata_missing: "api.unavailableReason.bilunDataSourceMetadataMissing",
  bilun_data_source_config_invalid: "api.unavailableReason.bilunDataSourceConfigInvalid",
  bilun_data_source_metadata_invalid: "api.unavailableReason.bilunDataSourceMetadataInvalid",
  synthetic_demo_requires_is_synthetic_true: "api.unavailableReason.syntheticDemoRequiresIsSyntheticTrue",
  real_claims_requires_is_synthetic_false: "api.unavailableReason.realClaimsRequiresIsSyntheticFalse",
  bilun_data_source_mode_missing_or_invalid: "api.unavailableReason.bilunDataSourceModeMissingOrInvalid",
};

const UNAVAILABLE_REASON_TEXT_KEYS: Record<string, string> = Object.fromEntries(
  Object.entries(enMessages.api.unavailableReason).map(([key, text]) => [
    text,
    `api.unavailableReason.${key}`,
  ]),
);

const METHODOLOGY_TEXT_KEYS: Record<string, string> = Object.fromEntries(
  Object.entries(enMessages.api.methodology).map(([key, text]) => [
    text,
    `api.methodology.${key}`,
  ]),
);

const PROVENANCE_TEXT_KEYS: Record<string, string> = Object.fromEntries(
  Object.entries(enMessages.api.provenance).map(([key, text]) => [
    text,
    `api.provenance.${key}`,
  ]),
);

const CONSISTENCY_WARNING_TEXT_KEYS: Record<string, string> = Object.fromEntries(
  Object.entries(enMessages.api.consistencyWarning).map(([key, text]) => [
    text,
    `api.consistencyWarning.${key}`,
  ]),
);

const HEALTH_TEXT_KEYS: Record<string, string> = Object.fromEntries(
  Object.entries(enMessages.api.health).map(([key, text]) => [text, `api.health.${key}`]),
);

export function translateRequiredInput(input: string): string {
  const key = `api.requiredInput.${input}`;
  const translated = t(key);
  if (translated !== key) {
    return translated;
  }
  return input.replace(/_/g, " ");
}

export function formatRequiredInputsLocalized(inputs: string[] | null | undefined): string {
  if (!inputs?.length) {
    return "";
  }
  const filtered = inputs.filter((input) => input !== "exactness_status");
  if (filtered.length === 0) {
    return "";
  }
  return filtered.map(translateRequiredInput).join(", ");
}

export function translateUnavailableReason(value: string | null | undefined): string {
  return tryTranslateUnavailableReason(value) ?? value?.trim() ?? "";
}

function tryTranslateUnavailableReason(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "";
  }

  if (/^[a-z][a-z0-9_]*$/.test(trimmed)) {
    const mapped = UNAVAILABLE_REASON_CODE_KEYS[trimmed];
    if (mapped) {
      return t(mapped);
    }
    const camelKey = `api.unavailableReason.${snakeToCamel(trimmed)}`;
    const byCamel = t(camelKey);
    if (byCamel !== camelKey) {
      return byCamel;
    }
  }

  const drgPriceMatch = trimmed.match(
    /^No exact historical DRG price available for admission date (.+)$/,
  );
  if (drgPriceMatch) {
    return t("api.unavailableReason.drgEpisodeNoHistoricalPrice", {
      admissionDate: drgPriceMatch[1],
    });
  }

  const mappedText = UNAVAILABLE_REASON_TEXT_KEYS[trimmed];
  if (mappedText) {
    return t(mappedText);
  }

  return null;
}

export function translateMethodology(value: string | null | undefined): string {
  return tryTranslateMethodology(value) ?? value?.trim() ?? "";
}

function tryTranslateMethodology(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "";
  }

  const chapterMatch = trimmed.match(
    /^Review EK-2C package vs itemized billing eligibility for ICD-10 chapter (.+)\.$/,
  );
  if (chapterMatch) {
    return t("api.methodology.billingStrategyReviewDetail", { chapter: chapterMatch[1] });
  }

  const mapped = METHODOLOGY_TEXT_KEYS[trimmed];
  if (mapped) {
    return t(mapped);
  }

  return tryTranslateUnavailableReason(trimmed);
}

export function translateProvenanceText(value: string | null | undefined): string {
  return tryTranslateProvenanceText(value) ?? value?.trim() ?? "";
}

function tryTranslateProvenanceText(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "";
  }
  const mapped = PROVENANCE_TEXT_KEYS[trimmed];
  if (mapped) {
    return t(mapped);
  }
  return tryTranslateUnavailableReason(trimmed);
}

export function translateConsistencyWarning(value: string | null | undefined): string {
  return tryTranslateConsistencyWarning(value) ?? value?.trim() ?? "";
}

function tryTranslateConsistencyWarning(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "";
  }
  const mapped = CONSISTENCY_WARNING_TEXT_KEYS[trimmed];
  if (mapped) {
    return t(mapped);
  }
  return tryTranslateUnavailableReason(trimmed);
}

export function translateHealthMessage(value: string | null | undefined): string {
  return tryTranslateHealthMessage(value) ?? value?.trim() ?? "";
}

function tryTranslateHealthMessage(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "";
  }
  const mapped = HEALTH_TEXT_KEYS[trimmed];
  if (mapped) {
    return t(mapped);
  }
  return null;
}

export function translateValidationMessage(message: string): string {
  return tryTranslateValidationMessage(message) ?? message.trim();
}

function tryTranslateValidationMessage(message: string): string | null {
  const trimmed = message.trim();
  if (!trimmed) {
    return "";
  }

  if (trimmed === enMessages.api.validation.noMaterialsToValidate) {
    return t("api.validation.noMaterialsToValidate");
  }

  const bundlingMatch = trimmed.match(
    /^'(.+)' is bundled into the procedure price \(EK-3B-1: (.+), match=(.+)\)\. Cannot be billed separately\.(?: Potential savings: (.+) TRY\.)?$/,
  );
  if (bundlingMatch) {
    const [, materialName, category, matchKind, billedAmount] = bundlingMatch;
    let result = t("api.validation.bundlingViolationMessage", {
      materialName,
      category,
      matchKind,
    });
    if (billedAmount) {
      result += t("api.validation.bundlingViolationSavingsSuffix", { billedAmount });
    }
    return result;
  }

  const exclusionMatch = trimmed.match(
    /^'(.+)' is non-reimbursable per EK-3B-2 \((.+), match=(.+)\)\. SGK will not cover (.+) TRY\.$/,
  );
  if (exclusionMatch) {
    const [, materialName, label, matchKind, billedAmount] = exclusionMatch;
    return t("api.validation.exclusionViolationMessage", {
      materialName,
      label,
      matchKind,
      billedAmount,
    });
  }

  return null;
}

export function translateValidationSummary(summary: string): string {
  return tryTranslateValidationSummary(summary) ?? summary.trim();
}

function tryTranslateValidationSummary(summary: string): string | null {
  const trimmed = summary.trim();
  if (!trimmed) {
    return "";
  }

  if (trimmed === enMessages.api.validation.noMaterialsToValidate) {
    return t("api.validation.noMaterialsToValidate");
  }

  const separator = enMessages.api.validation.summarySeparator;
  const parts = trimmed.split(separator);
  let allUnknown = true;
  const translatedParts = parts.map((part) => {
    const claimValid = part.match(/^Claim (.+): VALID$/);
    if (claimValid) {
      allUnknown = false;
      return t("api.validation.claimValidSummary", { claimId: claimValid[1] });
    }

    const claimInvalid = part.match(/^Claim (.+): INVALID$/);
    if (claimInvalid) {
      allUnknown = false;
      return t("api.validation.claimInvalidSummary", { claimId: claimInvalid[1] });
    }

    const materialsTotal = part.match(/^(\d+) materials, ([\d.]+) TRY total$/);
    if (materialsTotal) {
      allUnknown = false;
      return t("api.validation.materialsTotalSummary", {
        materialCount: materialsTotal[1],
        totalAmount: materialsTotal[2],
      });
    }

    const bundling = part.match(
      /^(\d+) bundling violation\(s\), savings: ([\d.]+) TRY$/,
    );
    if (bundling) {
      allUnknown = false;
      return t("api.validation.bundlingViolationsSummary", {
        violationCount: bundling[1],
        savingsAmount: bundling[2],
      });
    }

    const exclusion = part.match(/^(\d+) exclusion violation\(s\), risk: ([\d.]+) TRY$/);
    if (exclusion) {
      allUnknown = false;
      return t("api.validation.exclusionViolationsSummary", {
        violationCount: exclusion[1],
        riskAmount: exclusion[2],
      });
    }

    const validatedIn = part.match(/^validated in ([\d.]+)ms$/);
    if (validatedIn) {
      allUnknown = false;
      return t("api.validation.validatedInSummary", { elapsedMs: validatedIn[1] });
    }

    return part;
  });

  // If none of the parts matched a known pattern, signal no-match so the
  // dispatcher and the public wrapper apply the generic placeholder.
  return allUnknown ? null : translatedParts.join(t("api.validation.summarySeparator"));
}

/**
 * Translate any known API prose string (reason, methodology, provenance,
 * warnings, validation messages). Unrecognized strings pass through unchanged
 * so legitimate domain content (often already localized by the backend) is not
 * lost behind a generic placeholder.
 */
export function translateApiText(value: string | null | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "";
  }

  const match =
    tryTranslateConsistencyWarning(trimmed) ??
    tryTranslateHealthMessage(trimmed) ??
    tryTranslateMethodology(trimmed) ??
    tryTranslateUnavailableReason(trimmed) ??
    tryTranslateProvenanceText(trimmed) ??
    tryTranslateValidationSummary(trimmed) ??
    tryTranslateValidationMessage(trimmed);

  return match ?? trimmed;
}
