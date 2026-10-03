import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { validateSutClaim } from "@/lib/api/sut";
import en from "@/messages/en/sections";
import tr from "@/messages/tr/sections";
import { ClaimValidatorSection } from "./ClaimValidatorSection";
import { growthHormoneFields, praderWilliFields, clinicalReviewFields, clinicalMissingInputLabel,
  optionalClinicalNumber } from "./clinicalFields";

vi.mock("@/lib/api/sut", () => ({ validateSutClaim: vi.fn(), getSutProcedureInfo: vi.fn() }));
vi.mock("@/components/sut/MaterialBundlingScopeNotice", () => ({ MaterialBundlingScopeNotice: () => null }));
vi.mock("@/components/sut/SpecialtyProseScopeNotice", () => ({ SpecialtyProseScopeNotice: () => null }));
let renderer: ReactTestRenderer;
const fields = [...growthHormoneFields, ...praderWilliFields];
const labels: Record<string, string> = en.claimValidator.clinical.fields;
const change = async (name: string, value: string) => {
  await act(async () => { renderer.root.findByProps({ "aria-label": labels[name] }).props.onChange({ target: { value } }); });
};
const submit = async () => {
  await act(async () => { renderer.root.findAllByType("button").find(row => row.children.join("") === "Validate Claim")!.props.onClick(); });
  return vi.mocked(validateSutClaim).mock.calls.at(-1)![0];
};
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("document", { documentElement: { lang: "en" } });
  vi.mocked(validateSutClaim).mockReset().mockRejectedValue(new Error("synthetic response"));
  await act(async () => { renderer = create(<LocaleProvider initialLocale="en"><ClaimValidatorSection /></LocaleProvider>); });
  await act(async () => { renderer.root.findAllByType("input")[2].props.onChange({ target: { value: "somatropin" } }); });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
});
afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.unstubAllGlobals(); });

it("exposes only GH/PWS groups and leaves all13 supported facts unknown", async () => {
  expect(renderer.root.findAllByType("summary").map(row => row.children.join(""))).toEqual([
    en.claimValidator.clinical.groups.growthHormone, en.claimValidator.clinical.groups.praderWilli,
  ]);
  const material = (await submit()).materials[0];
  for (const field of fields) expect(material[field.name]).toBeNull();
  for (const key of ["sma_evidence", "antifungal_evidence", "renal_evidence"]) expect(material).not.toHaveProperty(key);
});

it("submits explicit categories, measuredzero and negativeflags, clears to unknown and disables safely", async () => {
  await change("gh_patient_group", "pediatric"); await change("gh_treatment_phase", "continuation");
  await change("gh_height_reference_sex", "female"); await change("epiphyses_closed", "false");
  await change("annual_growth_velocity_cm", "0"); await change("height_cm", "157");
  await change("pws_genetic_diagnosis_confirmed", "true");
  await change("pws_untreatable_obstructive_sleep_apnea", "false");
  expect((await submit()).materials[0]).toMatchObject({ gh_patient_group: "pediatric", gh_treatment_phase: "continuation",
    gh_height_reference_sex: "female", epiphyses_closed: false, annual_growth_velocity_cm: 0, height_cm: 157,
    pws_genetic_diagnosis_confirmed: true, pws_untreatable_obstructive_sleep_apnea: false });
  await change("height_cm", ""); await change("gh_height_reference_sex", "");
  expect((await submit()).materials[0]).toMatchObject({ height_cm: null, gh_height_reference_sex: null });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": true }).props.onClick(); });
  const disabled = await submit();
  for (const field of fields) expect(disabled.materials[0]).not.toHaveProperty(field.name);
  expect(disabled).not.toHaveProperty("drug_context");
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  expect(renderer.root.findByProps({ "aria-label": labels.epiphyses_closed }).props.value).toBe("false");
});

it.each([["", null], ["0", 0], ["4.01", 4.01], ["-1", null], ["Infinity", null]])("parses %s without inventing a measurement", (input, expected) => {
  expect(optionalClinicalNumber(String(input))).toBe(expected);
  expect(optionalClinicalNumber("0", true)).toBeNull();
});

it("localizes all13 inputs and source review gates in both languages", () => {
  for (const messages of [en, tr]) {
    const local: Record<string, string> = messages.claimValidator.clinical.fields;
    const options: Record<string, string> = messages.claimValidator.clinical.options;
    for (const field of fields) {
      expect(local[field.name], field.name).toBeTruthy();
      if ("options" in field) for (const option of field.options ?? []) expect(options[option], option).toBeTruthy();
    }
    const t = (key: string) => key.split(".").reduce<unknown>((value, part) =>
      (value as Record<string, unknown>)[part], { sections: messages }) as string;
    for (const field of clinicalReviewFields) expect(clinicalMissingInputLabel(field, t)).toBe(local[field]);
  }
  expect(tr.claimValidator.clinical.fields.pws_untreatable_obstructive_sleep_apnea).toContain("Tedavi edilemeyen");
  expect(tr.claimValidator.clinical.fields.pws_uncontrolled_diabetes).toBe("Kontrol edilemeyen diyabet");
});
