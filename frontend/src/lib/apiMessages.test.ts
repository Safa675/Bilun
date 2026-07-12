import { beforeEach, describe, expect, it } from "vitest";
import { setModuleLocale } from "@/lib/i18n/localeModule";
import {
  formatRequiredInputsLocalized,
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
});
