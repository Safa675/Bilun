import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DataTable } from "./DataTable";

describe("DataTable phone rows", () => {
  it("opts in without replacing labelled values or the desktop minimum width", () => {
    const html = renderToStaticMarkup(
      <DataTable mobileStacked minWidth={960}>
        <thead><tr><th>Claim</th><th>Risk</th></tr></thead>
        <tbody><tr data-finding-id="finding-1"><td data-label="Claim">claim-1</td><td data-label="Risk">Not computed</td></tr></tbody>
      </DataTable>,
    );
    expect(html).toContain('data-mobile-stacked="true"');
    expect(html).toContain("min-width:960px");
    expect(html).toContain('data-finding-id="finding-1"');
    expect(html).toContain('data-label="Risk">Not computed');
  });

  it("leaves ordinary tables unchanged", () => {
    expect(renderToStaticMarkup(<DataTable><tbody><tr><td>0.00 TRY</td></tr></tbody></DataTable>)).not.toContain("data-mobile-stacked");
  });
});
