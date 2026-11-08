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

  describe("drug lines without a price", () => {
    const drug = (overrides: Partial<PatientClaimDetail["drugs"][number]> = {}): PatientClaimDetail["drugs"][number] => ({
      drug_claim_line_id: "DRG-1",
      prescription_id: "RX-1",
      drug_claim_date: "2024-01-15",
      drug_name: "Metformin 1000 mg",
      drug_code: "D-1",
      barkod: "8699999999999",
      equivalence_group: "EQ-1",
      quantity: 2,
      unit_price_try: 0,
      billed_amount_try: 0,
      expected_payable_try: 0,
      discount_tier_expected: 0,
      ...overrides,
    });
    const claimWith = (drugs: PatientClaimDetail["drugs"]): PatientClaimDetail => ({ ...baseClaim, drugs });

    it.each([
      ["tr", "fiyat yok"],
      ["en", "no price"],
    ] as const)("shows the gap instead of 0.00 when unit price, billed and expected are all zero (%s)", (locale, label) => {
      const html = renderToStaticMarkupWithLocale(<OriginalBillView claim={claimWith([drug()])} />, locale);
      const row = html.match(/<tr[^>]*>(?:(?!<\/tr>)[\s\S])*Metformin(?:(?!<\/tr>)[\s\S])*<\/tr>/)?.[0] ?? "";
      expect(row).not.toBe("");
      expect(row.match(new RegExp(label, "g"))).toHaveLength(2);
      expect(row).not.toContain("0.00 TRY");
    });

    it("keeps every amount of a drug line that has any price figure", () => {
      for (const priced of [
        drug({ unit_price_try: 12.5 }),
        drug({ billed_amount_try: 25 }),
        drug({ expected_payable_try: 20 }),
      ]) {
        const html = renderToStaticMarkupWithLocale(<OriginalBillView claim={claimWith([priced])} />, "en");
        expect(html).not.toContain("no price");
      }
      const ghost = renderToStaticMarkupWithLocale(
        <OriginalBillView claim={claimWith([drug({ expected_payable_try: 20 })])} />, "en",
      );
      expect(ghost).toContain("0.00 TRY");
      expect(ghost).toContain("20.00 TRY");
    });

    it("leaves zero amounts on procedures untouched and the subtotals as numbers", () => {
      const zeroProcedure = { ...baseClaim.procedures[0], procedure_line_id: "PRC-0", unit_price_try: 0, billed_amount_try: 0, expected_payable_try: 0 };
      const html = renderToStaticMarkupWithLocale(
        <OriginalBillView claim={{ ...baseClaim, procedures: [zeroProcedure], drugs: [drug()] }} />, "en",
      );
      expect(html).toContain("0.00 TRY");
      expect(html.match(/no price/g)).toHaveLength(2);
      expect(html).toContain("Drugs subtotal");
    });
  });

  it("shows claim header totals in the grand total block", () => {
    const html = renderToStaticMarkupWithLocale(<OriginalBillView claim={baseClaim} />);

    expect(html).toContain(fmtTRY2Fixture(baseClaim.expected_total_billed_try));
    expect(html).toContain(fmtTRY2Fixture(baseClaim.expected_total_payable_try));
  });
});
