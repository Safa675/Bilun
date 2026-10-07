"use client";

import { inputClass } from "@/components/primitives";
import { adultGhEvidencePayload, type SutAdultGhDraftReview, type SutAdultGhEvidence,
  type SutAdultGhStimulationTest } from "@/lib/api/adultGhEvidence";

const copy = {
  tr: {
    title: "Erişkin somatropin — tanı ve uyarı testi taslağı",
    warning: "Kaynak/tarih kabulü ve bağımsız klinik yorum bekleyen taslak; ödeme uygunluğu kesinleşmez",
    scope: "Yalnız epifizleri kapalı erişkin somatropin kapsamı. Hasta grubu, epifiz kapanması ve tedavi aşaması ayrı kayıtlardır; yaş bunları belirlemez.",
    diagnosticScope: "Yalnız §4.2.6.A-2(2)–(4) tanı ve uyarı testi önkoşulları. Rapor/reçete koşulları ayrı değerlendirilir; bu taslak bunları doğrulamaz.",
    unknown: "Bilinmiyor", yes: "Evet", no: "Hayır", disabled: "Değerlendirme kapalı",
    tests: "Belgelenmiş büyüme hormonu uyarı testleri", add: "Test ekle", remove: "Testi kaldır",
    otherHint: "Diğer testlerde yetersiz yanıt için belgelenmiş klinik yorum gerekir; ITT sayısal eşiği diğer testlere uygulanmaz.",
    limit: "En fazla 20 test kaydı girilebilir.",
    invalidTests: "Test listesi okunamadı. Yeni test eklemek mevcut listeyi değiştirir; kaynak kaydı gözden geçirin.",
    runtime: "Kapalı değerlendirme sonucu", candidate: "Tanı/uyarı testi alt kümesi incelemesi", missing: "Eksik kayıtlar",
    pending: "Bekleyen incelemeler", emptyResult: "Sonuç bulunmuyor",
    statuses: { not_evaluated: "Değerlendirilmedi", unknown: "Bilinmiyor", criterion_clear: "Tanı/uyarı testi alt kümesindeki önkoşullar karşılandı", restriction_not_met: "Tanı/uyarı testi alt kümesindeki önkoşullar karşılanmadı" },
    requirements: {
      adult_gh_source_date_admission: "Kaynak ve tarih kabulü",
      adult_gh_independent_clinical_interpretation: "Bağımsız klinik yorum",
      shared_api_ui_integration: "API ve arayüz bağlantısı",
      verified_source_for_service_date: "Uygulama tarihi için doğrulanmış kaynak",
      adult_gh_clinical_interpretation_release: "Erişkin GH klinik yorumunun onayı",
      "adult_gh_evidence.stimulation_tests": "Belgelenmiş uyarı testi listesi",
      "adult_gh_evidence.stimulation_tests.distinct_test_records": "Ayrı test kayıtlarının doğrulanması",
      "adult_gh_evidence.stimulation_tests.count": "Gerekli uyarı testi sayısı",
      "adult_gh_evidence.stimulation_tests.test_set_interpretation": "Uyarı testlerinin birlikte klinik yorumu",
      "adult_gh_evidence.itt_contraindication_context_reconciliation": "ITT kontrendikasyon kaydının testlerle uyumu",
    },
    fields: {
      applies_on: "Uygulama tarihi", assessment_date: "Klinik değerlendirme tarihi", diagnosis_pathway: "Belgelenmiş tanı yolu",
      childhood_gh_deficiency_diagnosed: "Çocuklukta GH eksikliği tanısı konuldu",
      childhood_gh_treatment_received: "Çocuklukta GH tedavisi verildi",
      gh_stopped_due_to_epiphyseal_closure: "GH tedavisi epifiz kapanması nedeniyle kesildi",
      adult_hypothalamic_pituitary_gh_deficiency_suspected: "Erişkinde hipotalamohipofizer hastalığa bağlı GH eksikliği düşünüldü",
      additional_anterior_pituitary_deficiency_confirmed: "En az bir ek ön hipofiz hormonu eksikliği doğrulandı (prolaktin ve GH hariç)",
      itt_contraindicated: "ITT kontrendikasyonu var",
      two_distinct_stimulation_procedures_documented: "En az iki ayrı gerçek uyarı testi işlemi klinik kayıtta belgelenmiş",
      test_id: "Test kaydı kimliği", performed_on: "Test tarihi", kind: "Test türü",
      inadequate_response_documented: "Yetersiz yanıt belgelenmiş",
      peak_gh_mcg_l: "ITT pik GH değeri (mcg/L; yalnız ITT)",
      peak_gh_documented_in_report: "Pik GH yanıtı raporda belgelenmiş",
      retest_after_epiphyseal_closure_stop: "Epifiz kapanması nedeniyle tedavi kesildikten sonra tekrar test",
    },
    options: { childhood_onset_retest: "Çocuklukta başlayan eksiklik — tekrar test", adult_hypothalamic_pituitary: "Erişkin hipotalamohipofizer hastalık", itt: "İnsülin tolerans testi (ITT)", other: "Diğer uyarı testi" },
  },
  en: {
    title: "Adult somatropin — diagnosis and stimulation test draft",
    warning: "Draft awaiting source/date admission and independent clinical interpretation; payment eligibility is not established",
    scope: "Closed-epiphysis adult somatropin only. Patient group, epiphyseal closure and treatment phase are separate records; age does not establish them.",
    diagnosticScope: "Only diagnosis and stimulation prerequisites in §4.2.6.A-2(2)–(4). Report and prescription requirements are assessed separately; this draft does not verify them.",
    unknown: "Unknown", yes: "Yes", no: "No", disabled: "Evaluation disabled",
    tests: "Documented growth hormone stimulation tests", add: "Add test", remove: "Remove test",
    otherHint: "Other tests require a documented clinical interpretation of inadequate response; the ITT numeric threshold does not apply to other tests.",
    limit: "A maximum of 20 test records can be entered.",
    invalidTests: "The test list could not be read. Adding a new test replaces the existing list; review the source record.",
    runtime: "Disabled evaluation result", candidate: "Diagnosis/stimulation subset review", missing: "Missing records",
    pending: "Pending reviews", emptyResult: "No result available",
    statuses: { not_evaluated: "Not evaluated", unknown: "Unknown", criterion_clear: "Diagnosis/stimulation subset prerequisites met", restriction_not_met: "Diagnosis/stimulation subset prerequisites not met" },
    requirements: {
      adult_gh_source_date_admission: "Source and date admission",
      adult_gh_independent_clinical_interpretation: "Independent clinical interpretation",
      shared_api_ui_integration: "API and UI integration",
      verified_source_for_service_date: "Verified source for the application date",
      adult_gh_clinical_interpretation_release: "Adult GH clinical interpretation approval",
      "adult_gh_evidence.stimulation_tests": "Documented stimulation test list",
      "adult_gh_evidence.stimulation_tests.distinct_test_records": "Confirmation of distinct test records",
      "adult_gh_evidence.stimulation_tests.count": "Required stimulation test count",
      "adult_gh_evidence.stimulation_tests.test_set_interpretation": "Clinical interpretation of the complete stimulation test set",
      "adult_gh_evidence.itt_contraindication_context_reconciliation": "Reconciliation of ITT contraindication records with tests",
    },
    fields: {
      applies_on: "Application date", assessment_date: "Clinical assessment date", diagnosis_pathway: "Documented diagnosis pathway",
      childhood_gh_deficiency_diagnosed: "Childhood GH deficiency diagnosed",
      childhood_gh_treatment_received: "Childhood GH treatment received",
      gh_stopped_due_to_epiphyseal_closure: "GH treatment stopped because of epiphyseal closure",
      adult_hypothalamic_pituitary_gh_deficiency_suspected: "Adult GH deficiency due to hypothalamic-pituitary disease suspected",
      additional_anterior_pituitary_deficiency_confirmed: "At least one additional anterior pituitary hormone deficiency confirmed (excluding prolactin and GH)",
      itt_contraindicated: "ITT contraindicated",
      two_distinct_stimulation_procedures_documented: "At least two distinct stimulation test procedures documented in the clinical record",
      test_id: "Test record ID", performed_on: "Test date", kind: "Test type",
      inadequate_response_documented: "Inadequate response documented",
      peak_gh_mcg_l: "ITT peak GH (mcg/L; ITT only)",
      peak_gh_documented_in_report: "Peak GH response documented in the report",
      retest_after_epiphyseal_closure_stop: "Retest after treatment stopped because of epiphyseal closure",
    },
    options: { childhood_onset_retest: "Childhood-onset deficiency — retest", adult_hypothalamic_pituitary: "Adult hypothalamic-pituitary disease", itt: "Insulin tolerance test (ITT)", other: "Other stimulation test" },
  },
} as const;

