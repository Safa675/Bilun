import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SutClinicalRestriction, SutMesotheliomaEvidence } from "@/lib/api/clinicalEvidence";
import type { SutClaimRequest, SutValidationResult } from "@/lib/api/sut";
import { validateSutClaim } from "@/lib/api/sut";
import { postJSON } from "@/lib/api/request";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { useT } from "@/lib/i18n/useTranslations";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import en from "@/messages/en/sections";
import tr from "@/messages/tr/sections";
import { ClaimValidatorSection, ValidationResultPanel } from "./ClaimValidatorSection";
import { ClinicalMaterialInputs } from "./ClinicalMaterialInputs";
import { ClinicalRestrictionDetails } from "./ClinicalRestrictionDetails";
import { clinicalMissingInputLabel, mesotheliomaFields } from "./clinicalFields";
import { drugMaterialPayload, mesotheliomaEvidencePayload } from "./drugInputs";

vi.mock("@/lib/api/request", () => ({ postJSON: vi.fn(), requestJSON: vi.fn() }));
vi.mock("@/components/sut/MaterialBundlingScopeNotice", () => ({ MaterialBundlingScopeNotice: () => null }));
vi.mock("@/components/sut/SpecialtyProseScopeNotice", () => ({ SpecialtyProseScopeNotice: () => null }));

const material = { name: "pemetrexed", unit_price: 0, quantity: 1 };
const allFacts: SutMesotheliomaEvidence = {
  applies_on: "2026-10-04", assessment_date: "2026-10-03", diagnosis_site: "pleural",
  board_report_present: true, report_distinct_specialist_count: 3,
  treatment_protocol_documented_in_report: true, prescribed_by_specialist: true,
};
const blocked: SutClinicalRestriction = {
  constraint_set: "pleural_mesothelioma_documents", criterion_status: "not_evaluated", checks: [],
  missing_inputs: ["verified_source_for_service_date", "mesothelioma_documentary_interpretation_release"],
  source_refs: ["4.2.14.C.(2)#db104a38@under:4.2.14.C.m#ceda5531|4.2.14.C.n#37b794b9"],
  clinical_eligibility_complete: false, verification_status: "ai_generated_pending_review",
  checks_truncated: false, source_refs_truncated: false,
};
const reviewedResult: SutValidationResult = {
  contract_version: 2, request_id: "mesothelioma:1", claim_id: "C1",
  validation_status: "review_required", is_valid: null, violations: [],
  advisories: [{ evidence_id: "mesothelioma:review", rule: "drug_indication",
    material_name: "pemetrexed", message: "Historical rule observation requires source and input review.",
    disposition: "review_only", source_status: "historical_match_unverified",
    clinical_restrictions: [blocked], clinical_eligibility_complete: false }],
  material_applicability: [],
  coverage: { evaluation_count: 1, authored_rule_count: 1, unresolved_count: 1,
    disposition_counts: { review_only: 1 }, scope: "submitted_request_facts_only" },
  provenance: {}, summary: "", validation_time_ms: 1,
};

describe("experimental mesothelioma documentary contract", () => {
  it("covers all isolated backend facts, including the integer specialist count", () => {
    const source = readFileSync(resolve(process.cwd(), "../src/bilun/domain/claims/mesothelioma_evidence.py"), "utf8");
    const body = source.split("class MesotheliomaEvidence:")[1].split("\n\n")[0];
    const names = [...body.matchAll(/^    (\w+): /gm)].map(match => match[1]);
    expect(mesotheliomaFields.map(field => field.name).sort()).toEqual(names.sort());
    expect(body).toMatch(/report_distinct_specialist_count: int \| None/);
    expect(mesotheliomaFields.find(field => field.name === "report_distinct_specialist_count"))
      .toMatchObject({ kind: "number", integerOnly: true });
  });

  it.each([["en", en], ["tr", tr]] as const)("renders documentary fields, choices and draft warnings in %s", (locale, messages) => {
    const html = renderToStaticMarkupWithLocale(<ClinicalMaterialInputs material={material} onChange={() => {}} />, locale);
    expect(html).toContain(messages.claimValidator.clinical.groups.mesothelioma);
    expect(html).toContain(messages.claimValidator.clinical.hints.mesothelioma);
    const labels: Record<string, string> = messages.claimValidator.clinical.fields;
    const options: Record<string, string> = messages.claimValidator.clinical.options;
    for (const field of mesotheliomaFields) {
      expect(html).toContain(labels[field.name]);
      if ("options" in field) for (const option of field.options ?? []) expect(html).toContain(options[option]);
    }
    expect(html).toContain('step="1"');
    expect(html).not.toContain("sections.claimValidator.");
    const t = (key: string) => key.split(".").reduce<unknown>((value, part) =>
      (value as Record<string, unknown>)[part], { sections: messages }) as string;
    expect(clinicalMissingInputLabel("mesothelioma_documentary_interpretation_release", t))
      .toBe(labels.mesothelioma_documentary_interpretation_release);
    expect(clinicalMissingInputLabel("mesothelioma_evidence.report_board_composition_interpretation", t))
      .toContain(labels.report_board_composition_interpretation);
    expect(clinicalMissingInputLabel("mesothelioma_evidence.diagnosis_context_reconciliation", t))
      .toContain(labels.diagnosis_context_reconciliation);
  });

  it.each([null, undefined, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1])
    ("keeps invalid or absent specialist count %s unknown without changing other facts", count => {
      expect(mesotheliomaEvidencePayload({ ...allFacts, report_distinct_specialist_count: count }))
        .toEqual({ ...allFacts, report_distinct_specialist_count: null });
    });

  it("retains explicit negatives and nulls and removes documentary facts in disabled drug mode", () => {
    const facts: SutMesotheliomaEvidence = { diagnosis_site: null, board_report_present: false,
      report_distinct_specialist_count: 0, treatment_protocol_documented_in_report: false,
      prescribed_by_specialist: null, applies_on: null, assessment_date: null };
    expect(drugMaterialPayload({ ...material, mesothelioma_evidence: facts }, true).mesothelioma_evidence).toEqual(facts);
    expect(drugMaterialPayload({ ...material, mesothelioma_evidence: allFacts }, false)).not.toHaveProperty("mesothelioma_evidence");
    expect(drugMaterialPayload(material, true).mesothelioma_evidence).toBeNull();
  });
});

