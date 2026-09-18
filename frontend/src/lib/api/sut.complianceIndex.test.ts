import { afterEach, describe, expect, it, vi } from "vitest";

import { getComplianceIndex } from "./sut";

const responsePayload = {
  artifacts_available: true,
  n_patients: 0,
  n_findings: 0,
  n_patients_with_findings: 0,
  billed_at_risk_try: 0,
  by_surface: {},
  rows: [],
};

function mockFetch() {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(responsePayload), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getComplianceIndex", () => {
  it("keeps small filtered cohorts on the GET query path", async () => {
    const fetchMock = mockFetch();

    await getComplianceIndex({
      surface: "claim_compliance",
      patientId: ["P1", "P2"],
      limit: 100,
      offset: 100,
    });

    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/compliance-index?");
    expect(String(url)).toContain("surface=claim_compliance");
    expect(String(url)).toContain("patient_id=P1");
    expect(String(url)).toContain("patient_id=P2");
    expect(String(url)).toContain("limit=100");
    expect(String(url)).toContain("offset=100");
    expect(options?.method).toBeUndefined();
  });

  it("moves representative large cohorts to a JSON POST body", async () => {
    const fetchMock = mockFetch();
    const patientIds = Array.from({ length: 500 }, (_, i) => `P-${i.toString().padStart(6, "0")}`);

    await getComplianceIndex({
      surface: "claim_compliance",
      patientId: patientIds,
      limit: 100,
      offset: 200,
    });

    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("http://localhost:8000/api/compliance-index");
    expect(options?.method).toBe("POST");
    expect(JSON.parse(String(options?.body))).toEqual({
      surface: "claim_compliance",
      patient_id: patientIds,
      limit: 100,
      offset: 200,
    });
  });
});
