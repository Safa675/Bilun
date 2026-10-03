import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { validateSutClaim } from "@/lib/api/sut";
import en from "@/messages/en/sections";
import tr from "@/messages/tr/sections";
import { ClaimValidatorSection } from "./ClaimValidatorSection";
import { mecaserminFields, ckdGrowthHormoneFields, growthHormoneFields, praderWilliFields, smaFields, antifungalFields, renalFields, enteralFields, ravulizumabFields,
  clinicalReviewFields, clinicalMissingInputLabel, optionalClinicalNumber } from "./clinicalFields";

vi.mock("@/lib/api/sut", () => ({ validateSutClaim: vi.fn(), getSutProcedureInfo: vi.fn() }));
vi.mock("@/components/sut/MaterialBundlingScopeNotice", () => ({ MaterialBundlingScopeNotice: () => null }));
vi.mock("@/components/sut/SpecialtyProseScopeNotice", () => ({ SpecialtyProseScopeNotice: () => null }));
let renderer: ReactTestRenderer;
const groups = { mecasermin: mecaserminFields, ckdGrowthHormone: ckdGrowthHormoneFields, growthHormone: growthHormoneFields, praderWilli: praderWilliFields, sma: smaFields,
  antifungal: antifungalFields, renal: renalFields, enteral: enteralFields, ravulizumab: ravulizumabFields };
const group = (name: keyof typeof groups, index = 0) => renderer.root.findAllByType("details")
  .filter(row => row.findByType("summary").children.join("") === en.claimValidator.clinical.groups[name])[index];
const change = async (name: keyof typeof groups, field: string, value: string, index = 0) => {
  const labels: Record<string, string> = en.claimValidator.clinical.fields;
  await act(async () => { group(name, index).findByProps({ "aria-label": labels[field] })
    .props.onChange({ target: { value } }); });
};
const button = (label: string) => renderer.root.findAllByType("button")
  .find(row => row.children.join("") === label)!;
const submit = async () => {
  await act(async () => { button("Validate Claim").props.onClick(); });
  return vi.mocked(validateSutClaim).mock.calls.at(-1)![0];
};
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("document", { documentElement: { lang: "en" } });
  vi.mocked(validateSutClaim).mockReset().mockRejectedValue(new Error("synthetic response"));
  await act(async () => { renderer = create(<LocaleProvider initialLocale="en"><ClaimValidatorSection /></LocaleProvider>); });
  await act(async () => { renderer.root.findAllByType("input")[2].props.onChange({ target: { value: "synthetic medicine" } }); });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
});
afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.unstubAllGlobals(); });

it("leaves every clinical input unknown until explicitly entered", async () => {
  for (const name of Object.keys(groups) as Array<keyof typeof groups>) {
    for (const input of [...group(name).findAllByType("input"), ...group(name).findAllByType("select")]) {
      expect(input.props.value).toBe("");
    }
  }
  const payload = await submit();
  expect(payload.materials[0]).toMatchObject({ gh_patient_group: null, gh_height_reference_sex: null,
    gh_treatment_phase: null, epiphyses_closed: null, annual_growth_velocity_cm: null,
    height_cm: null, bone_age_years: null, sma_evidence: null, antifungal_evidence: null, renal_evidence: null });
  expect(payload.materials[0]).toMatchObject({ enteral_evidence: null, ravulizumab_evidence: null });
});