describe("mesothelioma form through the API request boundary", () => {
  let renderer: ReactTestRenderer;
  const labels: Record<string, string> = en.claimValidator.clinical.fields;
  const group = () => renderer.root.findAllByType("details").find(row =>
    row.findByType("summary").children.join("") === en.claimValidator.clinical.groups.mesothelioma)!;
  const change = async (field: string, value: string) => {
    await act(async () => { group().findByProps({ "aria-label": labels[field] }).props.onChange({ target: { value } }); });
  };
  const submit = async () => {
    await act(async () => {
      renderer.root.findAllByType("button").find(button => button.children.join("") === en.claimValidator.validateClaim)!.props.onClick();
    });
    expect(vi.mocked(postJSON).mock.calls.at(-1)![0]).toBe("/api/validate-claim");
    return vi.mocked(postJSON).mock.calls.at(-1)![1] as SutClaimRequest;
  };

  beforeEach(async () => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    vi.stubGlobal("document", { documentElement: { lang: "en" } });
    vi.mocked(postJSON).mockReset().mockRejectedValue(new Error("synthetic response"));
    await act(async () => { renderer = create(<LocaleProvider initialLocale="en"><ClaimValidatorSection /></LocaleProvider>); });
    await act(async () => { renderer.root.findByProps({ placeholder: en.claimValidator.namePlaceholder }).props.onChange({ target: { value: "pemetrexed" } }); });
    await act(async () => { renderer.root.findByProps({ "aria-expanded": false }).props.onClick(); });
  });
  afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.unstubAllGlobals(); });

  it("leaves documentary facts unknown when generic C45, report and prescriber context are entered", async () => {
    for (const input of [...group().findAllByType("input"), ...group().findAllByType("select")]) expect(input.props.value).toBe("");
    await act(async () => {
      renderer.root.findByProps({ placeholder: en.claimValidator.drugContext.icd10Placeholder }).props.onChange({ target: { value: "C45" } });
      renderer.root.findByProps({ placeholder: en.claimValidator.drugContext.prescriberPlaceholder }).props.onChange({ target: { value: "tıbbi onkoloji" } });
      renderer.root.findAllByType("label").find(label => label.children.join("") === en.claimValidator.drugContext.boardReport)!
        .parent!.findByType("select").props.onChange({ target: { value: "yes" } });
    });
    const request = await submit();
    expect(request.drug_context).toMatchObject({ primary_icd10: "C45", prescriber_specialty: "tıbbi onkoloji", board_report_present: true });
    expect(request.materials[0].mesothelioma_evidence).toBeNull();
    await change("board_report_present", "true");
    expect((await submit()).materials[0].mesothelioma_evidence).toEqual({ board_report_present: true, report_distinct_specialist_count: null });
  });

  it.each([0, 2, 3, 4])("transports integer count %i and explicit negatives without creating a clinical conclusion", async count => {
    expect(group().findByProps({ "aria-label": labels.report_distinct_specialist_count }).props.step).toBe(1);
    await change("report_distinct_specialist_count", String(count));
    await change("board_report_present", "false");
    await change("treatment_protocol_documented_in_report", "false");
    await change("prescribed_by_specialist", "false");
    await change("diagnosis_site", "nonpleural");
    expect((await submit()).materials[0].mesothelioma_evidence).toEqual({
      report_distinct_specialist_count: count, board_report_present: false,
      treatment_protocol_documented_in_report: false, prescribed_by_specialist: false, diagnosis_site: "nonpleural",
    });
  });

  it("keeps unknown site, cleared fields and invalid fractional counts unknown while dates stay independent", async () => {
    await change("diagnosis_site", "unknown");
    await change("applies_on", "2026-10-04");
    await change("assessment_date", "2026-10-03");
    await change("prescribed_by_specialist", "false");
    await change("prescribed_by_specialist", "");
    for (const invalid of ["", "1.5", "-1", "NaN", "Infinity"]) {
      await change("report_distinct_specialist_count", invalid);
      const request = await submit();
      expect(request.materials[0].mesothelioma_evidence).toEqual({ diagnosis_site: "unknown",
        applies_on: "2026-10-04", assessment_date: "2026-10-03",
        prescribed_by_specialist: null, report_distinct_specialist_count: null });
      expect(request.drug_context?.service_date).toBeNull();
    }
    await change("diagnosis_site", "");
    await change("applies_on", "");
    expect((await submit()).materials[0].mesothelioma_evidence).toMatchObject({ diagnosis_site: null, applies_on: null });
    await act(async () => { renderer.root.findByProps({ "aria-expanded": true }).props.onClick(); });
    const disabled = await submit();
    expect(disabled).not.toHaveProperty("drug_context");
    expect(disabled.materials[0]).not.toHaveProperty("mesothelioma_evidence");
  });

  it("shows review-required and unevaluated documentary output even after every fact is supplied", async () => {
    vi.mocked(postJSON).mockResolvedValue(reviewedResult);
    for (const [field, fact] of Object.entries(allFacts)) await change(field, String(fact));
    await act(async () => { renderer.root.findByProps({ "aria-label": en.claimValidator.drugContext.serviceDate })
      .props.onChange({ target: { value: "2026-10-04" } }); });
    const request = await submit();
    expect(request.materials[0].mesothelioma_evidence).toEqual(allFacts);
    expect(request.drug_context?.service_date).toBe("2026-10-04");
    const output = JSON.stringify(renderer.toJSON());
    expect(output).toContain(en.claimValidator.clinical.output.mesotheliomaDraft);
    expect(output).toContain(en.claimValidator.clinical.output.statuses.not_evaluated);
    expect(output).toContain(en.claimValidator.validationStatus.review_required);
    expect(output).not.toContain(en.claimValidator.clinical.output.statuses.criterion_clear);
    expect(output).not.toContain("Fully eligible");
  });
});

