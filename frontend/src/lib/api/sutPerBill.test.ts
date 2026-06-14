import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getBillBillingReport,
  getBillOptimization,
} from "./sut";

describe("per-bill SUT API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("getBillBillingReport calls the claim-scoped billing endpoint", async () => {
    const payload = {
      patient_id: "PAT-1",
      claim_id: "CLM-001",
      scope: "bill",
      total_recoverable_try: 1750,
      action_count: 3,
      priority: "high",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getBillBillingReport("PAT-1", "CLM-001");

    expect(result.claim_id).toBe("CLM-001");
    expect(result.scope).toBe("bill");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/billing-report/PAT-1/bills/CLM-001",
    );
  });

  it("getBillOptimization calls the claim-scoped optimization endpoint", async () => {
    const payload = {
      patient_id: "PAT-1",
      claim_id: "CLM-001",
      scope: "bill",
      n_diagnoses: 1,
      diagnoses: ["E11.9"],
      icd10_chapters: ["E"],
      copay_exemptions: { exempt: false },
      surcharge_exposure: { n_applicable: 0 },
      copay_rate_exposure: { n_applicable: 0 },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getBillOptimization("PAT-1", "CLM-001");

    expect(result.claim_id).toBe("CLM-001");
    expect(result.scope).toBe("bill");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/patient/PAT-1/bills/CLM-001/optimization",
    );
  });
});
