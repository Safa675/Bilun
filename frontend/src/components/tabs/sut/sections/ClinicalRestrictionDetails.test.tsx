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


it.each(["en", "tr"] as const)("renders indication source uncertainties and computed ALT interval in %s", locale => {
  const data: SutClinicalRestriction = { ...restriction, constraint_set: "other_indication_source_constraints",
    criterion_status: "unknown", checks: [{ field: "indication_evidence.alt_retest_interval", status: "unknown" }],
    missing_inputs: ["indication_evidence.histology_scoring_source_compatibility", "indication_evidence.hbv_noninvasive_boolean_grouping"],
    source_refs: ["4.2.13.1.(1)"] };
  const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[data]} />, locale);
  expect(html).toContain(locale === "en" ? "needs source review" : "kaynak incelemesi gerektiriyor");
  expect(html).toContain(locale === "en" ? "between the two ALT measurements" : "İki ALT ölçümü");
  expect(html).not.toContain("sections.claimValidator.");
  expect(html).not.toContain("PRIVATE_CLINICAL_SENTINEL");
});


it.each(["en", "tr"] as const)("renders the source-context guard as incomplete review without fabricating checked criteria in %s", locale => {
  const data: SutClinicalRestriction = { ...restriction, constraint_set: "source_context_clinical_review",
    criterion_status: "unknown", checks: [], checks_truncated: false,
    missing_inputs: ["remaining_sut_clinical_criteria"], source_refs: ["4.2.synthetic.source"] };
  const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[data]} />, locale);
  expect(html).toContain(locale === "en" ? "Remaining SUT clinical criteria require review" : "Diğer SUT klinik koşulları için inceleme gerekli");
  expect(html).toContain(locale === "en" ? "Missing evidence" : "Eksik kanıt");
  expect(html).not.toContain("This limited check passed");
  expect(html).not.toContain("source_context_clinical_review");
  expect(html).not.toContain("sections.claimValidator.");
  expect(html).not.toContain("PRIVATE_CLINICAL_SENTINEL");
});

const authority = {
  schema_version: 1 as const, status: "admitted" as const, reason: "covered" as const,
  family_id: "sma", version_id: "reviewed-source-version", service_date: "2026-10-03",
  legal_effective_from: "2025-03-25", source_observed_on: "2026-10-02",
  admission_basis: "reviewed_continuity" as const,
  admitted_from: "2026-10-03", admitted_through: "2026-10-03",
  official_review_checked_at: "2026-10-03T06:00:00Z", review_id: "test-review",
  next_action: "Retrieve and review the official source for the service date.",
  scope: "named_clinical_report_checks_only" as const,
  clinical_eligibility_complete: false as const,
  verification_status: "ai_generated_pending_review" as const,
};

it.each(["en", "tr"] as const)("separates observed, legal and admission dates with limited authority in %s", locale => {
  const source = { ...authority, raw_evidence: "PRIVATE_SOURCE_SENTINEL", savings_try: 987654321 };
  const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[
    { ...restriction, source_authority: source },
  ]} />, locale);
  const labels = locale === "en" ? [
    "Source admitted for these limited checks", "Only the named necessary clinical/report checks are covered.",
    "Source observed on: 2026-10-02", "Recorded legal effective date: 2025-03-25",
    "Source admission starts: 2026-10-03", "Source admission checked through: 2026-10-03",
    "Official-source review checked at: 2026-10-03T06:00:00Z",
  ] : [
    "Kaynak bu sınırlı kontroller için kabul edildi", "Yalnızca belirtilen gerekli klinik/rapor kontrollerini kapsar.",
    "Kaynağın gözlemlendiği tarih: 2026-10-02", "Kayıtlı hukuki yürürlük tarihi: 2025-03-25",
    "Kaynak kabul başlangıcı: 2026-10-03", "Kaynak kabulünün kontrol edildiği son tarih: 2026-10-03",
    "Resmi kaynak inceleme zamanı: 2026-10-03T06:00:00Z",
  ];
  for (const label of labels) expect(html).toContain(label);
  expect(html).not.toContain("PRIVATE_SOURCE_SENTINEL");
  expect(html).not.toContain("987654321");
  expect(html).not.toContain("Fully eligible");
  expect(html).not.toContain("sections.claimValidator.");
});

it.each(["en", "tr"] as const)("shows blocked-source action and last checked admission date in %s", locale => {
  const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[]}
    sourceAuthority={{ ...authority, status: "review_required", reason: "uncovered_service_date",
      admission_basis: null, service_date: "2026-10-04" }} />, locale);
  expect(html).toContain(locale === "en" ? "Source and service date require review" : "Kaynak ve hizmet tarihi için inceleme gerekli");
  expect(html).toContain(locale === "en" ? "Next action" : "Sonraki adım");
  expect(html).toContain(authority.next_action);
  expect(html).toContain("2026-10-04");
  expect(html).toContain("2026-10-03");
  expect(html).not.toContain("Source admitted for these limited checks");
  expect(html).not.toContain("This limited check passed");
});

it("keeps legacy source absence absent instead of inventing currentness", () => {
  const html = renderToStaticMarkupWithLocale(<ClinicalRestrictionDetails restrictions={[restriction]} />);
  expect(html).not.toContain("Source admitted for these limited checks");
  expect(html).not.toContain("Source observed on");
  expect(html).not.toContain("Source admission checked through");
});
