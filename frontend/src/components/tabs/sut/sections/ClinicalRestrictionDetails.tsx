import type { SutClinicalRestriction } from "@/lib/api/clinicalEvidence";
import { useT } from "@/lib/i18n/useTranslations";
import { clinicalMissingInputLabel } from "./clinicalFields";

const knownSets = new Set(["sma_safety_2025", "antifungal_source_constraints", "renal_source_constraints"]);

export function ClinicalRestrictionDetails({ restrictions, selectedRuleId }: {
  restrictions: SutClinicalRestriction[];
  selectedRuleId?: string | null;
}) {
  const t = useT();
  const prefix = "sections.claimValidator.clinical.output";
  if (!restrictions.length) return null;
  const fieldLabel = (field: string) => {
    const clinical = clinicalMissingInputLabel(field, t);
    if (clinical) return clinical;
    const key = ["service_date", "drug_claim_date"].includes(field) ? "serviceDate" : field;
    const path = `sections.claimValidator.drugContext.${key}`;
    const translated = t(path);
    return translated === path ? field.replaceAll("_", " ") : translated;
  };
  return <details className="mt-2 text-xs">
    <summary className="cursor-pointer font-medium">{t(`${prefix}.title`)}</summary>
    <p className="mt-2 text-[var(--text-muted)]">{t(`${prefix}.partial`)}</p>
    <p className="text-[var(--text-muted)]">{t(`${prefix}.pending`)}</p>
    {selectedRuleId && <p className="mt-1 break-all text-[var(--text-muted)]">{t(`${prefix}.selectedRule`)}: {selectedRuleId}</p>}
    <div className="mt-2 space-y-3">
      {restrictions.map((restriction, index) => <div key={`${restriction.constraint_set}:${index}`}>
        <p className="font-medium">{knownSets.has(restriction.constraint_set)
          ? t(`${prefix}.sets.${restriction.constraint_set}`) : restriction.constraint_set.replaceAll("_", " ")}
          {": "}{t(`${prefix}.statuses.${restriction.criterion_status}`)}</p>
        {restriction.missing_inputs.length > 0 && <p className="mt-1 text-[var(--text-muted)]">
          {t("sections.claimValidator.drugContext.missingInputs")}: {restriction.missing_inputs.map(fieldLabel).join(", ")}
        </p>}
        <ul className="mt-1 space-y-1">
          {restriction.checks.map((check, checkIndex) => <li key={`${check.field}:${checkIndex}`}>
            {fieldLabel(check.field)}: {t(`${prefix}.statuses.${check.status}`)}
          </li>)}
        </ul>
        {restriction.source_refs.length > 0 && <p className="mt-1 break-words text-[var(--text-muted)]">
          {t(`${prefix}.sources`)}: {restriction.source_refs.join(", ")}
        </p>}
        {(restriction.checks_truncated || restriction.source_refs_truncated) &&
          <p className="mt-1 text-[var(--text-muted)]">{t(`${prefix}.truncated`)}</p>}
      </div>)}
    </div>
  </details>;
}
