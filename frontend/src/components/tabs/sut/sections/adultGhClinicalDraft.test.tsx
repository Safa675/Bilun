import { act, useState } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, describe, expect, it } from "vitest";
import { adultGhEvidencePayload, type SutAdultGhEvidence } from "@/lib/api/adultGhEvidence";
import { AdultGhClinicalDraft } from "./AdultGhClinicalDraft";

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const emptyTest = {
  test_id: null, performed_on: null, kind: null, inadequate_response_documented: null,
  peak_gh_mcg_l: null, peak_gh_documented_in_report: null, retest_after_epiphyseal_closure_stop: null,
};
const booleanFields = ["childhood_gh_deficiency_diagnosed", "childhood_gh_treatment_received",
  "gh_stopped_due_to_epiphyseal_closure", "adult_hypothalamic_pituitary_gh_deficiency_suspected",
  "additional_anterior_pituitary_deficiency_confirmed", "itt_contraindicated",
  "two_distinct_stimulation_procedures_documented"] as const;

describe("adult GH draft payload", () => {
  it("keeps every absent fact unknown and excludes inferred context", () => {
    const facts = adultGhEvidencePayload({ gh_patient_group: "adult", epiphyses_closed: true,
      gh_treatment_phase: "initiation", age: 65 });
    expect(facts).toEqual({ applies_on: null, assessment_date: null, diagnosis_pathway: null,
      childhood_gh_deficiency_diagnosed: null, childhood_gh_treatment_received: null,
      gh_stopped_due_to_epiphyseal_closure: null, adult_hypothalamic_pituitary_gh_deficiency_suspected: null,
      additional_anterior_pituitary_deficiency_confirmed: null, itt_contraindicated: null,
      two_distinct_stimulation_procedures_documented: null, stimulation_tests: null });
  });

  it.each([null, undefined, "true", [], 1])("does not invent evidence from malformed root %s", value => {
    expect(adultGhEvidencePayload(value)).toBeNull();
  });

  it.each(booleanFields)("distinguishes explicit false from missing or coerced %s", field => {
    expect(adultGhEvidencePayload({ [field]: false })?.[field]).toBe(false);
    expect(adultGhEvidencePayload({ [field]: true })?.[field]).toBe(true);
    for (const value of ["true", "false", 0, 1, null, undefined]) {
      expect(adultGhEvidencePayload({ [field]: value })?.[field]).toBeNull();
    }
  });

  it.each([
    ["itt", "2026-10-04"], ["other", "2026-10-05"],
  ])("does not infer two actual procedures from unique IDs with method %s and date %s", (kind, performed_on) => {
    const facts = adultGhEvidencePayload({ stimulation_tests: [
      { test_id: "T1", kind: "itt", performed_on: "2026-10-04", inadequate_response_documented: true },
      { test_id: "T2", kind, performed_on, inadequate_response_documented: true },
    ] });
    expect(facts?.stimulation_tests).toHaveLength(2);
    expect(facts?.two_distinct_stimulation_procedures_documented).toBeNull();
  });

  it("does not infer a pair from the one-test exception or overwrite an explicit pair observation", () => {
    const evidence = { additional_anterior_pituitary_deficiency_confirmed: true,
      stimulation_tests: [{ test_id: "T1", inadequate_response_documented: true }] };
    expect(adultGhEvidencePayload(evidence)?.two_distinct_stimulation_procedures_documented).toBeNull();
    expect(adultGhEvidencePayload({ ...evidence, two_distinct_stimulation_procedures_documented: false }))
      .toMatchObject({ additional_anterior_pituitary_deficiency_confirmed: true,
        two_distinct_stimulation_procedures_documented: false });
  });

  it.each([
    ["2024-02-29", "2024-02-29"], ["2000-02-29", "2000-02-29"], ["1900-02-29", null],
    ["2026-02-29", null], ["2026-04-31", null], ["2026-00-01", null], ["2026-13-01", null],
    ["2026-10-00", null], ["0000-01-01", null], ["0001-01-01", "0001-01-01"],
    ["2026-1-01", null], [" 2026-10-05", null], ["2026-10-05T00:00:00Z", null], [20261005, null],
  ])("requires actual strict civil dates for %s", (value, expected) => {
    expect(adultGhEvidencePayload({ applies_on: value, assessment_date: value,
      stimulation_tests: [{ performed_on: value }] })).toMatchObject({ applies_on: expected,
      assessment_date: expected, stimulation_tests: [{ performed_on: expected }] });
  });

  it("does not silently alias a diagnosis pathway or stimulation test kind", () => {
    expect(adultGhEvidencePayload({ diagnosis_pathway: "adult", stimulation_tests: [{ kind: "ITT" }] }))
      .toMatchObject({ diagnosis_pathway: null, stimulation_tests: [{ kind: null }] });
    for (const diagnosis_pathway of ["childhood_onset_retest", "adult_hypothalamic_pituitary"]) {
      expect(adultGhEvidencePayload({ diagnosis_pathway })?.diagnosis_pathway).toBe(diagnosis_pathway);
    }
  });

  it("retains incomplete, malformed and sparse test rows as unknown facts", () => {
    const sparse = Array(1);
    expect(adultGhEvidencePayload({ stimulation_tests: sparse })?.stimulation_tests).toEqual([emptyTest]);
    const input = [{ test_id: " first ", inadequate_response_documented: false }, {}, "bad row", null];
    const result = adultGhEvidencePayload({ stimulation_tests: input });
    expect(result?.stimulation_tests).toEqual([
      { ...emptyTest, test_id: "first", inadequate_response_documented: false }, emptyTest, emptyTest, emptyTest,
    ]);
    expect(input).toEqual([{ test_id: " first ", inadequate_response_documented: false }, {}, "bad row", null]);
  });

  it("bounds the collection without keeping a misleading truncated set of tests", () => {
    expect(adultGhEvidencePayload({ stimulation_tests: Array.from({ length: 20 }, () => ({})) })?.stimulation_tests)
      .toHaveLength(20);
    for (const stimulation_tests of [Array.from({ length: 21 }, () => ({})), {}, "[]", null]) {
      expect(adultGhEvidencePayload({ stimulation_tests })?.stimulation_tests).toBeNull();
    }
    expect(adultGhEvidencePayload({ stimulation_tests: [] })?.stimulation_tests).toEqual([]);
  });

  it.each([[0, 0], [2.99, 2.99], [3, 3], [3.01, 3.01], [-0.01, null], [NaN, null],
    [Infinity, null], [-Infinity, null], ["2.99", null], [false, null]])("preserves only native finite nonnegative peak GH %s", (value, expected) => {
    const result = adultGhEvidencePayload({ stimulation_tests: [{ kind: "itt", peak_gh_mcg_l: value,
      peak_gh_documented_in_report: false, inadequate_response_documented: "true",
      retest_after_epiphyseal_closure_stop: true }] });
    expect(result?.stimulation_tests?.[0]).toMatchObject({ peak_gh_mcg_l: expected,
      peak_gh_documented_in_report: false, inadequate_response_documented: null,
      retest_after_epiphyseal_closure_stop: true });
  });

  it("keeps other-test peak records without deriving inadequate response from the ITT threshold", () => {
    expect(adultGhEvidencePayload({ stimulation_tests: [{ kind: "other", peak_gh_mcg_l: 2.5 }] })?.stimulation_tests?.[0])
      .toMatchObject({ kind: "other", peak_gh_mcg_l: 2.5, inadequate_response_documented: null,
        peak_gh_documented_in_report: null });
  });

  it("accepts bounded native test identities and leaves invalid identities unknown", () => {
    expect(adultGhEvidencePayload({ stimulation_tests: [{ test_id: "a".repeat(120) }] })?.stimulation_tests?.[0].test_id)
      .toHaveLength(120);
    for (const test_id of ["", "   ", "a".repeat(121), 1]) {
      expect(adultGhEvidencePayload({ stimulation_tests: [{ test_id }] })?.stimulation_tests?.[0].test_id).toBeNull();
    }
  });
});

