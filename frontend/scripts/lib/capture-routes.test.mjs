import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { COMPLIANCE_SUBTABS, subtabRoutes, TOOL_SUBTABS } from "./capture-routes.mjs";

const source = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "../../src/lib/workspaceSubtabs.ts"), "utf8");

/** The string ids of `export const <name>: readonly X[] = [ ... ]` in workspaceSubtabs.ts. */
function idsOf(name) {
  const block = source.match(new RegExp(`export const ${name}[^=]*= \\[([^\\]]*)\\]`))?.[1] ?? "";
  return [...block.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
}

describe("capture routes mirror the app's sub-view ids", () => {
  it("lists every compliance and reference-tools sub-view", () => {
    expect(COMPLIANCE_SUBTABS).toEqual(idsOf("COMPLIANCE_SUB_IDS"));
    expect(TOOL_SUBTABS).toEqual(idsOf("BILLING_SUB_IDS"));
    expect(COMPLIANCE_SUBTABS).toHaveLength(8);
    expect(TOOL_SUBTABS).toHaveLength(8);
  });

  it("adds one route per non-default sub-view, with unique ids", () => {
    const routes = subtabRoutes();
    expect(routes).toHaveLength(14);
    expect(new Set(routes.map((r) => r.id)).size).toBe(14);
    expect(routes[0]).toEqual({ id: "compliance-surcharge", kind: "home", url: "/?tab=compliance&compTab=surcharge" });
    expect(routes.at(-1)).toEqual({ id: "reference-tools-lab_prices", kind: "home", url: "/?tab=reference-tools&toolSub=lab_prices" });
  });
});