it("submits explicit GH categories, negative histories, zero counts, source units and scoped dates", async () => {
  await change("growthHormone", "gh_patient_group", "pediatric");
  await change("growthHormone", "gh_height_reference_sex", "female");
  await change("growthHormone", "gh_treatment_phase", "continuation");
  await change("growthHormone", "epiphyses_closed", "false");
  await change("growthHormone", "annual_growth_velocity_cm", "0");
  await change("growthHormone", "height_cm", "157");
  await change("praderWilli", "pws_genetic_diagnosis_confirmed", "true");
  await change("praderWilli", "pws_untreatable_obstructive_sleep_apnea", "false");
  await change("sma", "sma_type", "type_2");
  await change("sma", "bacterial_meningitis_history", "false");
  await change("sma", "applies_on", "2026-10-02");
  await change("sma", "assessment_date", "2026-10-01");
  await change("antifungal", "intent", "prophylaxis");
  await change("antifungal", "formulation", "oral_solution");
  await change("antifungal", "anc_per_mm3", "0");
  await change("antifungal", "fluconazole_resistant", "true");
  await change("renal", "dialysis", "false");
  await change("renal", "baseline_albumin_g_dl", "2.7");
  await change("renal", "six_month_albumin_g_dl", "3.6");
  await change("renal", "albumin_g_dl", "4");
  const payload = await submit();
  expect(payload.materials[0]).toMatchObject({ gh_patient_group: "pediatric", gh_height_reference_sex: "female",
    gh_treatment_phase: "continuation", epiphyses_closed: false, annual_growth_velocity_cm: 0, height_cm: 157,
    pws_genetic_diagnosis_confirmed: true, pws_untreatable_obstructive_sleep_apnea: false,
    sma_evidence: { sma_type: "type_2", bacterial_meningitis_history: false,
      applies_on: "2026-10-02", assessment_date: "2026-10-01" },
    antifungal_evidence: { intent: "prophylaxis", formulation: "oral_solution", anc_per_mm3: 0,
      fluconazole_resistant: true },
    renal_evidence: { dialysis: false, baseline_albumin_g_dl: 2.7, six_month_albumin_g_dl: 3.6, albumin_g_dl: 4 },
  });
  // The evidence date never silently fills the separate actual service date.
  expect(payload.drug_context?.service_date).toBeNull();
});

it("clears facts to unknown and strips all clinical evidence when drug mode is disabled", async () => {
  await change("growthHormone", "epiphyses_closed", "false");
  await change("growthHormone", "height_cm", "150");
  await change("sma", "csf_shunt_or_catheter", "false");
  await change("sma", "applies_on", "2026-10-02");
  await change("antifungal", "intent", "treatment");
  await change("renal", "phase", "continuation");
  await change("praderWilli", "pws_severe_obesity_source_criterion_present", "false");
  await change("growthHormone", "height_cm", "");
  await change("sma", "applies_on", "");
  expect((await submit()).materials[0]).toMatchObject({ height_cm: null,
    sma_evidence: { applies_on: null, csf_shunt_or_catheter: false } });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": true }).props.onClick(); });
  const disabled = await submit();
  expect(disabled).not.toHaveProperty("drug_context");
  for (const field of [...growthHormoneFields.map(row => row.name), ...praderWilliFields.map(row => row.name), ...ckdGrowthHormoneFields.map(row => row.name), ...mecaserminFields.map(row => row.name), "sma_evidence", "antifungal_evidence", "renal_evidence", "enteral_evidence", "ravulizumab_evidence"]) {
    expect(disabled.materials[0]).not.toHaveProperty(field);
  }
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  expect(group("growthHormone").findByProps({ "aria-label": en.claimValidator.clinical.fields.epiphyses_closed }).props.value).toBe("false");
});

it("retains the surviving material's nested clinical evidence after another line is removed", async () => {
  await act(async () => { button("+ Add Material").props.onClick(); });
  await change("renal", "six_month_albumin_g_dl", "3.2", 1);
  await act(async () => { renderer.root.findAllByProps({ title: "Remove" }).find(row => row.type === "button")!.props.onClick(); });
  expect(group("renal").findByProps({ "aria-label": en.claimValidator.clinical.fields.six_month_albumin_g_dl }).props.value).toBe(3.2);
});

