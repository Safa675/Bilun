import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { PatientMeta } from "@/lib/domains/patient";
import CohortFilterBar from "./CohortFilterBar";

const hook = vi.hoisted(() => ({ active: false }));
vi.mock("@/hooks/useCohortFilter", () => ({
  useCohortFilter: () => ({
    filter: { q: "", sex: hook.active ? "E" : "", ageMin: null, ageMax: null, doctor: "" },
    isActive: hook.active,
    setFilter: vi.fn(),
    clearFilter: vi.fn(),
  }),
}));

const patients = [
  { patient_id: "SENTETIK-HASTA-0001", age: 51, sex: "E" },
  { patient_id: "SENTETIK-HASTA-0002", age: 35, sex: "K" },
] as unknown as PatientMeta[];

beforeEach(() => {
  hook.active = false;
});

describe("CohortFilterBar", () => {
  it("is one toolbar row with the four filters and the summary chip, and no header essay", () => {
    const html = renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={50} totalCount={50} patients={patients} />,
    );
    expect(html).toContain("50 of 50 patients");
    for (const label of ["Patient", "Sex", "Age", "Doctor code"]) expect(html).toContain(label);
    expect(html).toContain("SENTETIK-HASTA-0001 · 51y · E");
    expect(html).not.toContain("Clear filters");
    expect(html).not.toContain("Filters carry across");
    // the old card header is gone; the toolbar keeps an accessible name instead
    expect(html).toContain('role="group"');
    expect(html).toContain('aria-label="Filtering"');
    expect(html.match(/rounded-\[var\(--r-lg\)\]/g)).toHaveLength(1);
  });

  it("shows Clear filters and a gold chip only while a filter is active", () => {
    hook.active = true;
    const html = renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={25} totalCount={50} patients={patients} />,
    );
    expect(html).toContain("Clear filters");
    expect(html).toContain("25 of 50 patients");
    expect(html).toContain("gold-subtle");
  });

  it("renders in Turkish", () => {
    const html = renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={50} totalCount={50} patients={patients} />,
      "tr",
    );
    expect(html).toContain("50 hastadan 50");
    for (const label of ["Hasta", "Cinsiyet", "Yaş", "Doktor kodu"]) expect(html).toContain(label);
  });

  it("never reads 0 of 0 patients: no chip while the list is empty (not loaded, or failed to load)", () => {
    const html = renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={0} totalCount={0} patients={[]} />,
    );
    expect(html).not.toContain("0 of 0");
    expect(html).toContain("Loading patients…");
  });

  it("shows no chip when a count is unknown", () => {
    const html = renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={null} totalCount={null} patients={[]} />,
    );
    expect(html).not.toContain("patients</span>");
    expect(html).not.toMatch(/\d+ of \d+ patients/);
  });
});
