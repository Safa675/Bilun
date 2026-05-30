import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ExemptionBasisChips } from "./ExemptionBasisChips";

describe("ExemptionBasisChips", () => {
  it("renders category chips for exempt patients", () => {
    const html = renderToStaticMarkup(
      <ExemptionBasisChips
        copay={{
          exempt: true,
          n_qualifying: 0,
          qualifying_diagnoses: [],
          exemption_sources: [{ category: "acil_servis" }],
          action: null,
        }}
      />,
    );
    expect(html).toContain("Acil");
  });
});
