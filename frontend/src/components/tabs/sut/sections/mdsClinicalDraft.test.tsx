import { act, useState } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import {
  buildMdsClinicalDraftRequest, mdsEvidencePayload, optionalMdsDate, optionalMdsNumber,
  type MdsClinicalDraftResponse, type MdsEvidence,
} from "@/lib/api/mdsClinicalDraft";
import { MdsClinicalDraft } from "./MdsClinicalDraft";

describe("MDS draft fact transport", () => {
  it.each([true, false, null])("preserves the explicit same-report relationship %s", value => {
    expect(mdsEvidencePayload({ prescription_based_on_same_hematology_report: value })
      ?.prescription_based_on_same_hematology_report).toBe(value);
  });

  it.each([undefined, "true", "false", "", 1, 0, [], {}])("keeps invalid same-report relationship %s unknown", value => {
    expect(mdsEvidencePayload({ prescription_based_on_same_hematology_report: value })
      ?.prescription_based_on_same_hematology_report).toBeNull();
  });

  it("does not derive the same-report relationship from separate report or prescriber facts", () => {
    expect(mdsEvidencePayload({ board_report_present: true, specialist_report_present: true,
      report_author_specialty: "hematology", report_date: "2026-10-05", prescribed_by_specialist: true,
      prescribed_by_specialty: "hematology", usage_dose_documented_in_report: true,
      usage_duration_documented_in_report: true })?.prescription_based_on_same_hematology_report).toBeNull();
  });

  it.each(["", " ", "-1", "NaN", "Infinity", "1e2", "0x10", "1,5", "500 mu/ml"])("keeps invalid numeric form input %s unknown", value => {
    expect(optionalMdsNumber(value)).toBeNull();
  });

  it("keeps zero and decimal form input explicit without accepting strings at transport", () => {
    expect(optionalMdsNumber("0")).toBe(0);
    expect(optionalMdsNumber("10.5")).toBe(10.5);
    const facts = mdsEvidencePayload({ hb_value: "10.5", blast_value: false, serum_epo_value: Infinity,
      weekly_dose_value: 0, prescribed_supply_months: 0.5, prescribed_by_specialist: false });
    expect(facts).toMatchObject({ hb_value: null, blast_value: null, serum_epo_value: null,
      weekly_dose_value: 0, prescribed_supply_months: 0.5, prescribed_by_specialist: false });
  });

  it.each([undefined, "", "2026-02-29", "2026-04-31", "2026-13-01", "0000-01-01", "2026-10-05T00:00:00Z", "05/10/2026"])("keeps missing or invalid date %s unknown", value => {
    expect(optionalMdsDate(value)).toBeNull();
  });

  it("preserves a real leap date without deriving another assessment or service date", () => {
    expect(optionalMdsDate("2024-02-29")).toBe("2024-02-29");
    expect(mdsEvidencePayload({ hb_date: "2024-02-29" })).toMatchObject({
      hb_date: "2024-02-29", assessment_date: null, applies_on: null,
    });
  });

  it("requires exact units, substance and phase without aliases or fact inference", () => {
    const facts = mdsEvidencePayload({ indication: "MDS", substance: "ESA", phase: "renewal",
      hb_value: 10.5, hb_unit: "g/L", blast_unit: "percent", serum_epo_unit: "mu/mL",
      weekly_dose_unit: "IU/week", report_author_specialty: "Hematology", specialist_report_present: "true" });
    expect(facts).toMatchObject({ indication: null, substance: null, phase: null, hb_value: 10.5,
      hb_unit: null, blast_unit: null, serum_epo_unit: null, weekly_dose_unit: null,
      report_author_specialty: null, specialist_report_present: null });
    expect(mdsEvidencePayload({ substance: "epoetin_alfa", phase: "restart", serum_epo_unit: "mu/ml" }))
      .toMatchObject({ substance: "epoetin_alfa", phase: "restart", serum_epo_unit: "mu/ml" });
    expect(mdsEvidencePayload({ specialist_report_present: true }))
      .toMatchObject({ report_author_specialty: null, prescribed_by_specialist: null, prescribed_by_specialty: null });
    expect(mdsEvidencePayload({ hb_value: 10.5, hb_date: "2026-10-05", serum_epo_value: 400, serum_epo_date: "2026-10-05" }))
      .toMatchObject({ lab_results_dates_documented_in_prescription_or_report: null });
  });

  it("whitelists the isolated request and excludes private or activation fields", () => {
    const input = { drug_name: "Aranesp", drug_claim_date: "2026-02-29", observed_icd10_codes: ["D46"],
      mode: "activate", enable: true, private_note: "private request detail", mds_evidence: {
        indication: "mds_anemia", substance: "epoetin_beta", hb_value: "10.5", private_note: "private clinical detail",
        board_report_present: true, clinical_eligibility_complete: true,
      } };
    const result = buildMdsClinicalDraftRequest(input as unknown as Parameters<typeof buildMdsClinicalDraftRequest>[0]);
    expect(result.drug_name).toBe("Aranesp");
    expect(result.drug_claim_date).toBeNull();
    expect(result.mds_evidence).toMatchObject({ substance: "epoetin_beta", hb_value: null, specialist_report_present: null });
    expect(Object.keys(result).sort()).toEqual(["drug_claim_date", "drug_name", "mds_evidence", "observed_icd10_codes", "selected_rule_id"]);
    expect(JSON.stringify(result)).not.toMatch(/private|activate|enable|board_report|clinical_eligibility_complete/);
    expect(mdsEvidencePayload(null)).toBeNull();
    expect(mdsEvidencePayload([])).toBeNull();
  });
});

