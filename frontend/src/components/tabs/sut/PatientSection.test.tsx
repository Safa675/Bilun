import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";

vi.mock("@/hooks/useStaggeredReveal", () => ({
  default: () => ({}),
}));

vi.mock("@/lib/constants", () => ({
  CHART_COLORS: {
    grid: "#E4E4E7",
    text: "#71717A",
  },
}));

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

vi.mock("@/lib/sutExactness", () => ({
  isExactOutput: (block: { exactness_status?: string | null; pricing_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" || block?.pricing_status === "exact",
  getUnavailableMessage: (
    block: { unavailable_reason?: string | null } | null | undefined,
    fallback: string,
  ) => block?.unavailable_reason ?? fallback,
}));

vi.mock("@/components/ui/PatientSearch", () => ({
  default: () => null,
}));

vi.mock("@/lib/api/sut", () => ({
  searchSutPatients: vi.fn(),
}));

vi.mock("@/components/skeletons/SutSkeletons", () => ({
  SutPatientAnalyticsSkeleton: () => null,
}));

let ClaimSummaryPanel: typeof import("./PatientSection").ClaimSummaryPanel;
let DRGPanel: typeof import("./PatientSection").DRGPanel;
let PatientSUTContent: typeof import("./PatientSection").PatientSUTContent;

beforeAll(async () => {
  ({ ClaimSummaryPanel, DRGPanel, PatientSUTContent } = await import("./PatientSection"));
});

describe("ClaimSummaryPanel", () => {
  it("renders exact claim totals and procedure rule flags", () => {
    const html = renderToStaticMarkupWithLocale(
      <ClaimSummaryPanel
        data={{
          patient_id: "SENTETIK-HASTA-001",
          drg_summary: null,
          sut_claim_totals: {
            patient_id: "SENTETIK-HASTA-001",
            total_billed_try: 131.77,
            total_expected_payable_try: 131.77,
            claim_count: 1,
            procedure_line_count: 3,
            material_line_count: 0,
            drug_line_count: 0,
            lab_billed_line_count: 2,
            exactness_status: "exact",
          },
          sut_claim_summary: {
            exactness_status: "exact",
            claim_count: 1,
            procedure_line_count: 3,
            material_line_count: 0,
            drug_line_count: 0,
            diagnosis_count: 1,
            claims: [],
            top_procedures: [
              {
                procedure_line_id: "PROC-1",
                claim_id: "CLAIM-1",
                episode_id: "EP-1",
                procedure_date: "2024-01-15",
                procedure_code: "520030",
                procedure_name: "Muayene",
                procedure_category: "visit",
                billed_amount_try: 85.73,
                expected_payable_try: 85.73,
                surcharge_applicable: false,
                copay_rate_applicable: true,
              },
            ],
            drug_claims: [],
            material_claims: [],
          },
        }}
      />,
    );

    expect(html).toContain("Exact Claim-Line Summary");
    expect(html).toContain("132 TRY");
    expect(html).toContain("520030");
    expect(html).toContain("EK-2C-1 add-on rate");
    expect(html).toContain("EK-2C-1");
    expect(html).not.toContain(">Yes<");
  });
});

describe("DRGPanel exactness rendering", () => {
  it("renders unavailable package values when pricing is unresolved", () => {
    const html = renderToStaticMarkupWithLocale(
      <DRGPanel
        data={{
          n_episodes: 1,
          total_drg_cost: 26,
          mean_episode_cost: 26,
          most_expensive_drg: "Circulatory system (I10)",
          dominant_icd10_chapter: "I",
          total_drg_package_price: null,
          fully_priced: false,
          priced_episode_count: 0,
          unknown_date_episode_count: 1,
          pricing_status: "unknown_date",
          unavailable_reason: "Missing admission date",
          episodes: [
            {
              episode_id: 0,
              primary_icd10: "I10",
              primary_icd10_chapter: "I",
              description: "Circulatory system (I10)",
              los_days: 2,
              lab_cost: 5,
              visit_cost: 6,
              rx_cost: 7,
              procedure_cost: 8,
              total_cost: 26,
              drg_package_price: null,
              ek2c_group: "A3",
              admission_date: null,
              discharge_date: null,
              pricing_status: "unknown_date",
              unavailable_reason: "Missing admission date",
              required_inputs_missing: ["visit_date"],
            },
          ],
        }}
      />,
    );

    expect(html).toContain("Missing admission date");
    expect(html).toContain("DRG Package Price:");
    expect(html).toContain("EK-2C");
    expect(html).toContain("A3");
    expect(html).not.toContain("Reimbursement Gap:");
    expect(html).toContain("Unavailable");
  });

  it("renders exact package values when pricing is exact", () => {
    const html = renderToStaticMarkupWithLocale(
      <DRGPanel
        data={{
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
          episodes: [
            {
              episode_id: 0,
              primary_icd10: "I10",
              primary_icd10_chapter: "I",
              description: "Circulatory system (I10)",
              los_days: 2,
              lab_cost: 5,
              visit_cost: 6,
              rx_cost: 7,
              procedure_cost: 8,
              total_cost: 26,
              drg_package_price: 20,
              ek2c_group: "A3",
              admission_date: "2024-01-01",
              discharge_date: "2024-01-03",
              pricing_status: "exact",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("20 TRY");
    expect(html).not.toContain("Reimbursement Gap:");
    expect(html).not.toContain("Missing admission date");
  });

  it("keeps only exact-only patient outcome messaging", () => {
    const html = renderToStaticMarkupWithLocale(
      <PatientSUTContent
        data={{
          patient_id: "P-001",
          data_source: {
            mode: "synthetic_demo",
            label: "Synthetic SUT demo claim data",
            is_synthetic: true,
            notice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
          },
          consistency_warnings: ["Missing exact price provenance for one record."],
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
            episodes: [
              {
                episode_id: 0,
                primary_icd10: "I10",
                primary_icd10_chapter: "I",
                description: "Circulatory system (I10)",
                los_days: 2,
                lab_cost: 5,
                visit_cost: 6,
                rx_cost: 7,
                procedure_cost: 8,
                total_cost: 26,
                drg_package_price: 20,
                ek2c_group: "A3",
                admission_date: "2024-01-01",
                discharge_date: "2024-01-03",
                pricing_status: "exact",
              },
            ],
          },
        }}
        error={null}
        loading={false}
        reveal={{} as never}
        selectedPatientId="P-001"
        onPatientSelect={() => {}}
        onRetry={() => {}}
      />,
    );

    expect(html).toContain("Estimate-backed SUT cost ranges and gap projections were removed.");
    expect(html).toContain("DRG Episode Cost Modeling");
    expect(html).not.toContain("Estimated SUT Cost");
    expect(html).not.toContain("Reimbursement Gap Analysis");
  });
});
