import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { RuleClause } from "@/lib/api/sut";

// Mock the i18n translation hook to return the key (predictable assertions).
vi.mock("@/lib/i18n/useTranslations", () => ({
  useT: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      const entries = Object.entries(params).map(([k, v]) => `${k}=${v}`);
      return `${key}{${entries.join(",")}}`;
    }
    return key;
  },
}));

// Mock theme to avoid CSS variable resolution in SSR.
vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

// Mock the deontic label hook.
vi.mock("../shared", () => ({
  useDeonticLabel: (modality: string | null) => modality || "",
  fmtNum: (n: number) => String(n),
}));

// Mock the SUT API hook to avoid network calls.
vi.mock("../useSutApi", () => ({
  useSutApi: () => ({ data: null, loading: false, error: null }),
}));

// Import after mocks are set up.
import { ClauseCard } from "./RuleDatabaseSection";

const mockClause: RuleClause = {
  clause_key: "2.2.1.(1)#c002684a",
  paragraph_index: 2684,
  section_id: "2.2.1",
  section_title: "Ödeme yöntemi",
  section_path: "2.2.1",
  chapter: "UCUNCU_BOLUM",
  clause_type: "fikra",
  clause_number: 1,
  clause_letter: null,
  clause_coordinate: "2.2.1.(1)",
  is_heading: false,
  text_tr: "Üçüncü basamak eğitim araştırma hastanelerinde paket fatura uygulanır.",
  annex_refs: ["EK-2C"],
  procedure_codes: ["609300"],
  percentages: [],
  amendment_refs: [],
  deontic_modality: "prohibition",
  source_effective_date: "2026-05-23",
  coverage_status: "implemented",
  primary_rule_id: "payment_method_2_2",
  primary_rule_category: "payment",
  matched_rule_ids: ["payment_method_2_2", "drg_package_adequacy", "copay_rate_ek2c1", "claim_validation", "billing_strategy"],
  matched_rules: [],
  is_primary: true,
  match_score: 100,
  has_algorithmic_gap: true,
  has_rule_encoding: true,
};

describe("ClauseCard", () => {
  it("renders clause_coordinate as primary identity without C* badge", () => {
    const html = renderToStaticMarkupWithLocale(<ClauseCard clause={mockClause} />);
    expect(html).toContain("2.2.1.(1)");
    expect(html).not.toContain("C002684");
  });

  it("renders section label", () => {
    const html = renderToStaticMarkupWithLocale(<ClauseCard clause={mockClause} />);
    expect(html).toContain("2.2.1");
    expect(html).toContain("Ödeme yöntemi");
  });

  it("renders text_tr content", () => {
    const html = renderToStaticMarkupWithLocale(<ClauseCard clause={mockClause} />);
    expect(html).toContain("Üçüncü basamak eğitim araştırma hastanelerinde");
  });

  it("renders utilization tier chip instead of separate gap/encoded badges", () => {
    const html = renderToStaticMarkupWithLocale(<ClauseCard clause={mockClause} />);
    expect(html).toContain("sections.ruleDatabase.utilization.encoded");
    expect(html).not.toContain("sections.ruleDatabase.detail.gapBadge");
  });

  it("does not render gap/encoded badges when flags are false", () => {
    const html = renderToStaticMarkupWithLocale(
      <ClauseCard clause={{ ...mockClause, has_algorithmic_gap: false, has_rule_encoding: null }} />,
    );
    expect(html).not.toContain("sections.ruleDatabase.detail.gapBadge");
    expect(html).not.toContain("sections.ruleDatabase.detail.encodedBadge");
  });

  it("renders primary motor label", () => {
    const html = renderToStaticMarkupWithLocale(<ClauseCard clause={mockClause} />);
    expect(html).toContain("payment_method_2_2");
  });

  it("renders matched_rule_ids with +N overflow when more than 3", () => {
    const html = renderToStaticMarkupWithLocale(<ClauseCard clause={mockClause} />);
    // First 3 shown directly
    expect(html).toContain("payment_method_2_2");
    expect(html).toContain("drg_package_adequacy");
    expect(html).toContain("copay_rate_ek2c1");
    // Overflow count (5 - 3 = 2)
    expect(html).toContain("count=2");
  });
});
