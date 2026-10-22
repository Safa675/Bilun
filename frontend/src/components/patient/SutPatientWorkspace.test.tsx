import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

vi.mock("next/link", () => ({
  default: ({ children }: { children: unknown }) => children,
}));

vi.mock("@/lib/constants", () => ({
  buildSutHomeHref: () => "/?tab=patients",
}));

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtLabel: (value: string) => value,
  fmtNum: (value: number) => String(value),
  fmtTRY2: (value: number) => String(value),
  fmtPctRatio: (value: number) => `${(value * 100).toFixed(1)}%`,
  KpiCard: ({ label, value }: { label: string; value: string }) => `${label}:${value}`,
}));

vi.mock("@/lib/sutExactness", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/sutExactness")>(),
  isExactOutput: (block: { exactness_status?: string | null; pricing_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" || block?.pricing_status === "exact",
  hasRecoverableBillingTotals: (block: { exactness_status?: string | null; pricing_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" ||
    block?.pricing_status === "exact" ||
    block?.exactness_status === "partial_exact",
  getUnavailableMessage: (
    block: { unavailable_reason?: string | null; required_inputs_missing?: string[] | null } | null | undefined,
    fallback: string,
  ) => {
    const reason = block?.unavailable_reason ?? fallback;
    const missing = block?.required_inputs_missing
      ?.map((value) => value.replace(/_/g, " "))
      .join(", ");
    return missing ? `${reason} Missing exact inputs: ${missing}.` : reason;
  },
}));

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

import SutPatientWorkspace, { PatientOptimizationSnapshot } from "./SutPatientWorkspace";

describe("PatientOptimizationSnapshot", () => {
  it("renders unavailable messaging for non-exact optimization blocks", () => {
    const html = renderToStaticMarkupWithLocale(
      <PatientOptimizationSnapshot
        optimization={{
          patient_id: "P-001",
          n_diagnoses: 3,
          diagnoses: ["E11.9", "I10", "J45.9"],
          icd10_chapters: ["E", "I", "J"],
          copay_exemptions: {
            exempt: true,
            exemption_sources: [{ category: "ek1a_chronic" }],
            n_qualifying: 1,
            qualifying_diagnoses: [
              { icd10: "E11.9", disease: "Diabetes", range: "E10-E14" },
            ],
          },
          surcharge_exposure: {
            exactness_status: "missing_exact_inputs",
            unavailable_reason: "Needs exact billed procedure lines.",
            required_inputs_missing: ["billed_procedure_codes"],
            n_applicable_procedures: null,
            n_total_ek2g: null,
            exposure_rate: null,
            applicable_rules: [],
          },
          copay_rate_exposure: {
            exactness_status: "missing_exact_inputs",
            unavailable_reason: "Needs exact billed procedure lines.",
            required_inputs_missing: ["procedure_dates"],
            n_applicable_procedures: null,
            n_total_ek2c1: null,
            procedures_with_rates: [],
            mean_rate: null,
            rate_distribution: {},
          },
          drg_unbundling: {
            exactness_status: "missing_exact_inputs",
            unavailable_reason: "Needs exact itemized claim lines.",
            required_inputs_missing: ["itemized_billed_procedure_lines"],
            has_unbundling_risk: null,
            n_chapters_analyzed: null,
            chapter_analysis: [],
            total_potential_savings: null,
          },
        }}
      />,
    );

    expect(html).toContain("Diabetes");
    expect(html).toContain("Needs exact billed procedure lines.");
    expect(html).toContain("Missing exact inputs: billed procedure codes.");
    expect(html).toContain("Needs exact itemized claim lines.");
    expect(html).toContain("Missing exact inputs: itemized billed procedure lines.");
  });

  it("renders the H1 with the italic-gold 'workspace' accent and the patient ID as a mono subtitle", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutPatientWorkspace
        patientId="P-007"
        outcome={null}
        optimization={null}
      />,
    );

    // H1 phrase
    expect(html).toContain("Billing ");
    // italic-gold accent on the single H1 word
    expect(html).toMatch(/<em[^>]*italic[^>]*var\(--gold\)[^>]*>\s*Report\s*<\/em>/);
    // patient ID rendered as mono subtitle (not as the H1 itself)
    expect(html).toContain("font-mono");
    expect(html).toContain("P-007");
    // legacy chrome must be gone
    expect(html).not.toContain("frost-panel");
    expect(html).not.toContain("sut-premium-panel");
    expect(html).not.toContain("sut-premium-glass");
    expect(html).not.toContain("sut-patient-id-title");
  });

  it("renders the workspace without estimate-backed panels", () => {
    const html = renderToStaticMarkupWithLocale(
      <SutPatientWorkspace
        patientId="P-001"
        outcome={{
          patient_id: "P-001",
          data_source: {
            mode: "synthetic_demo",
            label: "Synthetic SUT demo claim data",
            is_synthetic: true,
            notice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
          },
          sut_claim_totals: {
            patient_id: "P-001",
            total_billed_try: 100,
            total_expected_payable_try: 90,
            claim_count: 1,
            procedure_line_count: 1,
            material_line_count: 0,
            drug_line_count: 0,
            lab_billed_line_count: 0,
            exactness_status: "exact",
          },
        }}
        optimization={null}
      />,
    );

    expect(html).not.toContain("DRGPanel");
    expect(html).not.toContain("DRG Episode Cost Modeling");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });
});

