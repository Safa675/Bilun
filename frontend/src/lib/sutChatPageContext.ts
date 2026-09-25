import type {
  BillingActionReport,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import type { SutHomeTab } from "@/lib/constants";

export type SutChatPageId = "home" | "patient_workspace";

/** KPI slice matching BillingSummary — sent so dev chat sees on-screen amounts. */
export interface VisibleBillingSnapshot {
  scope: "patient" | "bill";
  patient_id: string;
  claim_id?: string;
  sgk_uplift_try?: number;
  compliance_adjustment_try?: number;
  audit_exposure_try?: number;
  capture_gap_try?: number;
  exemption_gap_try?: number;
  ilave_ucret_total_try?: number;
  line_decomposition_status?: BillingActionReport["copay"]["line_decomposition_status"];
  package_adequacy_review_try?: number;
  medula_playbook_entry_count?: number;
  total_recoverable_try: number;
  priority: BillingActionReport["priority"];
  exactness_status?: BillingActionReport["exactness_status"];
}

export function buildVisibleBillingSnapshot(
  report: BillingActionReport,
): VisibleBillingSnapshot {
  const isBillScope = report.scope === "bill" && Boolean(report.claim_id);
  const copayExact = report.copay?.exactness_status === "exact";
  const exemptionGapTotal =
    report.copay?.patient_copay_waived_total_try ??
    (report.copay?.visit_copay_savings_try ?? 0) + (report.copay?.rx_copay_savings_try ?? 0);
  const showExemptionGap =
    copayExact && report.copay?.is_exempt && exemptionGapTotal > 0;
  const showIlaveInfo = copayExact && (report.copay?.ilave_ucret_total_try ?? 0) > 0 &&
    report.copay?.line_decomposition_status === "exact";

  return {
    scope: isBillScope ? "bill" : "patient",
    patient_id: report.patient_id,
    claim_id: report.claim_id,
    sgk_uplift_try: report.sgk_uplift_try ?? report.total_recoverable_try,
    compliance_adjustment_try: report.compliance_adjustment_try,
    audit_exposure_try: report.audit_exposure_try,
    capture_gap_try: report.capture_gap_try,
    exemption_gap_try: showExemptionGap ? exemptionGapTotal : undefined,
    ilave_ucret_total_try: showIlaveInfo ? report.copay?.ilave_ucret_total_try : undefined,
    line_decomposition_status: report.copay?.line_decomposition_status,
    package_adequacy_review_try: report.package_adequacy_review_try,
    medula_playbook_entry_count: report.medula_playbook_entry_count,
    total_recoverable_try: report.total_recoverable_try,
    priority: report.priority,
    exactness_status: report.exactness_status,
  };
}

/** Structured snapshot of the page the user is viewing — sent with user questions. */
export interface SutChatPageContext {
  page: SutChatPageId;
  tab?: string;
  patient_id?: string;
  /** Section id the user scrolled to / landed on via `?section=`. */
  selected_section?: string;
  visible_billing?: VisibleBillingSnapshot;
  sections: Record<string, unknown>;
}

/** Lightweight, prompt-safe slice of a single recommended action. */
interface RecommendedActionSummary {
  action_id: string;
  surface: string;
  kind: string;
  title?: string;
  amount_try?: number;
}

function summarizeRecommendedActions(
  report: BillingActionReport,
): RecommendedActionSummary[] {
  const actions = report.recommended_actions;
  if (!actions || actions.length === 0) {
    return [];
  }
  return actions.slice(0, 3).map((action) => ({
    action_id: action.action_id,
    surface: action.surface,
    kind: action.kind,
    title:
      action.procedure_name ??
      action.material_name ??
      action.detail ??
      undefined,
    amount_try:
      action.sgk_uplift_try ??
      action.compliance_savings_try ??
      action.billed_try ??
      undefined,
  }));
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
  /** Section id the user is focused on, e.g. from a `?section=` deep link. */
  selectedSection?: string | null;
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
    const recommended = summarizeRecommendedActions(input.billingReport);
    sections.billing_report = {
      loaded: true,
      patient_id: input.billingReport.patient_id,
      claim_id: input.billingReport.claim_id,
      total_recoverable_try: input.billingReport.total_recoverable_try,
      priority: input.billingReport.priority,
      exactness_status: input.billingReport.exactness_status,
      recommended_actions: recommended.length > 0 ? recommended : undefined,
    };
  }

  return {
    page: "patient_workspace",
    tab: "SUT Patient Workspace",
    patient_id: input.patientId,
    selected_section: input.selectedSection ?? undefined,
    visible_billing: input.billingReport
      ? buildVisibleBillingSnapshot(input.billingReport)
      : undefined,
    sections,
  };
}
