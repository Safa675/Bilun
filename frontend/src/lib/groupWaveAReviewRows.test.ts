import { describe, expect, it } from "vitest";
import type { WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";
import { groupWaveAReviewRows } from "./groupWaveAReviewRows";

const first: WaveAEvidenceRow = {
  evidence_id: "evidence-1",
  source_evidence_id: "source-1",
  patient_id: "P-1",
  claim_id: "C-1",
  rule_id: "rule-1",
  line_kind: "claim",
  line_id: null,
  source_engine: "engine-1",
  evaluation_status: "evaluated",
  reason: "source applicability needs review",
  source_status: "authored_locator_unverified",
  regulatory_source: {
    clause_key: "2.1#abc",
    clause_id: "2.1",
    source_locators: ["SUT 2.1", "Appendix A"],
    fatura_inceleme_ref: "Fatura 4",
  },
  money_semantics: "unpriced",
};

function row(id: string, claimId: string | null, changes: Partial<WaveAEvidenceRow> = {}): WaveAEvidenceRow {
  return { ...first, evidence_id: id, source_evidence_id: `source-${id}`, claim_id: claimId, ...changes };
}

describe("groupWaveAReviewRows", () => {
  it("groups the same topic across loaded claims without dropping or rewriting any evidence", () => {
    const rows = [
      first,
      row("evidence-2", "C-2", {
        regulatory_source: {
          ...first.regulatory_source,
          source_locators: ["Appendix A", "SUT 2.1"],
        },
      }),
      row("evidence-3", "C-3"),
      row("evidence-4", "C-3", { line_id: "L-4" }),
    ];

    const groups = groupWaveAReviewRows(rows);

    expect(groups).toHaveLength(1);
    expect(groups[0].claimCount).toBe(3);
    expect(groups[0].rows).toEqual(rows);
    rows.forEach((original, index) => expect(groups[0].rows[index]).toBe(original));
    expect(groups[0].rows.map((item) => item.evidence_id)).toEqual([
      "evidence-1", "evidence-2", "evidence-3", "evidence-4",
    ]);
    expect(groupWaveAReviewRows([rows[2], rows[0]])[0].key).toBe(groups[0].key);
  });

  it("keeps different reason, source, engine, line kind, and outcome kind separate", () => {
    const variants = [
      first,
      row("reason", "C-2", { reason: "different reason" }),
      row("source-status", "C-2", { source_status: "unverified" }),
      row("source-engine", "C-2", { source_engine: "engine-2" }),
      row("line-kind", "C-2", { line_kind: "procedure" }),
      row("clause", "C-2", { regulatory_source: { ...first.regulatory_source, clause_key: "2.2#xyz" } }),
      row("clause-id", "C-2", { regulatory_source: { ...first.regulatory_source, clause_id: "2.2" } }),
      row("locator", "C-2", { regulatory_source: { ...first.regulatory_source, source_locators: ["SUT 2.1"] } }),
      row("fatura-ref", "C-2", { regulatory_source: { ...first.regulatory_source, fatura_inceleme_ref: "Fatura 5" } }),
      row("advisory-kind", "C-2", { advisory_kind: "permission" }),
      row("money-kind", "C-2", { money_semantics: "risk" }),
      row("status", "C-2", { evaluation_status: "unavailable" }),
    ];

    const groups = groupWaveAReviewRows(variants);

    expect(groups).toHaveLength(variants.length);
    expect(groups.map((group) => group.rows[0])).toEqual(variants);
    expect(new Set(groups.map((group) => group.key)).size).toBe(variants.length);
  });

  it("counts only distinct known claims in loaded rows and preserves first-seen topic order", () => {
    const otherTopic = row("other-1", null, { rule_id: "rule-2" });
    const repeatedTopic = row("other-2", "C-5", { rule_id: "rule-2" });
    const groups = groupWaveAReviewRows([
      otherTopic,
      first,
      repeatedTopic,
      row("same-claim", "C-1"),
    ]);

    expect(groups.map((group) => group.rows.map((item) => item.evidence_id))).toEqual([
      ["other-1", "other-2"],
      ["evidence-1", "same-claim"],
    ]);
    expect(groups.map((group) => group.claimCount)).toEqual([1, 1]);
    expect(groupWaveAReviewRows([])).toEqual([]);
  });
});
