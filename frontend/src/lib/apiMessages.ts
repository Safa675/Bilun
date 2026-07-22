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

function tryTranslateBillingProsePart(trimmed: string): string | null {
  const yatakSurgery = trimmed.match(
    /^Standart yatak \(510010\): (\d+) billable bed-day\(s\) \(gross LOS (\d+) day\(s\) at ([\d.]+) TRY\/day, surgery day (\S+) bundled into EK-2\/C package\) = ([\d.]+) TRY \(inclusive LOS, discharge day billed\)\.?$/,
  );
  if (yatakSurgery) {
    return t("api.billingProse.yatakStandardWithSurgery", {
      days: yatakSurgery[1],
      grossDays: yatakSurgery[2],
      rate: yatakSurgery[3],
      surgeryDay: yatakSurgery[4],
      amount: yatakSurgery[5],
    });
  }

  const yatak = trimmed.match(
    /^Standart yatak \(510010\): (\d+) billable bed-day\(s\) \(gross LOS (\d+) day\(s\) at ([\d.]+) TRY\/day\) = ([\d.]+) TRY \(inclusive LOS, discharge day billed\)\.?$/,
  );
  if (yatak) {
    return t("api.billingProse.yatakStandard", {
      days: yatak[1],
      grossDays: yatak[2],
      rate: yatak[3],
      amount: yatak[4],
    });
  }

  if (
    trimmed ===
    "Same-day admission/discharge — consider 510120 (gündüz yatak) instead of 510010 for <24h stays."
  ) {
    return t("api.billingProse.yatakSameDay");
  }

  const miat = trimmed.match(
    /^Catalog MIAT period: (.+) — verify interval vs patient history$/,
  );
  if (miat) {
    return t("api.billingProse.catalogMiat", { period: miat[1] });
  }

  if (
    trimmed ===
      "EK-3C-1 — tıbbi uygunluk (medical appropriateness) required before SGK submission (§3.1.2)" ||
    trimmed ===
      "EK-3C-1 — medical appropriateness (tıbbi uygunluk) required before SGK submission (§3.1.2)"
  ) {
    return t("api.billingProse.preauthNote");
  }

  if (trimmed === enMessages.api.billingProse.bundledEk3b1) {
    return t("api.billingProse.bundledEk3b1");
  }
  if (trimmed === enMessages.api.billingProse.bundledPackageFlag) {
    return t("api.billingProse.bundledPackageFlag");
  }
  if (trimmed === enMessages.api.billingProse.billedCorrectlyPackage) {
    return t("api.billingProse.billedCorrectlyPackage");
  }
  if (trimmed === enMessages.api.billingProse.billedCorrectlyItemized) {
    return t("api.billingProse.billedCorrectlyItemized");
  }

  const claimPackageOk = trimmed.match(
    /^Claim (.+) is billed correctly as package per SUT §2\.2\.2\(1\)\. Package total ([\d.]+) TRY\.$/,
  );
  if (claimPackageOk) {
    return t("api.billingProse.claimPackageOk", {
      claimId: claimPackageOk[1],
      amount: claimPackageOk[2],
    });
  }

  const claimItemizedOk = trimmed.match(
    /^Claim (.+) is billed correctly as itemized per SUT §2\.2\. Itemized total ([\d.]+) TRY\.$/,
  );
  if (claimItemizedOk) {
    return t("api.billingProse.claimItemizedOk", {
      claimId: claimItemizedOk[1],
      amount: claimItemizedOk[2],
    });
  }

  const claimMandatePackage = trimmed.match(
    /^SUT §2\.2 mandates package billing for claim (.+) \(EK-2\/C procedure present\)\. Package total ([\d.]+) TRY vs itemized ([\d.]+) TRY\.$/,
  );
  if (claimMandatePackage) {
    return t("api.billingProse.claimMandatePackage", {
      claimId: claimMandatePackage[1],
      packageTotal: claimMandatePackage[2],
      itemizedTotal: claimMandatePackage[3],
    });
  }

  const claimMandateItemized = trimmed.match(
    /^SUT §2\.2 mandates itemized billing for claim (.+)\. Itemized total ([\d.]+) TRY vs package ([\d.]+) TRY\.$/,
  );
  if (claimMandateItemized) {
    return t("api.billingProse.claimMandateItemized", {
      claimId: claimMandateItemized[1],
      itemizedTotal: claimMandateItemized[2],
      packageTotal: claimMandateItemized[3],
    });
  }

  const claimOptionalPackage = trimmed.match(
    /^Claim (.+): optional §2\.2\.2\(2\) override — package billing \(([\d.]+) TRY\) is the higher legal option vs itemized \(([\d.]+) TRY\)\.$/,
  );
  if (claimOptionalPackage) {
    return t("api.billingProse.claimOptionalPackageHigher", {
      claimId: claimOptionalPackage[1],
      packageTotal: claimOptionalPackage[2],
      itemizedTotal: claimOptionalPackage[3],
    });
  }

  const claimOptionalItemized = trimmed.match(
    /^Claim (.+): optional §2\.2\.2\(2\) override — itemized billing \(([\d.]+) TRY\) is the higher legal option vs package \(([\d.]+) TRY\)\.$/,
  );
  if (claimOptionalItemized) {
    return t("api.billingProse.claimOptionalItemizedHigher", {
      claimId: claimOptionalItemized[1],
      itemizedTotal: claimOptionalItemized[2],
      packageTotal: claimOptionalItemized[3],
    });
  }

  const mustPackage = trimmed.match(
    /^Procedure (.+) must use package billing \((.+)\) per (.+)\.$/,
  );
  if (mustPackage) {
    return t("api.billingProse.procedureMustPackage", {
      code: mustPackage[1],
      method: mustPackage[2],
      section: mustPackage[3],
    });
  }

  const mustItemized = trimmed.match(
    /^Procedure (.+) must use itemized billing \((.+)\) per (.+)\.$/,
  );
  if (mustItemized) {
    return t("api.billingProse.procedureMustItemized", {
      code: mustItemized[1],
      method: mustItemized[2],
      section: mustItemized[3],
    });
  }

  const materialRate = trimmed.match(
    /^SUT §1\.8\.3\(2\) material copay reference rate: (\d+)%$/,
  );
  if (materialRate) {
    return t("api.billingProse.materialCopayRate", { rate: materialRate[1] });
  }

  const exactBillingKeys: Array<keyof typeof enMessages.api.billingProse> = [
    "ek1aChronic",
    "emergencyWaiver",
    "preventiveWaiver",
    "workAccident",
    "vataniHizmet",
    "gssBeneficiary",
    "visitTypeRuleSource",
    "ek1aChronicShort",
    "ek1aChronicRanges",
  ];
  for (const key of exactBillingKeys) {
    if (trimmed === enMessages.api.billingProse[key]) {
      return t(`api.billingProse.${key}`);
    }
  }

  const honestyDrug = trimmed.match(
    /^Registry is ([^;]+); ([\d,]+) rows encoded, ([\d,]+) tier-C\/structural deferred, ([\d,]+) true algorithmic gaps\. ([\d,]+) EMR-blocked \(clinical data required\)\.$/,
  );
  if (honestyDrug) {
    const statusRaw = honestyDrug[1];
    const status =
      statusRaw === "implemented"
        ? "uygulanmış"
        : statusRaw === "partial"
          ? "kısmi"
          : statusRaw;
    return t("api.billingProse.honestyDrugIndication", {
      status: getModuleLocale() === "tr" ? status : statusRaw,
      encoded: honestyDrug[2],
      deferred: honestyDrug[3],
      gaps: honestyDrug[4],
      emr: honestyDrug[5],
    });
  }

  const honestyBundling = trimmed.match(
    /^Registry is implemented for the prose engine; manifest traces §3\.1–3\.2 encode candidates \(([\d,]+) clause IDs\) vs (\d+) JSON rules on disk\. Long-tail §3\.1 fikra stay manifest-only\.$/,
  );
  if (honestyBundling) {
    return t("api.billingProse.honestyMaterialBundling", {
      clauseIds: honestyBundling[1],
      rulesOnDisk: honestyBundling[2],
    });
  }

  const honestySpecialty = trimmed.match(
    /^L4\.4 export subset is 84 deontic §3\.3 rows; manifest traces all of them while (\d+) JSON rules cover branch themes \(3\.3\.1–3\.3\.4\)\. Catalog pricing \(specialty_materials\) remains separate\.$/,
  );
  if (honestySpecialty) {
    return t("api.billingProse.honestySpecialty", {
      rulesOnDisk: honestySpecialty[1],
    });
  }

  return null;
}

