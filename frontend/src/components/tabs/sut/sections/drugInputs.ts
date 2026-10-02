import type { SutMaterialItem } from "@/lib/api/sut";

/** Blank optional numbers are unknown, never an observed zero. */
export function optionalCount(value: string): number | null {
  if (!value.trim()) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= 0 ? number : null;
}

export function drugMaterialPayload(material: SutMaterialItem, enabled: boolean): SutMaterialItem {
  const { annual_application_count, is_loading_phase, biomarkers, prior_therapies, ...base } = material;
  if (!enabled) return base;
  return {
    ...base,
    annual_application_count: annual_application_count ?? null,
    is_loading_phase: is_loading_phase ?? null,
    // Incomplete edits are unknown facts, not negative clinical findings.
    biomarkers: biomarkers?.filter(row => row.marker.trim() && row.status.trim())
      .map(row => ({ marker: row.marker.trim(), status: row.status.trim() })) ?? null,
    // Keep an unfinished therapy identity: the evaluator treats it as unknown.
    // Dropping it next to unrelated known therapies would assert a mismatch.
    prior_therapies: prior_therapies?.map(row => ({
      drug_or_class: row.drug_or_class.trim(), outcome: row.outcome.trim(),
    })) ?? null,
  };
}
