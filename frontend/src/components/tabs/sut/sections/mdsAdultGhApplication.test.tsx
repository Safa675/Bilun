import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SutClaimRequest, SutValidationResult } from "@/lib/api/sut";
import type { SutClinicalRestriction } from "@/lib/api/clinicalEvidence";
import { postJSON } from "@/lib/api/request";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import en from "@/messages/en/sections";
import tr from "@/messages/tr/sections";
import { ClaimValidatorSection } from "./ClaimValidatorSection";
import { ClinicalRestrictionDetails } from "./ClinicalRestrictionDetails";
import { clinicalMissingInputLabel } from "./clinicalFields";
import { drugMaterialPayload } from "./drugInputs";

vi.mock("@/lib/api/request", () => ({ postJSON: vi.fn(), requestJSON: vi.fn() }));
vi.mock("@/components/sut/MaterialBundlingScopeNotice", () => ({ MaterialBundlingScopeNotice: () => null }));
vi.mock("@/components/sut/SpecialtyProseScopeNotice", () => ({ SpecialtyProseScopeNotice: () => null }));
const restrictions: SutClinicalRestriction[] = ["adult_gh_closed_epiphysis", "mds_epoetin"].map(constraint_set => ({
  constraint_set, criterion_status: "not_evaluated", checks: [], clinical_eligibility_complete: false,
  missing_inputs: ["verified_source_for_service_date", constraint_set.startsWith("adult")
    ? "adult_gh_clinical_interpretation_release" : "mds_clinical_interpretation_release"],
  source_refs: [], verification_status: "ai_generated_pending_review", checks_truncated: false, source_refs_truncated: false,
}));
const result = (name = "CURRENT_RESULT"): SutValidationResult => ({
  contract_version: 2, request_id: "combined:1", claim_id: "C1", validation_status: "review_required",
  is_valid: null, violations: [], advisories: [{ evidence_id: "combined:review", rule: "drug_indication",
    material_name: name, message: "Source and clinical interpretation require review.", disposition: "review_only",
    source_status: "historical_match_unverified", clinical_restrictions: restrictions, clinical_eligibility_complete: false }],
  material_applicability: [], coverage: { evaluation_count: 1, authored_rule_count: 1, unresolved_count: 1,
    disposition_counts: { review_only: 1 }, scope: "submitted_request_facts_only" }, provenance: {}, summary: "", validation_time_ms: 1,
});
let renderer: ReactTestRenderer;
const button = (label: string) => renderer.root.findAllByType("button").find(node => node.children.join("") === label)!;
const change = async (label: string, value: string, index = 0) => {
  await act(async () => { renderer.root.findAllByProps({ "aria-label": label })[index].props.onChange({ target: { value, valueAsNumber: Number(value) } }); });
};
const submit = async () => { await act(async () => { button("Validate Claim").props.onClick(); }); };
const snapshot = () => JSON.stringify(renderer.toJSON());
const request = () => vi.mocked(postJSON).mock.calls.at(-1)![1] as SutClaimRequest;
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("document", { documentElement: { lang: "en" } });
  vi.mocked(postJSON).mockReset().mockResolvedValue(result());
  await act(async () => { renderer = create(<LocaleProvider initialLocale="en"><ClaimValidatorSection /></LocaleProvider>); });
  await act(async () => { renderer.root.findAllByType("input")[2].props.onChange({ target: { value: "somatropin" } }); });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
});
afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.unstubAllGlobals(); });

