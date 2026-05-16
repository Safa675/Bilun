import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  getSutDataSource,
  isSyntheticDemoDataSource,
  SYNTHETIC_DEMO_COPY,
  SyntheticDemoProvenance,
} from "./SyntheticDemoProvenance";
import type { SUTDataSourceMetadata } from "@/lib/domains/sut";

const SYNTHETIC_SOURCE: SUTDataSourceMetadata = {
  mode: "synthetic_demo",
  label: "Synthetic SUT demo claim data",
  claim_source: "data/synthetic/sut/claims",
  clinical_source: "data/synthetic/sut/clean",
  is_synthetic: true,
  notice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
};

describe("SyntheticDemoProvenance", () => {
  it("normalizes snake_case and camelCase provenance carriers", () => {
    expect(getSutDataSource({ data_source: SYNTHETIC_SOURCE })).toBe(SYNTHETIC_SOURCE);
    expect(getSutDataSource({ dataSource: SYNTHETIC_SOURCE })).toBe(SYNTHETIC_SOURCE);
    expect(isSyntheticDemoDataSource({ data_source: SYNTHETIC_SOURCE })).toBe(true);
  });

  it("renders demo-safe copy only for synthetic SUT provenance", () => {
    const html = renderToStaticMarkup(
      <SyntheticDemoProvenance dataSource={SYNTHETIC_SOURCE} />,
    );

    expect(html).toContain(SYNTHETIC_DEMO_COPY);
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });

  it("does not render a badge for real-claims provenance", () => {
    const html = renderToStaticMarkup(
      <SyntheticDemoProvenance
        dataSource={{
          mode: "real_claims",
          label: "Hospital claim data",
          is_synthetic: false,
          notice: "Hospital claim data.",
        }}
      />,
    );

    expect(html).toBe("");
  });
});
