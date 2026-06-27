import type { RuleClause } from "@/lib/api/sut";

/** User-facing utilization tier (mutually exclusive). */
export type ClauseUtilizationTier = "referans" | "encoded" | "motorBound";

type ClauseUtilizationInput = Pick<
  RuleClause,
  "coverage_status" | "has_rule_encoding" | "primary_rule_id" | "has_algorithmic_gap"
>;

const MOTOR_BOUND_STATUSES = new Set(["partial", "missing", "needs_claim_lines"]);

export function clauseUtilizationTier(clause: ClauseUtilizationInput): ClauseUtilizationTier {
  if (clause.has_rule_encoding) {
    return "encoded";
  }
  if (clause.coverage_status === "non_algorithmic" || !clause.primary_rule_id) {
    return "referans";
  }
  if (
    clause.has_algorithmic_gap
    || (clause.coverage_status != null && MOTOR_BOUND_STATUSES.has(clause.coverage_status))
  ) {
    return "motorBound";
  }
  if (clause.primary_rule_id) {
    return "motorBound";
  }
  return "referans";
}

export const UTILIZATION_I18N_KEY: Record<ClauseUtilizationTier, string> = {
  referans: "sections.ruleDatabase.utilization.referans",
  encoded: "sections.ruleDatabase.utilization.encoded",
  motorBound: "sections.ruleDatabase.utilization.motorBound",
};

export const UTILIZATION_CHIP_VARIANT: Record<
  ClauseUtilizationTier,
  "neutral" | "success" | "warning"
> = {
  referans: "neutral",
  encoded: "success",
  motorBound: "warning",
};

/** Display label for registry rule_id (e.g. definitions → friendly name). */
export function ruleMotorLabel(
  ruleId: string,
  t: (key: string) => string,
): string {
  if (ruleId === "definitions") {
    return t("sections.ruleDatabase.rules.definitionsLabel");
  }
  return ruleId;
}
