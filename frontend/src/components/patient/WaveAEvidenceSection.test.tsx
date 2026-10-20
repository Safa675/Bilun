import { describe, expect, it, vi } from "vitest";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { WaveAEvidenceBlock, WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";
import { PatientWaveAEvidenceSection, WaveACoverageSummary, WaveAEvidenceRowsTable, WaveAUnavailableNotice, matchesPatientEvidenceScope, waveABlockUnavailable } from "./WaveAEvidenceSection";

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
  observed_billed_amount_try: null,
  observed_amount_basis: null,
  observed_amount_unavailable_reason: "procedure_line_charge_invalid",
  currency: "TRY",
  headline_relation: "separate_yatak_reconciliation",
};
const advisoryBase = { ...row };
delete advisoryBase.observed_billed_amount_try;
delete advisoryBase.observed_amount_basis;
delete advisoryBase.observed_amount_unavailable_reason;

function reviewRow(claimId: string, suffix: string): WaveAEvidenceRow {
  const source_evidence_id = `claim_evaluation:review-${suffix}`;
  return {
    evidence_id: `wavea_review:${source_evidence_id}`,
    source_evidence_id,
    patient_id: "P-1",
    claim_id: claimId,
    rule_id: "1.9.1.(1).extra_fee_permissible_scope",
    line_kind: "claim",
    line_id: null,
    source_engine: "extra_fee_scope",
    evaluation_status: "evaluated",
    reason: "authored_source_pending_independent_review",
    source_status: "structured_locator",
    regulatory_source: { clause_key: "1.9.1.(1)#43cd69a1" },
    money_semantics: "unpriced_review",
  };
}

function render(block: WaveAEvidenceBlock) {
  return renderToStaticMarkupWithLocale(
    <WorkspaceProvider>
      <PatientWaveAEvidenceSection patientId="P-1" kind="financial_rows" block={block} />
    </WorkspaceProvider>,
    "en",
  );
}

