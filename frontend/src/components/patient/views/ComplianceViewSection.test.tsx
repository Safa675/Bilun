import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import type { BillingActionReport } from "@/lib/domains/sut";
import ComplianceViewSection from "./ComplianceViewSection";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

describe("ComplianceViewSection", () => {
  const baseReport: BillingActionReport = {
    patient_id: "P-COMP",
    priority: "high",
    total_recoverable_try: 0,
    action_count: 2,
    audit_exposure_try: 1500,
    recommended_actions: [
      {
        action_id: "act-1",
        surface: "materials",
        kind: "material_pre_auth",
        finding_type: "compliance",
        billed_try: 500,
      },
      {
        action_id: "act-2",
        surface: "lab",
        kind: "hemogram_unbundling",
        finding_type: "compliance",
        compliance_savings_try: 120,
      },
    ],
    claim_compliance: {
      findings: [],
      evaluations: Array.from({ length: 25 }, (_, i) => ({
        patient_id: "P-COMP",
        claim_id: "C-1",
        rule_id: `rule_${i + 1}`,
        status: "evaluated",
        missing_inputs: [],
      })),
    },
    materials: {
      items: [],
      error_count: 0,
      pre_auth_required: [],
      miat_restricted: [],
      gazette_ceiling_by_specialty: {},
    },
    billing_strategy: {
      recommendations: [],
    },
    lab: {
      flagged_tests: [],
    },
  } as unknown as BillingActionReport;

  it("renders a single unified table and no separate second findings table", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={baseReport} />
      </WorkspaceProvider>,
      "tr",
    );

    // Exactly one data table element in the compliance section
    expect(html.match(/<table/g)?.length).toBe(1);

    // Both compliance actions appear in this single table
    expect(html).toContain("Malzeme ön kontrol");
    expect(html).toContain("Laboratuvar");
  });

  it("matches KPI findings value with the unified rows count", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={baseReport} />
      </WorkspaceProvider>,
      "tr",
    );

    // 2 findings in KPI
    expect(html).toContain("Riskli bulgu");
    // KPI Card renders label and formatted value
    expect(html).toContain(">2<");
  });

  it("renders structural coverage as a distinct subset without implying a clean result", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={baseReport} />
      </WorkspaceProvider>,
      "tr",
    );

    expect(html).toContain("Yapısal kontroller: 25 değerlendirme · 0 bulgu");
    expect(html).toContain("Yalnızca yapısal kontrollerin özeti; değerlendirme uygunluk kararı değildir.");
    // No details disclosure when all are evaluated
    expect(html).not.toContain("<details");
  });

  it("displays missing inputs and unavailable counts in coverage summary and provides disclosure", () => {
    const reportWithMissing: BillingActionReport = {
      ...baseReport,
      claim_compliance: {
        findings: [],
        evaluations: [
          ...baseReport.claim_compliance!.evaluations.slice(0, 23),
          {
            patient_id: "P-COMP",
            claim_id: "C-1",
            rule_id: "rule_missing",
            status: "missing_inputs",
            missing_inputs: ["diagnosis_code"],
          },
          {
            patient_id: "P-COMP",
            claim_id: "C-1",
            rule_id: "rule_unavail",
            status: "unavailable",
            missing_inputs: [],
          },
        ],
      },
    } as unknown as BillingActionReport;

    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={reportWithMissing} />
      </WorkspaceProvider>,
      "tr",
    );

    expect(html).toContain("Yapısal kontroller: 23 değerlendirme · 0 bulgu");
    expect(html).toContain("1 eksik girdi");
    expect(html).toContain("1 değerlendirilemedi");
    expect(html).toContain("<details");
    expect(html).toContain("diagnosis_code");
  });

  it("preserves detail section anchors in correct order", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={baseReport} />
      </WorkspaceProvider>,
      "tr",
    );

    expect(html).toContain('id="claim-compliance"');
    expect(html).toContain('id="billing-lab"');
    expect(html).toContain('id="billing-strategy"');
    expect(html).toContain('id="materials-pre-check"');
  });

  it("wraps the unified table inside the claim-compliance anchor", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={baseReport} />
      </WorkspaceProvider>,
      "tr",
    );

    const anchorIndex = html.indexOf('id="claim-compliance"');
    const tableIndex = html.indexOf("<table");
    const labIndex = html.indexOf('id="billing-lab"');

    expect(anchorIndex).toBeGreaterThanOrEqual(0);
    expect(tableIndex).toBeGreaterThanOrEqual(0);
    // The unified table must be inside (or immediately after) the
    // claim-compliance anchor so ?finding= exact scroll lands on the row,
    // not on the coverage summary below it.
    expect(anchorIndex).toBeLessThan(tableIndex);
    expect(tableIndex).toBeLessThan(labIndex);
    // Single anchor: no duplicate claim-compliance ids.
    expect(html.match(/id="claim-compliance"/g)?.length).toBe(1);
  });
});