describe("PatientOptimizationSnapshot copay exemption states", () => {
  const unavailable = {
    exactness_status: "missing_exact_inputs" as const,
    unavailable_reason: "Needs exact billed procedure lines.",
    required_inputs_missing: [],
  };
  const copd = [
    { icd10: "J44.0", disease: "Kronik obstrüktif akciğer hastalığı", range: "J44" },
    { icd10: "I10", disease: "Hipertansiyon", range: "I10-I15" },
  ];
  const snapshot = (copay: Record<string, unknown>, locale: "en" | "tr" = "en") =>
    renderToStaticMarkupWithLocale(
      <PatientOptimizationSnapshot
        optimization={{
          patient_id: "P-002",
          n_diagnoses: 3,
          diagnoses: ["J44.0", "I10", "J18.9"],
          icd10_chapters: ["I", "J"],
          copay_exemptions: { n_qualifying: 2, qualifying_diagnoses: copd, ...copay } as never,
          surcharge_exposure: { ...unavailable, n_applicable_procedures: null, n_total_ek2g: null, exposure_rate: null, applicable_rules: [] },
          copay_rate_exposure: { ...unavailable, n_applicable_procedures: null, n_total_ek2c1: null, procedures_with_rates: [], mean_rate: null, rate_distribution: {} },
          drg_unbundling: { ...unavailable, has_unbundling_risk: null, n_chapters_analyzed: null, chapter_analysis: [], total_potential_savings: null },
        }}
      />,
      locale,
    );
  const unmetEk1a = { category: "ek1a_chronic", counts_toward_exempt: false, missing_requirements: ["chronic_health_report"] };

  it("says an EK-1A match without a recorded report is no waiver, not 'nothing matched'", () => {
    const html = snapshot({ exempt: false, partial_exempt: true, has_chronic_health_report: null, exemption_sources: [unmetEk1a] });
    expect(html).toContain("EK-1A diagnosis matched; chronic health report not recorded");
    expect(html).toContain(
      "2 qualifying EK-1A codes. The outpatient copay waiver (§1.8.5(7)) needs a chronic health report; none is recorded, so no waiver is claimed.",
    );
    expect(html).toContain("Report needed");
    expect(html).toContain("Kronik obstrüktif akciğer hastalığı"); // the matched disease still shows
    expect(html).not.toContain("No exemption ground matched");
    expect(html).not.toContain("No EK-1A, visit-type, or status exemption matched");
    expect(html).not.toContain(">Clear<");
  });

  it("derives the partial state from the EK-1A source when the payload has no partial flag", () => {
    const html = snapshot({ exempt: false, exemption_sources: [unmetEk1a] }, "tr");
    expect(html).toContain("EK-1A tanısı eşleşti; kronik hastalık raporu kayıtlı değil");
    expect(html).toContain(
      "2 EK-1A tanısı eşleşti. Ayakta katılım payı muafiyeti (§1.8.5(7)) kronik hastalık raporu gerektirir; kayıtlı rapor yok, bu yüzden muafiyet öne sürülmüyor.",
    );
    expect(html).toContain("Rapor gerekli");
    expect(html).not.toContain("Muafiyet gerekçesi eşleşmedi");
  });

  it("names the report when EK-1A exempts, and keeps 'Eligible' for other grounds", () => {
    const ek1a = snapshot({
      exempt: true,
      has_chronic_health_report: true,
      exemption_sources: [{ category: "ek1a_chronic", counts_toward_exempt: true }],
    });
    expect(ek1a).toContain("Exempt: EK-1A, chronic health report on file");
    expect(ek1a).toContain("Actionable");
    const emergency = snapshot({
      exempt: true,
      n_qualifying: 0,
      qualifying_diagnoses: [],
      exemption_sources: [{ category: "acil_servis", counts_toward_exempt: true }],
    });
    expect(emergency).toContain("Eligible");
    expect(emergency).not.toContain("chronic health report");
  });

  it("keeps the no-match wording when nothing matched", () => {
    const html = snapshot({ exempt: false, n_qualifying: 0, qualifying_diagnoses: [], exemption_sources: [] });
    expect(html).toContain("No exemption ground matched");
    expect(html).toContain("Clear");
    expect(html).not.toContain("Report needed");
  });
});
