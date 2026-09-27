import { describe, expect, it } from "vitest";
import type { SutLegacyValidationResult, SutValidationResult } from "@/lib/api/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { ValidationResultPanel } from "./ClaimValidatorSection";

// Even an unexpected extra historical blob must not enter the result display.
const result: SutValidationResult & { legacy_result: SutLegacyValidationResult } = {
  contract_version: 2, request_id: "request:1", claim_id: "C1",
  validation_status: "partially_evaluated", is_valid: null,
  violations: [], advisories: [],
  material_applicability: [],
  coverage: { evaluation_count: 496, authored_rule_count: 496, unresolved_count: 496,
    disposition_counts: { missing_inputs: 496 }, scope: "submitted_request_facts_only" },
  provenance: {}, summary: "", validation_time_ms: 1,
  legacy_result: { claim_id: "C1", is_valid: false, total_claim_amount: 987654,
    total_savings_try: 123456, total_risk_try: 654321, n_bundling_violations: 1,
    n_exclusion_violations: 0, validation_time_ms: 1, summary: "legacy only",
    violations: [{ rule: "bundling", severity: "error", material_name: "Legacy false positive",
      message: "Legacy definitive statement", savings_try: 123456, risk_amount: 0 }],
    material_lines: [] },
};

function Panel({ data }: { data: SutValidationResult }) {
  return <ValidationResultPanel result={data} t={useT()} />;
}

describe("typed validator result", () => {
  it("keeps missing inputs incomplete and never renders legacy money or false findings", () => {
    const html = renderToStaticMarkupWithLocale(<Panel data={result} />);
    expect(html).toContain("Incomplete checks");
    expect(html).toContain("496");
    expect(html).not.toContain("Legacy false positive");
    expect(html).not.toContain("Legacy definitive statement");
    expect(html).not.toContain("123,456");
    expect(html).not.toContain("654,321");
    expect(html).not.toContain("Findings confirmed");
  });

  it("renders permissions and reviews separately without changing the finding count", () => {
    const data = { ...result, validation_status: "review_required" as const, advisories: [
      { evidence_id: "A1", rule: "payment_method_2_2", material_name: "Payment context",
        message: "Source instruction", disposition: "information_only", source_status: "reviewed" },
      { evidence_id: "A2", rule: "dental_2_4_1", material_name: "Composition review",
        message: "Evidence needed", disposition: "review_only", source_status: "unverified" },
    ] };
    const html = renderToStaticMarkupWithLocale(<Panel data={data} />);
    expect(html).toContain("Review required");
    expect(html).toContain("Information and review");
    expect(html).toContain("Payment context");
    expect(html).toContain("Composition review");
    expect(html).not.toContain("Confirmed finding");
  });

  it.each([
    ["bundling", "ek3b1_exception_setting_and_exact_line_proof_required", "EK-3B-1"],
    ["exclusion", "ek3b2_exception_applicability_and_exact_line_proof_required", "EK-3B-2"],
  ])("shows the real %s typed annex review reason in both languages", (rule, reason, annex) => {
    const data = { ...result, validation_status: "review_required" as const, advisories: [
      { evidence_id: `C1:${rule}`, rule, material_name: "Conditional material",
        message: "Historical rule observation requires source and input review.",
        disposition: "review_only", reason, source_status: "historical_match_unverified" },
    ] };
    const english = renderToStaticMarkupWithLocale(<Panel data={data} />, "en");
    const turkish = renderToStaticMarkupWithLocale(<Panel data={data} />, "tr");
    expect(english).toContain("Conditional material");
    expect(english).toContain("Applicability unconfirmed");
    expect(english).toContain(annex);
    expect(english).toContain("Review required");
    expect(turkish).toContain("Uygulanabilirlik doğrulanmadı");
    expect(turkish).toContain(annex);
    for (const html of [english, turkish]) {
      expect(html).not.toContain("Legacy false positive");
      expect(html).not.toContain("123,456");
      expect(html).not.toContain("Confirmed finding");
    }
  });

  it("uses only the typed finding list for confirmed findings", () => {
    const data = { ...result, validation_status: "violations_found" as const, is_valid: false,
      violations: [{ evidence_id: "F1", rule: "source-proven", material_name: "Exact line",
        message: "Proven adverse finding", disposition: "unpriced_compliance",
        source_status: "reviewed" }] };
    const html = renderToStaticMarkupWithLocale(<Panel data={data} />);
    expect(html).toContain("Findings confirmed");
    expect(html).toContain("Exact line");
    expect(html).not.toContain("Legacy false positive");
  });

  it("renders each corrected annex assessment without implying reimbursement", () => {
    const data = { ...result, material_applicability: [
      { material_index: 0, material_id: "request:1:material:0", material_name: "Cerrahi steril eldiven",
        material_code: null, ek3b1: { matched: false, source_reason: "surgical_sterile_glove_exception" },
        ek3b2: { matched: false, source_reason: null } },
      { material_index: 1, material_id: "request:1:material:1", material_name: "Viskosüplemantasyon ürünleri",
        material_code: null, ek3b1: { matched: false, source_reason: null },
        ek3b2: { matched: null, source_reason: "sut_annex_exception_applicability_required" } },
    ] };
    const english = renderToStaticMarkupWithLocale(<Panel data={data} />, "en");
    const turkish = renderToStaticMarkupWithLocale(<Panel data={data} />, "tr");
    expect(english).toContain("No applicable annex match");
    expect(english).toContain("Applicability needs review");
    expect(english).toContain("does not determine reimbursement");
    expect(turkish).toContain("Uygulanabilir ek liste eşleşmesi yok");
    expect(turkish).toContain("geri ödeme veya ödeme kararı değildir");
    for (const html of [english, turkish]) {
      expect(html).toContain("EK-3B-1");
      expect(html).toContain("EK-3B-2");
      expect(html).not.toContain("Legacy false positive");
      expect(html).not.toContain("123,456");
    }
  });

  it("keeps the validator usable if a rollback serves the prior v2 API shape", () => {
    const previous = { ...result } as Partial<SutValidationResult>;
    delete previous.material_applicability;
    const html = renderToStaticMarkupWithLocale(<Panel data={previous as SutValidationResult} />);
    expect(html).toContain("Incomplete checks");
    expect(html).not.toContain("Material annex assessment");
    expect(html).not.toContain("Legacy false positive");
  });
});
