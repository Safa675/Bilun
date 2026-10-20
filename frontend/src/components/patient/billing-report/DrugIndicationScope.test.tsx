import { beforeEach, describe, expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport, DrugIndicationLineEvaluation } from "@/lib/domains/sut";
import { setModuleLocale } from "@/lib/i18n/localeModule";
import { translateUnavailableReason } from "@/lib/apiMessages";
import { DrugIndicationReviewSection } from "./DrugIndicationReviewSection";
import { buildDrugIndicationSectionModel } from "./DrugIndicationReviewSection.model";

type Review = NonNullable<BillingActionReport["drug_indication"]>;

function line(
  name: string,
  applicability: string,
  scope: DrugIndicationLineEvaluation["ingredient_scope"],
): DrugIndicationLineEvaluation {
  return {
    patient_id: "P-1",
    claim_id: "C-1",
    drug_claim_line_id: `D-${name}`,
    drug_name: name,
    applicability_status: applicability,
    evaluation_status: applicability === "no_sut_restriction_found" ? "evaluated" : "unavailable",
    observed_icd10_codes: [],
    matched_icd10_codes: [],
    unmatched_icd10_codes: [],
    eligible_routes: [],
    required_inputs: [],
    missing_inputs: [],
    ingredient_scope: scope,
  };
}

const PLAIN = line("IESEF 1 G IV", "no_sut_restriction_found", {
  result: "not_named_in_sut",
  ingredients: ["seftriakson"],
  named_ingredients: [],
  sut_sections: [],
  class_sections: [],
});
const CLASS_LEVEL = line("CLEXANE 4000", "not_in_encoded_corpus", {
  result: "class_level_in_sut",
  ingredients: ["enoksaparin"],
  named_ingredients: [],
  sut_sections: [],
  class_sections: ["4.2.7"],
});
const NAMED = line("RIVAROKS 20 MG", "not_in_encoded_corpus", {
  result: "named_in_sut",
  ingredients: ["rivaroksaban"],
  named_ingredients: ["rivaroksaban"],
  sut_sections: ["4.2.15.D", "4.2.15.D-1"],
  class_sections: [],
});
const UNKNOWN = line("BILINMEYEN", "not_in_encoded_corpus", {
  result: "ingredient_unknown",
  ingredients: [],
  named_ingredients: [],
  sut_sections: [],
  class_sections: [],
});

function review(evaluations: DrugIndicationLineEvaluation[], overrides: Partial<Review> = {}): Review {
  return {
    exactness_status: "partial_exact",
    unavailable_reason: null,
    required_inputs_missing: [],
    violations: [],
    findings: [],
    evaluations,
    violation_count: 0,
    error_count: 0,
    ...overrides,
  };
}

