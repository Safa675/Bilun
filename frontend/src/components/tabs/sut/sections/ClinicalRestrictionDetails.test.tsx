import { describe, expect, it } from "vitest";
import type { SutClinicalRestriction } from "@/lib/api/clinicalEvidence";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { ClinicalRestrictionDetails } from "./ClinicalRestrictionDetails";

const restriction: SutClinicalRestriction & { raw_evidence: string; savings_try: number } = {
  constraint_set: "sma_safety_2025", criterion_status: "restriction_not_met",
  missing_inputs: ["sma_evidence.hypoxic_birth_neurological_sequelae"],
  checks: [{ field: "sma_evidence.bacterial_meningitis_history", status: "fail" },
    { field: "drug_report_duration_months", status: "pass" },
    { field: "sma_evidence.hypoxic_birth_neurological_sequelae", status: "unknown" }],
  source_refs: ["4.2.49.(4)#d9c6cd1d"],
  clinical_eligibility_complete: false, verification_status: "ai_generated_pending_review",
  checks_truncated: true, source_refs_truncated: false,
  raw_evidence: "PRIVATE_CLINICAL_SENTINEL", savings_try: 987654321,
};

describe("bounded clinical evidence display", () => {
  it.each(["en", "tr"] as const)("renders only bounded check statuses and honest partial scope in %s", locale => {
    const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[restriction]}
      selectedRuleId="rule:actual-selected-source" />, locale);
    expect(html).toContain("rule:actual-selected-source");
    expect(html).toContain("4.2.49.(4)#d9c6cd1d");
    if (locale === "en") {
      expect(html).toContain("Current bacterial meningitis or history of it");
      expect(html).toContain("Requirement not met");
      expect(html).toContain("Missing evidence");
      expect(html).toContain("Source interpretation pending review");
      expect(html).toContain("do not establish full clinical or reimbursement eligibility");
      expect(html).toContain("Some evidence details are omitted");
    } else {
      expect(html).toContain("Mevcut bakteriyel menenjit veya öyküsü");
      expect(html).toContain("Koşul karşılanmadı");
      expect(html).toContain("Eksik kanıt");
      expect(html).toContain("Kaynak yorumunun incelemesi bekleniyor");
    }
    expect(html).not.toContain("PRIVATE_CLINICAL_SENTINEL");
    expect(html).not.toContain("987654321");
    expect(html).not.toContain("sections.claimValidator.");
  });
  it("does not turn a passed limited check into complete clearance", () => {
    const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[
      { ...restriction, criterion_status: "criterion_clear", missing_inputs: [], checks_truncated: false },
    ]} />);
    expect(html).toContain("This limited check passed");
    expect(html).toContain("do not establish full clinical or reimbursement eligibility");
    expect(html).not.toContain("Fully eligible");
  });
  it("keeps old responses without clinical restrictions visually unchanged", () => {
    expect(renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[]} />)).toBe("");
  });
});

it("labels the ravulizumab computed EDSS stop check without exposing it as a user input", () => {
  const data: SutClinicalRestriction = { ...restriction, constraint_set: "ravulizumab_nmosd_continuation_2026",
    checks: [{ field: "ravulizumab_evidence.six_month_edss_stop", status: "fail" }],
    missing_inputs: ["ravulizumab_evidence.edss_in_report"], source_refs: [] };
  const english = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[data]} />);
  const turkish = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[data]} />, "tr");
  expect(english).toContain("Six-month EDSS continuation requirement");
  expect(english).toContain("Requirement not met");
  expect(turkish).toContain("Altıncı ay EDSS devam tedavisi koşulu");
  expect(english).not.toContain("<input");
  expect(english).not.toContain("Fully eligible");
});

it("renders response prerequisites and a limited follow-up check without a payment conclusion", () => {
  const data: SutClinicalRestriction = { ...restriction, constraint_set: "followup_source_constraints",
    checks: [{ field: "followup_evidence.response_easi", status: "pass" }],
    missing_inputs: ["followup_evidence.documented_16_week_response"], source_refs: ["4.2.57.(2)#af1ccf61"] };
  const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[data]} />);
  expect(html).toContain("Treatment response and annual reassessment conditions");
  expect(html).toContain("EASI at the week-16 checkpoint");
  expect(html).toContain("Documented response after 16 completed treatment weeks");
  expect(html).toContain("do not establish full clinical or reimbursement eligibility");
  expect(html).not.toContain("sections.claimValidator.");
});
