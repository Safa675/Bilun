import { describe, expect, it, vi } from "vitest";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { WaveAEvidenceBlock, WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";
import { PatientWaveAEvidenceSection, WaveACoverageSummary } from "./WaveAEvidenceSection";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const row: WaveAEvidenceRow = {
  evidence_id: "wavea_financial:claim_evaluation:source-1",
  source_evidence_id: "claim_evaluation:source-1",
  patient_id: "P-1",
  claim_id: "C-1",
  rule_id: "yatak_icu_overlap_510010",
  line_kind: "procedure",
  line_id: "L-1",
  source_engine: "yatak_icu_overlap",
  evaluation_status: "evaluated",
  reason: "Review the original bed charge",
  source_status: "structured_locator",
  regulatory_source: { clause_key: "2.4.2#abc123" },
  money_semantics: "amount_unavailable",
  financial_kind: "risk",
  confirmed_amount_try: null,
  amount_status: "unavailable",
  currency: "TRY",
  headline_relation: "separate_yatak_reconciliation",
};

function render(block: WaveAEvidenceBlock) {
  return renderToStaticMarkupWithLocale(
    <WorkspaceProvider>
      <PatientWaveAEvidenceSection patientId="P-1" kind="financial_rows" block={block} />
    </WorkspaceProvider>,
    "en",
  );
}

describe("Wave A patient evidence", () => {
  it("shows a sourced, distinct financial candidate without inventing an amount or adding a headline", () => {
    const html = render({
      available: true,
      unavailable_reason: null,
      total_rows: 2,
      rows: [row],
      has_more: true,
    });
    expect(html).toContain("Separate financial evidence");
    expect(html).toContain("Risk exposure");
    expect(html).toContain("Amount unverified");
    expect(html).toContain("Shown separately from the existing reconciliation");
    expect(html).toContain("2.4.2#abc123");
    expect(html).not.toContain("source=\"");
    expect(html).toContain("Show more (1 of 2)");
    expect(html).toContain('data-finding-id="wavea_financial:claim_evaluation:source-1"');
  });

  it("marks an exact patient deep link for post-mount navigation", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="financial_rows"
          block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [row], has_more: false }}
          selectedFindingId={row.evidence_id}
        />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain(`data-finding-id="${row.evidence_id}" data-selected="true"`);
  });

  it("shows information as review-only advisory outside violation and financial totals", () => {
    const advisory = {
      ...row,
      evidence_id: "wavea_advisory:claim_evaluation:source-1",
      advisory_kind: "information" as const,
      money_semantics: "unpriced_advisory",
      financial_kind: undefined,
      confirmed_amount_try: undefined,
    };
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="advisories"
          block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [advisory], has_more: false }}
          selectedFindingId={advisory.evidence_id}
        />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain("Informational and permission outcomes");
    expect(html).toContain("Information · review only");
    expect(html).toContain("excluded from violation and financial totals");
    expect(html).toContain('id="wavea-advisories"');
    expect(html).toContain('data-selected="true"');
    expect(html).not.toContain("Amount unverified");
  });

  it("shows broad authored locators as traceable references without implying verified applicability", () => {
    const advisory = {
      ...row,
      evidence_id: "wavea_advisory:claim_evaluation:source-1",
      advisory_kind: "information" as const,
      money_semantics: "unpriced_advisory",
      financial_kind: undefined,
      confirmed_amount_try: undefined,
      source_status: "authored_locator_unverified",
      regulatory_source: { source_locators: ["F21", "2.4.1.(1)"], fatura_inceleme_ref: "F21" },
    };
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="advisories"
          block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [advisory], has_more: false }}
        />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain("F21");
    expect(html).toContain("2.4.1.(1)");
    expect(html).toContain("Source locator; applicability unverified");
  });

  it("withholds an advisory whose kind or money semantics is malformed", () => {
    const advisory = {
      ...row,
      evidence_id: "wavea_advisory:claim_evaluation:source-1",
      money_semantics: "amount_unavailable",
    };
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="advisories"
          block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [advisory], has_more: false }}
        />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain("Wave A evidence is unavailable");
    expect(html).not.toContain("Permission · check conditions");
  });

  it("does not treat an old build with no advisory block as a clean advisory zero", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection patientId="P-1" kind="advisories" />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain("Wave A evidence is unavailable");
    expect(html).not.toContain("No observations in this category");
  });

  it("keeps old or draft evidence unavailable instead of presenting a clean zero", () => {
    const html = render({
      available: false,
      unavailable_reason: "wavea_capability_unavailable",
      total_rows: null,
      rows: [],
      has_more: false,
    });
    expect(html).toContain("Wave A evidence is unavailable");
    expect(html).not.toContain("No observations in this category");
    expect(html).not.toContain("<table");
  });

  it("hides a malformed preview whose ownership or total disagrees", () => {
    const html = render({
      available: true,
      unavailable_reason: null,
      total_rows: 0,
      rows: [{ ...row, patient_id: "P-2" }],
      has_more: false,
    });
    expect(html).toContain("Wave A evidence is unavailable");
    expect(html).not.toContain("Risk exposure");
  });

  it("summarizes exact evaluated/missing/unavailable statuses without listing every rule ID", () => {
    const html = renderToStaticMarkupWithLocale(
      <WaveACoverageSummary coverage={{
        schema_version: "wavea-evidence-v1",
        available: false,
        unavailable_reason: "claim_context_unavailable",
        tracked_rule_count: 528,
        evaluation_count: 3,
        by_group: {
          dental: { evaluated: 1, missing_inputs: 1, unavailable: 0 },
          payment: { evaluated: 0, missing_inputs: 0, unavailable: 1 },
        },
      }} />,
      "en",
    );
    expect(html).toContain("2 groups · 1 evaluated · 1 missing inputs · 1 unavailable");
    expect(html).toContain("Some claim inputs are unavailable");
    expect(html).toContain("View group status counts");
  });
});
