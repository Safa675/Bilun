"use client";

import { Surface, inputClass } from "@/components/primitives";
import { useLocale } from "@/lib/i18n";
import {
  mdsEvidencePayload, optionalMdsDate, optionalMdsNumber,
  type MdsClinicalDraftResponse, type MdsEvidence,
} from "@/lib/api/mdsClinicalDraft";

type Labels = Record<keyof MdsEvidence, string>;
const labels: Record<"en" | "tr", Labels> = {
  en: {
    applies_on: "Service date", assessment_date: "Assessment date", indication: "Recorded indication",
    substance: "Exact substance", phase: "Treatment phase", hb_value: "Hemoglobin value", hb_unit: "Hemoglobin unit",
    hb_date: "Hemoglobin date", blast_value: "Blast value", blast_unit: "Blast unit", blast_date: "Blast date",
    serum_epo_value: "Serum EPO value", serum_epo_unit: "Serum EPO unit", serum_epo_date: "Serum EPO date",
    weekly_dose_value: "Weekly dose value", weekly_dose_unit: "Weekly dose unit",
    specialist_report_present: "Hematologist specialist report present", report_author_specialty: "Report author specialty",
    report_date: "Report date", prescribed_by_specialist: "Prescribed by a specialist", prescribed_by_specialty: "Prescribing specialist specialty",
    usage_dose_documented_in_report: "Dose documented in report",
    usage_duration_documented_in_report: "Duration documented in report", hemogram_date: "Hemogram date",
    lab_results_dates_documented_in_prescription_or_report: "Lab results and dates in prescription or report",
    hemogram_result_documented_in_prescription: "Hemogram result in prescription",
    hemogram_date_documented_in_prescription: "Hemogram date in prescription",
    prescribed_supply_months: "Prescribed supply (calendar months)",
  },
  tr: {
    applies_on: "Hizmet tarihi", assessment_date: "Değerlendirme tarihi", indication: "Kaydedilen endikasyon",
    substance: "Kesin etkin madde", phase: "Tedavi aşaması", hb_value: "Hemoglobin değeri", hb_unit: "Hemoglobin birimi",
    hb_date: "Hemoglobin tarihi", blast_value: "Blast değeri", blast_unit: "Blast birimi", blast_date: "Blast tarihi",
    serum_epo_value: "Serum EPO değeri", serum_epo_unit: "Serum EPO birimi", serum_epo_date: "Serum EPO tarihi",
    weekly_dose_value: "Haftalık doz değeri", weekly_dose_unit: "Haftalık doz birimi",
    specialist_report_present: "Hematoloji uzmanı raporu mevcut", report_author_specialty: "Rapor yazan uzmanlık",
    report_date: "Rapor tarihi", prescribed_by_specialist: "Uzman tarafından reçete edildi", prescribed_by_specialty: "Reçete yazan uzmanlık",
    usage_dose_documented_in_report: "Doz raporda belgeli", usage_duration_documented_in_report: "Süre raporda belgeli",
    lab_results_dates_documented_in_prescription_or_report: "Laboratuvar sonuçları ve tarihleri reçete veya raporda",
    hemogram_date: "Hemogram tarihi", hemogram_result_documented_in_prescription: "Hemogram sonucu reçetede",
    hemogram_date_documented_in_prescription: "Hemogram tarihi reçetede",
    prescribed_supply_months: "Reçete miktarı (takvim ayı)",
  },
};

const optionLabels = {
  en: {
    mds_anemia: "MDS anemia", ckd_anemia: "CKD anemia", other: "Other", epoetin_alfa: "Epoetin alfa",
    epoetin_beta: "Epoetin beta", initiation: "Initiation", continuation: "Continuation", restart: "Restart (review required)",
    hematology: "Hematology", internal_medicine: "Internal medicine", true: "Yes", false: "No",
  },
  tr: {
    mds_anemia: "MDS anemisi", ckd_anemia: "KBH anemisi", other: "Diğer", epoetin_alfa: "Epoetin alfa",
    epoetin_beta: "Epoetin beta", initiation: "Başlangıç", continuation: "Devam", restart: "Yeniden başlangıç (inceleme gerekli)",
    hematology: "Hematoloji", internal_medicine: "İç hastalıkları", true: "Evet", false: "Hayır",
  },
};

