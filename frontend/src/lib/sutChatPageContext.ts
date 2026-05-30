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
    sections.outcome = {
      loaded: true,
      patient_id: input.outcome.patient_id,
    };
  }
  if (input.optimization) {
    sections.optimization_snapshot = {
      loaded: true,
      patient_id: input.optimization.patient_id,
      n_diagnoses: input.optimization.n_diagnoses,
    };
  }
  if (input.billingReport) {
    sections.billing_report = {
      loaded: true,
      patient_id: input.billingReport.patient_id,
      total_recoverable_try: input.billingReport.total_recoverable_try,
      priority: input.billingReport.priority,
      exactness_status: input.billingReport.exactness_status,
    };
  }

  return {
    page: "patient_workspace",
    tab: "SUT Patient Workspace",
    patient_id: input.patientId,
    sections,
  };
}