const booleanFields = ["childhood_gh_deficiency_diagnosed", "childhood_gh_treatment_received",
  "gh_stopped_due_to_epiphyseal_closure", "adult_hypothalamic_pituitary_gh_deficiency_suspected",
  "additional_anterior_pituitary_deficiency_confirmed", "itt_contraindicated",
  "two_distinct_stimulation_procedures_documented"] as const;
const testBooleanFields = ["inadequate_response_documented", "peak_gh_documented_in_report",
  "retest_after_epiphyseal_closure_stop"] as const;

/** Controlled evidence editor; the enclosing claim form owns submission and runtime review. */
export function AdultGhClinicalDraft({ value, onChange, locale = "tr", result, embedded = false }: {
  value?: SutAdultGhEvidence | null;
  onChange: (value: SutAdultGhEvidence) => void;
  locale?: "en" | "tr";
  result?: SutAdultGhDraftReview | null;
  embedded?: boolean;
}) {
  const t = copy[locale];
  const facts = adultGhEvidencePayload(value ?? {})!;
  const tests = facts.stimulation_tests ?? [];
  const update = (patch: Partial<SutAdultGhEvidence>) => onChange(adultGhEvidencePayload({ ...facts, ...patch })!);
  const updateTest = (index: number, patch: Partial<SutAdultGhStimulationTest>) =>
    update({ stimulation_tests: tests.map((test, row) => row === index ? { ...test, ...patch } : test) });
  const booleanInput = (label: string, current: boolean | null | undefined, change: (value: boolean | null) => void) =>
    <label className="text-xs"><span className="block mb-1">{label}</span>
      <select aria-label={label} className={inputClass} value={current == null ? "" : String(current)}
        onChange={e => change(e.target.value === "true" ? true : e.target.value === "false" ? false : null)}>
        <option value="">{t.unknown}</option><option value="true">{t.yes}</option><option value="false">{t.no}</option>
      </select>
    </label>;
  const recordLabel = (key: string) => {
    const requirement = t.requirements[key as keyof typeof t.requirements];
    if (requirement) return requirement;
    const indexed = /^adult_gh_evidence\.stimulation_tests\[(\d{1,2})\]\.(test_id|performed_on|kind|inadequate_response_documented|peak_gh_mcg_l|peak_gh_documented_in_report|retest_after_epiphyseal_closure_stop)$/.exec(key);
    if (indexed && Number(indexed[1]) < 20) {
      return `Test ${Number(indexed[1]) + 1} — ${t.fields[indexed[2] as keyof typeof t.fields]}`;
    }
    const field = key.split(".").at(-1) ?? key;
    return t.fields[field as keyof typeof t.fields] ?? key;
  };

  return <section aria-label={t.title} className="space-y-4">
    <h3 className="text-sm font-medium">{t.title}</h3>
    <p role="status" className="text-xs text-[var(--text-muted)]">{t.warning}</p>
    <p className="text-xs text-[var(--text-muted)]">{t.scope}</p>
    <p className="text-xs text-[var(--text-muted)]">{t.diagnosticScope}</p>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {(["applies_on", "assessment_date"] as const).map(field => <label key={field} className="text-xs">
        <span className="block mb-1">{t.fields[field]}</span>
        <input type="date" aria-label={t.fields[field]} className={inputClass} value={facts[field] ?? ""}
          onChange={e => update({ [field]: e.target.value || null })} />
      </label>)}
      <label className="text-xs"><span className="block mb-1">{t.fields.diagnosis_pathway}</span>
        <select aria-label={t.fields.diagnosis_pathway} className={inputClass} value={facts.diagnosis_pathway ?? ""}
          onChange={e => update({ diagnosis_pathway: e.target.value === "childhood_onset_retest"
            || e.target.value === "adult_hypothalamic_pituitary" ? e.target.value : null })}>
          <option value="">{t.unknown}</option>
          <option value="childhood_onset_retest">{t.options.childhood_onset_retest}</option>
          <option value="adult_hypothalamic_pituitary">{t.options.adult_hypothalamic_pituitary}</option>
        </select>
      </label>
      {booleanFields.map(field => <div key={field}>{booleanInput(t.fields[field], facts[field], fact => update({ [field]: fact }))}</div>)}
    </div>
    <div className="space-y-3">
      <h4 className="text-xs font-medium">{t.tests}</h4>
      <p className="text-xs text-[var(--text-muted)]">{t.otherHint}</p>
      {value?.stimulation_tests != null && facts.stimulation_tests === null &&
        <p role="alert" className="text-xs">{t.invalidTests}</p>}
      {tests.map((test, index) => <fieldset key={index} className="border-t border-[var(--border-subtle)] pt-3">
        <legend className="text-xs">{t.tests} {index + 1}</legend>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {(["test_id", "performed_on"] as const).map(field => <label key={field} className="text-xs">
            <span className="block mb-1">{t.fields[field]}</span>
            <input type={field === "performed_on" ? "date" : "text"} aria-label={`${t.fields[field]} ${index + 1}`}
              className={inputClass} maxLength={field === "test_id" ? 120 : undefined} value={test[field] ?? ""}
              onChange={e => updateTest(index, { [field]: e.target.value || null })} />
          </label>)}
          <label className="text-xs"><span className="block mb-1">{t.fields.kind}</span>
            <select aria-label={`${t.fields.kind} ${index + 1}`} className={inputClass} value={test.kind ?? ""}
              onChange={e => updateTest(index, { kind: e.target.value === "itt" || e.target.value === "other" ? e.target.value : null })}>
              <option value="">{t.unknown}</option><option value="itt">{t.options.itt}</option><option value="other">{t.options.other}</option>
            </select>
          </label>
          {testBooleanFields.map(field => <div key={field}>{booleanInput(`${t.fields[field]} ${index + 1}`, test[field], fact => updateTest(index, { [field]: fact }))}</div>)}
          {test.kind === "itt" && <label className="text-xs"><span className="block mb-1">{t.fields.peak_gh_mcg_l}</span>
            <input type="number" aria-label={`${t.fields.peak_gh_mcg_l} ${index + 1}`} className={inputClass}
              min={0} step="any" placeholder={t.unknown} value={test.peak_gh_mcg_l ?? ""}
              onChange={e => updateTest(index, { peak_gh_mcg_l: e.target.value === "" ? null : e.target.valueAsNumber })} />
          </label>}
        </div>
        <button type="button" className="mt-2 text-xs" aria-label={`${t.remove} ${index + 1}`}
          onClick={() => update({ stimulation_tests: tests.filter((_, row) => row !== index) })}>{t.remove}</button>
      </fieldset>)}
      <button type="button" className="text-xs" disabled={tests.length >= 20}
        onClick={() => update({ stimulation_tests: [...tests, {}] })}>{t.add}</button>
      {tests.length >= 20 && <p className="text-xs text-[var(--text-muted)]">{t.limit}</p>}
    </div>
    {!embedded && <button type="button" disabled className="text-xs text-[var(--text-muted)]">{t.disabled}</button>}
    {result && <div className="space-y-3 border-t border-[var(--border-subtle)] pt-3">
      {(["runtime_result", "candidate_result"] as const).map(key => {
        const restriction = result[key];
        return <div key={key} className="text-xs">
          <h4 className="font-medium">{key === "runtime_result" ? t.runtime : t.candidate}</h4>
          <p>{restriction ? t.statuses[restriction.criterion_status] : t.emptyResult}</p>
          {restriction && restriction.missing_inputs.length > 0 && <div><p>{t.missing}</p>
            <ul className="list-disc pl-4">{restriction.missing_inputs.map((input, index) => <li key={`${input}:${index}`}>{recordLabel(input)}</li>)}</ul>
          </div>}
        </div>;
      })}
      {(result.pending_requirements?.length ?? 0) > 0 && <div className="text-xs"><h4>{t.pending}</h4>
        <ul className="list-disc pl-4">{result.pending_requirements?.map((requirement, index) =>
          <li key={`${requirement}:${index}`}>{recordLabel(requirement)}</li>)}</ul>
      </div>}
    </div>}
  </section>;
}
