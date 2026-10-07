import { describe, expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { CohortRecoverySummary } from "@/lib/domains/sut";
import RevenueRecoverySummary, { recoveryCategories } from "./RevenueRecoverySummary";

const summary = {
  exactness_status: "exact",
  n_patients: 50,
  grand_total_recoverable: 100,
  total_lab_savings: 0,
  total_copay_savings: 30,
  total_strategy_savings: 70,
  total_optional_override_uplift: 0,
  n_optional_override_patients: 0,
  total_drg_uplift: 100,
  n_drg_uplift_patients: 1,
  total_blood_uplift: 0,
  n_blood_uplift_patients: 0,
  total_yatak_puani: 80,
  n_yatak_puani_patients: 22,
  total_material_flags: 0,
  top_patients: [],
  priority_distribution: {},
  savings_by_category: { session_uplift: 25 },
} as CohortRecoverySummary;

describe("RevenueRecoverySummary honesty", () => {
  it("ranks amounts while grouping only exact zeros backed by zero patient counts", () => {
    const { rows, noFindings } = recoveryCategories(summary);
    expect(rows[0]).toMatchObject({ key: "drg_uplift", amount: 100, patients: 1 });
    expect(noFindings.map((row) => row.key)).toEqual(["optional_override", "blood_uplift"]);
    expect(rows.find((row) => row.key === "lab")).toMatchObject({ amount: 0, patients: null });
    expect(rows.find((row) => row.key === "yatak_puani")).toMatchObject({ amount: 80, patients: 22 });
  });

  it("keeps partial zeros visible and never invents missing money or patient counts", () => {
    const { rows, noFindings } = recoveryCategories({ ...summary, exactness_status: "partial_exact" });
    expect(noFindings).toEqual([]);
    expect(rows.find((row) => row.key === "blood_uplift")).toMatchObject({ amount: 0, patients: 0 });
    expect(rows.find((row) => row.key === "capture_gap")).toMatchObject({ amount: null, patients: null });
    expect(rows.find((row) => row.key === "copay_waiver")).toMatchObject({ patients: null });
  });

  it("withholds every amount for unavailable cohort output despite stale numeric fields", () => {
    const { rows, noFindings } = recoveryCategories({ ...summary, exactness_status: "missing_exact_inputs" });
    expect(noFindings).toEqual([]);
    expect(rows.every((row) => row.amount === null)).toBe(true);
    const html = renderToStaticMarkupWithLocale(<RevenueRecoverySummary data={{ ...summary, exactness_status: "missing_exact_inputs" }} />);
    expect(html).toContain("Missing exact inputs");
    expect(html).not.toContain("100 TRY");
    expect(html).not.toContain("0 TRY");
  });

  it.each(["en", "tr"] as const)("renders the category and uncertainty labels in %s", (locale) => {
    const html = renderToStaticMarkupWithLocale(<RevenueRecoverySummary data={{ ...summary, exactness_status: "partial_exact" }} />, locale);
    expect(html).toContain(locale === "en" ? "Partial exact" : "Kısmi kesin");
    expect(html).toContain(locale === "en" ? "Procedure capture gap (EMR)" : "İşlem yakalama farkı (EMR)");
    expect(html).not.toContain("optimizer.recoveryList.");
    expect(html).not.toContain("billing.recommendedActions.exactness.");
    expect(html).not.toContain("data-recovery-no-findings");
  });
});
