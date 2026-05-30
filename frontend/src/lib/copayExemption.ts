import type {
  CopayExemptionResult,
  ExemptionSource,
  PatientAlertCopay,
} from "@/lib/domains/sut";

export const EXEMPTION_CATEGORY_LABELS: Record<string, string> = {
  ek1a_chronic: "EK-1A",
  acil_servis: "Acil",
  koruyucu_saglik: "Koruyucu",
  yesil_kart: "Yeşil kart",
  sehit_gazi: "Şehit / gazi",
  vatani_hizmet: "Vatani hizmet",
  kanun_2022_65: "65+ (2022)",
  is_kazasi_meslek: "İş kazası",
};

export function formatExemptionCategory(category: string): string {
  const key = category.trim().toLowerCase();
  return EXEMPTION_CATEGORY_LABELS[key] ?? category.replaceAll("_", " ");
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

export function formatExemptionBasisSummary(categories: string[]): string {
  if (categories.length === 0) {
    return "";
  }
  return categories.map(formatExemptionCategory).join(" · ");
}

export type { ExemptionSource };
