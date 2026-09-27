import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCohortWaveAEvidence, getCohortWaveAIndex, getPatientWaveAEvidence } from "./waveaEvidence";

const calls = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("./request", () => ({
  requestJSON: calls.get,
  postJSON: calls.post,
}));

beforeEach(() => {
  calls.get.mockReset().mockResolvedValue({ available: true });
  calls.post.mockReset().mockResolvedValue({ available: true });
});

describe("Wave A evidence clients", () => {
  it("keeps patient detail kind and offset scoped to an encoded patient ID", async () => {
    await getPatientWaveAEvidence("P /1", { kind: "financial_rows", offset: 20 });
    expect(calls.get).toHaveBeenCalledWith(
      "/api/wavea-evidence/P%20%2F1?kind=financial_rows&offset=20&limit=20",
      undefined,
    );
  });

  it("requests one exact evidence identity for a patient deep link", async () => {
    await getPatientWaveAEvidence("P-1", {
      kind: "reviews",
      offset: 0,
      limit: 1,
      evidenceId: "wavea_review:claim_evaluation:one",
    });
    expect(calls.get).toHaveBeenCalledWith(
      "/api/wavea-evidence/P-1?kind=reviews&offset=0&limit=1&evidence_id=wavea_review%3Aclaim_evaluation%3Aone",
      undefined,
    );
  });

  it("uses a bounded GET for small filtered cohorts", async () => {
    await getCohortWaveAEvidence({ kind: "reviews", patientIds: ["P-1", "P-2"], limit: 20, offset: 40 });
    expect(calls.get).toHaveBeenCalledWith(
      "/api/wavea-evidence-rows?kind=reviews&limit=20&offset=40&patient_id=P-1&patient_id=P-2",
      undefined,
    );
    expect(calls.post).not.toHaveBeenCalled();
  });

  it("uses POST for large selected cohorts without silently dropping IDs", async () => {
    const ids = Array.from({ length: 350 }, (_, index) => `P-${index.toString().padStart(4, "0")}-long-selected-id`);
    await getCohortWaveAEvidence({ kind: "financial_rows", patientIds: ids, offset: 20 });
    expect(calls.post).toHaveBeenCalledWith(
      "/api/wavea-evidence-rows",
      expect.objectContaining({ kind: "financial_rows", patient_id: ids, offset: 20 }),
      undefined,
    );
    await getCohortWaveAIndex({ patientIds: ids });
    expect(calls.post).toHaveBeenLastCalledWith(
      "/api/wavea-evidence-index",
      expect.objectContaining({ patient_id: ids, limit: 20 }),
      undefined,
    );
  });
});