function tryTranslateBillingProse(value: string): string | null {
  if (value.includes(" · ")) {
    const parts = value.split(" · ").map((part) => part.trim());
    let any = false;
    const translated = parts.map((part) => {
      const hit = tryTranslateBillingProsePart(part);
      if (hit) {
        any = true;
        return hit;
      }
      return part;
    });
    return any ? translated.join(" · ") : null;
  }
  return tryTranslateBillingProsePart(value);
}

function tryTranslateLlmError(trimmed: string): string | null {
  const withoutWarn = trimmed.replace(/^⚠️\s*/, "").trim();
  const prefixed = withoutWarn.match(/^API error (\d+):\s*(.+)$/i);
  if (prefixed) {
    const detail = tryTranslateLlmError(prefixed[2].trim()) ?? prefixed[2].trim();
    return `⚠️ ${t("api.llmError.prefix", { status: prefixed[1], detail })}`;
  }

  const map: Array<[string, string]> = [
    [enMessages.api.llmError.malformed, "api.llmError.malformed"],
    [enMessages.api.llmError.authFailed, "api.llmError.authFailed"],
    [enMessages.api.llmError.quotaExhausted, "api.llmError.quotaExhausted"],
    [enMessages.api.llmError.forbidden, "api.llmError.forbidden"],
    [enMessages.api.llmError.timedOut, "api.llmError.timedOut"],
    [enMessages.api.llmError.contextTooLarge, "api.llmError.contextTooLarge"],
    [enMessages.api.llmError.rateLimited, "api.llmError.rateLimited"],
  ];
  for (const [en, key] of map) {
    if (withoutWarn === en) {
      return `⚠️ ${t(key)}`;
    }
  }

  const server = withoutWarn.match(
    /^The LLM provider returned a server error \((\d+)\)\. Please retry\.$/,
  );
  if (server) {
    return `⚠️ ${t("api.llmError.serverError", { status: server[1] })}`;
  }
  const unexpected = withoutWarn.match(
    /^The LLM provider returned an unexpected error \((\d+)\)\.$/,
  );
  if (unexpected) {
    return `⚠️ ${t("api.llmError.unexpected", { status: unexpected[1] })}`;
  }

  // Collapse raw provider JSON bodies into a short TR auth message when present.
  if (/User not found/i.test(withoutWarn) || /"code"\s*:\s*401/.test(withoutWarn)) {
    return `⚠️ ${t("api.llmError.authFailed")}`;
  }

  return null;
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
    tryTranslateLlmError(trimmed) ??
    tryTranslateBillingProse(trimmed) ??
    tryTranslateConsistencyWarning(trimmed) ??
    tryTranslateHealthMessage(trimmed) ??
    tryTranslateMethodology(trimmed) ??
    tryTranslateUnavailableReason(trimmed) ??
    tryTranslateProvenanceText(trimmed) ??
    tryTranslateValidationSummary(trimmed) ??
    tryTranslateValidationMessage(trimmed);

  return match ?? trimmed;
}
