import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { COMPLIANCE_SUBTABS, complianceFindingId, detectPagers, INSPECT_CLAUSE_LABEL, pageUrl, subtabRoutes, TOOL_SUBTABS } from "./capture-routes.mjs";

const srcDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../src");
const source = fs.readFileSync(path.join(srcDir, "lib/workspaceSubtabs.ts"), "utf8");

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

describe("clause button and pager recognition mirror the app's strings", () => {
  const message = (locale, file, pattern) => fs.readFileSync(path.join(srcDir, "messages", locale, file), "utf8").match(pattern)?.[1];

  it("knows the aria-label prefix of the Inspect clause button in EN and TR", () => {
    for (const locale of ["en", "tr"]) {
      const template = message(locale, "billing.ts", /"inspectClause":\s*"([^"]*)"/);
      expect(template, locale).toBe(`${INSPECT_CLAUSE_LABEL[locale]} {coordinate}`);
    }
  });

  it("reads the pager templates of the Patients table, Reference Tools and Materials", () => {
    expect(message("en", "home.ts", /"pageOf":\s*"([^"]*)"/)).toBe("Page {current} of {total}");
    expect(message("tr", "home.ts", /"pageOf":\s*"([^"]*)"/)).toBe("Sayfa {current} / {total}");
    expect(detectPagers("Prev\nPage 1 of 5\nNext")).toEqual([{ kind: "page", current: 1, total: 5 }]);
    expect(detectPagers("Önceki\nSayfa 2 / 5\nSonraki")).toEqual([{ kind: "page", current: 2, total: 5 }]);
    expect(detectPagers("Prev\nPage 1 / 270\nNext")).toEqual([{ kind: "page", current: 1, total: 270 }]);
    expect(detectPagers("Prev\n1–100 / 163\nNext")).toEqual([{ kind: "range", from: 1, to: 100, total: 163 }]);
  });

  it("ignores single pages and ordinary text", () => {
    expect(detectPagers("Prev\n1 / 1\nNext")).toEqual([]);
    expect(detectPagers("Page 1 of 1")).toEqual([]);
    expect(detectPagers("1–54 / 54\n50 of 50 patients")).toEqual([]);
    expect(detectPagers("")).toEqual([]);
  });

  it("builds the page URL of a home route", () => {
    expect(pageUrl("/?tab=patients", 3)).toBe("/?tab=patients&p=3");
    expect(pageUrl("/patients", 2)).toBe("/patients?p=2");
  });

  it("looks for the page param under the key the table writes", () => {
    const table = fs.readFileSync(path.join(srcDir, "components/tables/PatientInvoiceTable.tsx"), "utf8");
    expect(table).toMatch(/searchParams\.get\("p"\)/);
  });
});

describe("the compliance finding a deep link can select", () => {
  it("prefers a canonical claim-compliance finding, in sorted order", () => {
    const report = {
      claim_compliance: { findings: [{ finding_id: "rule:b" }, { finding_id: "rule:a" }] },
      recommended_actions: [{ finding_type: "compliance", finding_id: "action:0" }],
    };
    expect(complianceFindingId(report)).toBe("rule:a");
  });

  it("falls back to the finding_id of a compliance action (the claim-compliance list is empty in the showcase cohort)", () => {
    const report = {
      claim_compliance: { findings: [] },
      recommended_actions: [
        { finding_type: "informational", finding_id: "checklist:1" },
        { finding_type: "compliance" },
        { finding_type: "compliance", finding_id: "drug_indication:unit:1" },
      ],
    };
    expect(complianceFindingId(report)).toBe("drug_indication:unit:1");
  });

  it("returns null when the page has nothing to select", () => {
    expect(complianceFindingId({})).toBeNull();
    expect(complianceFindingId(null)).toBeNull();
    expect(complianceFindingId({ claim_compliance: { findings: [{ finding_id: "" }, {}] }, recommended_actions: [{ finding_type: "opportunity", finding_id: "x" }, { finding_type: "compliance", action_id: "only-an-action-id" }] })).toBeNull();
  });
});
