import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { OpportunityCell, resolveOpportunityTry } from "./PatientInvoiceTable";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

describe("resolveOpportunityTry", () => {
  it("prefers the reported total_opportunity_try", () => {
    expect(
      resolveOpportunityTry({
        total_recoverable_try: 100,
        exemption_gap_try: 20,
        total_opportunity_try: 120,
      }),
    ).toEqual({ amount: 120, missing: null });
  });

  it("adds recoverable and exemption gap when both are present", () => {
    expect(
      resolveOpportunityTry({ total_recoverable_try: 100, exemption_gap_try: 20 }),
    ).toEqual({ amount: 120, missing: null });
    expect(
      resolveOpportunityTry({ total_recoverable_try: 0, exemption_gap_try: 0 }),
    ).toEqual({ amount: 0, missing: null });
  });

  it("flags the missing component instead of counting it as zero", () => {
    expect(resolveOpportunityTry({ total_recoverable_try: 100 })).toEqual({
      amount: 100,
      missing: "gap",
    });
    expect(
      resolveOpportunityTry({ total_recoverable_try: 100, exemption_gap_try: null }),
    ).toEqual({ amount: 100, missing: "gap" });
    expect(resolveOpportunityTry({ exemption_gap_try: 20 })).toEqual({
      amount: 20,
      missing: "recoverable",
    });
  });

  it("returns no amount when nothing is known", () => {
    expect(resolveOpportunityTry({})).toEqual({ amount: null, missing: null });
    expect(
      resolveOpportunityTry({ total_recoverable_try: null, exemption_gap_try: null }),
    ).toEqual({ amount: null, missing: null });
    expect(resolveOpportunityTry(undefined)).toEqual({ amount: null, missing: null });
  });
});

describe("OpportunityCell", () => {
  const cell = (row: Parameters<typeof OpportunityCell>[0]["row"], locale: "en" | "tr" = "en") =>
    renderToStaticMarkupWithLocale(<OpportunityCell row={row} />, locale).replace(/<[^>]+>/g, "");

  it("shows the exact figure with no note when both components are present", () => {
    expect(
      cell({
        total_opportunity_try: 120,
        opportunity_missing: null,
        total_recoverable_try: 100,
        exemption_gap_try: 20,
      }),
    ).toBe("120.00 TRY");
  });

  it("keeps the exemption-gap-only note for a genuine zero recoverable amount", () => {
    expect(
      cell({
        total_opportunity_try: 20,
        opportunity_missing: null,
        total_recoverable_try: 0,
        exemption_gap_try: 20,
      }),
    ).toContain("exemption gap");
  });

  it("labels a figure with a missing exemption gap as partial", () => {
    const text = cell({
      total_opportunity_try: 100,
      opportunity_missing: "gap",
      total_recoverable_try: 100,
      exemption_gap_try: null,
    });
    expect(text).toContain("100.00 TRY");
    expect(text).toContain("Partial: exemption gap not computed");
  });

  it("labels a figure with a missing recoverable amount as partial, not as gap-only", () => {
    const text = cell({
      total_opportunity_try: 20,
      opportunity_missing: "recoverable",
      total_recoverable_try: null,
      exemption_gap_try: 20,
    });
    expect(text).toContain("20.00 TRY");
    expect(text).toContain("Partial: recoverable amount not computed");
    expect(text).not.toContain("exemption gap");
  });

  it("shows a dash when nothing is known", () => {
    expect(
      cell({
        total_opportunity_try: null,
        opportunity_missing: null,
        total_recoverable_try: null,
        exemption_gap_try: null,
      }),
    ).toBe("—");
  });

  it("localizes the partial notes in Turkish", () => {
    expect(
      cell(
        {
          total_opportunity_try: 100,
          opportunity_missing: "gap",
          total_recoverable_try: 100,
          exemption_gap_try: null,
        },
        "tr",
      ),
    ).toContain("Kısmi: muafiyet farkı hesaplanmadı");
    expect(
      cell(
        {
          total_opportunity_try: 20,
          opportunity_missing: "recoverable",
          total_recoverable_try: null,
          exemption_gap_try: 20,
        },
        "tr",
      ),
    ).toContain("Kısmi: kurtarılabilir tutar hesaplanmadı");
  });
});
