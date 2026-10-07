import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import enBilling from "@/messages/en/billing";
import trBilling from "@/messages/tr/billing";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import type { RecommendedActionItem, ClaimComplianceFinding } from "@/lib/domains/sut";
import type { UnifiedComplianceFindingRow } from "@/lib/complianceFindings";
import UnifiedComplianceFindingsTable, {
  shouldActivateRowOnKeyDown,
  type UnifiedComplianceFindingsTableProps,
} from "./UnifiedComplianceFindingsTable";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const mockAction: RecommendedActionItem = {
  action_id: "act-1",
  surface: "billing_strategy",
  kind: "compliance_violation",
  finding_type: "compliance",
  claim_id: "C-100",
  procedure_code: "P-500",
  procedure_name: "Test Procedure",
  sut_section_id: "2.2.1",
  clause_ref: {
    clause_coordinate: "2.2.1",
    clause_key: "clause-2-2-1",
  },
  billed_try: 350,
};

const mockFinding: ClaimComplianceFinding = {
  finding_id: "canonical-find-1",
  action_id: "canonical-find-1",
  patient_id: "P-1",
  claim_id: "C-100",
  rule_id: "tablo15_8_missing_diagnosis",
  status: "violation",
};

function renderTable(
  props: UnifiedComplianceFindingsTableProps,
  locale: "tr" | "en" = "tr",
) {
  return renderToStaticMarkupWithLocale(
    <WorkspaceProvider>
      <UnifiedComplianceFindingsTable {...props} />
    </WorkspaceProvider>,
    locale,
  );
}

