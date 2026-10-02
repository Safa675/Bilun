import type { DrugIndicationReview } from "@/lib/domains/sut";
import { expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { DrugIndicationReviewSection } from "./DrugIndicationReviewSection";
import fixture from "@/test/fixtures/checklist-constraint-inputs.json";

// The backend regression compares this fixture with the real public projection.
it("shows missing dose certainty and the exactness notice for an eligible route", () => {
  const html = renderToStaticMarkupWithLocale(
    <DrugIndicationReviewSection reviewData={fixture.drugReview as DrugIndicationReview} />,
  );
  expect(html).toContain("Dose protocol requires verification");
  expect(html).toContain("Missing input — manual verification");
  expect(html).toContain('role="status"');
  expect(html).toContain("annual_application_count");
  expect(html).not.toContain(">Evaluated<");
});