describe("drug indication: no SUT restriction found vs restricted but not encoded", () => {
  beforeEach(() => setModuleLocale("en"));

  it("flags a review made only of plain drugs as such, not as corpus noncoverage", () => {
    const model = buildDrugIndicationSectionModel(review([PLAIN, { ...PLAIN, drug_claim_line_id: "D-2" }]));
    expect(model.display).toMatchObject({
      kind: "evaluations",
      hasCorpusNoncoverage: false,
      allNoSutRestriction: true,
    });
  });

  it("keeps the corpus-noncoverage flag when one line is restricted but not encoded", () => {
    const model = buildDrugIndicationSectionModel(review([PLAIN, CLASS_LEVEL]));
    expect(model.display).toMatchObject({
      kind: "evaluations",
      hasCorpusNoncoverage: true,
      allNoSutRestriction: false,
    });
  });

  it("does not call a clean encoded evaluation a no-restriction result", () => {
    const encoded = line("AVASTIN", "route_matched", undefined);
    const model = buildDrugIndicationSectionModel(review([encoded]));
    expect(model.display).toMatchObject({ kind: "evaluations", allNoSutRestriction: false, hasCorpusNoncoverage: false });
  });

  it("says in Turkish that no clause names the ingredient and asks for no review", () => {
    const html = renderToStaticMarkupWithLocale(<DrugIndicationReviewSection reviewData={review([PLAIN])} />, "tr");
    expect(html).toContain("Bu etken maddeleri adıyla anan bir SUT hükmü bulunamadı");
    // Once in the summary and once in the opened detail panel.
    expect(html.split("Bu etken maddeleri adıyla anan bir SUT hükmü bulunamadı").length - 1).toBe(2);
    expect(html).toContain("manuel inceleme istenmez");
    expect(html).toContain("ilaç sınıfı için yazılmış kısıtlar");
    expect(html).not.toContain("değerlendiremiyor");
    expect(html).not.toContain("manuel inceleyin");
    expect(html).toContain("IESEF 1 G IV");
  });

  it("says in English that no clause names the ingredient and states the limit", () => {
    const html = renderToStaticMarkupWithLocale(<DrugIndicationReviewSection reviewData={review([PLAIN])} />, "en");
    expect(html).toContain("No SUT clause naming these active ingredients was found");
    expect(html).toContain("No manual review is requested by default");
    expect(html).toContain("whole drug class");
    expect(html).not.toContain("cannot evaluate this drug");
  });

  it("labels each line of a mixed review with what the SUT says about it", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection reviewData={review([PLAIN, CLASS_LEVEL, NAMED, UNKNOWN])} />,
      "tr",
    );
    expect(html).toContain("Kodlanmış kural derlemi bu ilacı değerlendiremiyor");
    expect(html).toContain("bu etken maddeyi adıyla anan hüküm yok");
    expect(html).toContain("§4.2.7");
    expect(html).toContain("§4.2.15.D, §4.2.15.D-1");
    expect(html).toContain("etken madde belirlenemedi");
    expect(html.match(/manuel inceleyin/g)?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("labels lines in English too", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection reviewData={review([PLAIN, CLASS_LEVEL, NAMED, UNKNOWN])} />,
      "en",
    );
    expect(html).toContain("no SUT clause names this active ingredient");
    expect(html).toContain("restricts this drug class");
    expect(html).toContain("named in SUT §4.2.15.D");
    expect(html).toContain("active ingredient could not be determined");
  });

  it("keeps the old wording for a line the corpus did not decide and no scope describes", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection reviewData={review([line("UNENCODED", "not_in_encoded_corpus", undefined)])} />,
      "tr",
    );
    expect(html).toContain("Kodlanmış kural derlemi bu ilacı değerlendiremiyor");
    expect(html).toContain("UNENCODED");
  });
});

describe("drug indication block reasons are localized", () => {
  const corpus =
    "Drug is not covered by the encoded Drug Indication corpus; manual SUT review is required and no financial value is inferred.";
  const unknown =
    "The active ingredient of a drug outside the encoded Drug Indication corpus could not be determined, so the SUT text could not be checked; manual SUT review is required and no financial value is inferred.";
  const nameCheck =
    "Drug lines outside the encoded Drug Indication corpus were checked only by active ingredient name against the SUT text: no clause names the ingredient, but restrictions written for a whole drug class without naming the ingredient cannot be detected. No manual review is requested by default and no financial value is inferred.";

  it("returns the English text in English", () => {
    setModuleLocale("en");
    expect(translateUnavailableReason(corpus)).toBe(corpus);
    expect(translateUnavailableReason(unknown)).toBe(unknown);
    expect(translateUnavailableReason(nameCheck)).toBe(nameCheck);
  });

  it("returns Turkish text in Turkish", () => {
    setModuleLocale("tr");
    expect(translateUnavailableReason(corpus)).toContain("manuel SUT incelemesi gerekir");
    expect(translateUnavailableReason(unknown)).toContain("etken maddesi belirlenemedi");
    const translated = translateUnavailableReason(nameCheck);
    expect(translated).toContain("manuel inceleme istenmez");
    expect(translated).toContain("ilaç sınıfı");
  });
});
