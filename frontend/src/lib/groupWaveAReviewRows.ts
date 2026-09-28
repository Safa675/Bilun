import type { WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";

export interface WaveAReviewGroup {
  /** Stable for the review topic, regardless of input row order or pagination. */
  key: string;
  /** Loaded evidence rows in their original order; no evidence is discarded. */
  rows: WaveAEvidenceRow[];
  /** Distinct claim IDs among loaded rows only. */
  claimCount: number;
}

function sourceIdentity(row: WaveAEvidenceRow): readonly unknown[] {
  const source = row.regulatory_source;
  if (!source) return [null, null, [], null];

  const locators = Array.isArray(source.source_locators)
    ? [...new Set(source.source_locators
      .filter((locator): locator is string => typeof locator === "string")
      .map((locator) => locator.trim())
      .filter(Boolean))].sort()
    : [];

  return [
    source.clause_key?.trim() || null,
    source.clause_id?.trim() || null,
    locators,
    source.fatura_inceleme_ref?.trim() || null,
  ];
}

function reviewIdentity(row: WaveAEvidenceRow): string {
  return JSON.stringify([
    row.rule_id,
    row.reason,
    row.source_status,
    row.source_engine,
    row.line_kind,
    sourceIdentity(row),
    row.advisory_kind ?? null,
    row.financial_kind ?? null,
    row.money_semantics,
    row.evaluation_status,
  ]);
}

/** Groups only loaded presentation rows; never infers totals or changes evidence IDs. */
export function groupWaveAReviewRows(rows: WaveAEvidenceRow[]): WaveAReviewGroup[] {
  const byKey = new Map<string, { rows: WaveAEvidenceRow[]; claimIds: Set<string> }>();

  for (const row of rows) {
    const key = reviewIdentity(row);
    let group = byKey.get(key);
    if (!group) {
      group = { rows: [], claimIds: new Set<string>() };
      byKey.set(key, group);
    }
    group.rows.push(row);
    if (row.claim_id) group.claimIds.add(row.claim_id);
  }

  return [...byKey].map(([key, group]) => ({
    key,
    rows: group.rows,
    claimCount: group.claimIds.size,
  }));
}
