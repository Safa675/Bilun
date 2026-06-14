import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

vi.mock("next/link", () => ({
  default: ({ children }: { children: unknown }) => children,
}));

vi.mock("@/lib/constants", () => ({
  buildSutHomeHref: () => "/?tab=patients",
}));

vi.mock("@/components/tabs/sut/PatientSection", () => ({
  DRGPanel: () => "DRGPanel",
}));

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtLabel: (value: string) => value,
  fmtNum: (value: number) => String(value),
  fmtPctRatio: (value: number) => `${(value * 100).toFixed(1)}%`,
  KpiCard: ({ label, value }: { label: string; value: string }) => `${label}:${value}`,
}));

vi.mock("@/lib/sutExactness", () => ({
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

  it("renders the surviving DRG workspace without estimate-backed panels", () => {
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
          consistency_warnings: ["Needs provenance review."],
          drg_summary: {
            n_episodes: 1,
            total_drg_cost: 26,
            mean_episode_cost: 26,
            most_expensive_drg: "Circulatory system (I10)",
            dominant_icd10_chapter: "I",
            total_drg_package_price: 20,
            fully_priced: true,
            priced_episode_count: 1,
            unknown_date_episode_count: 0,
            pricing_status: "exact",
            episodes: [],
          },
        }}
        optimization={null}
      />,
    );

    expect(html).toContain("DRGPanel");
    expect(html).toContain("Needs provenance review.");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });
});
