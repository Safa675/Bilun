import { describe, expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import OriginalBillView from "./OriginalBillView";
import type { PatientClaimDetail } from "@/lib/domains/sut";

// No mock of the shared formatters: the quantity cell is checked as the user sees it.
type DrugLine = PatientClaimDetail["drugs"][number];

const drug = (id: string, name: string, quantity: number): DrugLine => ({
  drug_claim_line_id: id,
  prescription_id: "RX-1",
  drug_claim_date: "2024-01-15",
  drug_name: name,
  drug_code: `D-${id}`,
  barkod: "8699999999999",
  equivalence_group: "EQ-1",
  quantity,
  unit_price_try: 0,
  billed_amount_try: 0,
  expected_payable_try: 0,
  discount_tier_expected: 0,
});

// A split box (#302): half a box of PARTEMOL, PK-Merz's 3 bottles of a 2-bottle box, two whole boxes.
const claim: PatientClaimDetail = {
  claim_id: "F-PAT-302",
  patient_id: "PAT-302",
  episode_id: "B-PAT-302",
  claim_type: "inpatient",
  facility_tier: "3",
  provider_type: "hospital",
  department: "neurology",
  admission_date: "2024-01-14",
  discharge_date: "2024-01-16",
  claim_start_date: "2024-01-14",
  claim_end_date: "2024-01-16",
  primary_icd10: "G20",
  expected_total_billed_try: 1240,
  expected_total_payable_try: 992,
  procedures: [
    {
      procedure_line_id: "PRC-1",
      procedure_date: "2024-01-15",
      procedure_code: "510010",
      procedure_name: "Standard bed day",
      procedure_category: "yatak",
      quantity: 2,
      unit_price_try: 400,
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
      unit_price_try: 40,
      billed_amount_try: 40,
      expected_payable_try: 32,
      is_package_included: false,
    },
  ],
  materials: [
    {
      material_line_id: "MAT-1",
      material_date: "2024-01-15",
      material_code: "KS1001",
      material_name: "IV cannula",
      material_type: "consumable",
      specialty_category: "general",
      quantity: 4000,
      unit_price_try: 0.1,
      billed_amount_try: 400,
      expected_payable_try: 320,
      is_bundled: false,
      requires_pre_auth: false,
    },
  ],
  drugs: [
    drug("1", "PARTEMOL 500 MG", 0.5),
    drug("2", "PK-MERZ 100 MG", 1.5),
    drug("3", "METFORMIN 1000 MG", 2),
  ],
};

/** The text of the quantity cell (the fourth column) in the row that names the line. */
function quantityCell(html: string, name: string): string {
  const row = [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)]
    .map((match) => match[1])
    .find((body) => body.includes(name));
  expect(row, name).toBeDefined();
  const cells = [...(row ?? "").matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((match) =>
    match[1].replace(/<[^>]+>/g, ""),
  );
  expect(cells).toHaveLength(6);
  return cells[3];
}

describe("OriginalBillView quantity column", () => {
  it.each([
    { locale: "tr", half: "0,5", oneAndHalf: "1,5", two: "2", bedDays: "2", lab: "1", material: "4.000" },
    { locale: "en", half: "0.5", oneAndHalf: "1.5", two: "2", bedDays: "2", lab: "1", material: "4,000" },
  ] as const)("shows a decimal drug quantity with its decimals and a whole count as before ($locale)", (expected) => {
    const html = renderToStaticMarkupWithLocale(<OriginalBillView claim={claim} />, expected.locale);
    expect(quantityCell(html, "PARTEMOL 500 MG")).toBe(expected.half);
    expect(quantityCell(html, "PK-MERZ 100 MG")).toBe(expected.oneAndHalf);
    expect(quantityCell(html, "METFORMIN 1000 MG")).toBe(expected.two);
    expect(quantityCell(html, "Standard bed day")).toBe(expected.bedDays);
    expect(quantityCell(html, "CBC")).toBe(expected.lab);
    expect(quantityCell(html, "IV cannula")).toBe(expected.material);
  });
});
