import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children }: { children: unknown }) => children,
}));

vi.mock("@/lib/constants", () => ({
  buildSutBillingHref: (patientId: string) => `/patient/${patientId}/billing`,
  buildSutHomeHref: () => "/?tab=analytics",
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

const SYNTHETIC_DEMO_COPY = vi.hoisted(
  () => "Synthetic demo claims — SUT rule calculations are exact for this generated claim-line fixture.",
);

vi.mock("@/components/sut/SyntheticDemoProvenance", () => ({
  SYNTHETIC_DEMO_COPY,
  SyntheticDemoProvenance: () => <div>{SYNTHETIC_DEMO_COPY}</div>,
}));

import SutPatientWorkspace, { PatientOptimizationSnapshot } from "./SutPatientWorkspace";

describe("PatientOptimizationSnapshot", () => {
  it("renders unavailable messaging for non-exact optimization blocks", () => {
    const html = renderToStaticMarkup(
      <PatientOptimizationSnapshot
        optimization={{
          patient_id: "P-001",
          n_diagnoses: 3,
          diagnoses: ["E11.9", "I10", "J45.9"],
          icd10_chapters: ["E", "I", "J"],
          copay_exemptions: {
            exempt: true,
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

  it("renders the surviving DRG workspace without estimate-backed panels", () => {
    const html = renderToStaticMarkup(
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
    expect(html).toContain(SYNTHETIC_DEMO_COPY);
    expect(html).toContain("Needs provenance review.");
    expect(html).toContain("Exactness note: this page does not invent billing totals locally.");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });
});
