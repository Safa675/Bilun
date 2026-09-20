import { describe, expect, it } from "vitest";
import { parsePatientWorkspaceQuery } from "@/lib/patientRoute";

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
