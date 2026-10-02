import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { validateSutClaim } from "@/lib/api/sut";
import { ClaimValidatorSection } from "./ClaimValidatorSection";
import { drugMaterialPayload, optionalCount } from "./drugInputs";

vi.mock("@/lib/api/sut", () => ({ validateSutClaim: vi.fn(), getSutProcedureInfo: vi.fn() }));
vi.mock("@/components/sut/MaterialBundlingScopeNotice", () => ({ MaterialBundlingScopeNotice: () => null }));
vi.mock("@/components/sut/SpecialtyProseScopeNotice", () => ({ SpecialtyProseScopeNotice: () => null }));
let renderer: ReactTestRenderer;
const button = (text: string) => renderer.root.findAllByType("button").find(row => row.children.join("") === text)!;
const change = async (label: string, value: string) => {
  await act(async () => { renderer.root.findByProps({ "aria-label": label }).props.onChange({ target: { value } }); });
};
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("document", { documentElement: { lang: "en" } });
  vi.mocked(validateSutClaim).mockReset().mockRejectedValue(new Error("test response"));
  await act(async () => { renderer = create(<LocaleProvider initialLocale="en"><ClaimValidatorSection /></LocaleProvider>); });
  // The name field is the first material input, after claim ID and procedure code.
  await act(async () => { renderer.root.findAllByType("input")[2].props.onChange({ target: { value: "trastuzumab" } }); });
});
afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.unstubAllGlobals(); });

it("submits enabled checks with unknown diagnosis and explicit false/zero, then clears and disables safely", async () => {
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  await change("Administration count", "0");
  await change("Loading phase", "no");
  await change("Report validity (months)", "6");
  await change("Service date", "2026-06-30");
  await act(async () => { button("Add biomarker").props.onClick(); });
  await change("Marker", "HER2");
  await change("Measured marker status", "negative");
  await act(async () => { button("Add prior treatment").props.onClick(); });
  await change("Drug or class", "imatinib");
  await change("Recorded outcome", "resistant");
  await act(async () => { button("Validate Claim").props.onClick(); });
  expect(vi.mocked(validateSutClaim).mock.calls.at(-1)![0]).toMatchObject({
    drug_context: { primary_icd10: "", board_report_present: null, report_duration_months: 6, service_date: "2026-06-30" },
    materials: [{ annual_application_count: 0, is_loading_phase: false,
      biomarkers: [{ marker: "HER2", status: "negative" }], prior_therapies: [{ drug_or_class: "imatinib", outcome: "resistant" }] }],
  });
  await change("Administration count", "");
  await change("Loading phase", "");
  await change("Measured marker status", "");
  await act(async () => { button("Validate Claim").props.onClick(); });
  expect(vi.mocked(validateSutClaim).mock.calls.at(-1)![0].materials[0]).toMatchObject({ annual_application_count: null, is_loading_phase: null, biomarkers: [] });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": true }).props.onClick(); });
  await act(async () => { button("Validate Claim").props.onClick(); });
  const disabled = vi.mocked(validateSutClaim).mock.calls.at(-1)![0];
  expect(disabled).not.toHaveProperty("drug_context");
  expect(disabled.materials[0]).not.toHaveProperty("biomarkers");
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  expect(renderer.root.findByProps({ "aria-label": "Marker" }).props.value).toBe("HER2");
});

it("keeps line-specific entries associated after material removal", async () => {
  await act(async () => { button("+ Add Material").props.onClick(); });
  await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  await act(async () => { renderer.root.findAllByProps({ "aria-label": "Administration count" })[1].props.onChange({ target: { value: "4" } }); });
  await act(async () => { renderer.root.findAllByProps({ title: "Remove" }).find(row => row.type === "button")!.props.onClick(); });
  expect(renderer.root.findByProps({ "aria-label": "Administration count" }).props.value).toBe(4);
});

describe("drug payload unknown handling", () => {
  it.each([["", null], ["0", 0], ["3", 3], ["-1", null], ["1.5", null], ["NaN", null]])("parses %s without manufacturing a fact", (value, expected) => {
    expect(optionalCount(String(value))).toBe(expected);
  });
  it("omits incomplete marker results and preserves actual negative", () => {
    const payload = drugMaterialPayload({ name: "drug", quantity: 1, unit_price: 0,
      biomarkers: [{ marker: "ER", status: " " }, { marker: " HER2 ", status: " negative " }],
      prior_therapies: [{ drug_or_class: "imatinib", outcome: "" }],
    }, true);
    expect(payload.biomarkers).toEqual([{ marker: "HER2", status: "negative" }]);
    expect(payload.prior_therapies).toEqual([{ drug_or_class: "imatinib", outcome: "" }]);
  });
  it("preserves unknown prior treatment identity beside known unrelated treatments", () => {
    const payload = drugMaterialPayload({ name: "drug", quantity: 1, unit_price: 0,
      prior_therapies: [{ drug_or_class: " other drug ", outcome: "resistant" },
        { drug_or_class: " ", outcome: " " }],
    }, true);
    expect(payload.prior_therapies).toEqual([
      { drug_or_class: "other drug", outcome: "resistant" }, { drug_or_class: "", outcome: "" },
    ]);
  });
  it("keeps untouched lists unknown and empty lists empty, never a negative finding", () => {
    const base = { name: "drug", quantity: 1, unit_price: 0 };
    expect(drugMaterialPayload(base, true)).toMatchObject({ biomarkers: null, prior_therapies: null });
    expect(drugMaterialPayload({ ...base, biomarkers: [], prior_therapies: [] }, true))
      .toMatchObject({ biomarkers: [], prior_therapies: [] });
  });
});
