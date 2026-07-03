/** Canonical tebliğ annex + SUT section labels for procedure-level attribution. */

export const SURCHARGE_EK2G_ANNEX = "EK-2G";
export const SURCHARGE_SUT_SECTION = "§1.9.3";
/** EK-2C-1 ilave oran listesi (§2.2 faturalama; §1.8 katılım payı değil). */
export const COPAY_RATE_EK2C1_ANNEX = "EK-2C-1";
export const COPAY_RATE_SUT_SECTION = "§2.2";
export const DRG_PACKAGE_EK2C_ANNEX = "EK-2C";

export type RegulatorySourceRef = {
  annex: string;
  sutSection?: string;
};

export const SURCHARGE_REGULATORY_SOURCE: RegulatorySourceRef = {
  annex: SURCHARGE_EK2G_ANNEX,
  sutSection: SURCHARGE_SUT_SECTION,
};

export const COPAY_RATE_REGULATORY_SOURCE: RegulatorySourceRef = {
  annex: COPAY_RATE_EK2C1_ANNEX,
  sutSection: COPAY_RATE_SUT_SECTION,
};

const EK_ANNEX_PATTERN = /EK-(?:\d+[A-Z]?(?:-\d+)?)/gi;

/** Normalize EK-1/A style references before annex extraction. */
function normalizeRuleSourceText(ruleSource: string): string {
  return ruleSource.replace(/EK-(\d+)\/([A-Z])/gi, "EK-$1$2");
}

/** Extract unique EK annex labels from a backend `rule_source` string. */
export function parseEkAnnexLabels(ruleSource: string): string[] {
  const normalized = normalizeRuleSourceText(ruleSource);
  const seen = new Set<string>();
  const labels: string[] = [];

  for (const match of normalized.matchAll(EK_ANNEX_PATTERN)) {
    const label = match[0].toUpperCase();
    if (seen.has(label)) {
      continue;
    }
    seen.add(label);
    labels.push(label);
  }

  return labels;
}

/** Normalize per-row catalog hints such as `ek2b` → `EK-2B`. */
export function normalizeEkCatalogHint(catalog?: string | null): string | null {
  const raw = catalog?.trim();
  if (!raw) {
    return null;
  }
  if (/^EK-/i.test(raw)) {
    return raw.toUpperCase();
  }

  const lower = raw.toLowerCase();
  if (lower === "ek2b") {
    return "EK-2B";
  }
  if (lower === "ek2c") {
    return "EK-2C";
  }

  return raw.toUpperCase();
}

export function resolveBillingEkAnnexLabels(
  ruleSource?: string | null,
  rowCatalog?: string | null,
): string[] {
  const fromCatalog = normalizeEkCatalogHint(rowCatalog);
  if (fromCatalog) {
    return [fromCatalog];
  }
  if (!ruleSource?.trim()) {
    return [];
  }
  return parseEkAnnexLabels(ruleSource);
}
