import { describe, expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { MaterialBundlingScopeNotice } from "./MaterialBundlingScopeNotice";
import { SpecialtyProseScopeNotice } from "./SpecialtyProseScopeNotice";
import type { SutMaterialBundlingCoverageScope, SutSpecialtyProseCoverageScope } from "@/lib/api/sut";

describe("public material notices", () => {
  it("keeps the manual review warning without inventing engine counts or source paths", () => {
    const scope = { prose_engine_status: "implemented", implemented_annexes: ["EK-3B-1"], medula_savings_note: "Pre-submission advisory" } as SutMaterialBundlingCoverageScope;
    const html = renderToStaticMarkupWithLocale(<MaterialBundlingScopeNotice scope={scope} />);
    expect(html).toContain("manual review");
    expect(html).toContain("EK-3B-1");
    expect(html).toContain("Not guaranteed SGK recovery");
    expect(html).not.toContain("plans/");
    expect(html).not.toContain("0 prose");
    expect(renderToStaticMarkupWithLocale(<MaterialBundlingScopeNotice />)).not.toContain("22");
  });

  it("preserves a specialty review notice when public projection omits rule count", () => {
    const scope = { prose_engine_status: "implemented" } as SutSpecialtyProseCoverageScope;
    const html = renderToStaticMarkupWithLocale(<SpecialtyProseScopeNotice scope={scope} />);
    expect(html).toContain("documentation requirements");
    expect(html).not.toContain("0 prose");
  });
});
