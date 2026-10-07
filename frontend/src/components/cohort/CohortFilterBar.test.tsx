import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { PatientMeta } from "@/lib/domains/patient";
import CohortFilterBar from "./CohortFilterBar";

const hook = vi.hoisted(() => ({ active: false, q: "" }));
vi.mock("@/hooks/useCohortFilter", () => ({
  useCohortFilter: () => ({
    filter: { q: hook.q, sex: hook.active ? "E" : "", ageMin: null, ageMax: null, doctor: "" },
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
  hook.q = "";
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

  it("gives the closed patient select the full label as a tooltip once a patient is chosen", () => {
    expect(renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={50} totalCount={50} patients={patients} />,
    )).not.toContain("title=");

    hook.q = "SENTETIK-HASTA-0001";
    expect(renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={1} totalCount={50} patients={patients} />,
    )).toContain('title="SENTETIK-HASTA-0001 · 51y · E"');
    expect(renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={1} totalCount={50} patients={patients} />,
      "tr",
    )).toContain('title="SENTETIK-HASTA-0001 · 51 yaş · E"');

    // an id that is not in the loaded list still shows as typed
    hook.q = "SENTETIK-HASTA-9999";
    expect(renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={0} totalCount={50} patients={patients} />,
    )).toContain('title="SENTETIK-HASTA-9999"');
  });

  it("sizes the patient select for the longest chosen label and still fits the toolbar in one row at 1280px", () => {
    const html = renderToStaticMarkupWithLocale(
      <CohortFilterBar matchedCount={50} totalCount={50} patients={patients} />,
    );
    const labels = [...html.matchAll(/<label class="([^"]*)"/g)].map((m) => m[1]);
    expect(labels).toHaveLength(4);
    const widths = labels.map((cls) => Number(/(?:^|\s)(?:sm:)?w-\[(\d+)px\]/.exec(cls)?.[1]));
    // measured in Chrome: the widest Turkish label (239px of text) is cut below about 288px with pr-3
    expect(widths[0]).toBeGreaterThanOrEqual(300);
    // below 640px the patient select takes the whole row: a fixed 310px made the page scroll sideways at 390px
    expect(labels[0]).toMatch(/(?:^|\s)w-full\b/);
    expect(labels[0]).toMatch(/\bsm:w-\[310px\]/);
    const selects = [...html.matchAll(/<select class="([^"]*)"/g)].map((m) => m[1]);
    expect(selects[0]).toMatch(/\bpr-3\b/);
    expect(selects[0]).not.toMatch(/\bpr-8\b/);
    expect(selects[1]).toMatch(/\bmin-w-0\b/); // the sex select is narrower than the select default of 140px
    // the four controls, three 12px gaps, the 12px gap to the trailing group and its widest content (Turkish clear
    // button and chip, 233px) must fit the 978px inside the toolbar at a 1280px screen
    expect(widths.reduce((a, b) => a + b, 0) + 3 * 12 + 12 + 233).toBeLessThanOrEqual(978);
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
