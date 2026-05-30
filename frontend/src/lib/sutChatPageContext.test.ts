import { describe, expect, it } from "vitest";

import {
  buildHomePageContext,
  buildPatientWorkspacePageContext,
} from "./sutChatPageContext";

describe("sutChatPageContext", () => {
  it("builds home page context from active tab id", () => {
    expect(buildHomePageContext("patients")).toEqual({
      page: "home",
      tab: "patients",
      sections: {
        workspace: {
          label: "patients",
          description: "Cohort-level SUT workspace tab",
        },
      },
    });
  });

  it("builds patient workspace context with loaded sections", () => {
    const outcome = { patient_id: "P-001" } as Parameters<
      typeof buildPatientWorkspacePageContext
    >[0]["outcome"];
    const optimization = { patient_id: "P-001" } as Parameters<
      typeof buildPatientWorkspacePageContext
    >[0]["optimization"];
    const billingReport = { patient_id: "P-001", lab: { total_savings: 100 } } as Parameters<
      typeof buildPatientWorkspacePageContext
    >[0]["billingReport"];

    expect(
      buildPatientWorkspacePageContext({
        patientId: "P-001",
        outcome,
        optimization,
        billingReport,
      }),
    ).toEqual({
      page: "patient_workspace",
      tab: "SUT Patient Workspace",
      patient_id: "P-001",
      sections: {
        workspace_header: {
          patient_id: "P-001",
          description:
            "Patient workspace with optimization snapshot and billing review sections",
        },
        outcome,
        optimization_snapshot: optimization,
        billing_report: billingReport,
      },
    });
  });
});