let renderer: ReactTestRenderer | undefined;
let current: SutAdultGhEvidence;

async function mount(value: SutAdultGhEvidence = {}) {
  current = value;
  function Harness() {
    const [facts, setFacts] = useState(value);
    return <AdultGhClinicalDraft value={facts} locale="en" onChange={next => { current = next; setFacts(next); }} />;
  }
  await act(async () => { renderer = create(<Harness />); });
}

async function change(label: string, value: string, valueAsNumber?: number) {
  await act(async () => { renderer!.root.findByProps({ "aria-label": label }).props.onChange({ target: { value, valueAsNumber } }); });
}

async function click(label: string) {
  await act(async () => {
    const button = renderer!.root.findAllByType("button").find(node => node.props["aria-label"] === label || node.children.includes(label));
    if (!button) throw new Error(`Missing button: ${label}`);
    button.props.onClick();
  });
}

afterEach(async () => { if (renderer) await act(async () => renderer!.unmount()); renderer = undefined; });

describe("isolated adult GH draft editor", () => {
  it.each(["tr", "en"] as const)("renders source, scope, other-test interpretation and disabled-runtime warnings in %s", locale => {
    const html = renderToStaticMarkup(<AdultGhClinicalDraft locale={locale} onChange={() => {}} />);
    expect(html).toContain(locale === "tr"
      ? "Kaynak/tarih kabulü ve bağımsız klinik yorum bekleyen taslak; ödeme uygunluğu kesinleşmez"
      : "Draft awaiting source/date admission and independent clinical interpretation; payment eligibility is not established");
    expect(html).toContain(locale === "tr" ? "prolaktin ve GH hariç" : "excluding prolactin and GH");
    expect(html).toContain(locale === "tr" ? "ITT sayısal eşiği diğer testlere uygulanmaz" : "the ITT numeric threshold does not apply to other tests");
    expect(html).toContain(locale === "tr" ? "yaş bunları belirlemez" : "age does not establish them");
    expect(html).toContain("§4.2.6.A-2(2)–(4)");
    expect(html).toContain(locale === "tr" ? "Rapor/reçete koşulları ayrı değerlendirilir; bu taslak bunları doğrulamaz"
      : "Report and prescription requirements are assessed separately; this draft does not verify them");
    expect(html).toContain(locale === "tr" ? "En az iki ayrı gerçek uyarı testi işlemi klinik kayıtta belgelenmiş"
      : "At least two distinct stimulation test procedures documented in the clinical record");
    expect(html).not.toContain("type=\"submit\"");
    expect(html).toContain("disabled=\"\"");
  });

  it("defaults to Turkish and makes every selection unknown", async () => {
    await act(async () => { renderer = create(<AdultGhClinicalDraft onChange={() => {}} />); });
    expect(renderer!.root.findByType("h3").children.join("")).toContain("Erişkin somatropin");
    const selects = renderer!.root.findAllByType("select");
    expect(selects).toHaveLength(8);
    for (const select of selects) expect(select.props.value).toBe("");
    for (const input of renderer!.root.findAllByType("input")) expect(input.props.value).toBe("");
  });

  it("edits and clears explicit false without changing separate clinical context", async () => {
    await mount();
    await change("Childhood GH deficiency diagnosed", "false");
    expect(current.childhood_gh_deficiency_diagnosed).toBe(false);
    await change("Documented diagnosis pathway", "childhood_onset_retest");
    expect(current.childhood_gh_treatment_received).toBeNull();
    expect(current.gh_stopped_due_to_epiphyseal_closure).toBeNull();
    expect(current).not.toHaveProperty("epiphyses_closed");
    await change("Childhood GH deficiency diagnosed", "");
    await change("Documented diagnosis pathway", "");
    expect(current.childhood_gh_deficiency_diagnosed).toBeNull();
    expect(current.diagnosis_pathway).toBeNull();
    await change("Application date", "2026-02-29");
    expect(current.applies_on).toBeNull();
  });

  it("keeps the documented procedure pair independent from test rows and the one-test exception", async () => {
    await mount({ stimulation_tests: [{ test_id: "T1" }, { test_id: "T2" }] });
    const label = "At least two distinct stimulation test procedures documented in the clinical record";
    expect(renderer!.root.findByProps({ "aria-label": label }).props.value).toBe("");
    await change("At least one additional anterior pituitary hormone deficiency confirmed (excluding prolactin and GH)", "true");
    expect(current.two_distinct_stimulation_procedures_documented).toBeNull();
    await change(label, "true");
    expect(current.two_distinct_stimulation_procedures_documented).toBe(true);
    await change(label, "false");
    expect(current.two_distinct_stimulation_procedures_documented).toBe(false);
    await change(label, "");
    expect(current.two_distinct_stimulation_procedures_documented).toBeNull();
    expect(current.additional_anterior_pituitary_deficiency_confirmed).toBe(true);
    expect(current.stimulation_tests?.map(test => test.test_id)).toEqual(["T1", "T2"]);
  });

  it("retains incomplete nested test rows through edits and only removes explicitly selected rows", async () => {
    await mount();
    await click("Add test");
    await click("Add test");
    expect(current.stimulation_tests).toEqual([emptyTest, emptyTest]);
    await change("Test record ID 1", "TEST-1");
    await change("Test date 1", "2026-10-01");
    await change("Inadequate response documented 1", "false");
    await change("Retest after treatment stopped because of epiphyseal closure 1", "true");
    expect(current.stimulation_tests?.[0]).toMatchObject({ test_id: "TEST-1", performed_on: "2026-10-01",
      inadequate_response_documented: false, retest_after_epiphyseal_closure_stop: true });
    expect(current.stimulation_tests?.[1]).toEqual(emptyTest);
    await click("Remove test 1");
    expect(current.stimulation_tests).toEqual([emptyTest]);
  });

  it("offers a numeric peak GH input only for ITT, preserving report facts and hidden recorded values", async () => {
    await mount({ stimulation_tests: [{ kind: "other", peak_gh_mcg_l: 2.99 }] });
    const peakLabel = "ITT peak GH (mcg/L; ITT only) 1";
    expect(renderer!.root.findAllByProps({ "aria-label": peakLabel })).toHaveLength(0);
    await change("Test type 1", "itt");
    const peak = renderer!.root.findByProps({ "aria-label": peakLabel });
    expect(peak.props).toMatchObject({ type: "number", min: 0, step: "any", value: 2.99 });
    await change(peakLabel, "3", 3);
    expect(current.stimulation_tests?.[0]).toMatchObject({ peak_gh_mcg_l: 3, inadequate_response_documented: null });
    await change("Peak GH response documented in the report 1", "false");
    await change(peakLabel, "-1", -1);
    expect(current.stimulation_tests?.[0]).toMatchObject({ peak_gh_mcg_l: null, peak_gh_documented_in_report: false });
    await change(peakLabel, "0", 0);
    await change("Test type 1", "other");
    expect(current.stimulation_tests?.[0]).toMatchObject({ peak_gh_mcg_l: 0, inadequate_response_documented: null });
    expect(renderer!.root.findAllByProps({ "aria-label": peakLabel })).toHaveLength(0);
  });

  it("prevents adding beyond the collection limit", async () => {
    await mount({ stimulation_tests: Array.from({ length: 20 }, () => ({})) });
    expect(renderer!.root.findAllByType("button").find(node => node.children.includes("Add test"))?.props.disabled).toBe(true);
    await click("Remove test 20");
    expect(current.stimulation_tests).toHaveLength(19);
    expect(renderer!.root.findAllByType("button").find(node => node.children.includes("Add test"))?.props.disabled).toBe(false);
  });

  it.each(["tr", "en"] as const)("limits a clear candidate to diagnostic prerequisites and keeps runtime disabled in %s", locale => {
    const html = renderToStaticMarkup(<AdultGhClinicalDraft locale={locale} onChange={() => {}} result={{
      runtime_enabled: false, clinical_eligibility_complete: false,
      runtime_result: { criterion_status: "not_evaluated", missing_inputs: ["adult_gh_source_date_admission"], clinical_eligibility_complete: false },
      candidate_result: { criterion_status: "criterion_clear", missing_inputs: [], clinical_eligibility_complete: false },
      pending_requirements: ["adult_gh_independent_clinical_interpretation"],
    }} />);
    expect(html).toContain(locale === "tr" ? "Tanı/uyarı testi alt kümesindeki önkoşullar karşılandı" : "Diagnosis/stimulation subset prerequisites met");
    expect(html).toContain("§4.2.6.A-2(2)–(4)");
    expect(html).toContain(locale === "tr" ? "Rapor/reçete koşulları ayrı değerlendirilir; bu taslak bunları doğrulamaz"
      : "Report and prescription requirements are assessed separately; this draft does not verify them");
    expect(html).toContain(locale === "tr" ? "Değerlendirilmedi" : "Not evaluated");
    expect(html).toContain(locale === "tr" ? "Kaynak ve tarih kabulü" : "Source and date admission");
    expect(html).toContain(locale === "tr" ? "Bağımsız klinik yorum" : "Independent clinical interpretation");
    expect(html).toContain(locale === "tr" ? "ödeme uygunluğu kesinleşmez" : "payment eligibility is not established");
    expect(html).toContain("disabled=\"\"");
  });

  it.each(["tr", "en"] as const)("identifies separate missing test rows and known review requirements in %s", locale => {
    const missing_inputs = [
      "adult_gh_evidence.stimulation_tests[0].test_id", "adult_gh_evidence.stimulation_tests[1].test_id",
      "adult_gh_evidence.stimulation_tests", "adult_gh_evidence.stimulation_tests.distinct_test_records",
      "adult_gh_evidence.stimulation_tests.count", "adult_gh_evidence.stimulation_tests.test_set_interpretation",
      "adult_gh_evidence.itt_contraindication_context_reconciliation",
      "adult_gh_evidence.two_distinct_stimulation_procedures_documented", "unknown_review_requirement",
    ];
    const html = renderToStaticMarkup(<AdultGhClinicalDraft locale={locale} onChange={() => {}} result={{
      runtime_enabled: false, clinical_eligibility_complete: false,
      candidate_result: { criterion_status: "unknown", missing_inputs, clinical_eligibility_complete: false },
      pending_requirements: ["verified_source_for_service_date", "adult_gh_clinical_interpretation_release"],
    }} />);
    const labels = locale === "tr" ? [
      "Test 1 — Test kaydı kimliği", "Test 2 — Test kaydı kimliği", "Belgelenmiş uyarı testi listesi",
      "Ayrı test kayıtlarının doğrulanması", "Gerekli uyarı testi sayısı", "Uyarı testlerinin birlikte klinik yorumu",
      "ITT kontrendikasyon kaydının testlerle uyumu", "Uygulama tarihi için doğrulanmış kaynak",
      "Erişkin GH klinik yorumunun onayı",
      "En az iki ayrı gerçek uyarı testi işlemi klinik kayıtta belgelenmiş",
    ] : [
      "Test 1 — Test record ID", "Test 2 — Test record ID", "Documented stimulation test list",
      "Confirmation of distinct test records", "Required stimulation test count",
      "Clinical interpretation of the complete stimulation test set", "Reconciliation of ITT contraindication records with tests",
      "Verified source for the application date", "Adult GH clinical interpretation approval",
      "At least two distinct stimulation test procedures documented in the clinical record",
    ];
    for (const label of labels) expect(html).toContain(`<li>${label}</li>`);
    for (const key of missing_inputs.slice(0, -1)) expect(html).not.toContain(key);
    expect(html).not.toContain("verified_source_for_service_date");
    expect(html).not.toContain("adult_gh_clinical_interpretation_release");
    expect(html).toContain("<li>unknown_review_requirement</li>");
  });
});
