import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";
import { SessionUpliftSection } from "./SessionUpliftSection";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

type SessionData = NonNullable<BillingActionReport["session_uplift"]>;
type Row = Record<string, unknown>;

const session = (opportunities: Row[], extra: Record<string, unknown> = {}): SessionData =>
  ({
    exactness_status: "exact",
    opportunities: opportunities.map((row, index) => ({
      claim_id: `C-${index}`,
      procedure_code: `P-${index}`,
      ...row,
    })),
    ...extra,
  }) as unknown as SessionData;

// Header total and the note under the footnote, as plain text.
function headerAndNote(sessionData: SessionData, locale: "en" | "tr" = "en") {
  const html = renderToStaticMarkupWithLocale(
    <SessionUpliftSection sessionData={sessionData} />,
    locale,
  );
  const total = /font-mono text-sm font-semibold tabular-nums[^>]*>([^<]*)</.exec(html);
  expect(total).not.toBeNull();
  return { total: (total as RegExpExecArray)[1], html };
}

describe("SessionUpliftSection total with missing uplift amounts", () => {
  it("sums every row and adds no note when all amounts are present and no total is reported", () => {
    const { total, html } = headerAndNote(
      session([{ recoverable_uplift_try: 100 }, { recoverable_uplift_try: 50.5 }]),
    );
    expect(total).toBe("150.50 TRY");
    expect(html).not.toContain("Partial total");
    expect(html).not.toContain("None of the");
  });

  it("shows a labelled partial total when one row has no uplift amount", () => {
    const { total, html } = headerAndNote(
      session([{ recoverable_uplift_try: 100 }, { recoverable_uplift_try: null }]),
    );
    expect(total).toBe("100.00 TRY");
    expect(html).toContain("Partial total: only 1 of 2 rows in this total have an uplift amount");
  });

  it("shows a dash and no 0.00 when no row has an uplift amount", () => {
    const { total, html } = headerAndNote(
      session([{ recoverable_uplift_try: null }, {}]),
    );
    expect(total).toBe("—");
    expect(html).toContain("None of the 2 rows in this total has an uplift amount");
    expect(html).not.toContain("0.00 TRY</span>");
  });

  it("does not count rows excluded from the SGK total", () => {
    const { total, html } = headerAndNote(
      session([
        { recoverable_uplift_try: 100 },
        { recoverable_uplift_try: null, included_in_sgk_total: false },
      ]),
    );
    expect(total).toBe("100.00 TRY");
    expect(html).not.toContain("Partial total");
  });

  it("uses the reported confirmed total unchanged, even when a row amount is missing", () => {
    const { total, html } = headerAndNote(
      session([{ recoverable_uplift_try: 100 }, { recoverable_uplift_try: null }], {
        confirmed_uplift_try: 300,
      }),
    );
    expect(total).toBe("300.00 TRY");
    expect(html).not.toContain("Partial total");
  });

  it("localizes the partial and none notes in Turkish", () => {
    const partial = headerAndNote(
      session([{ recoverable_uplift_try: 100 }, { recoverable_uplift_try: null }]),
      "tr",
    );
    expect(partial.html).toContain(
      "Kısmi toplam: bu toplamdaki 2 satırdan yalnızca 1 tanesinde artış tutarı var",
    );

    const none = headerAndNote(
      session([{ recoverable_uplift_try: null }, { recoverable_uplift_try: null }]),
      "tr",
    );
    expect(none.total).toBe("—");
    expect(none.html).toContain("Bu toplamdaki 2 satırın hiçbirinde artış tutarı yok");
  });
});