interface Field {
  name: keyof MdsEvidence;
  kind: "number" | "date" | "boolean" | "select";
  options?: readonly string[];
}
const fields: readonly Field[] = [
  { name: "applies_on", kind: "date" }, { name: "assessment_date", kind: "date" },
  { name: "indication", kind: "select", options: ["mds_anemia", "ckd_anemia", "other"] },
  { name: "substance", kind: "select", options: ["epoetin_alfa", "epoetin_beta"] },
  { name: "phase", kind: "select", options: ["initiation", "continuation", "restart"] },
  { name: "hb_value", kind: "number" }, { name: "hb_unit", kind: "select", options: ["g/dL"] },
  { name: "hb_date", kind: "date" }, { name: "blast_value", kind: "number" },
  { name: "blast_unit", kind: "select", options: ["%"] }, { name: "blast_date", kind: "date" },
  { name: "serum_epo_value", kind: "number" }, { name: "serum_epo_unit", kind: "select", options: ["mu/ml"] },
  { name: "serum_epo_date", kind: "date" }, { name: "weekly_dose_value", kind: "number" },
  { name: "weekly_dose_unit", kind: "select", options: ["IU/kg/week"] },
  { name: "specialist_report_present", kind: "boolean" },
  { name: "report_author_specialty", kind: "select", options: ["hematology", "internal_medicine", "other"] },
  { name: "report_date", kind: "date" },
  { name: "prescribed_by_specialist", kind: "boolean" },
  { name: "prescribed_by_specialty", kind: "select", options: ["hematology", "internal_medicine", "other"] },
  { name: "usage_dose_documented_in_report", kind: "boolean" },
  { name: "usage_duration_documented_in_report", kind: "boolean" },
  { name: "lab_results_dates_documented_in_prescription_or_report", kind: "boolean" },
  { name: "hemogram_date", kind: "date" }, { name: "hemogram_result_documented_in_prescription", kind: "boolean" },
  { name: "hemogram_date_documented_in_prescription", kind: "boolean" },
  { name: "prescribed_supply_months", kind: "number" },
];