describe("Wave A patient evidence", () => {
  it("keeps review counts and unavailable/not-evaluated markers visible while collapsed", () => {
    const reviews = [
      { ...reviewRow("C-1", "1"), evaluation_status: "missing_inputs" },
      { ...reviewRow("C-2", "2"), evaluation_status: "unavailable" },
    ];
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection patientId="P-1" kind="reviews" block={{ available: true, unavailable_reason: null, total_rows: 2, rows: reviews, has_more: false }} />
      </WorkspaceProvider>,
      "en",
    );
    const summary = html.match(/<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(summary).toContain("2 review records in total");
    expect(summary).toContain("Not evaluated");
    expect(summary).toContain("Unavailable");
    expect(html).not.toMatch(/<details[^>]* open=/);
  });

  it("opens a review section for an anchor-only deep link", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection patientId="P-1" kind="reviews" selectedSection="wavea-reviews" block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [reviewRow("C-1", "1")], has_more: false }} />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toMatch(/<details open=""/);
  });

  it("keeps the information count and partial marker in its collapsed header", () => {
    const advisory = {
      ...advisoryBase,
      evidence_id: "wavea_advisory:claim_evaluation:source-1",
      advisory_kind: "information" as const,
      money_semantics: "unpriced_advisory",
      evaluation_status: "partial",
      financial_kind: undefined,
      confirmed_amount_try: undefined,
    };
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection patientId="P-1" kind="advisories" block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [advisory], has_more: false }} />
      </WorkspaceProvider>,
      "en",
    );
    const summary = html.match(/<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(summary).toContain("1 information or conditional permission records");
    expect(summary).toContain("Partial");
    expect(html).not.toMatch(/<details[^>]* open=/);
  });
  it("groups loaded review evidence by topic and keeps each exact claim link and identity", () => {
    const reviews = [reviewRow("C-1", "1"), reviewRow("C-2", "2"), reviewRow("C-3", "3")];
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="reviews"
          block={{ available: true, unavailable_reason: null, total_rows: 5, rows: reviews, has_more: true }}
        />
      </WorkspaceProvider>,
      "tr",
    );

    expect(html).toContain("Toplam 5 inceleme kaydı");
    expect(html).toContain("Gösterilen kayıtlarda 3 fatura");
    expect(html.match(/Ek ücret kapsamı/g)).toHaveLength(1);
    expect(html).toContain("henüz ihlal veya finansal kazanç olarak sayılmadı");
    expect(html).not.toContain("<table");
    for (const review of reviews) {
      expect(html).toContain(`data-finding-id="${review.evidence_id}"`);
      expect(html).toContain(review.claim_id);
      expect(html).toContain(encodeURIComponent(review.evidence_id));
      expect(html).toContain(`claim=${review.claim_id}`);
    }
    expect(html).toContain("Daha fazla göster (3/5)");
  });

  it("opens the selected review group and never presents a source-free review as verified", () => {
    const selected = reviewRow("C-2", "2");
    const noSource = { ...selected, regulatory_source: null, source_status: "unverified" };
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="reviews"
          block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [noSource], has_more: false }}
          selectedFindingId={selected.evidence_id}
          selectedClaimId="C-2"
        />
      </WorkspaceProvider>,
      "tr",
    );

    expect(html).toContain('open=""');
    expect(html).toContain(`data-finding-id="${selected.evidence_id}" data-selected="true"`);
    expect(html.match(/Bu kayıtta doğrulanmış kaynak yok/g)).toHaveLength(1);
    expect(html).toContain("claim=C-2");
  });

  it("rejects a patient response when a selected bill is expected and vice versa", () => {
    const page = {
      available: true,
      unavailable_reason: null,
      patient_id: "P-1",
      kind: "financial_rows" as const,
      rows: [row],
      pagination: { total_matching: 1, limit: 20, offset: 0, has_more: false },
    };
    expect(matchesPatientEvidenceScope({ ...page, scope: "patient", claim_id: null }, null)).toBe(true);
    expect(matchesPatientEvidenceScope({ ...page, scope: "bill", claim_id: "C-1" }, "C-1")).toBe(true);
    expect(matchesPatientEvidenceScope({ ...page, scope: "patient", claim_id: null }, "C-1")).toBe(false);
    expect(matchesPatientEvidenceScope({ ...page, scope: "bill", claim_id: "C-2" }, "C-1")).toBe(false);
    expect(matchesPatientEvidenceScope(page, "C-1")).toBe(false);
  });

  it("shows an exact billed charge separately from unverified risk", () => {
    const html = render({
      available: true,
      unavailable_reason: null,
      total_rows: 1,
      rows: [{
        ...row,
        observed_billed_amount_try: 175.25,
        observed_amount_basis: "procedure_claim_line.billed_amount_try",
        observed_amount_unavailable_reason: null,
      }],
      has_more: false,
    });
    expect(html).toContain("Amount unverified");
    expect(html).toContain("Observed billed charge");
    expect(html).toContain("Source: exact procedure claim line; separate from risk or uplift");
    expect(html).toContain("175.25 TRY");
  });

  it("withholds a billed charge without exact procedure-line provenance", () => {
    const html = render({
      available: true,
      unavailable_reason: null,
      total_rows: 1,
      rows: [{ ...row, observed_billed_amount_try: 175.25 }],
      has_more: false,
    });
    expect(html).toContain("unavailable");
    expect(html).not.toContain("Observed billed charge");
    const fractionalCent = render({
      available: true,
      unavailable_reason: null,
      total_rows: 1,
      rows: [{
        ...row,
        observed_billed_amount_try: 175.255,
        observed_amount_basis: "procedure_claim_line.billed_amount_try",
        observed_amount_unavailable_reason: null,
      }],
      has_more: false,
    });
    expect(fractionalCent).not.toContain("Observed billed charge");
  });

  it("explains why a procedure charge cannot be verified, apart from risk", () => {
    const html = render({ available: true, unavailable_reason: null, total_rows: 1, rows: [row], has_more: false });
    expect(html).toContain("Observed billed charge");
    expect(html).toContain("Procedure line charge is missing or invalid");
    expect(html).toContain("Risk exposure");
  });

  it("withholds malformed observed-charge states and omits line charges for claim reviews", () => {
    const malformed = render({
      available: true, unavailable_reason: null, total_rows: 1,
      rows: [{ ...row, observed_amount_unavailable_reason: null }], has_more: false,
    });
    expect(malformed).toContain("Wave A evidence is unavailable");

    const claimReview: WaveAEvidenceRow = { ...advisoryBase,
      evidence_id: row.evidence_id, line_kind: "claim", line_id: null,
      financial_kind: "uplift", money_semantics: "amount_unavailable",
    };
    const claimHtml = render({
      available: true, unavailable_reason: null, total_rows: 1,
      rows: [claimReview], has_more: false,
    });
    expect(claimHtml).toContain("Recoverable uplift candidate");
    expect(claimHtml).not.toContain("Observed billed charge");
  });

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
    expect(html).toContain("section=wavea-financial");
    expect(html).not.toContain("claim=C-1");
  });

  it("keeps a selected bill's evidence deep link in that bill's scope", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection
          patientId="P-1"
          kind="financial_rows"
          block={{ available: true, unavailable_reason: null, total_rows: 1, rows: [row], has_more: false }}
          selectedClaimId="C-1"
        />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain("claim=C-1");
    expect(html).toContain("section=wavea-financial");
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
      ...advisoryBase,
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
    expect(html).toContain("Information and conditional permissions");
    expect(html).toContain("Information record");
    expect(html).toContain("excluded from violation and financial totals");
    expect(html).toContain('id="wavea-advisories"');
    expect(html).toContain('data-selected="true"');
    expect(html).not.toContain("Amount unverified");
  });

  it("shows broad authored locators as traceable references without implying verified applicability", () => {
    const advisory = {
      ...advisoryBase,
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
    expect(html).toContain("Source locator recorded; applicability to this claim unverified");
  });

  it("withholds an advisory whose kind or money semantics is malformed", () => {
    const advisory = {
      ...advisoryBase,
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
    expect(html).not.toContain("Conditional permission");
  });

  it("does not treat an old build with no advisory block as a clean advisory zero", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <PatientWaveAEvidenceSection patientId="P-1" kind="advisories" />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain("Information and conditional permissions");
    expect(html).toContain("Wave A evidence is unavailable");
    expect(html).not.toContain("No observations in this category");
    const summary = html.match(/<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(summary).toContain("Count unavailable");
    expect(summary).toContain("Wave A evidence is unavailable");
    expect(summary).not.toContain("0 information");
  });

  it("shows an absent source once in the shared cohort table", () => {
    const review = { ...reviewRow("C-1", "no-source"), regulatory_source: null, source_status: "unverified" };
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <WaveAEvidenceRowsTable rows={[review]} kind="reviews" />
      </WorkspaceProvider>,
      "tr",
    );
    expect(html.match(/Bu kayıtta doğrulanmış kaynak yok/g)).toHaveLength(1);
    expect(html).toContain("claim=C-1");
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

  it.each([
    ["tr", true, "Genişletilmiş kanıt katmanı bu derlemede etkin değil; bu katmanın kayıtları ve kapsam sayıları gösterilemiyor. Bu, sıfır bulgu olduğu anlamına gelmez."],
    ["en", true, "The extended evidence layer is not active in this build, so its records and coverage counts cannot be shown. This does not mean zero findings."],
    ["tr", false, "Wave A kanıtları bu derleme veya fatura için kullanılamıyor. Bu, sıfır bulgu olduğu anlamına gelmez."],
    ["en", false, "Wave A evidence is unavailable for this build or claim. No zero finding count is implied."],
  ] as const)("shows one notice that never reads as a zero (%s, layer off: %s)", (locale, layerOff, sentence) => {
    const html = renderToStaticMarkupWithLocale(<WaveAUnavailableNotice layerOff={layerOff} />, locale);
    expect(html).toContain(sentence);
    expect(html).toContain('id="wavea-unavailable"');
    expect(html).not.toMatch(/\b0\b/);
  });

  it("treats absent, unavailable and malformed blocks as unavailable and a valid empty block as available", () => {
    const unavailable = { available: false, unavailable_reason: "wavea_capability_unavailable", total_rows: null, rows: [], has_more: false };
    expect(waveABlockUnavailable(undefined, "P-1", "reviews")).toBe(true);
    expect(waveABlockUnavailable(unavailable, "P-1", "reviews")).toBe(true);
    expect(waveABlockUnavailable({ available: true, unavailable_reason: null, total_rows: 0, rows: [{ ...row, patient_id: "P-2" }], has_more: false }, "P-1", "financial_rows")).toBe(true);
    expect(waveABlockUnavailable({ available: true, unavailable_reason: null, total_rows: 0, rows: [], has_more: false }, "P-1", "reviews")).toBe(false);
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
    expect(html).toContain("2 rule groups · 1 evaluated · 1 missing inputs · 1 unavailable");
    expect(html).toContain("Some claim inputs or evaluation results are unavailable");
    expect(html).toContain("Coverage and missing data");
    const summary = html.match(/<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(summary).toContain("3 evaluations");
    expect(summary).toContain("1 missing inputs · 1 unavailable");
    expect(summary).toContain("Evaluation is partial");
    expect(html).not.toMatch(/<details[^>]* open=/);
  });
});
