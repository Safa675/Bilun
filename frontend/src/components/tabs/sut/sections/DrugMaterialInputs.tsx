import type { SutMaterialItem } from "@/lib/api/sut";
import { Button, inputClass } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { optionalCount } from "./drugInputs";
import { ClinicalMaterialInputs } from "./ClinicalMaterialInputs";

export function DrugMaterialInputs({ material, onChange }: {
  material: SutMaterialItem;
  onChange: (patch: Partial<SutMaterialItem>) => void;
}) {
  const t = useT();
  const label = (key: string) => t(`sections.claimValidator.drugContext.${key}`);
  return <div className="space-y-3 border-t border-[var(--border-subtle)] pt-3">
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      <label className="text-xs">{label("annualCount")}
        <input aria-label={label("annualCount")} className={inputClass} type="number" min="0" step="1"
          value={material.annual_application_count ?? ""} placeholder={label("unknown")}
          onChange={e => onChange({ annual_application_count: optionalCount(e.target.value) })} />
      </label>
      <label className="text-xs">{label("loadingPhase")}
        <select aria-label={label("loadingPhase")} className={inputClass}
          value={material.is_loading_phase == null ? "" : material.is_loading_phase ? "yes" : "no"}
          onChange={e => onChange({ is_loading_phase: e.target.value === "" ? null : e.target.value === "yes" })}>
          <option value="">{label("unknown")}</option><option value="yes">{label("yes")}</option><option value="no">{label("no")}</option>
        </select>
      </label>
    </div>
    <p className="text-xs text-[var(--text-muted)]">{label("countHint")}</p>
    <fieldset className="space-y-2">
      <legend className="text-xs font-medium">{label("biomarkers")}</legend>
      {(material.biomarkers ?? []).map((row, index) => <div key={index} className="flex gap-2">
        <input aria-label={label("marker")} className={inputClass} value={row.marker} placeholder="HER2"
          onChange={e => onChange({ biomarkers: material.biomarkers!.map((entry, i) => i === index ? { ...entry, marker: e.target.value } : entry) })} />
        <input aria-label={label("markerStatus")} className={inputClass} value={row.status} placeholder={label("markerExample")}
          onChange={e => onChange({ biomarkers: material.biomarkers!.map((entry, i) => i === index ? { ...entry, status: e.target.value } : entry) })} />
        <Button variant="icon" title={label("removeMarker")} onClick={() => onChange({ biomarkers: material.biomarkers!.filter((_, i) => i !== index) })}>✕</Button>
      </div>)}
      <Button variant="secondary" onClick={() => onChange({ biomarkers: [...(material.biomarkers ?? []), { marker: "", status: "" }] })}>{label("addMarker")}</Button>
    </fieldset>
    <fieldset className="space-y-2">
      <legend className="text-xs font-medium">{label("priorTherapies")}</legend>
      {(material.prior_therapies ?? []).map((row, index) => <div key={index} className="flex gap-2">
        <input aria-label={label("therapy")} className={inputClass} value={row.drug_or_class} placeholder="imatinib"
          onChange={e => onChange({ prior_therapies: material.prior_therapies!.map((entry, i) => i === index ? { ...entry, drug_or_class: e.target.value } : entry) })} />
        <input aria-label={label("outcome")} className={inputClass} value={row.outcome} placeholder={label("outcomeExample")}
          onChange={e => onChange({ prior_therapies: material.prior_therapies!.map((entry, i) => i === index ? { ...entry, outcome: e.target.value } : entry) })} />
        <Button variant="icon" title={label("removeTherapy")} onClick={() => onChange({ prior_therapies: material.prior_therapies!.filter((_, i) => i !== index) })}>✕</Button>
      </div>)}
      <Button variant="secondary" onClick={() => onChange({ prior_therapies: [...(material.prior_therapies ?? []), { drug_or_class: "", outcome: "" }] })}>{label("addTherapy")}</Button>
    </fieldset>
    <p className="text-xs text-[var(--text-muted)]">{label("clinicalUnknownHint")}</p>
    <ClinicalMaterialInputs material={material} onChange={onChange} />
  </div>;
}
