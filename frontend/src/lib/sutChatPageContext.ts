import type {
  BillingActionReport,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import type { SutHomeTab } from "@/lib/constants";

export type SutChatPageId = "home" | "patient_workspace";

/** Structured snapshot of the page the user is viewing — sent with user questions. */
export interface SutChatPageContext {
  page: SutChatPageId;
  tab?: string;
  patient_id?: string;
  sections: Record<string, unknown>;
}

export function buildHomePageContext(tab: SutHomeTab): SutChatPageContext {
  return {
    page: "home",
    tab,
    sections: {
      workspace: {
        label: tab,
        description: "Cohort-level SUT workspace tab",
      },
    },
  };
}

export function buildPatientWorkspacePageContext(input: {
  patientId: string;
  outcome: SutPatientOutcomeData | null;
  optimization: PatientOptimization | null;
  billingReport: BillingActionReport | null;
}): SutChatPageContext {
  const sections: Record<string, unknown> = {
    workspace_header: {
      patient_id: input.patientId,
      description: "Patient workspace with optimization snapshot and billing review sections",
    },
  };

  if (input.outcome) {
    sections.outcome = input.outcome;
  }
  if (input.optimization) {
    sections.optimization_snapshot = input.optimization;
  }
  if (input.billingReport) {
    sections.billing_report = input.billingReport;
  }

  return {
    page: "patient_workspace",
    tab: "SUT Patient Workspace",
    patient_id: input.patientId,
    sections,
  };
}
