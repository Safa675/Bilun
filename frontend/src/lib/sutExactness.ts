import type { ExactnessStatus } from "./domains/sut";

const REQUIRED_INPUT_LABELS: Record<string, string> = {
  billed_procedure_codes: "billed procedure codes",
  procedure_dates: "procedure dates",
  itemized_billed_procedure_lines: "itemized billed procedure lines",
  episode_package_eligibility_context: "package eligibility context",
  admission_dates: "admission dates",
  dispensed_drug_claim_lines: "dispensed drug claim lines",
  drug_claim_dates: "drug claim dates",
  billed_drug_amounts: "billed drug amounts",
};

export interface ExactnessLike {
  exactness_status?: ExactnessStatus | null;
  pricing_status?: ExactnessStatus | null;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[] | null;
}

export function isExactOutput(block: ExactnessLike | null | undefined): boolean {
  return block?.exactness_status === "exact" || block?.pricing_status === "exact";
}

export function formatRequiredInputs(inputs: string[] | null | undefined): string {
  if (!inputs || inputs.length === 0) {
    return "";
  }

  return inputs
    .map((input) => REQUIRED_INPUT_LABELS[input] ?? input.replace(/_/g, " "))
    .join(", ");
}

export function getUnavailableMessage(
  block: ExactnessLike | null | undefined,
  fallback: string,
): string {
  const reason = block?.unavailable_reason?.trim();
  const inputs = formatRequiredInputs(block?.required_inputs_missing);
  if (reason && inputs) {
    return `${reason} Missing exact inputs: ${inputs}.`;
  }
  if (reason) {
    return reason;
  }
  if (inputs) {
    return `Missing exact inputs: ${inputs}.`;
  }
  return fallback;
}
