import { describe, expect, it } from "vitest";
import { clauseUtilizationTier } from "./clauseUtilization";
import type { RuleClause } from "@/lib/api/sut";

function clause(overrides: Partial<RuleClause>): RuleClause {
  return {
    clause_id: "C000001",
    section_id: null,
    section_title: null,
    section_path: null,
    chapter: null,
    clause_type: "fikra",
    text_tr: "x",
    annex_refs: [],
    procedure_codes: [],
    percentages: [],
    amendment_refs: [],
    deontic_modality: null,
    source_effective_date: null,
    coverage_status: "partial",
    primary_rule_id: "drug_indication_prose",
    primary_rule_category: null,
    matched_rule_ids: [],
    matched_rules: [],
    is_primary: true,
    match_score: 0,
    has_algorithmic_gap: true,
    has_rule_encoding: false,
    ...overrides,
  };
}

describe("clauseUtilizationTier", () => {
  it("returns encoded when has_rule_encoding", () => {
    expect(clauseUtilizationTier(clause({ has_rule_encoding: true }))).toBe("encoded");
  });

  it("returns referans for non_algorithmic", () => {
    expect(
      clauseUtilizationTier(
        clause({ coverage_status: "non_algorithmic", primary_rule_id: "definitions" }),
      ),
    ).toBe("referans");
  });

  it("returns motorBound for partial motor with gap", () => {
    expect(clauseUtilizationTier(clause({}))).toBe("motorBound");
  });

  it("returns referans when no motor and not encoded", () => {
    expect(
      clauseUtilizationTier(
        clause({
          primary_rule_id: null,
          coverage_status: "non_algorithmic",
          has_algorithmic_gap: false,
        }),
      ),
    ).toBe("referans");
  });
});
