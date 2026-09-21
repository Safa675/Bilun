import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";
import type { UnifiedComplianceFindingRow } from "@/lib/complianceFindings";
import PatientWorkspaceViews from "./PatientWorkspaceViews";

const complianceProps = vi.hoisted(() => ({
  selectedFindingId: undefined as string | null | undefined,
  patientId: undefined as string | undefined,
  unifiedRows: undefined as UnifiedComplianceFindingRow[] | undefined,
}));

vi.mock("./ComplianceViewSection", () => ({
  default: ({
    selectedFindingId,
    patientId,
    unifiedRows,
  }: {
    selectedFindingId?: string | null;
    patientId?: string;
    unifiedRows?: UnifiedComplianceFindingRow[];
  }) => {
    complianceProps.selectedFindingId = selectedFindingId;
    complianceProps.patientId = patientId;
    complianceProps.unifiedRows = unifiedRows;
    return <div>MOCK-COMPLIANCE</div>;
  },
}));
vi.mock("./RevenueViewSection", () => ({
  default: () => <div>MOCK-REVENUE</div>,
}));
vi.mock("./AuditViewSection", () => ({
  default: () => <div>MOCK-AUDIT</div>,
}));

const report = {
  patient_id: "P-VIEWS",
  total_recoverable_try: 100,
  recommended_actions: [
    { action_id: "a1", surface: "materials", kind: "material_pre_auth", finding_type: "compliance" },
    { action_id: "a2", surface: "drug_indication", kind: "drug_indication", finding_type: "compliance" },
    { action_id: "a3", surface: "yatak_puani", kind: "yatak_puani_standard_bed", finding_type: "opportunity" },
    { action_id: "a4", surface: "claim_checklist", kind: "documentation_requirement", finding_type: "informational" },
  ],
} as unknown as BillingActionReport;

describe("PatientWorkspaceViews", () => {
  it("renders three tabs with live finding-count badges", () => {
    const html = renderToStaticMarkupWithLocale(
      <PatientWorkspaceViews billingReport={report} patientId="P-VIEWS" />,
    );

    expect(html).toContain("Compliance");
    expect(html).toContain("Revenue");
    expect(html).toContain("Documents");
    // Badge counts: 2 compliance, 1 revenue, 1 informational.
    expect(html.match(/>2</g)?.length).toBe(1);
    expect(html.match(/>1</g)?.length).toBe(2);
  });

  it("renders the compliance view content by default", () => {
    const html = renderToStaticMarkupWithLocale(
      <PatientWorkspaceViews billingReport={report} patientId="P-VIEWS" />,
    );

    expect(html).toContain("MOCK-COMPLIANCE");
    expect(html).not.toContain("MOCK-REVENUE");
    expect(html).not.toContain("MOCK-AUDIT");
  });

  it("labels the tab list for assistive technology", () => {
    const html = renderToStaticMarkupWithLocale(
      <PatientWorkspaceViews billingReport={report} patientId="P-VIEWS" />,
    );

    expect(html).toContain('aria-label="Billing review views"');
  });

  it("forwards the patient-route finding query into the Compliance view", () => {
    renderToStaticMarkupWithLocale(
      <PatientWorkspaceViews
        billingReport={report}
        patientId="P-VIEWS"
        selectedFindingId="claim_compliance:future-rule:P-VIEWS:C-VIEWS:procedure:L-1"
      />,
    );

    expect(complianceProps.selectedFindingId).toBe(
      "claim_compliance:future-rule:P-VIEWS:C-VIEWS:procedure:L-1",
    );
  });

  it("uses deduplicated unified findings count for the compliance badge and forwards props", () => {
    const reportWithSharedFinding = {
      ...report,
      recommended_actions: [
        {
          action_id: "a1",
          finding_id: "shared-1",
          surface: "materials",
          kind: "material_pre_auth",
          finding_type: "compliance",
        },
      ],
      claim_compliance: {
        findings: [
          {
            finding_id: "shared-1",
            action_id: "shared-1",
            patient_id: "P-VIEWS",
            rule_id: "r1",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const html = renderToStaticMarkupWithLocale(
      <PatientWorkspaceViews
        billingReport={reportWithSharedFinding}
        patientId="P-VIEWS"
      />,
    );

    // 1 deduplicated compliance finding
    expect(html.match(/>1</g)?.length).toBe(1);
    expect(complianceProps.unifiedRows).toHaveLength(1);
    expect(complianceProps.patientId).toBe("P-VIEWS");
  });
});
