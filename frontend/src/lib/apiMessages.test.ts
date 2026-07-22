import { beforeEach, describe, expect, it } from "vitest";
import { setModuleLocale } from "@/lib/i18n/localeModule";
import {
  formatRequiredInputsLocalized,
  translateApiText,
  translateMethodology,
  translateUnavailableReason,
  translateValidationMessage,
  translateValidationSummary,
} from "./apiMessages";

describe("apiMessages", () => {
  beforeEach(() => {
    setModuleLocale("en");
  });

  it("translates unavailable reason codes and prose", () => {
    expect(translateUnavailableReason("exact_claim_lines_missing_for_patient")).toBe(
      "Exact claim lines are missing for this patient.",
    );
    expect(
      translateUnavailableReason(
        "Surcharge compliance requires exact billed procedure codes and procedure dates, which are not available in the active SUT runtime inputs.",
      ),
    ).toContain("Surcharge compliance requires");
  });

  it("translates methodology prose from the API", () => {
    expect(
      translateMethodology(
        "Aggregated per-patient DRG unbundling findings from exact claim lines with SUT §2.2 prose rule checks.",
      ),
    ).toContain("Aggregated per-patient DRG unbundling");
  });

  it("localizes required input labels and validation templates in Turkish", () => {
    setModuleLocale("tr");
    expect(formatRequiredInputsLocalized(["billed_procedure_codes", "procedure_dates"])).toBe(
      "faturalandırılmış işlem kodları, işlem tarihleri",
    );
    expect(
      translateValidationMessage(
        "'Stent' is bundled into the procedure price (EK-3B-1: Kardiyoloji, match=exact). Cannot be billed separately.",
      ),
    ).toContain("paketlenmiştir");
    expect(translateValidationSummary("Claim CLM-001: VALID | 2 materials, 10.00 TRY total")).toContain(
      "GEÇERLİ",
    );
  });

  it("passes through unrecognized strings unchanged (preserves backend content)", () => {
    // Unrecognized content passes through so legitimate domain text (often
    // already localized by the backend) is not lost behind a placeholder.
    expect(translateUnavailableReason("some_unknown_reason_code")).toBe("some_unknown_reason_code");
    expect(translateValidationMessage("Unrecognized violation text.")).toBe(
      "Unrecognized violation text.",
    );

    setModuleLocale("tr");
    // Turkish backend content passes through verbatim.
    expect(translateValidationMessage("Uzmanlık sağlık kurulu raporu eksik")).toBe(
      "Uzmanlık sağlık kurulu raporu eksik",
    );
  });

  it("translates billing prose and LLM errors in Turkish", () => {
    setModuleLocale("tr");
    expect(
      translateApiText(
        "Standart yatak (510010): 16 billable bed-day(s) (gross LOS 17 day(s) at 222.36 TRY/day, surgery day 2024-10-11 bundled into EK-2/C package) = 3557.76 TRY (inclusive LOS, discharge day billed).",
      ),
    ).toContain("faturalanabilir yatak-günü");
    expect(
      translateApiText(
        "Claim F-SENTETIK-HASTA-0001-001 is billed correctly as package per SUT §2.2.2(1). Package total 8705.13 TRY.",
      ),
    ).toContain("paket olarak doğru");
    expect(
      translateApiText(
        "SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions · SUT §1.8.5(5) emergency visit copay waiver (520021 excluded)",
      ),
    ).toContain("kronik hastalık");
    expect(
      translateApiText(
        '⚠️ API error 401: {"error":{"message":"User not found.","code":401}}',
      ),
    ).toContain("kimlik doğrulaması");
    expect(
      translateApiText(
        "Claim F-SENTETIK-HASTA-0003-011: optional §2.2.2(2) override — package billing (9000.00 TRY) is the higher legal option vs itemized (2700.00 TRY).",
      ),
    ).toContain("isteğe bağlı");
    expect(
      translateMethodology(
        "Aggregated per-patient DRG unbundling findings from exact claim lines with SUT §2.2 prose rule checks.",
      ),
    ).toContain("DRG paket ayrıştırma");
  });
});
