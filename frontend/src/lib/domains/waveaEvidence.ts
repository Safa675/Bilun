/** Wave A display-only evidence. Monetary values never feed recovery totals. */
export interface WaveAEvidenceRow {
  evidence_id: string;
  source_evidence_id: string;
  patient_id: string;
  claim_id: string | null;
  rule_id: string;
  line_kind: string;
  line_id: string | null;
  source_engine: string;
  evaluation_status: string;
  reason: string | null;
  source_status: string;
  regulatory_source: { clause_key?: string | null; clause_id?: string | null } | null;
  money_semantics: string;
  financial_kind?: "risk" | "uplift";
  confirmed_amount_try?: number | null;
  amount_status?: string;
  currency?: "TRY";
  headline_relation?: string;
}

export interface WaveAEvidenceBlock {
  available: boolean;
  unavailable_reason: string | null;
  total_rows: number | null;
  rows: WaveAEvidenceRow[];
  has_more: boolean;
}

export interface WaveAStatusCounts {
  evaluated: number;
  missing_inputs: number;
  unavailable: number;
}

export interface WaveACoverage {
  schema_version: string;
  available: boolean;
  unavailable_reason: string | null;
  tracked_rule_count: number;
  evaluation_count: number;
  by_group: Record<string, WaveAStatusCounts>;
}

export interface WaveAEvidencePage {
  available: boolean;
  unavailable_reason: string | null;
  patient_id?: string;
  kind?: "evaluations" | "reviews" | "financial_rows";
  rows: WaveAEvidenceRow[];
  pagination: {
    total_matching: number | null;
    limit: number;
    offset: number;
    has_more: boolean | null;
  };
}

export interface WaveACohortEvidencePage extends Omit<WaveAEvidencePage, "patient_id"> {
  kind?: "reviews" | "financial_rows";
  counts: { matching_rows: number } | null;
}

export interface WaveAEvidenceIndexPage {
  available: boolean;
  unavailable_reason: string | null;
  counts: {
    by_group: Record<string, WaveAStatusCounts>;
    evaluation_count: number;
    review_count: number;
    financial_count: number;
  } | null;
  rows: Array<{
    patient_id: string;
    available: boolean;
    unavailable_reason: string | null;
    counts: unknown;
  }>;
  pagination: {
    total_matching: number | null;
    limit: number;
    offset: number;
    has_more: boolean | null;
  };
}
