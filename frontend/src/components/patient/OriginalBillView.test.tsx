import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRY2Fixture } from "@/test/fmtMoney";

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtNum: (value: number) => String(value),
  fmtTRY2: (value: number) => `${value.toFixed(2)} TRY`,
}));

import OriginalBillView from "./OriginalBillView";
import type { PatientClaimDetail } from "@/lib/domains/sut";

const baseClaim: PatientClaimDetail = {
  claim_id: "F-PAT-001",
  patient_id: "PAT-001",
  episode_id: "B-PAT-001",
  claim_type: "outpatient",
  facility_tier: "1",
  provider_type: "physician",
  department: "cardiology",
  admission_date: null,
  discharge_date: null,
  claim_start_date: "2024-01-15",
  claim_end_date: "2024-01-15",
  primary_icd10: "I10",
  package_candidate: false,
  expected_total_billed_try: 1100,
  expected_total_payable_try: 880,
  procedures: [
    {
      procedure_line_id: "PRC-1",
      procedure_date: "2024-01-15",
      procedure_code: "99213",
      procedure_name: "Office visit",
      procedure_category: "visit",
      quantity: 1,
      unit_price_try: 800,
      billed_amount_try: 800,
      expected_payable_try: 640,
      is_package_included: false,
    },
    {
      procedure_line_id: "LAB-1",
      procedure_date: "2024-01-15",
      procedure_code: "L108600",
      procedure_name: "CBC",
      procedure_category: "laboratuvar",
      quantity: 1,
      unit_price_try: 100,
      billed_amount_try: 100,
      expected_payable_try: 80,
      is_package_included: false,
    },
  ],
  materials: [],
  drugs: [],
};

describe("OriginalBillView", () => {
  it("splits procedures and labs into separate invoice sections", () => {
    const html = renderToStaticMarkupWithLocale(<OriginalBillView claim={baseClaim} />);

    expect(html).toContain("Original invoice");
    expect(html).toContain("Office visit");
    expect(html).toContain("CBC");
    expect(html).toContain("Laboratory");
    expect(html).toContain(fmtTRY2Fixture(baseClaim.procedures[0].billed_amount_try));
    expect(html).toContain(fmtTRY2Fixture(baseClaim.procedures[1].billed_amount_try));
  });

  it("shows claim header totals in the grand total block", () => {
    const html = renderToStaticMarkupWithLocale(<OriginalBillView claim={baseClaim} />);

    expect(html).toContain(fmtTRY2Fixture(baseClaim.expected_total_billed_try));
    expect(html).toContain(fmtTRY2Fixture(baseClaim.expected_total_payable_try));
  });
});
