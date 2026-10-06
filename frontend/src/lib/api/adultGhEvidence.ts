/** Source-specific draft facts; null means unknown, never a negative finding. */
export interface SutAdultGhStimulationTest {
  test_id?: string | null;
  performed_on?: string | null;
  kind?: "itt" | "other" | null;
  inadequate_response_documented?: boolean | null;
  peak_gh_mcg_l?: number | null;
  peak_gh_documented_in_report?: boolean | null;
  retest_after_epiphyseal_closure_stop?: boolean | null;
}

/** Patient group, epiphyseal closure and treatment phase remain separate context fields. */
export interface SutAdultGhEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  diagnosis_pathway?: "childhood_onset_retest" | "adult_hypothalamic_pituitary" | null;
  childhood_gh_deficiency_diagnosed?: boolean | null;
  childhood_gh_treatment_received?: boolean | null;
  gh_stopped_due_to_epiphyseal_closure?: boolean | null;
  adult_hypothalamic_pituitary_gh_deficiency_suspected?: boolean | null;
  /** At least one additional anterior pituitary hormone deficiency, excluding prolactin and GH. */
  additional_anterior_pituitary_deficiency_confirmed?: boolean | null;
  itt_contraindicated?: boolean | null;
  /** Independent documentary fact; test IDs, methods and dates never establish it. */
  two_distinct_stimulation_procedures_documented?: boolean | null;
  stimulation_tests?: SutAdultGhStimulationTest[] | null;
}

export interface SutAdultGhDraftRestriction {
  criterion_status: "not_evaluated" | "unknown" | "criterion_clear" | "restriction_not_met";
  missing_inputs: readonly string[];
  clinical_eligibility_complete: false;
}

/** A candidate result is a review aid and cannot enable runtime or establish payment eligibility. */
export interface SutAdultGhDraftReview {
  runtime_enabled: false;
  clinical_eligibility_complete: false;
  runtime_result?: SutAdultGhDraftRestriction | null;
  candidate_result?: SutAdultGhDraftRestriction | null;
  pending_requirements?: readonly string[];
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

function exactBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function nonnegativeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function civilDate(value: unknown): string | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (year < 1 || month < 1 || month > 12) return null;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= monthDays[month - 1] ? value : null;
}

function testId(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const id = value.trim();
  return id.length >= 1 && id.length <= 120 ? id : null;
}

function stimulationTest(value: unknown): SutAdultGhStimulationTest {
  // Preserve even malformed rows as unknown facts; removing them would conceal missing evidence.
  const row = record(value) ?? {};
  return {
    test_id: testId(row.test_id),
    performed_on: civilDate(row.performed_on),
    kind: row.kind === "itt" || row.kind === "other" ? row.kind : null,
    inadequate_response_documented: exactBoolean(row.inadequate_response_documented),
    peak_gh_mcg_l: nonnegativeNumber(row.peak_gh_mcg_l),
    peak_gh_documented_in_report: exactBoolean(row.peak_gh_documented_in_report),
    retest_after_epiphyseal_closure_stop: exactBoolean(row.retest_after_epiphyseal_closure_stop),
  };
}

/** Normalize only explicit native values, without deriving adequacy, dates or clinical classifications. */
export function adultGhEvidencePayload(value: unknown): SutAdultGhEvidence | null {
  const facts = record(value);
  if (!facts) return null;
  const tests = facts.stimulation_tests;
  return {
    applies_on: civilDate(facts.applies_on),
    assessment_date: civilDate(facts.assessment_date),
    diagnosis_pathway: facts.diagnosis_pathway === "childhood_onset_retest"
      || facts.diagnosis_pathway === "adult_hypothalamic_pituitary" ? facts.diagnosis_pathway : null,
    childhood_gh_deficiency_diagnosed: exactBoolean(facts.childhood_gh_deficiency_diagnosed),
    childhood_gh_treatment_received: exactBoolean(facts.childhood_gh_treatment_received),
    gh_stopped_due_to_epiphyseal_closure: exactBoolean(facts.gh_stopped_due_to_epiphyseal_closure),
    adult_hypothalamic_pituitary_gh_deficiency_suspected:
      exactBoolean(facts.adult_hypothalamic_pituitary_gh_deficiency_suspected),
    additional_anterior_pituitary_deficiency_confirmed:
      exactBoolean(facts.additional_anterior_pituitary_deficiency_confirmed),
    itt_contraindicated: exactBoolean(facts.itt_contraindicated),
    two_distinct_stimulation_procedures_documented: exactBoolean(facts.two_distinct_stimulation_procedures_documented),
    stimulation_tests: Array.isArray(tests) && tests.length <= 20 ? Array.from(tests, stimulationTest) : null,
  };
}