describe("clinical contract metadata", () => {
  it.each([["", null], ["0", 0], ["4.1", 4.1], ["-1", null], ["NaN", null], ["Infinity", null]])("parses %s without inventing a measurement", (raw, expected) => {
    expect(optionalClinicalNumber(String(raw))).toBe(expected);
  });
  it("does not accept zero as a measured height", () => { expect(optionalClinicalNumber("0", true)).toBeNull(); });
  it("preserves EDSS boundaries but does not accept out-of-range measurements", () => {
    expect(optionalClinicalNumber("0", false, 10)).toBe(0);
    expect(optionalClinicalNumber("10", false, 10)).toBe(10);
    expect(optionalClinicalNumber("10.1", false, 10)).toBeNull();
  });
  it("covers every exact family field declared by the backend contract", () => {
    const source = readFileSync(resolve(process.cwd(), "../src/bilun/domain/claims/clinical_evidence.py"), "utf8");
    for (const [cls, fields] of [["SmaEvidence", smaFields], ["AntifungalEvidence", antifungalFields], ["RenalEvidence", renalFields], ["EnteralEvidence", enteralFields], ["RavulizumabEvidence", ravulizumabFields]] as const) {
      const body = source.split(`class ${cls}:`)[1].split("\n\n")[0];
      const names = [...body.matchAll(/^    (\w+): (?:date|bool|float|str) \| None/gm)].map(match => match[1]);
      expect(fields.map(row => row.name).sort(), cls).toEqual(names.sort());
    }
  });
  it("localizes every field, choice and uneditable review reason in both languages", () => {
    for (const messages of [en, tr]) {
      const labels: Record<string, string> = messages.claimValidator.clinical.fields;
      const options: Record<string, string> = messages.claimValidator.clinical.options;
      for (const fields of Object.values(groups)) {
        for (const field of fields) {
          expect(labels[field.name], field.name).toBeTruthy();
          if ("options" in field) for (const option of field.options ?? []) expect(options[option], option).toBeTruthy();
        }
      }
      for (const field of clinicalReviewFields) expect(labels[field], field).toBeTruthy();
      const t = (key: string) => key.split(".").reduce<unknown>((value, part) =>
        (value as Record<string, unknown>)[part], { sections: messages }) as string;
      expect(clinicalMissingInputLabel("gh_treatment_phase", t)).toBe(labels.gh_treatment_phase);
      expect(clinicalMissingInputLabel("renal_evidence.source_supported_treatment_phase", t)).toContain(labels.source_supported_treatment_phase);
    }
  });
});

it("submits distinct enteral and ravulizumab facts without copying dates or inferring an indication", async () => {
  await change("enteral", "pediatric", "false");
  await change("enteral", "phase", "renewal");
  await change("enteral", "malnutrition_path", "exemption");
  await change("enteral", "report_author_specialty", "pediatric_neurology");
  await change("enteral", "neurological_disease", "true");
  await change("enteral", "applies_on", "2026-09-05");
  await change("ravulizumab", "indication", "pnh");
  await change("ravulizumab", "adult", "false");
  await change("ravulizumab", "therapy_months", "0");
  await change("ravulizumab", "edss", "8");
  await change("ravulizumab", "edss_in_report", "false");
  const payload = await submit();
  expect(payload.materials[0]).toMatchObject({
    enteral_evidence: { pediatric: false, phase: "renewal", malnutrition_path: "exemption",
      report_author_specialty: "pediatric_neurology", neurological_disease: true, applies_on: "2026-09-05" },
    ravulizumab_evidence: { indication: "pnh", adult: false, therapy_months: 0, edss: 8, edss_in_report: false },
  });
  expect(payload.materials[0].ravulizumab_evidence).not.toHaveProperty("applies_on");
  expect(payload.drug_context?.service_date).toBeNull();
  await change("ravulizumab", "edss", "10.1");
  await change("enteral", "pediatric", "");
  expect((await submit()).materials[0]).toMatchObject({ enteral_evidence: { pediatric: null }, ravulizumab_evidence: { edss: null } });
});

it("submits CKD dose and PTH exactly without deriving persistent disease or converting units", async () => {
  await change("ckdGrowthHormone", "ckd_growth_disorder_confirmed", "true");
  await change("ckdGrowthHormone", "ckd_parathyroid_hormone_pg_ml", "500");
  await change("ckdGrowthHormone", "gh_daily_dose_mg_per_kg", "0.045");
  await change("ckdGrowthHormone", "ckd_first_post_transplant_year", "false");
  let material = (await submit()).materials[0];
  expect(material).toMatchObject({ ckd_growth_disorder_confirmed: true, ckd_parathyroid_hormone_pg_ml: 500,
    gh_daily_dose_mg_per_kg: 0.045, ckd_first_post_transplant_year: false,
    ckd_persistent_severe_secondary_hyperparathyroidism: null });
  // A recorded noncompliant dose must reach the evaluator rather than being normalized to a pass.
  await change("ckdGrowthHormone", "gh_daily_dose_mg_per_kg", "0.051");
  expect((await submit()).materials[0].gh_daily_dose_mg_per_kg).toBe(0.051);
  await change("ckdGrowthHormone", "gh_daily_dose_mg_per_kg", "0");
  expect((await submit()).materials[0].gh_daily_dose_mg_per_kg).toBe(0);
  await change("ckdGrowthHormone", "gh_daily_dose_mg_per_kg", ""); await change("ckdGrowthHormone", "ckd_parathyroid_hormone_pg_ml", "");
  material = (await submit()).materials[0];
  expect(material).toMatchObject({ gh_daily_dose_mg_per_kg: null, ckd_parathyroid_hormone_pg_ml: null });
});

