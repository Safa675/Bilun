import { describe, expect, it, vi } from "vitest";
import type { BillingStrategyRecommendation, CopayOptimization, DrugIndicationReview, MaterialPreCheck } from "@/lib/domains/sut";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRY2Fixture } from "@/test/fmtMoney";
import {
  BillingStrategySection,
  CopayOptimizationSection,
  DrugIndicationReviewSection,
  MaterialsPreCheckSection,
  OptionalOverrideSection,
} from "./SutBillingReportSections";

vi.mock("@/components/tabs/sut/shared", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/components/tabs/sut/shared")>(),
  fmtTRY2: (value: number) => `${value.toFixed(2)} TRY`,
  fmtTRY2OrUnavailable: (value: number | null | undefined) =>
    value == null ? "Unavailable" : `${value.toFixed(2)} TRY`,
}));

function tableRows(html: string): string[][] {
  return [...html.matchAll(/<tbody>([\s\S]*?)<\/tbody>/g)].flatMap((body) =>
    [...body[1].matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((row) =>
      [...row[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((cell) =>
        cell[1].replace(/<[^>]+>/g, ""),
      ),
    ),
  );
}

const copayBase: CopayOptimization = {
  exactness_status: "exact",
  is_exempt: false,
  exemption_disease: "",
  exemption_range: "",
  visit_copay_savings_try: 0,
  rx_copay_savings_try: 0,
  total_copay_savings_try: 0,
  rate_corrections: [],
};

const drugRepresentations: DrugIndicationReview = {
  exactness_status: "partial_exact",
  violation_count: 0,
  findings: [{ finding_id: "finding-first", drug_name: "STRUCTURED_MARKER", finding_kind: "indication_mismatch" }],
  violations: [{ drug_name: "LEGACY_MARKER", violation_kind: "missing_board_report" }],
  evaluations: [{ drug_name: "EVALUATION_MARKER", applicability_status: "not_in_encoded_corpus" }],
};

describe("billing presentation compatibility at the public sections", () => {
  it.each(["legacy", "claim"] as const)("uses the first non-insight %s row for headers while each mixed row keeps its own money shape", (firstShape) => {
    const legacy = { procedure: "LEGACY_ROW", gazette_rate: 71, correction_try: 4 };
    const claim = { code: "ZERO", name: "CLAIM_ROW", billed_try: 0, copay_component_try: 0 };
    const orderedRows = firstShape === "legacy" ? [legacy, claim] : [claim, legacy];
    const html = renderToStaticMarkupWithLocale(<CopayOptimizationSection copayData={{
      ...copayBase,
      rate_corrections: [{ detail: "INSIGHT_ONLY_MARKER" }, ...orderedRows],
    }} />);
    const header = html.match(/<thead>([\s\S]*?)<\/thead>/)?.[1] ?? "";
    expect([...header.matchAll(/<th(?:\s|>)/g)]).toHaveLength(firstShape === "legacy" ? 3 : 5);
    const rows = tableRows(html);
    expect(rows.map((row) => row[0])).toEqual(firstShape === "legacy"
      ? ["LEGACY_ROW", "CLAIM_ROW (ZERO)"] : ["CLAIM_ROW (ZERO)", "LEGACY_ROW"]);
    expect(rows.find((row) => row[0] === "LEGACY_ROW")).toEqual([
      "LEGACY_ROW", fmtTRY2Fixture(71), fmtTRY2Fixture(4),
    ]);
    expect(rows.find((row) => row[0] === "CLAIM_ROW (ZERO)")).toEqual([
      "CLAIM_ROW (ZERO)", fmtTRY2Fixture(0), "Unavailable", fmtTRY2Fixture(0), fmtTRY2Fixture(0),
    ]);
    expect(html.match(/INSIGHT_ONLY_MARKER/g)).toHaveLength(1);
  });

  it("preserves overlapping strategy rows and violation-first order while presenting a dedicated override separately", () => {
    const strategy: BillingStrategyRecommendation = {
      exactness_status: "exact",
      recommendations: [
        { claim_id: "CLAIM_NORMAL", recommendation: "package", recommendation_kind: "mandatory_compliance", savings_try: 0 },
        { claim_id: "CLAIM_OVERLAP", recommendation: "package", recommendation_kind: "mandatory_compliance", type: "compliance_violation", savings_try: null },
        { chapter: "HEURISTIC_MARKER", recommendation: "review_package_eligibility", savings_try: null },
        { claim_id: "CLAIM_OVERRIDE", recommendation: "itemized", recommendation_kind: "optional_override", savings_try: 1200 },
      ],
    };
    const strategyHtml = renderToStaticMarkupWithLocale(<BillingStrategySection strategyData={strategy} />);
    const rows = tableRows(strategyHtml);
    expect(rows.slice(0, 3).map((row) => row[1])).toEqual(["CLAIM_OVERLAP", "CLAIM_NORMAL", "CLAIM_OVERLAP"]);
    expect(rows[3][0]).toBe("HEURISTIC_MARKER");
    expect(rows[1][8]).toBe("Compliant");
    expect(rows[3][3]).toBe("Unavailable");
    expect(strategyHtml).not.toContain("CLAIM_OVERRIDE");
    const overrideHtml = renderToStaticMarkupWithLocale(<OptionalOverrideSection strategyData={strategy} />);
    expect(tableRows(overrideHtml).map((row) => row[0])).toEqual(["CLAIM_OVERRIDE"]);
    expect(overrideHtml).toContain(fmtTRY2Fixture(1200));
    expect(overrideHtml).not.toContain("CLAIM_OVERLAP");
  });

  it("prefers structured findings over both other representations and retains an explicit zero total", () => {
    const html = renderToStaticMarkupWithLocale(<DrugIndicationReviewSection reviewData={drugRepresentations} />);
    expect(html).toContain("STRUCTURED_MARKER");
    expect(html).not.toContain("LEGACY_MARKER");
    expect(html).not.toContain("EVALUATION_MARKER");
    expect(html.match(/<header[^>]*>([\s\S]*?)<\/header>/)?.[1]).toMatch(/>0<\/span>/);
  });

  it("prefers the legacy disclosure over evaluations when findings are empty", () => {
    const html = renderToStaticMarkupWithLocale(<DrugIndicationReviewSection reviewData={{ ...drugRepresentations, findings: [] }} />);
    expect(html).toMatch(/<details[^>]*>[\s\S]*LEGACY_MARKER[\s\S]*<\/details>/);
    expect(html).not.toContain("EVALUATION_MARKER");
    expect(html).not.toContain("data-finding-id");
  });

  it.each(["exact", "not_applicable", "partial_exact", undefined] as const)("keeps the existing empty drug shell behavior for %s", (exactness_status) => {
    const html = renderToStaticMarkupWithLocale(<DrugIndicationReviewSection reviewData={{
      exactness_status, violations: [], findings: [], evaluations: [], unavailable_reason: "EMPTY_PARTIAL_MARKER",
    }} />);
    if (exactness_status === "exact" || exactness_status === "not_applicable") {
      expect(html).toBe("");
    } else {
      expect(html).toContain('id="drug-indication"');
      expect(html).toContain("EMPTY_PARTIAL_MARKER");
      expect(html).not.toContain("<table");
      expect(html).not.toContain("<article");
    }
  });

  it("renders every material category together in its existing order, including partial ceiling context", () => {
    const materials: MaterialPreCheck = {
      exactness_status: "partial_exact",
      unavailable_reason: "MATERIAL_PARTIAL_MARKER",
      pre_auth_required: [{ sut_code: "M1", material_name: "PREAUTH_MARKER", price_try: 1, note: "" }],
      miat_interval_violations: [{ sut_code: "M2", material_name: "INTERVAL_MARKER", miat_period: "365", price_try: 2, savings_try: null, note: "" }],
      miat_restricted: [{ sut_code: "M3", material_name: "RESTRICTED_MARKER", miat_period: "365", price_try: 3, note: "" }],
      bundled_separate_billing: [{ sut_code: "M4", material_name: "BUNDLED_MARKER", price_try: 4, note: "" }],
      prose_bundling_violations: [{ material_name: "PROSE_MARKER", material_code: "M5", risk_amount: 5 }],
      specialty_prose_violations: [{ material_name: "SPECIALTY_MARKER", material_code: "M6", risk_amount: 6 }],
      kdv_price_reviews: [{ material_name: "KDV_MARKER", sut_code: "M7", billed_try: 7, gazette_ceiling_try: 0 }],
      gazette_ceiling_by_specialty: { CEILING_MARKER: 8 },
    };
    const html = renderToStaticMarkupWithLocale(<MaterialsPreCheckSection materialsData={materials} />);
    const markers = ["PREAUTH_MARKER", "INTERVAL_MARKER", "RESTRICTED_MARKER", "BUNDLED_MARKER", "PROSE_MARKER", "SPECIALTY_MARKER", "KDV_MARKER", "CEILING_MARKER"];
    let previous = -1;
    for (const marker of markers) {
      expect(html.split(marker)).toHaveLength(2);
      expect(html.indexOf(marker)).toBeGreaterThan(previous);
      previous = html.indexOf(marker);
    }
    expect(tableRows(html)).toHaveLength(7);
    expect(html).toContain('id="materials-pre-check"');
    expect(html).toContain("MATERIAL_PARTIAL_MARKER");
  });
});
