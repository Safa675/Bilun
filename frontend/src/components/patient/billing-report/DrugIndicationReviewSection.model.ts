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
      /** Every line sits outside the corpus and no SUT clause names its ingredient. */
      allNoSutRestriction: boolean;
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
      allNoSutRestriction: evaluations.every((item) => item.applicability_status === "no_sut_restriction_found"),
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

/** Message keys for the notice above the evaluation list. */
export function drugEvaluationNoticeKeys(flags: {
  hasCorpusNoncoverage: boolean;
  allNoSutRestriction: boolean;
}): { title: string; detail: string } {
  if (flags.allNoSutRestriction) {
    return {
      title: "billing.drugIndication.noSutRestriction",
      detail: "billing.drugIndication.noSutRestrictionDetail",
    };
  }
  if (flags.hasCorpusNoncoverage) {
    return {
      title: "billing.drugIndication.corpusNoncoverage",
      detail: "billing.drugIndication.corpusNoncoverageDetail",
    };
  }
  return {
    title: "billing.drugIndication.evaluationOnly",
    detail: "billing.drugIndication.evaluationOnlyDetail",
  };
}

/** The message key and section list that say what the SUT text holds about a line's ingredient. */
export function drugLineScopeLabel(
  evaluation: NonNullable<DrugReviewData["evaluations"]>[number],
): { key: string; sections: string } | null {
  const scope = evaluation.ingredient_scope;
  if (!scope) return null;
  const sections = scope.result === "class_level_in_sut" ? scope.class_sections : scope.sut_sections;
  return {
    key: `billing.drugIndication.lineScope.${scope.result}`,
    sections: (sections ?? []).map((section) => `§${section}`).join(", "),
  };
}