it("keeps all seven CKD GH facts unknown until entered alongside earlier groups", async () => {
  const material = (await submit()).materials[0];
  for (const field of ckdGrowthHormoneFields) expect(material[field.name]).toBeNull();
  expect(material).toMatchObject({ sma_evidence: null, renal_evidence: null, enteral_evidence: null, ravulizumab_evidence: null });
});

it("does not describe the partial GH checks as continuation-only after adding CKD initiation", () => {
  expect(en.claimValidator.clinical.hints.growthHormone).toContain("partial checks");
  expect(en.claimValidator.clinical.hints.growthHormone).not.toContain("continuation");
  expect(tr.claimValidator.clinical.hints.growthHormone).toContain("tam uygunluk sağlamaz");
});

it("keeps mecasermin facts and mcg dose separate from CKD mg dose without inferring source facts", async () => {
  await change("mecasermin", "mecasermin_laron_syndrome_confirmed", "false");
  await change("mecasermin", "pretreatment_annual_growth_velocity_cm", "0");
  await change("growthHormone", "height_cm", "155");
  await change("mecasermin", "mecasermin_daily_dose_mcg_per_kg", "120");
  await change("ckdGrowthHormone", "gh_daily_dose_mg_per_kg", "0.045");
  expect((await submit()).materials[0]).toMatchObject({
    mecasermin_laron_syndrome_confirmed: false, pretreatment_annual_growth_velocity_cm: 0,
    mecasermin_daily_dose_mcg_per_kg: 120, gh_daily_dose_mg_per_kg: 0.045,
    height_percentile: null, gh_treatment_phase: null, gh_height_reference_sex: null,
  });
  // A dose above the clinical ceiling must be evaluated, not erased or converted.
  await change("mecasermin", "mecasermin_daily_dose_mcg_per_kg", "120.001");
  expect((await submit()).materials[0].mecasermin_daily_dose_mcg_per_kg).toBe(120.001);
  await change("mecasermin", "mecasermin_daily_dose_mcg_per_kg", "0");
  expect((await submit()).materials[0].mecasermin_daily_dose_mcg_per_kg).toBe(0);
  await change("mecasermin", "mecasermin_daily_dose_mcg_per_kg", "");
  await change("mecasermin", "mecasermin_laron_syndrome_confirmed", "");
  expect((await submit()).materials[0]).toMatchObject({
    mecasermin_daily_dose_mcg_per_kg: null, mecasermin_laron_syndrome_confirmed: null,
    gh_daily_dose_mg_per_kg: 0.045,
  });
});

it.each([["0", 0], ["100", 100], ["100.01", null], ["-0.01", null], ["", null]])(
  "bounds recorded height percentile %s without calculating it from height", async (input, expected) => {
    await change("mecasermin", "height_percentile", input);
    expect((await submit()).materials[0].height_percentile).toBe(expected);
  },
);

it("keeps mecasermin facts unknown without deriving percentile from recorded height", async () => {
  const material = (await submit()).materials[0];
  for (const field of mecaserminFields) expect(material[field.name]).toBeNull();
});


it("preserves the recorded initiation obesity flag without deriving it from other measurements", async () => {
  await change("growthHormone", "height_cm", "155");
  await change("praderWilli", "pws_progressive_scoliosis", "true");
  expect((await submit()).materials[0].pws_severe_obesity_source_criterion_present).toBeNull();
  for (const [input, expected] of [["true", true], ["false", false], ["", null]] as const) {
    await change("praderWilli", "pws_severe_obesity_source_criterion_present", input);
    expect((await submit()).materials[0].pws_severe_obesity_source_criterion_present).toBe(expected);
  }
  expect(tr.claimValidator.clinical.fields.pws_severe_obesity_source_criterion_present)
    .toBe("Şiddetli obezite (ideal ağırlığının %225 üzerinde olması)");
  expect(en.claimValidator.clinical.hints.praderWilli).toContain("initiation-only");
  expect(en.claimValidator.clinical.hints.growthHormone).toContain("partial checks");
  expect(en.claimValidator.clinical.hints.growthHormone).not.toContain("continuation criteria");
});
