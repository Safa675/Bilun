import { describe, expect, it } from "vitest";
import { matchingBillReport } from "./scopedPatientReport";

describe("bill report identity", () => {
  const report = { patient_id: "P-1", claim_id: "C-1", scope: "bill" };

  it("withholds a previous bill during a switch or failed request", () => {
    expect(matchingBillReport(report, "P-1", "C-2")).toBeNull();
    expect(matchingBillReport(null, "P-1", "C-2")).toBeNull();
    expect(matchingBillReport(report, "P-1", "C-1")).toBe(report);
  });

  it("rejects another patient and unscoped reports", () => {
    expect(matchingBillReport(report, "P-2", "C-1")).toBeNull();
    expect(matchingBillReport({ ...report, scope: undefined }, "P-1", "C-1")).toBeNull();
  });
});