const allMetReview: MdsClinicalDraftResponse = {
  review_status: "review_required", is_draft: true, clinical_eligibility_complete: false,
  integration_status: "registered_gated_draft", inspection_kind: "local_candidate",
  restriction: {
    constraint_set: "mds_epoetin", criterion_status: "criterion_clear", clinical_eligibility_complete: false,
    verification_status: "ai_generated_pending_review", checks_truncated: false, source_refs_truncated: false,
    missing_inputs: ["verified_source_for_service_date", "mds_clinical_interpretation_release"],
    checks: [{ field: "mds_evidence.hb_value", status: "pass" }], source_refs: [],
  },
};

describe("standalone MDS gated review", () => {
  it.each(["en", "tr"] as const)("labels the same-report relationship and leaves it unknown in %s", locale => {
    const html = renderToStaticMarkupWithLocale(<MdsClinicalDraft onChange={() => {}} />, locale);
    const label = locale === "tr" ? "Reçete aynı hematoloji raporuna dayanıyor" : "Prescription based on the same hematology report";
    expect(html).toContain(`aria-label="${label}"`);
    expect(html).toMatch(new RegExp(`aria-label="${label}"[^>]*><option value="" selected="">${locale === "tr" ? "Bilinmiyor" : "Unknown"}</option>`));
  });

  it.each(["en", "tr"] as const)("keeps all gates and incomplete eligibility visible in %s even with passed candidate checks", locale => {
    const html = renderToStaticMarkupWithLocale(<MdsClinicalDraft onChange={() => {}} review={allMetReview} />, locale);
    expect(html).toContain(locale === "tr" ? "MDS — taslak inceleme" : "MDS — draft review");
    expect(html).toContain(locale === "tr" ? "Klinik uygunluk değerlendirmesi tamamlanmadı" : "Clinical eligibility assessment is incomplete");
    expect(html).toContain(locale === "tr" ? "MDS kaynak kabulü bekliyor" : "MDS source admission pending");
    expect(html).toContain(locale === "tr" ? "Hizmet tarihi için kaynak doğrulaması bekliyor" : "Source verification for service date pending");
    expect(html).toContain(locale === "tr" ? "Bağımsız klinik yorum incelemesi bekliyor" : "Independent clinical interpretation review pending");
    expect(html).toContain(locale === "tr" ? "Hemoglobin değeri: Koşul karşılandı" : "Hemoglobin value: Criterion met");
    expect(html).not.toMatch(/pay_clear|clinical_eligibility_complete|criterion_clear|ai_generated_pending_review/);
  });

  it("does not echo private facts, unknown identifiers, source text or next_action from the review payload", () => {
    const review = { ...allMetReview, private_note: "PRIVATE_ENVELOPE", restriction: {
      ...allMetReview.restriction!, private_note: "PRIVATE_FACT", next_action: "PRIVATE_ACTION",
      source_refs: ["PRIVATE_SOURCE"], checks: [{ field: "PRIVATE_FIELD", status: "unknown" }],
      missing_inputs: ["PRIVATE_MISSING_FIELD"],
    } } as MdsClinicalDraftResponse;
    const html = renderToStaticMarkupWithLocale(<MdsClinicalDraft onChange={() => {}} review={review} />);
    expect(html).toContain("Additional clinical review: Unknown");
    expect(html).not.toContain("PRIVATE_");
  });
});

