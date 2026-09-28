import type { BillingActionReport, DrugIndicationFinding } from "@/lib/domains/sut";
import { isExactOutput } from "@/lib/sutExactness";

type DrugReviewData = NonNullable<BillingActionReport["drug_indication"]>;

type DrugIndicationDisplay =
  | { kind: "hidden" }
  | { kind: "structured"; findings: DrugIndicationFinding[] }
  | { kind: "legacy"; violations: DrugReviewData["violations"] }
  | {
      kind: "evaluations";
      evaluations: NonNullable<DrugReviewData["evaluations"]>;
      hasCorpusNoncoverage: boolean;
    }
  | { kind: "empty" };

interface DrugIndicationSectionModel {
  reviewExact: boolean;
  violationCount: number;
  display: DrugIndicationDisplay;
}

export function buildDrugIndicationSectionModel(reviewData: DrugReviewData): DrugIndicationSectionModel {
  const findings = reviewData.findings ?? [];
  const violations = reviewData.violations ?? [];
  const evaluations = reviewData.evaluations ?? [];
  let display: DrugIndicationDisplay;

  if (findings.length > 0) {
    display = { kind: "structured", findings };
  } else if (violations.length > 0) {
    display = { kind: "legacy", violations };
  } else if (evaluations.length > 0) {
    display = {
      kind: "evaluations",
      evaluations,
      hasCorpusNoncoverage: evaluations.some((item) => item.applicability_status === "not_in_encoded_corpus"),
    };
  } else if (reviewData.exactness_status === "exact" || reviewData.exactness_status === "not_applicable") {
    display = { kind: "hidden" };
  } else {
    display = { kind: "empty" };
  }

  return {
    reviewExact: isExactOutput(reviewData),
    violationCount: reviewData.violation_count ?? (findings.length > 0 ? findings.length : violations.length),
    display,
  };
}
