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
    // Secondary coverage starts collapsed even when all checks were evaluated.
    expect(html).toContain('<details id="claim-coverage"');
    expect(html).not.toContain('<details id="claim-coverage" open=');
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
    const header = html.match(/<details id="claim-coverage"[^>]*>\s*<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(header).toContain("2 değerlendirilmedi");
    expect(header).toContain("1 eksik girdi");
    expect(header).toContain("1 değerlendirilemedi");
  });

  it("keeps missing amounts unavailable rather than synthesizing zero in the KPI row", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={{ ...baseReport, audit_exposure_try: undefined, recommended_actions: [] }} />
      </WorkspaceProvider>,
      "en",
    );
    const beforeTable = html.slice(0, html.indexOf('id="claim-compliance"'));
    expect(beforeTable).not.toContain("0.00 TRY");
    expect(beforeTable.match(/>—</g)).toHaveLength(2);
  });

  it("puts bill and patient details after findings and before collapsed secondary sections", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceViewSection billingReport={baseReport} detailsPrelude={<div>ORIGINAL BILL AND DETAILS</div>} selectedSection="claim-coverage" />
      </WorkspaceProvider>,
      "en",
    );
    expect(html.indexOf("ORIGINAL BILL AND DETAILS")).toBeGreaterThan(html.indexOf("</table>"));
    expect(html.indexOf("ORIGINAL BILL AND DETAILS")).toBeLessThan(html.indexOf('id="claim-coverage"'));
    expect(html).toContain('<details id="claim-coverage" open=""');
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

  describe("billed amount at risk KPI with missing billed amounts", () => {
    const reportWith = (actions: Array<Record<string, unknown>>): BillingActionReport =>
      ({
        ...baseReport,
        action_count: actions.length,
        audit_exposure_try: 0,
        recommended_actions: actions.map((action, index) => ({
          action_id: `act-${index}`,
          surface: "materials",
          kind: "material_pre_auth",
          finding_type: "compliance",
          ...action,
        })),
      }) as unknown as BillingActionReport;

    // Text of the "Billed amount at risk" KPI block only (label + value + hint).
    function billedKpiText(report: BillingActionReport, locale: "en" | "tr" = "en"): string {
      const html = renderToStaticMarkupWithLocale(
        <WorkspaceProvider>
          <ComplianceViewSection billingReport={report} />
        </WorkspaceProvider>,
        locale,
      );
      const label = locale === "en" ? "Billed amount at risk" : "Riskli faturalanan tutar";
      const block = new RegExp(`${label}</p>(.*?)</div>`).exec(html);
      expect(block).not.toBeNull();
      return (block as RegExpExecArray)[1].replace(/<[^>]+>/g, "|");
    }

    it("shows the exact sum and no hint when every amount is present", () => {
      const text = billedKpiText(
        reportWith([{ billed_try: 192.32 }, { billed_try: 192.32 }]),
      );
      expect(text).toBe("|384.64 TRY|");
    });

    it("shows a labelled partial sum, not a bare total, when some amounts are missing", () => {
      const text = billedKpiText(
        reportWith([
          { billed_try: 10000 },
          { billed_try: 15000 },
          ...Array.from({ length: 5 }, () => ({ billed_try: null })),
        ]),
      );
      expect(text).toContain("25,000.00 TRY");
      expect(text).toContain("Partial total: only 2 of 7 findings have a billed amount");
    });

    it("shows a dash and no 0.00 when no counted finding has a billed amount", () => {
      const text = billedKpiText(
        reportWith(Array.from({ length: 5 }, () => ({ billed_try: null }))),
      );
      expect(text).toContain("|—|");
      expect(text).not.toContain("0.00");
      expect(text).toContain("None of the 5 findings has a billed amount");
    });

    it("keeps excluding drug_indication findings without marking the sum partial", () => {
      const text = billedKpiText(
        reportWith([
          { billed_try: 100 },
          { surface: "drug_indication", kind: "drug_indication", billed_try: null },
        ]),
      );
      expect(text).toBe("|100.00 TRY|");
    });

    it("localizes the partial and unavailable states in Turkish", () => {
      const partial = billedKpiText(
        reportWith([{ billed_try: 100 }, { billed_try: null }]),
        "tr",
      );
      expect(partial).toContain("Kısmi toplam: 2 bulgudan yalnızca 1 tanesinde faturalanan tutar var");

      const none = billedKpiText(
        reportWith([{ billed_try: null }, { billed_try: null }]),
        "tr",
      );
      expect(none).toContain("|—|");
      expect(none).not.toContain("0,00");
      expect(none).toContain("2 bulgunun hiçbirinde faturalanan tutar yok");
    });
  });
});