describe("controlled MDS inputs", () => {
  let renderer: ReactTestRenderer;
  let latest: MdsEvidence;
  const fetchMock = vi.fn();
  beforeEach(async () => {
    latest = {};
    fetchMock.mockClear();
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    vi.stubGlobal("document", { documentElement: { lang: "en" } });
    vi.stubGlobal("fetch", fetchMock);
    function Harness() {
      const [value, setValue] = useState<MdsEvidence>({});
      return <MdsClinicalDraft value={value} onChange={next => { latest = next; setValue(next); }} />;
    }
    await act(async () => { renderer = create(<LocaleProvider initialLocale="en"><Harness /></LocaleProvider>); });
  });
  afterEach(async () => { await act(async () => { renderer.unmount(); }); vi.unstubAllGlobals(); });
  const change = async (label: string, value: string) => {
    await act(async () => { renderer.root.findByProps({ "aria-label": label }).props.onChange({ target: { value } }); });
  };

  it("starts entirely unknown and keeps numbers independent from unit/date/phase", async () => {
    expect(renderer.root.findAllByType("input").every(input => input.props.value === "")).toBe(true);
    expect(renderer.root.findAllByType("select").every(select => select.props.value === "")).toBe(true);
    await change("Hemoglobin value", "10.5");
    expect(latest).toMatchObject({ hb_value: 10.5, hb_unit: null, hb_date: null, phase: null, applies_on: null });
    await change("Hemoglobin unit", "g/dL");
    await change("Hemoglobin date", "2026-10-05");
    await change("Treatment phase", "initiation");
    expect(latest).toMatchObject({ hb_value: 10.5, hb_unit: "g/dL", hb_date: "2026-10-05", phase: "initiation" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns invalid edits to unknown and preserves explicit false and zero", async () => {
    await change("Weekly dose value", "0");
    await change("Hematologist specialist report present", "false");
    await change("Prescribed by a specialist", "false");
    await change("Lab results and dates in prescription or report", "false");
    expect(latest).toMatchObject({ weekly_dose_value: 0, specialist_report_present: false, prescribed_by_specialist: false,
      lab_results_dates_documented_in_prescription_or_report: false });
    await change("Hemoglobin value", "0x10");
    await change("Hemoglobin date", "2026-02-29");
    await change("Hemoglobin unit", "g/L");
    await change("Treatment phase", "renewal");
    expect(latest).toMatchObject({ hb_value: null, hb_date: null, hb_unit: null, phase: null });
    await change("Hematologist specialist report present", "unknown");
    await change("Weekly dose value", "");
    expect(latest).toMatchObject({ specialist_report_present: null, weekly_dose_value: null });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps same-report edits independent and allows true, false and clearing to unknown", async () => {
    const label = "Prescription based on the same hematology report";
    await change("Hematologist specialist report present", "true");
    await change("Prescribed by a specialist", "true");
    expect(latest.prescription_based_on_same_hematology_report).toBeNull();
    await change(label, "true");
    expect(latest.prescription_based_on_same_hematology_report).toBe(true);
    await change(label, "false");
    expect(latest.prescription_based_on_same_hematology_report).toBe(false);
    await change(label, "");
    expect(latest).toMatchObject({ prescription_based_on_same_hematology_report: null,
      specialist_report_present: true, prescribed_by_specialist: true });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps CKD and unsupported restart explicit for backend reconciliation without changing substance", async () => {
    await change("Recorded indication", "ckd_anemia");
    await change("Exact substance", "epoetin_beta");
    await change("Treatment phase", "restart");
    expect(latest).toMatchObject({ indication: "ckd_anemia", substance: "epoetin_beta", phase: "restart" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
