import type {
  BillingActionReport,
  ClaimComplianceEvaluation,
} from "@/lib/domains/sut";
import { scopedClaimComplianceFindings } from "@/lib/workspaceViews";
import type { TranslateFn } from "@/lib/complianceFindings";
import { waveALayerOff } from "@/lib/waveaAvailability";

export interface ClaimComplianceCoverage {
  evaluated: number;
  missingInputs: number;
  unavailable: number;
  additionalFindings: number;
  /** Distinct structural checks (rules) that have an evaluation in scope. */
  checkCount: number;
  /** The backend says the extended evidence layer is not active in this build. */
  extendedLayerOff: boolean;
  summaryText: string;
  nonEvaluatedTotal: number;
  details: ClaimComplianceEvaluation[];
}

export function buildComplianceCoverage(
  report: BillingActionReport,
  t: TranslateFn,
): ClaimComplianceCoverage | null {
  const projection = report.claim_compliance;
  if (!projection) return null;

  const inScope = (row: { patient_id: string; claim_id?: string | null }) =>
    row.patient_id === report.patient_id &&
    (!report.claim_id || row.claim_id === report.claim_id || row.claim_id == null);

  const evaluations = projection.evaluations?.filter(inScope) ?? [];
  const additionalFindings = scopedClaimComplianceFindings(report).length;

  const counts = evaluations.reduce(
    (acc, evaluation) => {
      const status = evaluation.status;
      if (
        status === "evaluated" ||
        status === "missing_inputs" ||
        status === "unavailable"
      ) {
        acc[status] += 1;
      }
      return acc;
    },
    { evaluated: 0, missing_inputs: 0, unavailable: 0 },
  );

  const nonEvaluated = evaluations.filter((ev) => ev.status !== "evaluated");

  const checkCount = new Set(evaluations.map((evaluation) => evaluation.rule_id)).size;
  const extendedLayerOff = waveALayerOff([
    report.claim_reviews,
    report.claim_advisories,
    report.financial_findings,
  ]);

  // "0 not evaluated" reads as "everything was checked", so the gap wording only
  // appears when something is missing or unavailable. Otherwise say what ran.
  let summaryText: string;
  if (evaluations.length === 0) {
    summaryText = t("billing.views.compliance.coverageNoneRan");
  } else if (nonEvaluated.length === 0) {
    summaryText = t(
      additionalFindings > 0
        ? "billing.views.compliance.coverageAllRanFindings"
        : "billing.views.compliance.coverageAllRan",
      { count: checkCount, findings: additionalFindings },
    );
  } else {
    summaryText = t("billing.views.compliance.coverageSummary", {
      evaluated: counts.evaluated,
      findings: additionalFindings,
    });
    if (counts.missing_inputs > 0) {
      summaryText += t("billing.views.compliance.coverageMissing", {
        count: counts.missing_inputs,
      });
    }
    if (counts.unavailable > 0) {
      summaryText += t("billing.views.compliance.coverageUnavailable", {
        count: counts.unavailable,
      });
    }
  }

  return {
    evaluated: counts.evaluated,
    missingInputs: counts.missing_inputs,
    unavailable: counts.unavailable,
    additionalFindings,
    checkCount,
    extendedLayerOff,
    summaryText,
    nonEvaluatedTotal: nonEvaluated.length,
    details: nonEvaluated.slice(0, 20),
  };
}
