import type { SutMaterialItem } from "@/lib/api/sut";
import { inputClass } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { growthHormoneFields, mecaserminFields, ckdGrowthHormoneFields, praderWilliFields, smaFields, antifungalFields, renalFields, enteralFields, ravulizumabFields,
  optionalClinicalNumber, type ClinicalField } from "./clinicalFields";

type ClinicalValue = string | number | boolean | null | undefined;

function ClinicalGroup({ group, fields, value, onChange }: {
  group: string;
  fields: readonly ClinicalField[];
  value: object | null | undefined;
  onChange: (patch: Record<string, ClinicalValue>) => void;
}) {
  const t = useT();
  const prefix = "sections.claimValidator.clinical";
  const facts = (value ?? {}) as Record<string, ClinicalValue>;
  const update = (field: string, fact: ClinicalValue) => onChange({ ...facts, [field]: fact });
  const unknown = t("sections.claimValidator.drugContext.unknown");
  return <details className="border-t border-[var(--border-subtle)] pt-2">
    <summary className="cursor-pointer text-xs font-medium">{t(`${prefix}.groups.${group}`)}</summary>
    <p className="mt-2 text-xs text-[var(--text-muted)]">{t(`${prefix}.hints.${group}`)}</p>
    <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {fields.map(field => {
        const label = t(`${prefix}.fields.${field.name}`);
        const current = facts[field.name];
        return <label key={field.name} className="text-xs">
          <span className="block mb-1">{label}</span>
          {field.kind === "boolean" || field.kind === "select" ? <select
            aria-label={label} className={inputClass}
            value={current == null ? "" : String(current)}
            onChange={e => update(field.name, e.target.value === "" ? null
              : field.kind === "boolean" ? e.target.value === "true" : e.target.value)}>
            <option value="">{unknown}</option>
            {(field.kind === "boolean" ? ["true", "false"] : field.options ?? []).map(option =>
              <option key={option} value={option}>{field.kind === "boolean"
                ? t(`sections.claimValidator.drugContext.${option === "true" ? "yes" : "no"}`)
                : t(`${prefix}.options.${option}`)}</option>)}
          </select> : <input aria-label={label} className={inputClass}
            type={field.kind === "date" ? "date" : "number"}
            min={field.kind === "number" ? 0 : undefined} max={field.max} step={field.kind === "number" ? "any" : undefined}
            placeholder={unknown} value={typeof current === "boolean" ? "" : current ?? ""}
            onChange={e => update(field.name, field.kind === "number"
              ? optionalClinicalNumber(e.target.value, field.positiveOnly, field.max) : e.target.value || null)} />}
        </label>;
      })}
    </div>
  </details>;
}

export function ClinicalMaterialInputs({ material, onChange }: {
  material: SutMaterialItem;
  onChange: (patch: Partial<SutMaterialItem>) => void;
}) {
  return <div className="space-y-2">
    <ClinicalGroup group="growthHormone" fields={growthHormoneFields} value={material}
      onChange={onChange} />
    <ClinicalGroup group="praderWilli" fields={praderWilliFields} value={material}
      onChange={onChange} />
    <ClinicalGroup group="ckdGrowthHormone" fields={ckdGrowthHormoneFields} value={material}
      onChange={onChange} />
    <ClinicalGroup group="mecasermin" fields={mecaserminFields} value={material}
      onChange={onChange} />
    <ClinicalGroup group="sma" fields={smaFields} value={material.sma_evidence}
      onChange={value => onChange({ sma_evidence: value })} />
    <ClinicalGroup group="antifungal" fields={antifungalFields} value={material.antifungal_evidence}
      onChange={value => onChange({ antifungal_evidence: value })} />
    <ClinicalGroup group="renal" fields={renalFields} value={material.renal_evidence}
      onChange={value => onChange({ renal_evidence: value })} />
    <ClinicalGroup group="enteral" fields={enteralFields} value={material.enteral_evidence}
      onChange={value => onChange({ enteral_evidence: value })} />
    <ClinicalGroup group="ravulizumab" fields={ravulizumabFields} value={material.ravulizumab_evidence}
      onChange={value => onChange({ ravulizumab_evidence: value })} />
  </div>;
}
