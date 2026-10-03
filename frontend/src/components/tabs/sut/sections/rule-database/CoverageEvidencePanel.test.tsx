import { describe, expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { CoverageEvidencePanel } from "./CoverageEvidencePanel";

describe("CoverageEvidencePanel", () => {
  it("shows unknown runtime counts independently of nonzero source and predicate counts", () => {
    const html = renderToStaticMarkupWithLocale(<CoverageEvidencePanel evidence={{
      schema_version: 1, available: true, source_represented_clause_count: 1144,
      executable_predicate_rule_count: 123, inputs_available_count: null, actually_evaluated_count: null,
    }} />, "en");
    expect(html).toContain("1,144");
    expect(html).toContain("123");
    expect(html.match(/Not measured/g)).toHaveLength(2);
    expect(html).toContain("lower bound");
    expect(html).toContain("not every clinical constraint");
  });

  it("does not treat measured zero as unknown", () => {
    const html = renderToStaticMarkupWithLocale(<CoverageEvidencePanel evidence={{
      schema_version: 1, available: true, source_represented_clause_count: 0,
      executable_predicate_rule_count: 0, inputs_available_count: 0, actually_evaluated_count: 0,
    }} />, "en");
    expect(html).not.toContain("Not measured");
  });

  it("fails closed for unavailable artifacts and localizes uncertainty", () => {
    const html = renderToStaticMarkupWithLocale(<CoverageEvidencePanel evidence={{
      schema_version: 1, available: false, source_represented_clause_count: 999,
    }} />, "tr");
    expect(html).not.toContain("999");
    expect(html.match(/Ölçülmedi/g)).toHaveLength(4);
  });
});
