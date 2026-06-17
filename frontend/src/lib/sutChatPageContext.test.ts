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

  it("builds patient workspace context with lightweight section metadata", () => {
    const outcome = { patient_id: "P-001" } as Parameters<
      typeof buildPatientWorkspacePageContext
    >[0]["outcome"];
    const optimization = {
      patient_id: "P-001",
      n_diagnoses: 3,
    } as Parameters<typeof buildPatientWorkspacePageContext>[0]["optimization"];
    const billingReport = {
      patient_id: "P-001",
      total_recoverable_try: 100,
      priority: "high",
      exactness_status: "exact",
    } as Parameters<typeof buildPatientWorkspacePageContext>[0]["billingReport"];

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
      visible_billing: {
        scope: "patient",
        patient_id: "P-001",
        sgk_uplift_try: 100,
        compliance_adjustment_try: undefined,
        audit_exposure_try: undefined,
        capture_gap_try: undefined,
        exemption_gap_try: undefined,
        package_adequacy_review_try: undefined,
        gazette_repricing_try: undefined,
        medula_playbook_entry_count: undefined,
        total_recoverable_try: 100,
        priority: "high",
        exactness_status: "exact",
      },
      sections: {
        workspace_header: {
          patient_id: "P-001",
          description:
            "Patient workspace with optimization snapshot and billing review sections",
        },
        outcome: { loaded: true, patient_id: "P-001" },
        optimization_snapshot: {
          loaded: true,
          patient_id: "P-001",
          n_diagnoses: 3,
        },
        billing_report: {
          loaded: true,
          patient_id: "P-001",
          total_recoverable_try: 100,
          priority: "high",
          exactness_status: "exact",
        },
      },
    });
  });
});