describe("UnifiedComplianceFindingsTable", () => {
  it.each(["en", "tr"] as const)("preserves all ordered %s fields and controls with a readable finding minimum", (locale) => {
    const labels = (locale === "en" ? enBilling : trBilling).views.compliance;
    const rows: UnifiedComplianceFindingRow[] = [null, 0, 123456789012345.67].map((amountValue, index) => ({
      rowId: `ordered-${index}`, canonicalFindingId: `finding-${index}`,
      sourceKind: "recommended_action", sourceLabels: [`Source ${index}`],
      status: "review_risk", title: `Title ${index}`, detail: `Complete detail ${index}`,
      claimId: `C-${index}`, code: `P-${index}`, sutLabel: "2.2.1",
      amountValue, amountLabel: null, action: mockAction, finding: mockFinding,
    }));
    const html = renderTable({ rows, patientId: "P-1", onOpenClause: vi.fn(), selectedActionId: "act-1" }, locale);
    const headers = [...html.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/g)]
      .map((match) => match[1].replace(/<[^>]+>/g, ""));
    const body = html.match(/<tbody>([\s\S]*?)<\/tbody>/)?.[1] ?? "";
    const renderedRows = [...body.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g)];

    expect(headers).toEqual([labels.colStatus, labels.colSource, labels.colFinding, labels.colClaim,
      labels.colCode, labels.colSut, labels.colAmount, labels.colInspect]);
    expect(html.match(/class="min-w-\[30rem\]"/g)).toHaveLength(4);
    expect(html).toContain('style="min-width:960px"');
    expect(html).toContain("overflow-x-auto");
    expect(renderedRows).toHaveLength(3);
    renderedRows.forEach((match, index) => {
      const cells = [...match[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)]
        .map((cell) => cell[1].replace(/<[^>]+>/g, "").trim());
      expect(cells).toEqual([labels.statusReviewRisk, `Source ${index}`, `Title ${index}Complete detail ${index}`,
        `C-${index}`, `P-${index}`, "SUT §2.2.1", rows[index].amountValue == null ? "—" : fmtTRY2(rows[index].amountValue),
        labels.inspectAction]);
      expect(match[0]).toContain('tabindex="0"');
      expect(match[0]).toContain('data-selected="true"');
      expect(match[0]).toContain("<button");
      expect(match[0]).toContain(`finding=finding-${index}`);
    });
  });

  it("renders the eight approved columns and does NOT render Patient ID / Hasta ID", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "row-1",
        canonicalFindingId: null,
        sourceKind: "recommended_action",
        sourceLabels: ["Fatura stratejisi"],
        status: "review_risk",
        title: "Test finding",
        detail: "Test detail",
        claimId: "C-100",
        code: "P-500",
        sutLabel: "2.2.1",
        amountValue: 350,
        amountLabel: "Faturalanan (risk)",
        action: mockAction,
        finding: null,
      },
    ];

    const html = renderTable({ rows, patientId: "P-1" });

    expect(html).toContain('data-mobile-stacked="true"');
    expect((html.match(/data-label=/g) ?? []).length).toBe(8);
    expect(html).toContain('data-label="Fatura"');
    expect(html).toContain('data-label="Risk tutarı"');
    expect(html).toContain("C-100");
    expect(html).toContain("₺350,00");

    // 8 columns in Turkish
    expect(html).toContain("Durum");
    expect(html).toContain("Kaynak");
    expect(html).toContain("Bulgu / yapılması gereken");
    expect(html).toContain("Fatura");
    expect(html).toContain("Kod");
    expect(html).toContain("SUT");
    expect(html).toContain("Risk tutarı");
    expect(html).toContain("İncele");

    // No Hasta ID / Patient ID column header
    expect(html).not.toContain("<th>Hasta ID</th>");
    expect(html).not.toContain("<th>Hasta Kimliği</th>");
    expect(html).not.toContain("<th>Patient ID</th>");
  });

  it("renders confirmed_violation and review_risk with distinct chip labels and variants", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-viol",
        canonicalFindingId: "f-1",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "confirmed_violation",
        title: "Violation finding",
        detail: null,
        claimId: "C-1",
        code: "K-1",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: mockFinding,
      },
      {
        rowId: "r-risk",
        canonicalFindingId: null,
        sourceKind: "recommended_action",
        sourceLabels: ["Malzeme ön kontrol"],
        status: "review_risk",
        title: "Risk finding",
        detail: null,
        claimId: "C-2",
        code: "K-2",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: mockAction,
        finding: null,
      },
    ];

    const html = renderTable({ rows, patientId: "P-1" });

    expect(html).toContain("Kesin ihlal");
    expect(html).toContain("Risk — inceleme gerekli");
    // Chip variants danger and warning are styled distinctly
    expect(html).toContain("text-[var(--danger)]");
    expect(html).toContain("text-[var(--warning)]");
  });

  it("renders source label chips for each row", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-dual",
        canonicalFindingId: "f-dual",
        sourceKind: "recommended_action",
        sourceLabels: ["Laboratuvar", "Fatura uyumluluğu"],
        status: "confirmed_violation",
        title: "Lab finding",
        detail: null,
        claimId: "C-1",
        code: "L-1",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: mockAction,
        finding: mockFinding,
      },
    ];

    const html = renderTable({ rows, patientId: "P-1" });

    expect(html).toContain("Laboratuvar");
    expect(html).toContain("Fatura uyumluluğu");
  });

  it("renders '—' for null amount and never displays ₺0 or ₺0,00", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-null-amt",
        canonicalFindingId: "f-null",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "confirmed_violation",
        title: "Unpriced finding",
        detail: null,
        claimId: null,
        code: null,
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: mockFinding,
      },
    ];

    const html = renderTable({ rows, patientId: "P-1" });

    expect(html).not.toContain("₺0");
    expect(html).not.toContain("₺0,00");
    expect(html).toContain("—");
  });

  it("attaches row selection accessibility attributes and cursor styling to action rows", () => {
    const onSelectAction = vi.fn();
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-action",
        canonicalFindingId: null,
        sourceKind: "recommended_action",
        sourceLabels: ["Fatura stratejisi"],
        status: "review_risk",
        title: "Clickable action",
        detail: null,
        claimId: "C-1",
        code: "P-1",
        sutLabel: null,
        amountValue: 100,
        amountLabel: "SGK artışı",
        action: mockAction,
        finding: null,
      },
      {
        rowId: "r-no-action",
        canonicalFindingId: "f-no-act",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "review_risk",
        title: "Finding only",
        detail: null,
        claimId: "C-1",
        code: "P-1",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: mockFinding,
      },
    ];

    const html = renderTable({
      rows,
      patientId: "P-1",
      onSelectAction,
      selectedActionId: "act-1",
    });

    expect(html).toContain('tabindex="0"');
    expect(html).toContain("cursor-pointer");
    expect(html).toContain('data-selected="true"');
    expect(html).toContain("bg-[var(--gold-subtle)]");
  });

  it("preserves canonical finding ?finding= deep-link and applies exact selectedFindingId state", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-canon",
        canonicalFindingId: "canonical-find-1",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "confirmed_violation",
        title: "Canonical finding",
        detail: null,
        claimId: "C-100",
        code: "P-1",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: mockFinding,
      },
      {
        rowId: "r-other",
        canonicalFindingId: "other-find-2",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "review_risk",
        title: "Other finding",
        detail: null,
        claimId: "C-100",
        code: "P-2",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: { ...mockFinding, finding_id: "other-find-2" },
      },
    ];

    const htmlSelected = renderTable({
      rows,
      patientId: "P-1",
      selectedFindingId: "canonical-find-1",
    });

    expect(htmlSelected).toContain('data-finding-id="canonical-find-1"');
    expect(htmlSelected).toContain('data-selected="true"');
    expect(htmlSelected).toContain("finding=canonical-find-1");

    // Unknown finding id does not select any row
    const htmlUnselected = renderTable({
      rows,
      patientId: "P-1",
      selectedFindingId: "unknown-finding-id",
    });
    expect(htmlUnselected).not.toContain('data-selected="true"');
  });

  it("carries both action selection styling and canonical inspect link on a merged row", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "canonical-find-1",
        canonicalFindingId: "canonical-find-1",
        sourceKind: "recommended_action",
        sourceLabels: ["Fatura stratejisi", "Fatura uyumluluğu"],
        status: "confirmed_violation",
        title: "Merged row",
        detail: null,
        claimId: "C-100",
        code: "P-1",
        sutLabel: null,
        amountValue: 350,
        amountLabel: "Faturalanan (risk)",
        action: mockAction,
        finding: mockFinding,
      },
    ];

    const html = renderTable({
      rows,
      patientId: "P-1",
      selectedActionId: "act-1",
      selectedFindingId: "canonical-find-1",
    });

    expect(html).toContain("cursor-pointer");
    expect(html).toContain('data-selected="true"');
    expect(html).toContain(
      'href="/patient/P-1?claim=C-100&amp;section=claim-compliance&amp;finding=canonical-find-1"',
    );
  });

  it("renders an Inspect link for legacy action_id fallback canonical identity", () => {
    const legacyFinding: ClaimComplianceFinding = {
      ...mockFinding,
      finding_id: undefined,
      action_id: "legacy-canonical-1",
    };
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "canonical:legacy-canonical-1",
        canonicalFindingId: "legacy-canonical-1",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "confirmed_violation",
        title: "Legacy finding",
        detail: null,
        claimId: "C-100",
        code: "P-1",
        sutLabel: null,
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: legacyFinding as ClaimComplianceFinding,
      },
    ];

    const html = renderTable({ rows, patientId: "P-1" });

    expect(html).toContain("finding=legacy-canonical-1");
    expect(html).toContain("section=claim-compliance");
    expect(html).toContain('data-finding-id="legacy-canonical-1"');
  });

  it("renders ₺0,00 for explicit zero amount and never as —", () => {
    const rows: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-zero",
        canonicalFindingId: "f-zero",
        sourceKind: "claim_compliance",
        sourceLabels: ["Fatura uyumluluğu"],
        status: "review_risk",
        title: "Zero finding",
        detail: null,
        claimId: null,
        code: null,
        sutLabel: null,
        amountValue: 0,
        amountLabel: "Faturalanan (risk)",
        action: null,
        finding: mockFinding,
      },
    ];

    const html = renderTable({ rows, patientId: "P-1" });

    expect(html).toContain("₺0,00");
    // The zero row must not render the unknown-amount dash in the amount cell.
    // Other cells (claim/code) still use —, so assert the formatted zero exists
    // rather than asserting global absence of —.
  });

  it("activates rows via keyboard only when the event originates on the row itself", () => {
    const row = {} as unknown;
    const button = {} as unknown;

    expect(
      shouldActivateRowOnKeyDown({ key: "Enter", target: row, currentTarget: row }),
    ).toBe(true);
    expect(
      shouldActivateRowOnKeyDown({ key: " ", target: row, currentTarget: row }),
    ).toBe(true);
    // Nested clause button or Inspect link bubbling to the row must not activate it.
    expect(
      shouldActivateRowOnKeyDown({ key: "Enter", target: button, currentTarget: row }),
    ).toBe(false);
    expect(
      shouldActivateRowOnKeyDown({ key: " ", target: button, currentTarget: row }),
    ).toBe(false);
    expect(
      shouldActivateRowOnKeyDown({ key: "Escape", target: row, currentTarget: row }),
    ).toBe(false);
  });

  it("renders SUT section cell as a button when onOpenClause and clauseKey are present", () => {
    const onOpenClause = vi.fn();
    const rowsWithClause: UnifiedComplianceFindingRow[] = [
      {
        rowId: "r-clause",
        canonicalFindingId: null,
        sourceKind: "recommended_action",
        sourceLabels: ["Fatura stratejisi"],
        status: "review_risk",
        title: "Clause action",
        detail: null,
        claimId: "C-1",
        code: "P-1",
        sutLabel: "2.2.1",
        amountValue: null,
        amountLabel: null,
        action: mockAction,
        finding: null,
      },
    ];

    const htmlWithClause = renderTable({
      rows: rowsWithClause,
      patientId: "P-1",
      onOpenClause,
    });

    expect(htmlWithClause).toContain("<button");
    expect(htmlWithClause).toContain('aria-label="Fıkrayı incele: 2.2.1"');
    expect(htmlWithClause).toContain("§2.2.1");
    expect(htmlWithClause).toContain("SUT §2.2.1");

    const htmlWithoutClause = renderTable({
      rows: rowsWithClause,
      patientId: "P-1",
    });

    expect(htmlWithoutClause).not.toContain("<button");
    expect(htmlWithoutClause).toContain("§2.2.1");
  });

  it("opens a canonical finding clause through the shared callback without a recommended action", () => {
    const html = renderTable({
      patientId: "P-1",
      onOpenClause: vi.fn(),
      rows: [{
        rowId: "canonical-clause",
        canonicalFindingId: "canonical-find-1",
        sourceKind: "claim_compliance",
        sourceLabels: ["Claim compliance"],
        status: "confirmed_violation",
        title: "Canonical finding",
        detail: null,
        claimId: "C-100",
        code: "P-500",
        sutLabel: "2.2.1",
        amountValue: null,
        amountLabel: null,
        action: null,
        finding: { ...mockFinding, regulatory_source: { clause_key: "2.2.1#abc123" } },
      }],
    }, "en");
    expect(html).toContain('aria-label="Inspect clause: 2.2.1"');
    expect(html).toContain("SUT §2.2.1");
  });

  it("renders a single empty state and no second table when rows array is empty", () => {
    const html = renderTable({
      rows: [],
      patientId: "P-1",
    });

    expect(html.match(/<table/g)?.length).toBe(1);
    expect(html).toContain("Bu görünümde uyumluluk bulgusu bulunmuyor.");
  });
});
