import { postJSON, requestJSON } from "./request";
import type { WaveACohortEvidencePage, WaveAEvidenceIndexPage, WaveAEvidencePage } from "../domains/waveaEvidence";

const MAX_GET_QUERY_LENGTH = 6000;

function cohortQuery(
  params: {
    patientIds?: readonly string[];
    kind?: "reviews" | "advisories" | "financial_rows";
    ruleId?: string;
    claimId?: string;
    limit?: number;
    offset?: number;
  },
): URLSearchParams {
  const query = new URLSearchParams();
  if (params.kind) query.set("kind", params.kind);
  if (params.ruleId) query.set("rule_id", params.ruleId);
  if (params.claimId) query.set("claim_id", params.claimId);
  if (params.limit != null) query.set("limit", String(params.limit));
  if (params.offset != null) query.set("offset", String(params.offset));
  for (const patientId of params.patientIds ?? []) query.append("patient_id", patientId);
  return query;
}

export function getCohortWaveAEvidence(
  params: {
    patientIds?: readonly string[];
    kind: "reviews" | "advisories" | "financial_rows";
    ruleId?: string;
    claimId?: string;
    limit?: number;
    offset?: number;
  },
  options?: RequestInit,
): Promise<WaveACohortEvidencePage> {
  const query = cohortQuery(params).toString();
  if (query.length > MAX_GET_QUERY_LENGTH) {
    return postJSON<WaveACohortEvidencePage, Record<string, unknown>>("/api/wavea-evidence-rows", {
      kind: params.kind,
      patient_id: params.patientIds ?? [],
      rule_id: params.ruleId,
      claim_id: params.claimId,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0,
    }, options);
  }
  return requestJSON<WaveACohortEvidencePage>(`/api/wavea-evidence-rows?${query}`, options);
}

export function getCohortWaveAIndex(
  params: { patientIds?: readonly string[]; limit?: number; offset?: number },
  options?: RequestInit,
): Promise<WaveAEvidenceIndexPage> {
  const query = cohortQuery(params).toString();
  if (query.length > MAX_GET_QUERY_LENGTH) {
    return postJSON<WaveAEvidenceIndexPage, Record<string, unknown>>("/api/wavea-evidence-index", {
      patient_id: params.patientIds ?? [],
      limit: params.limit ?? 20,
      offset: params.offset ?? 0,
    }, options);
  }
  return requestJSON<WaveAEvidenceIndexPage>(`/api/wavea-evidence-index?${query}`, options);
}

export function getPatientWaveAEvidence(
  patientId: string,
  params: {
    kind: "reviews" | "advisories" | "financial_rows";
    offset: number;
    limit?: number;
    evidenceId?: string;
    billClaimId?: string | null;
  },
  options?: RequestInit,
): Promise<WaveAEvidencePage> {
  const query = new URLSearchParams({
    kind: params.kind,
    offset: String(params.offset),
    limit: String(params.limit ?? 20),
  });
  if (params.evidenceId) query.set("evidence_id", params.evidenceId);
  if (params.billClaimId) {
    query.set("scope", "bill");
    query.set("claim_id", params.billClaimId);
  }
  return requestJSON<WaveAEvidencePage>(
    `/api/wavea-evidence/${encodeURIComponent(patientId)}?${query}`,
    options,
  );
}
