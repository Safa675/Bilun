import { describe, expect, it } from "vitest";
import {
  findFindingRowElement,
  parsePatientWorkspaceQuery,
  resolvePatientScrollTarget,
} from "@/lib/patientRoute";

describe("patient workspace route query", () => {
  it("decodes and propagates the canonical finding query alongside claim and section", () => {
    const findingId = "claim_compliance:future/rule:P /1:C &1:procedure:L:1";
    const query = parsePatientWorkspaceQuery(
      new URLSearchParams({
        claim: "C &1",
        section: "claim-compliance",
        finding: findingId,
      }),
    );

    expect(query).toEqual({
      claimId: "C &1",
      section: "claim-compliance",
      findingId,
    });
  });
});

describe("patient scroll target", () => {
  function makeDocumentStub() {
    const rows: Array<{ findingId: string; element: object }> = [];
    const sections = new Map<string, object>();
    const root = {
      querySelectorAll: (selector: string) => {
        if (selector !== "[data-finding-id]") return [];
        return rows.map((row) => ({
          dataset: { findingId: row.findingId },
          __findingId: row.findingId,
        }));
      },
      getElementById: (id: string) => sections.get(id) ?? null,
      __rows: rows,
      __sections: sections,
    } as unknown as ParentNode & {
      getElementById: (id: string) => Element | null;
      __rows: Array<{ findingId: string; element: object }>;
      __sections: Map<string, object>;
    };
    return root;
  }

  it("prefers the exact finding row over the section anchor", () => {
    const root = makeDocumentStub();
    const exactElement = { dataset: { findingId: "canonical-1" } };
    const sectionElement = {};
    root.__rows.push({ findingId: "canonical-1", element: exactElement });
    root.__sections.set("claim-compliance", sectionElement);

    expect(
      resolvePatientScrollTarget(root, "canonical-1", "claim-compliance"),
    ).not.toBeNull();
    // Exact row wins: the returned element carries the finding dataset.
    const target = resolvePatientScrollTarget(root, "canonical-1", "claim-compliance");
    expect((target as unknown as { dataset: { findingId: string } }).dataset.findingId).toBe(
      "canonical-1",
    );
  });

  it("falls back to the section anchor when the exact row is absent", () => {
    const root = makeDocumentStub();
    const sectionElement = {};
    root.__sections.set("claim-compliance", sectionElement);

    expect(
      resolvePatientScrollTarget(root, "missing-finding", "claim-compliance"),
    ).toBe(sectionElement as unknown as Element);
  });

  it("returns null when neither finding nor section resolves", () => {
    const root = makeDocumentStub();
    expect(resolvePatientScrollTarget(root, "missing", "missing-section")).toBeNull();
    expect(resolvePatientScrollTarget(root, null, null)).toBeNull();
  });

  it("matches finding ids with CSS-special characters via dataset equality", () => {
    const specialId = "claim_compliance:future/rule:P /1:C &1:procedure:L:1";
    const root = makeDocumentStub();
    root.__rows.push({ findingId: specialId, element: {} });
    root.__rows.push({ findingId: "other", element: {} });

    const found = findFindingRowElement(root, specialId);
    expect(found).not.toBeNull();
    expect(
      (found as unknown as { dataset: { findingId: string } }).dataset.findingId,
    ).toBe(specialId);
  });
});