function ResultPanel({ result }: { result: SutValidationResult }) {
  return <ValidationResultPanel result={result} t={useT()} />;
}

describe("review-only documentary output", () => {
  it.each([["en", en], ["tr", tr]] as const)("preserves API review status, empty checks and explicit experimental scope in %s", async (locale, messages) => {
    vi.mocked(postJSON).mockResolvedValue(reviewedResult);
    const response = await validateSutClaim({ claim_id: "C1", procedure_code: "GENERIC",
      drug_context: { primary_icd10: "C45.0", prescriber_specialty: "tıbbi onkoloji", service_date: "2026-10-04" },
      materials: [drugMaterialPayload({ ...material, mesothelioma_evidence: allFacts }, true)] });
    expect(response.validation_status).toBe("review_required");
    expect(response.is_valid).toBeNull();
    expect(response.advisories[0].clinical_eligibility_complete).toBe(false);
    expect(response.advisories[0].clinical_restrictions![0]).toMatchObject({ criterion_status: "not_evaluated", checks: [], clinical_eligibility_complete: false });
    const html = renderToStaticMarkupWithLocale(<ResultPanel result={response} />, locale);
    expect(html).toContain(messages.claimValidator.validationStatus.review_required);
    expect(html).toContain(messages.claimValidator.clinical.output.sets.pleural_mesothelioma_documents);
    expect(html).toContain(messages.claimValidator.clinical.output.mesotheliomaDraft);
    expect(html).toContain(messages.claimValidator.clinical.output.statuses.not_evaluated);
    expect(html).toContain(messages.claimValidator.clinical.fields.mesothelioma_documentary_interpretation_release);
    expect(html).not.toContain("sections.claimValidator.");
    expect(html).not.toContain(messages.claimValidator.clinical.output.statuses.criterion_clear);
    expect(html).not.toContain(messages.claimValidator.confirmedFinding);
    expect(html).not.toContain("Fully eligible");
  });

  it("retains incomplete scope and release warnings for an isolated all-clear draft candidate", () => {
    const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[
      { ...blocked, criterion_status: "criterion_clear", checks: [{ field: "mesothelioma_evidence.board_report_present", status: "pass" }], missing_inputs: [] },
    ]} />);
    expect(html).toContain(en.claimValidator.clinical.output.partial);
    expect(html).toContain(en.claimValidator.clinical.output.mesotheliomaDraft);
    expect(html).not.toContain("Fully eligible");
  });
});
