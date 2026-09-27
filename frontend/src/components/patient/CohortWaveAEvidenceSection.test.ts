import { describe, expect, it } from "vitest";
import type { WaveACohortEvidencePage, WaveAEvidenceIndexPage } from "@/lib/domains/waveaEvidence";
import { validCohortEvidencePage } from "./CohortWaveAEvidenceSection";

const page: WaveACohortEvidencePage = {
  available: true,
  unavailable_reason: null,
  kind: "financial_rows",
  counts: { matching_rows: 1 },
  rows: [{
    evidence_id: "wavea_financial:claim_evaluation:one",
    source_evidence_id: "claim_evaluation:one",
    patient_id: "P-1",
    claim_id: "C-1",
    rule_id: "rule-1",
    line_kind: "claim",
    line_id: null,
    source_engine: "engine-1",
    evaluation_status: "evaluated",
    reason: null,
    source_status: "unverified",
    regulatory_source: null,
    money_semantics: "amount_unavailable",
    financial_kind: "risk",
    confirmed_amount_try: null,
  }],
  pagination: { total_matching: 1, limit: 20, offset: 0, has_more: false },
};

const index: WaveAEvidenceIndexPage = {
  available: true,
  unavailable_reason: null,
  counts: {
    by_group: { focused: { evaluated: 1, missing_inputs: 0, unavailable: 0 } },
    evaluation_count: 1,
    review_count: 0,
    advisory_count: 0,
    financial_count: 1,
  },
  rows: [],
  pagination: { total_matching: 1, limit: 1, offset: 0, has_more: false },
};

describe("cohort Wave A response integrity", () => {
  it("accepts a matching filtered row and exhaustive status summary", () => {
    expect(validCohortEvidencePage(page, "financial_rows", 0, ["P-1"], index, true)).toBe(true);
  });

  it("rejects a row outside the selected cohort or with a forged canonical ID", () => {
    expect(validCohortEvidencePage(page, "financial_rows", 0, ["P-2"], index, true)).toBe(false);
    expect(validCohortEvidencePage({
      ...page,
      rows: [{ ...page.rows[0], evidence_id: "wavea_review:claim_evaluation:one" }],
    }, "financial_rows", 0, ["P-1"], index, true)).toBe(false);
  });

  it("accepts only exact procedure-line billed charges, separate from risk", () => {
    const sourceRow = {
      ...page.rows[0],
      line_kind: "procedure",
      line_id: "L-1",
      observed_billed_amount_try: 175.25,
      observed_amount_basis: "procedure_claim_line.billed_amount_try" as const,
      observed_amount_unavailable_reason: null,
    };
    expect(validCohortEvidencePage({ ...page, rows: [sourceRow] }, "financial_rows", 0, ["P-1"], index, true)).toBe(true);
    expect(validCohortEvidencePage({ ...page, rows: [{ ...sourceRow, line_id: null }] }, "financial_rows", 0, ["P-1"], index, true)).toBe(false);
    expect(validCohortEvidencePage({ ...page, rows: [{ ...sourceRow, observed_billed_amount_try: -1 }] }, "financial_rows", 0, ["P-1"], index, true)).toBe(false);
    expect(validCohortEvidencePage({ ...page, rows: [{ ...sourceRow, observed_billed_amount_try: 175.255 }] }, "financial_rows", 0, ["P-1"], index, true)).toBe(false);
  });

  it("keeps informational advisories separate from review and financial counts", () => {
    const advisory: WaveACohortEvidencePage = {
      ...page,
      kind: "advisories",
      rows: [{
        ...page.rows[0],
        evidence_id: "wavea_advisory:claim_evaluation:one",
        advisory_kind: "information",
        money_semantics: "unpriced_advisory",
        financial_kind: undefined,
        confirmed_amount_try: undefined,
      }],
    };
    const advisoryIndex: WaveAEvidenceIndexPage = {
      ...index,
      counts: { ...index.counts!, advisory_count: 1, financial_count: 0 },
    };
    expect(validCohortEvidencePage(advisory, "advisories", 0, ["P-1"], advisoryIndex, true)).toBe(true);
    expect(validCohortEvidencePage(advisory, "advisories", 0, ["P-1"], index, true)).toBe(false);
    expect(validCohortEvidencePage({
      ...advisory,
      rows: [{ ...advisory.rows[0], advisory_kind: undefined }],
    }, "advisories", 0, ["P-1"], advisoryIndex, true)).toBe(false);
  });

  it("rejects a false clean zero or malformed cohort count", () => {
    expect(validCohortEvidencePage({
      ...page,
      rows: [],
      counts: { matching_rows: 0 },
      pagination: { ...page.pagination, total_matching: 0 },
    }, "financial_rows", 0, ["P-1"], index, true)).toBe(false);
    expect(validCohortEvidencePage({
      ...page,
      rows: [],
      pagination: { ...page.pagination, has_more: true },
    }, "financial_rows", 0, ["P-1"], index, true)).toBe(false);
    expect(validCohortEvidencePage(page, "financial_rows", 0, ["P-1"], {
      ...index,
      counts: { ...index.counts!, review_count: -1 },
    }, true)).toBe(false);
  });
});