it("submits both controlled editors through the actual v2 API client with separate service, scope and test facts", async () => {
  await change("Service date", "2026-10-05");
  await change("Application date", "2026-10-05");
  await change("Clinical assessment date", "2026-10-05");
  await change("Documented diagnosis pathway", "childhood_onset_retest");
  await change("ITT contraindicated", "false");
  await act(async () => { button("Add test").props.onClick(); });
  await change("Test record ID 1", "T1"); await change("Test type 1", "itt");
  await change("ITT peak GH (mcg/L; ITT only) 1", "0");
  await change("Inadequate response documented 1", "false");
  await change("MDS: Service date", "2026-10-05");
  await change("MDS: Exact substance", "epoetin_alfa");
  await change("MDS: Treatment phase", "initiation");
  await change("MDS: Hemoglobin value", "10.9");
  await change("MDS: Hematologist specialist report present", "false");
  await submit();
  expect(vi.mocked(postJSON).mock.calls.at(-1)![0]).toBe("/api/validate-claim");
  expect(vi.mocked(postJSON).mock.calls.at(-1)![2]).toMatchObject({ headers: { "x-bilun-validation-contract": "2" } });
  expect(request()).toMatchObject({ drug_context: { service_date: "2026-10-05" }, materials: [{
    adult_gh_evidence: { applies_on: "2026-10-05", diagnosis_pathway: "childhood_onset_retest", itt_contraindicated: false,
      stimulation_tests: [{ test_id: "T1", kind: "itt", peak_gh_mcg_l: 0, inadequate_response_documented: false }] },
    mds_evidence: { applies_on: "2026-10-05", substance: "epoetin_alfa", phase: "initiation", hb_value: 10.9,
      specialist_report_present: false }, epiphyses_closed: null, gh_patient_group: null,
  }] });
  // Neither age nor a nested GH diagnosis supplies the separate epiphyseal scope.
  expect(snapshot()).toContain("CURRENT_RESULT");
  expect(snapshot()).toContain(en.claimValidator.clinical.output.gatedClinicalDraft);
  await change("MDS: Hemoglobin value", "");
  expect(snapshot()).not.toContain("CURRENT_RESULT");
  await submit(); expect(request().materials[0].mds_evidence?.hb_value).toBeNull();
  await act(async () => { renderer.root.findByProps({ "aria-expanded": true }).props.onClick(); });
  await submit();
  expect(request()).not.toHaveProperty("drug_context");
  expect(request().materials[0]).not.toHaveProperty("adult_gh_evidence");
  expect(request().materials[0]).not.toHaveProperty("mds_evidence");
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  expect(renderer.root.findByProps({ "aria-label": "ITT contraindicated" }).props.value).toBe("false");
  expect(renderer.root.findByProps({ "aria-label": "MDS: Hematologist specialist report present" }).props.value).toBe("false");
});

it("submits same-report true, false and unknown without deriving the relationship from separate report flags", async () => {
  const label = "MDS: Prescription based on the same hematology report";
  expect(renderer.root.findByProps({ "aria-label": label }).props.value).toBe("");
  const genericReport = renderer.root.findAllByType("label").find(node =>
    node.children.join("") === en.claimValidator.drugContext.boardReport)!.parent!.findByType("select");
  await act(async () => { genericReport.props.onChange({ target: { value: "yes" } }); });
  await change("MDS: Hematologist specialist report present", "true");
  await change("MDS: Report author specialty", "hematology");
  await change("MDS: Prescribed by a specialist", "true");
  await change("MDS: Prescribing specialist specialty", "hematology");
  await submit();
  expect(request().drug_context?.board_report_present).toBe(true);
  expect(request().materials[0].mds_evidence).toMatchObject({ specialist_report_present: true,
    prescribed_by_specialist: true, prescription_based_on_same_hematology_report: null });

  for (const [edit, expected] of [["true", true], ["false", false], ["", null]] as const) {
    await change(label, edit);
    expect(snapshot()).not.toContain("CURRENT_RESULT");
    await submit();
    expect(request().materials[0].mds_evidence?.prescription_based_on_same_hematology_report).toBe(expected);
  }

  await change(label, "true");
  await act(async () => { renderer.root.findByProps({ "aria-expanded": true }).props.onClick(); });
  await submit();
  expect(request()).not.toHaveProperty("drug_context");
  expect(request().materials[0]).not.toHaveProperty("mds_evidence");
  expect(request().materials[0]).not.toHaveProperty("adult_gh_evidence");
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  expect(renderer.root.findByProps({ "aria-label": label }).props.value).toBe("true");
});

