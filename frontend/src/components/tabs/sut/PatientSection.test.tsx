import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRYFixture } from "@/test/fmtMoney";

vi.mock("@/hooks/useStaggeredReveal", () => ({
  default: () => ({}),
}));

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

vi.mock("@/lib/sutExactness", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/sutExactness")>(),
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
let PatientSUTContent: typeof import("./PatientSection").PatientSUTContent;

beforeAll(async () => {
  ({ ClaimSummaryPanel, PatientSUTContent } = await import("./PatientSection"));
});

describe("ClaimSummaryPanel", () => {
  it("renders exact claim totals and procedure rule flags", () => {
    const html = renderToStaticMarkupWithLocale(
      <ClaimSummaryPanel
        data={{
          patient_id: "SENTETIK-HASTA-001",
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
    expect(html).toContain(fmtTRYFixture(Math.round(131.77)));
    expect(html).toContain("520030");
    expect(html).toContain("EK-2C-1 copay rate");
    expect(html).toContain("EK-2C-1");
    expect(html).not.toContain(">Yes<");
  });
});

describe("PatientSUTContent", () => {
  it("keeps exact-only patient outcome messaging without DRG panel", () => {
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
        error={null}
        loading={false}
        reveal={{} as never}
        selectedPatientId="P-001"
        onPatientSelect={() => {}}
        onRetry={() => {}}
      />,
    );

    expect(html).toContain("Only calculated billed-item amounts are shown; no estimated amounts are added.");
    expect(html).toContain("Exact Claim-Line Summary");
    expect(html).not.toContain("DRG Episode Cost Modeling");
    expect(html).not.toContain("Estimated SUT Cost");
    expect(html).not.toContain("Reimbursement Gap Analysis");
  });
});
