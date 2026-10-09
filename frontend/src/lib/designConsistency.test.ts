import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { chipVariantFromColor } from "@/components/patient/billing-report/shared";

const scopedPaths = [
  "components/chat/SutInlineAIPanel.tsx",
  "components/cohort/CohortFilterBar.tsx",
  "components/feedback/ReportProblemModal.tsx",
  "components/patient/OriginalBillView.tsx",
  "components/patient/PatientFinancialSummary.tsx",
  "components/patient/SutPatientWorkspace.tsx",
  "components/patient/UnifiedComplianceFindingsTable.tsx",
  "components/patient/billing-report/BillingStrategySection.tsx",
  "components/patient/billing-report/CopayOptimizationSection.tsx",
  "components/patient/billing-report/OptionalOverrideSection.tsx",
  "components/patient/views/AuditViewSection.tsx",
  "components/patient/views/ComplianceViewSection.tsx",
  "components/patient/views/RevenueViewSection.tsx",
  "components/primitives/Stat.tsx",
  "components/shell/AppSidebar.tsx",
  "components/skeletons/SutSkeletons.tsx",
  "components/sut/ExemptionBasisChips.tsx",
  "components/sut/SutClauseDrawer.tsx",
  "components/tables/PatientInvoiceTable.tsx",
  "components/tabs/sut/operations/MedulaRejectionQueueTab.tsx",
  "components/tabs/sut/optimizer/SUTOptimizerTab.tsx",
];

describe("Phase 5 scoped design contracts", () => {
  it.each(scopedPaths)("uses color and type tokens in %s", (path) => {
    const source = readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
    expect(source).not.toMatch(/#[0-9a-f]{3,8}\b|rgba\(/i);
    expect(source).not.toMatch(/text-\[(?:\d|\.\d)/);
    expect(source).not.toContain("font-[var(--font-display)]");
  });

  it("keeps font loader variables separate from design tokens", () => {
    const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
    const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
    expect(css).toContain('--font-display: var(--font-fraunces, "Fraunces")');
    expect(css).toContain('--font-sans: var(--font-inter, "Inter")');
    expect(css).not.toMatch(/--font-(display|sans): var\(--font-\1/);
    expect(layout).toContain('variable: "--font-fraunces"');
    expect(layout).toContain('variable: "--font-inter"');
  });

  it("preserves status variants for CSS tokens and untouched legacy consumers", () => {
    expect(chipVariantFromColor("var(--danger)")).toBe("danger");
    expect(chipVariantFromColor("var(--warning)")).toBe("warning");
    expect(chipVariantFromColor("var(--success)")).toBe("success");
    expect(chipVariantFromColor("var(--gold)")).toBe("success");
    expect(chipVariantFromColor("var(--info)")).toBe("outline");
    expect(chipVariantFromColor("var(--text-muted)")).toBe("neutral");
    expect(chipVariantFromColor("#B91C1C")).toBe("danger");
    expect(chipVariantFromColor("#D97706")).toBe("warning");
    expect(chipVariantFromColor("#2F6E4E")).toBe("success");
    expect(chipVariantFromColor("#2563EB")).toBe("outline");
  });
});
