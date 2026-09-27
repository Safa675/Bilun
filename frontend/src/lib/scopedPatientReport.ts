/** A selected bill may render only data explicitly bound to that bill. */
export function matchingBillReport<T extends {
  patient_id: string;
  claim_id?: string;
  scope?: string;
}>(report: T | null, patientId: string, claimId: string | null): T | null {
  return claimId && report?.patient_id === patientId &&
    report.claim_id === claimId && report.scope === "bill"
    ? report
    : null;
}
