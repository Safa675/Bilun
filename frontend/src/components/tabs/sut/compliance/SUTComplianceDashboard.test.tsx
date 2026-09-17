import { describe, expect, it, vi } from "vitest";
import React from "react";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { ComplianceIndexGroup, SUTComplianceDashboard } from "./SUTComplianceDashboard";
import ComplianceViewSection from "@/components/patient/views/ComplianceViewSection";
import PatientWorkspaceViews from "@/components/patient/views/PatientWorkspaceViews";
import { ComplianceFindingTable } from "./modules/ComplianceFindingTable";
import type { BillingActionReport, ClaimCompliance, ComplianceIndexResponse } from "@/lib/domains/sut";
import { recommendedActionSectionId } from "@/lib/recommendedActions";
import { complianceBilledAtRisk, recoverableUplift, viewActions, viewForSection } from "@/lib/workspaceViews";
import { ComplianceSubtabStrip } from "./ComplianceSubtabStrip";

const dashboardState = vi.hoisted(() => ({ index: undefined as ComplianceIndexResponse | undefined }));

vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useState: ((initial: unknown) => {
      if (initial === null && dashboardState.index !== undefined) {
        const value = dashboardState.index;
        dashboardState.index = undefined;
        return actual.useState(value);
      }
      return actual.useState(initial);
    }) as typeof actual.useState,
  };
});

vi.mock("./ComplianceSubtabStrip", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./ComplianceSubtabStrip")>();
  return { ...actual, ComplianceSubtabStrip: vi.fn(actual.ComplianceSubtabStrip) };
});

vi.mock("@/components/patient/SutBillingReportSections", () => ({
  BillingStrategySection: () => null,
  DrugIndicationReviewSection: () => null,
  LabOptimizationSection: () => null,
  MaterialsPreCheckSection: () => null,
  OptionalOverrideSection: () => null,
  RecommendedActionsPanel: () => null,
}));

const searchGet = vi.fn<(key: string) => string | null>(() => null);

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
  useSearchParams: () => ({
    get: (key: string) => searchGet(key),
    toString: () => "",
  }),
}));

vi.mock("@/lib/api/sut", () => ({
  getPatientAlerts: vi.fn().mockResolvedValue({
    patients: [],
    pagination: { total_matching: 0, limit: 50, offset: 0, has_more: false },
    summary: {},
  }),
  getComplianceIndex: vi.fn().mockResolvedValue({
    artifacts_available: true,
    n_patients: 0,
    n_findings: 0,
    n_patients_with_findings: 0,
    billed_at_risk_try: 0,
    by_surface: {},
    rows: [],
  }),
  getMedulaRejectionQueue: vi.fn().mockResolvedValue({
    total: 10,
    rows: [],
  }),
}));

const projection: ClaimCompliance = {
  findings: ["icu_bundled_leakage_510090", "tablo15_8_missing_diagnosis"].map((rule, i) => ({
    patient_id: "P /1",
    claim_id: "C &1",
    action_id: `claim_compliance:${rule}:P:C:${i}`,
    rule_id: rule as ClaimCompliance["findings"][number]["rule_id"],
    kind: rule as ClaimCompliance["findings"][number]["kind"],
    status: "violation",
    finding_type: "compliance",
    detail: `Detector detail ${i}`,
    sut_section_id: i === 0 ? "2.4.4.H" : "Tablo 15.8",
    procedure_line_id: i === 0 ? "L-ICU" : undefined,
    procedure_code: i === 0 ? "530130" : undefined,
    amount_try: null, billed_try: null, payable_try: null, savings_try: null,
    recoverable_uplift_try: null, compliance_savings_try: null,
    risk_amount_try: null, audit_exposure_try: null,
  })),
  evaluations: [{
    patient_id: "P /1", claim_id: "C &1", rule_id: "icu_bundled_leakage_510090",
    status: "evaluated", missing_inputs: [],
  }, {
    patient_id: "P /1", claim_id: "C &1", rule_id: "tablo15_8_missing_diagnosis",
    status: "evaluated", missing_inputs: [],
  }],
};

const index: ComplianceIndexResponse = {
  artifacts_available: true, n_patients: 2, n_findings: 3, n_patients_with_findings: 2,
  billed_at_risk_try: 10, by_surface: {},
  rows: [
    ...projection.findings.map((row) => ({ ...row, surface: "claim_compliance" as const })),
    { patient_id: "OTHER", surface: "materials", detail: "Other surface", billed_try: 10 },
  ],
  claim_compliance: { evaluations: [
    ...projection.evaluations,
    { patient_id: "MISSING", claim_id: null, rule_id: "tablo15_8_missing_diagnosis", status: "missing_inputs", missing_inputs: ["claim_context"] },
  ] },
};

function renderGroup(data: ComplianceIndexResponse | null = index, ids = new Set(["P /1"]), surface: "claim_compliance" | "materials" = "claim_compliance") {
  return renderToStaticMarkupWithLocale(<WorkspaceProvider><ComplianceIndexGroup index={data} surface={surface} loading={false} cohortPatientIds={ids} cohortFilterActive /></WorkspaceProvider>);
}

