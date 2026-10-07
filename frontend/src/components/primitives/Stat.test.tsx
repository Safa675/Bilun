import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Stat from "./Stat";

describe("Stat typography", () => {
  it("keeps long labels in their supplied case with the existing small-text token", () => {
    const html = renderToStaticMarkup(<Stat label="Billed amount with missing information" value="Unavailable" />);
    expect(html).toContain("Billed amount with missing information");
    expect(html).toContain('class="text-xs font-semibold text-[var(--text-muted)]"');
    expect(html).not.toContain("uppercase");
    expect(html).not.toContain("tracking-");
  });

  it("uses an unambiguous display-font family for the primary value", () => {
    const html = renderToStaticMarkup(<Stat label="Recoverable" value="1,234.56 TRY" display="gold" />);
    expect(html).toContain("font-display italic");
    expect(html).toContain("tabular-nums lining-nums");
    expect(html).not.toContain("font-[var(--font-display)]");
  });
});