/** Controlled evidence editor; mounting and editing do not send a request. */
export function MdsClinicalDraft({ value, onChange, review, embedded = false }: {
  value?: MdsEvidence | null;
  onChange: (value: MdsEvidence) => void;
  review?: MdsClinicalDraftResponse | null;
  embedded?: boolean;
}) {
  const locale = useLocale();
  const tr = locale === "tr";
  const text = labels[locale];
  const options = optionLabels[locale] as Record<string, string>;
  const facts = mdsEvidencePayload(value) ?? {};
  const unknown = tr ? "Bilinmiyor" : "Unknown";
  const additionalReview = tr ? "Ek klinik inceleme" : "Additional clinical review";
  const reviewLabel = (field: string): string => {
    const name = field.startsWith("mds_evidence.") ? field.slice("mds_evidence.".length) : field;
    if (Object.prototype.hasOwnProperty.call(text, name)) return text[name as keyof MdsEvidence];
    const gateLabels: Record<string, string> = {
      verified_source_for_service_date: tr ? "Hizmet tarihi için kaynak doğrulaması" : "Source verification for service date",
      mds_clinical_interpretation_release: tr ? "Bağımsız klinik yorum incelemesi" : "Independent clinical interpretation review",
      substance_context_reconciliation: tr ? "Etkin madde bağlamı incelemesi" : "Substance context review",
      indication_context_reconciliation: tr ? "Endikasyon bağlamı incelemesi" : "Indication context review",
      phase_context_reconciliation: tr ? "Tedavi aşaması bağlamı incelemesi" : "Treatment phase context review",
      phase_interpretation: tr ? "Tedavi aşaması yorumu" : "Treatment phase interpretation",
    };
    return Object.prototype.hasOwnProperty.call(gateLabels, name) ? gateLabels[name] : additionalReview;
  };
  const statusLabels = { pass: tr ? "Koşul karşılandı" : "Criterion met", fail: tr ? "Koşul karşılanmadı" : "Criterion not met", unknown };
  const update = (field: keyof MdsEvidence, fact: string | number | boolean | null) => {
    onChange(mdsEvidencePayload({ ...facts, [field]: fact }) ?? {});
  };
  return <Surface variant="inset" padding="none" className="space-y-4" aria-label={tr ? "MDS klinik taslağı" : "MDS clinical draft"}>
    <div className="space-y-1 text-xs text-[var(--text-muted)]">
      <h3 className="font-medium text-[var(--text-primary)]">{tr ? "MDS — taslak inceleme" : "MDS — draft review"}</h3>
      <p>{tr ? "Klinik uygunluk değerlendirmesi tamamlanmadı. Ödeme kararı üretmez." : "Clinical eligibility assessment is incomplete. No payment decision is produced."}</p>
      <ul className="list-disc pl-4">
        <li>{tr ? "MDS kaynak kabulü bekliyor" : "MDS source admission pending"}</li>
        <li>{tr ? "Hizmet tarihi için kaynak doğrulaması bekliyor" : "Source verification for service date pending"}</li>
        <li>{tr ? "Bağımsız klinik yorum incelemesi bekliyor" : "Independent clinical interpretation review pending"}</li>
      </ul>
    </div>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map(field => {
        const current = facts[field.name];
        const label = embedded ? `MDS: ${text[field.name]}` : text[field.name];
        const isSelect = field.kind === "boolean" || field.kind === "select";
        return <label key={field.name} className="text-xs">
          <span className="mb-1 block">{label}</span>
          {isSelect ? <select aria-label={label} className={inputClass}
            value={current == null ? "" : String(current)}
            onChange={event => {
              const next = event.target.value;
              update(field.name, field.kind === "boolean" ? next === "true" ? true : next === "false" ? false : null : next || null);
            }}>
            <option value="">{unknown}</option>
            {(field.kind === "boolean" ? ["true", "false"] : field.options ?? []).map(option =>
              <option key={option} value={option}>{options[option] ?? option}</option>)}
          </select> : <input aria-label={label} className={inputClass}
            type={field.kind === "date" ? "date" : "number"}
            min={field.kind === "number" ? 0 : undefined} step={field.kind === "number" ? "any" : undefined}
            placeholder={unknown} value={typeof current === "boolean" ? "" : current ?? ""}
            onChange={event => update(field.name, field.kind === "number"
              ? optionalMdsNumber(event.target.value) : optionalMdsDate(event.target.value))} />}
        </label>;
      })}
    </div>
    {review?.restriction && <div className="border-t border-[var(--border-subtle)] pt-3 text-xs" aria-label={tr ? "Taslak koşul incelemesi" : "Draft criterion review"}>
      {review.restriction.checks.length > 0 && <ul className="space-y-1">
        {review.restriction.checks.map((check, index) => <li key={index}>
          {reviewLabel(check.field)}
          {": "}{statusLabels[check.status] ?? unknown}
        </li>)}
      </ul>}
      {review.restriction.missing_inputs.length > 0 && <p className="mt-2 text-[var(--text-muted)]">
        {tr ? "Eksik kanıt veya inceleme: " : "Missing evidence or review: "}
        {review.restriction.missing_inputs.map(reviewLabel).join(", ")}
      </p>}
    </div>}
  </Surface>;
}