function renderPatient(block: ClaimCompliance | null | undefined = projection) {
  const report = { patient_id: "P /1", claim_id: "C &1", claim_compliance: block, recommended_actions: [] } as unknown as BillingActionReport;
  return renderToStaticMarkupWithLocale(<WorkspaceProvider><ComplianceViewSection billingReport={report} /></WorkspaceProvider>);
}

describe("claim compliance projection", () => {
  it.each([
    [undefined, true, 4],
    ["C &1", true, 3],
    ["C &1", false, 1],
  ] as const)("counts scoped presentation findings for claim %s with projection %s", (claimId, withProjection, count) => {
    const report = {
      patient_id: "P /1", claim_id: claimId,
      claim_compliance: withProjection ? {
        ...projection,
        findings: [...projection.findings,
          { ...projection.findings[0], claim_id: "SECOND", action_id: "second" },
          { ...projection.findings[0], patient_id: "OTHER", action_id: "foreign" }],
      } : undefined,
      recommended_actions: [{ action_id: "legacy", surface: "materials", kind: "material_pre_auth", finding_type: "compliance", billed_try: 123.45 }],
      audit_exposure_try: 17, sgk_uplift_try: 23, total_recoverable_try: 23,
    } as unknown as BillingActionReport;
    const before = JSON.stringify(report);
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider><PatientWorkspaceViews billingReport={report} patientId={report.patient_id} /></WorkspaceProvider>,
    );
    expect(html).toMatch(new RegExp(`At-risk findings</p><p[^>]*>${count}</p>`));
    expect(html).toMatch(new RegExp(`Compliance <span[^>]*>${count}</span>`));
    expect(viewActions(report, "compliance").map((row) => row.action_id)).toEqual(["legacy"]);
    expect(complianceBilledAtRisk(report)).toBe(123.45);
    expect(recoverableUplift(report)).toBe(23);
    expect(JSON.stringify(report)).toBe(before);
  });

  it("keeps large evaluation summaries compact without hiding findings or treating unknowns as passes", () => {
    const evaluations: ClaimCompliance["evaluations"] = Array.from({ length: 120 }, (_, i) => ({
      ...projection.evaluations[0],
      claim_id: `SUMMARY-${i}`,
      status: i < 80 ? "evaluated" : i % 2 === 0 ? "missing_inputs" : "unavailable",
      missing_inputs: i < 80 ? [] : ["claim_context"],
    }));
    const renderTable = (withFindings: boolean, entries = evaluations) => renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <ComplianceFindingTable
          rows={withFindings ? index.rows.filter((row) => row.surface === "claim_compliance") : []}
          evaluations={entries}
          loading={false}
          claimCompliance
        />
      </WorkspaceProvider>,
    );
    const html = renderTable(true);
    const summary = html.match(/<p class="text-xs tabular-nums[^>]*>(.*?)<\/p>/)?.[1];
    expect(summary).toBeDefined();
    expect(summary).toMatch(/\b80\b/);
    expect(summary?.match(/\b20\b/g)).toHaveLength(2);
    const details = html.match(/<details\b[^>]*>[\s\S]*?<\/details>/)?.[0];
    expect(details).toBeDefined();
    expect(details).not.toMatch(/<details\b[^>]*\bopen\b/);
    expect(details?.match(/<li\b/g)).toHaveLength(20);
    expect(details).toContain("SUMMARY-80");
    expect(details).not.toContain("SUMMARY-100");
    expect(details).toContain("Not evaluated — missing inputs");
    expect(details).toContain("Claim compliance unavailable — not evaluated.");
    expect(html).toContain("Detector detail 0");
    expect(html).toContain("Detector detail 1");
    expect(html).toContain('/patient/P%20%2F1?claim=C+%261&amp;section=claim-compliance');
    expect(html.match(/text-right tabular-nums text-\[var\(--text-primary\)\]">—/g)).toHaveLength(2);
    const emptyMessage = (markup: string) => markup.match(/<td colSpan="7"[^>]*>(.*?)<\/td>/)?.[1];
    const unknownMessage = emptyMessage(renderTable(false));
    const evaluatedMessage = emptyMessage(renderTable(false, evaluations.slice(0, 80)));
    expect(unknownMessage).toBeDefined();
    expect(evaluatedMessage).toBeDefined();
    expect(unknownMessage).not.toBe(evaluatedMessage);
  });

  it("renders both rules, details, null money and encoded patient/claim-scoped links", () => {
    const html = renderGroup();
    expect(html).toContain("ICU bundled service billed separately");
    expect(html).toContain("Missing claim diagnosis");
    expect(html).toContain("Detector detail 0");
    expect(html).toContain("Detector detail 1");
    expect(html).toContain("L-ICU");
    expect(html).toContain('/patient/P%20%2F1?claim=C+%261&amp;section=claim-compliance');
    expect(html.match(/text-right tabular-nums text-\[var\(--text-primary\)\]">—/g)).toHaveLength(2);
    expect(html).not.toContain("Other surface");
    expect(html).not.toContain("MISSING");
  });

  it("preserves missing evaluations for patients without findings and respects surfaces", () => {
    const html = renderGroup(index, new Set(["MISSING"]));
    expect(html).toContain("Not evaluated — missing inputs");
    expect(html).toContain("claim_context");
    expect(html).not.toContain("Detector detail");
    expect(renderGroup(index, new Set(["MISSING"]), "materials")).not.toContain("claim_context");
  });

  it("never presents old or absent cache projections as evaluated", () => {
    for (const data of [null, { ...index, rows: [], claim_compliance: undefined }]) {
      const html = renderGroup(data);
      expect(html).toContain("Claim compliance unavailable — not evaluated.");
      expect(html).not.toContain(": Evaluated");
    }
  });

  it("renders the mapped patient anchor and filters foreign patient/claim rows", () => {
    const html = renderPatient({
      findings: [...projection.findings, { ...projection.findings[0], claim_id: "FOREIGN", detail: "Foreign claim" }, { ...projection.findings[0], patient_id: "OTHER", detail: "Foreign patient" }],
      evaluations: projection.evaluations,
    });
    expect(recommendedActionSectionId("claim_compliance")).toBe("claim-compliance");
    expect(viewForSection("claim-compliance")).toBe("compliance");
    expect(html).toContain('id="claim-compliance"');
    expect(html).toContain("Detector detail 0");
    expect(html).toContain("Detector detail 1");
    expect(html).not.toContain("Foreign claim");
    expect(html).not.toContain("Foreign patient");
  });

  it("renders old and missing patient context honestly", () => {
    expect(renderPatient(null)).toContain("Claim compliance unavailable — not evaluated.");
    expect(renderPatient({ findings: [], evaluations: [{ ...projection.evaluations[0], claim_id: null, status: "missing_inputs", missing_inputs: ["claim_context"] }] })).toContain("Not evaluated — missing inputs");
  });

  it("labels partial results instead of silently treating a capped page as complete", () => {
    const html = renderGroup({ ...index, pagination: { total_matching: 5001, limit: 5000, offset: 0, has_more: true } });
    expect(html).toContain("Partial results:");
  });
});

describe("SUTComplianceDashboard", () => {
  it("omits the new badge count for old caches while preserving legacy counts", () => {
    searchGet.mockImplementation((key) => key === "compTab" ? "claim_compliance" : null);
    for (const available of [false, true]) {
      dashboardState.index = { ...index, claim_compliance: available ? index.claim_compliance : undefined };
      vi.mocked(ComplianceSubtabStrip).mockClear();
      const html = renderToStaticMarkupWithLocale(
        <WorkspaceProvider><SUTComplianceDashboard cohortPatientIds={new Set()} cohortFilterActive={false} /></WorkspaceProvider>,
      );
      const counts = vi.mocked(ComplianceSubtabStrip).mock.calls[0][0].badgeCounts;
      expect(counts?.materials).toBe(1);
      if (available) {
        expect(counts?.claim_compliance).toBe(2);
      } else {
        expect(counts).not.toHaveProperty("claim_compliance");
        expect(html).toMatch(/Claim Compliance<\/span><\/button>/);
      }
    }
  });

  it("renders live finding-family subtabs without demo marketing copy", () => {
    searchGet.mockImplementation(() => null);
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
    );

    expect(html).toContain("Copay Exemptions");
    expect(html).toContain("Surcharge Compliance");
    expect(html).toContain("Copay Rates");
    expect(html).toContain("Materials");
    expect(html).toContain("Drug Indication");
    expect(html).toContain("Payment Methods");
    expect(html).toContain("MEDULA rejections");
    expect(html).not.toContain("8 Boyutlu Denetim Aktif");
    expect(html).not.toContain("SUT Mevzuat ve Fatura Uyumluluk Merkezi");
    expect(html).not.toContain("MEDULA Rejection Playbook");
    expect(html).not.toContain("%98,4");
    expect(html).not.toContain("121.714");
  });

  it("renders live subtabs in Turkish", () => {
    searchGet.mockImplementation(() => null);
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
      "tr",
    );

    expect(html).toContain("Katılım Payı Muafiyetleri");
    expect(html).toContain("İlave Ücret &amp; Tavan Sınırı");
    expect(html).toContain("Tıbbi malzeme");
    expect(html).toContain("İlaç endikasyon");
    expect(html).toContain("Ödeme yöntemi");
    expect(html).not.toContain("MEDULA Red Kılavuzu");
  });

  it("falls back to exemptions when compTab is an unknown demo id", () => {
    searchGet.mockImplementation((key: string) =>
      key === "compTab" ? "surgical_sessions" : null,
    );
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
    );

    expect(html).toContain("Copay Exemptions");
    expect(html).not.toContain("OP1266");
    expect(html).not.toContain("Toplam Tıbbi Malzeme Riski");
  });
});