it("cancels, submits again and discards late responses and errors from obsolete requests", async () => {
  const first = deferred<SutValidationResult>(), second = deferred<SutValidationResult>();
  vi.mocked(postJSON).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  await submit();
  const firstSignal = vi.mocked(postJSON).mock.calls[0][2]?.signal;
  await act(async () => { button("Cancel").props.onClick(); });
  expect(firstSignal?.aborted).toBe(true);
  await submit();
  await act(async () => { second.resolve(result("SECOND_RESULT")); });
  await act(async () => { first.reject(new Error("OBSOLETE_ERROR")); });
  expect(snapshot()).toContain("SECOND_RESULT"); expect(snapshot()).not.toContain("OBSOLETE_ERROR");
  const old = deferred<SutValidationResult>();
  vi.mocked(postJSON).mockReturnValueOnce(old.promise);
  await submit();
  const oldSignal = vi.mocked(postJSON).mock.calls.at(-1)![2]?.signal;
  await change("MDS: Hemoglobin value", "10");
  expect(oldSignal?.aborted).toBe(true);
  expect(button("Validate Claim").props.disabled).toBe(false);
  await submit();
  await act(async () => { old.resolve(result("STALE_RESULT")); });
  expect(snapshot()).toContain("CURRENT_RESULT"); expect(snapshot()).not.toContain("STALE_RESULT");
});

it("aborts an in-flight combined request on unmount", async () => {
  const pending = deferred<SutValidationResult>(); vi.mocked(postJSON).mockReturnValueOnce(pending.promise);
  await submit(); const signal = vi.mocked(postJSON).mock.calls.at(-1)![2]?.signal;
  await act(async () => { renderer.unmount(); }); expect(signal?.aborted).toBe(true);
  await act(async () => { pending.resolve(result("UNMOUNTED_RESULT")); });
});

it("normalizes invalid nested facts and excludes all draft fields when drug context is disabled", () => {
  const material = { name: "drug", unit_price: 0, quantity: 1,
    adult_gh_evidence: { itt_contraindicated: "false", stimulation_tests: [{ peak_gh_mcg_l: true, private_note: "PRIVATE" }] },
    mds_evidence: { hb_value: "10", specialist_report_present: 1,
      prescription_based_on_same_hematology_report: "true", private_note: "PRIVATE" } };
  const enabled = drugMaterialPayload(material as never, true);
  expect(enabled.adult_gh_evidence).toMatchObject({ itt_contraindicated: null, stimulation_tests: [{ peak_gh_mcg_l: null }] });
  expect(enabled.mds_evidence).toMatchObject({ hb_value: null, specialist_report_present: null,
    prescription_based_on_same_hematology_report: null });
  expect(JSON.stringify(enabled)).not.toContain("PRIVATE");
  expect(drugMaterialPayload(material as never, false)).toEqual({ name: "drug", unit_price: 0, quantity: 1 });
});

function Details() { return <ClinicalRestrictionDetails restrictions={restrictions} selectedRuleId="4.2.6.adult_somatropin_board_report" />; }
describe("bounded bilingual clinical review", () => {
  it.each([["en", en], ["tr", tr]] as const)("renders both gated warnings and nested missing fields in %s", (locale, messages) => {
    const html = renderToStaticMarkupWithLocale(<Details />, locale);
    expect(html).toContain(messages.claimValidator.clinical.output.gatedClinicalDraft);
    expect(html).toContain(messages.claimValidator.clinical.output.sets.adult_gh_closed_epiphysis);
    expect(html).toContain(messages.claimValidator.clinical.output.sets.mds_epoetin);
    expect(html).not.toContain("sections.claimValidator.");
    const t = (key: string): string => {
      let value: unknown = { sections: messages };
      for (const part of key.split(".")) value = value && typeof value === "object" ? (value as Record<string, unknown>)[part] : undefined;
      return typeof value === "string" ? value : key;
    };
    expect(clinicalMissingInputLabel("adult_gh_evidence.stimulation_tests[19].peak_gh_mcg_l", t))
      .toContain(messages.claimValidator.clinical.adultGh.fields.peak_gh_mcg_l);
    expect(clinicalMissingInputLabel("adult_gh_evidence.stimulation_tests.count", t))
      .toContain(messages.claimValidator.clinical.adultGh.fields.stimulation_tests_count);
    expect(clinicalMissingInputLabel("mds_evidence.hb_value", t)).toContain(messages.claimValidator.clinical.mds.fields.hb_value);
    expect(clinicalMissingInputLabel("mds_evidence.prescription_based_on_same_hematology_report", t))
      .toContain(locale === "tr" ? "Reçete aynı hematoloji raporuna dayanıyor" : "Prescription based on the same hematology report");
    expect(clinicalMissingInputLabel("adult_gh_evidence.stimulation_tests[20].private_note", t)).not.toContain("private_note");
  });
});
