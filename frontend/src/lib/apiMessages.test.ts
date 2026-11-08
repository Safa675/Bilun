import { beforeEach, describe, expect, it } from "vitest";
import { setModuleLocale } from "@/lib/i18n/localeModule";
import { translate } from "@/lib/i18n/translate";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import {
  formatRequiredInputsLocalized,
  translateApiText,
  translateMethodology,
  translateStructuredApiMessage,
  translateUnavailableReason,
  translateValidationMessage,
  translateValidationSummary,
} from "./apiMessages";

type TranslateParams = Record<string, string | number | undefined | null>;

const enT = (key: string, params?: TranslateParams) =>
  translate(enMessages, key, params);
const trT = (key: string, params?: TranslateParams) =>
  translate(trMessages, key, params);

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

  it.each([
    [
      "en",
      "Pre-authorization review requested by the material-line input flag; EK-3C-1 catalog membership not verified",
    ],
    [
      "tr",
      "Malzeme satırında girilen işaret nedeniyle ön onay incelemesi istendi; EK-3C-1 listesinde bulunduğu doğrulanmadı.",
    ],
  ] as const)("localizes only the known material input-flag note in %s", (locale, expected) => {
    setModuleLocale(locale);
    const note =
      "Pre-authorization review requested by the material-line input flag; EK-3C-1 catalog membership not verified";
    const row = Object.freeze({ detail: note });

    expect(translateApiText(note)).toBe(expected);
    expect(translateStructuredApiMessage(locale === "tr" ? trT : enT, row)).toBe(expected);
    expect(row.detail).toBe(note);
    expect(translateApiText(`${note}; additional source text`)).toBe(
      `${note}; additional source text`,
    );
    const sourceText = "EK-3C-1 özgün kaynak metni";
    expect(translateApiText(sourceText)).toBe(sourceText);
    expect(translateApiText(enMessages.api.billingProse.preauthNote)).toBe(
      (locale === "tr" ? trMessages : enMessages).api.billingProse.preauthNote,
    );
  });

  it("translates billing prose and LLM errors in Turkish", () => {
    setModuleLocale("tr");
    expect(
      translateApiText(
        "Standart yatak (510010): 16 billable bed-day(s) (gross LOS 17 day(s) at 222.36 TRY/day, surgery day 2024-10-11 bundled into EK-2/C package) = 3557.76 TRY (inclusive LOS, discharge day billed).",
      ),
    ).toContain("faturalanabilir yatak-günü");
    // §2.2 cluster regex parsers were removed (Aşama 3 cutover): bare prose
    // now passes through unchanged — structured rows carry message_code and
    // render via translateStructuredApiMessage instead.
    expect(
      translateApiText(
        "Claim F-SENTETIK-HASTA-0001-001 is billed correctly as package per SUT §2.2.2(1). Package total 8705.13 TRY.",
      ),
    ).toBe(
      "Claim F-SENTETIK-HASTA-0001-001 is billed correctly as package per SUT §2.2.2(1). Package total 8705.13 TRY.",
    );
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
    ).toBe(
      "Claim F-SENTETIK-HASTA-0003-011: optional §2.2.2(2) override — package billing (9000.00 TRY) is the higher legal option vs itemized (2700.00 TRY).",
    );
    expect(
      translateMethodology(
        "Aggregated per-patient DRG unbundling findings from exact claim lines with SUT §2.2 prose rule checks.",
      ),
    ).toContain("DRG paket ayrıştırma");
  });
});

describe("translateStructuredApiMessage (§2.2 message contract)", () => {
  beforeEach(() => {
    setModuleLocale("en");
  });

  it("renders each §2.2 message code in English", () => {
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "claim_package_ok",
        message_params: { claim_id: "C1", amount_try: "8705.13" },
      }),
    ).toBe(
      "Claim C1 is billed correctly as package per SUT §2.2.2(1). Package total 8705.13 TRY.",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "claim_mandate_package",
        message_params: {
          claim_id: "C1",
          package_total_try: "1000.00",
          itemized_total_try: "900.00",
        },
      }),
    ).toBe(
      "SUT §2.2 mandates package billing for claim C1 (EK-2/C procedure present). Package total 1000.00 TRY vs itemized 900.00 TRY.",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "claim_mandate_itemized",
        message_params: {
          claim_id: "C1",
          itemized_total_try: "900.00",
          package_total_try: "800.00",
        },
      }),
    ).toBe(
      "SUT §2.2 mandates itemized billing for claim C1. Itemized total 900.00 TRY vs package 800.00 TRY.",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "claim_optional_package_higher",
        message_params: {
          claim_id: "C1",
          package_total_try: "9000.00",
          itemized_total_try: "2700.00",
        },
      }),
    ).toBe(
      "Claim C1: optional §2.2.2(2) override — package billing (9000.00 TRY) is the higher legal option vs itemized (2700.00 TRY).",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "claim_optional_itemized_higher",
        message_params: {
          claim_id: "C1",
          itemized_total_try: "9000.00",
          package_total_try: "2700.00",
        },
      }),
    ).toBe(
      "Claim C1: optional §2.2.2(2) override — itemized billing (9000.00 TRY) is the higher legal option vs package (2700.00 TRY).",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "procedure_must_package",
        message_params: {
          procedure_code: "610070",
          method: "tanıya dayalı işlem üzerinden ödeme",
          section: "2.2.2.(1)",
        },
      }),
    ).toBe(
      "Procedure 610070 must use package billing (tanıya dayalı işlem üzerinden ödeme) per 2.2.2.(1).",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "procedure_must_itemized",
        message_params: {
          procedure_code: "600150",
          method: "hizmet başına ödeme",
          section: "2.2.1.B-1.b",
        },
      }),
    ).toBe(
      "Procedure 600150 must use itemized billing (hizmet başına ödeme) per 2.2.1.B-1.b.",
    );
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "material_copay_rate",
        message_params: { rate_pct: 20 },
      }),
    ).toBe("SUT §1.8.3(2) material copay reference rate: 20%");
    expect(
      translateStructuredApiMessage(enT, { message_code: "ek1a_report_unknown", detail: "x" }),
    ).toBe(
      "EK-1/A diagnosis matched; chronic health report status unknown, so the §1.8.5(7) waiver is not claimed.",
    );
    expect(
      translateStructuredApiMessage(enT, { message_code: "ek1a_report_missing", detail: "x" }),
    ).toBe(
      "EK-1/A diagnosis matched; no chronic health report on file, so the §1.8.5(7) waiver is not claimed.",
    );
  });

  it("renders each §2.2 message code in Turkish", () => {
    setModuleLocale("tr");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "claim_package_ok",
        message_params: { claim_id: "C1", amount_try: "8705.13" },
      }),
    ).toContain("paket olarak doğru faturalandırılmış");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "claim_mandate_package",
        message_params: {
          claim_id: "C1",
          package_total_try: "1000.00",
          itemized_total_try: "900.00",
        },
      }),
    ).toContain("paket faturalandırmayı zorunlu kılar");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "claim_mandate_itemized",
        message_params: {
          claim_id: "C1",
          itemized_total_try: "900.00",
          package_total_try: "800.00",
        },
      }),
    ).toContain("kalemli faturalandırmayı zorunlu kılar");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "claim_optional_package_higher",
        message_params: {
          claim_id: "C1",
          package_total_try: "9000.00",
          itemized_total_try: "2700.00",
        },
      }),
    ).toContain("paket faturalandırma (9000.00 ₺)");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "claim_optional_itemized_higher",
        message_params: {
          claim_id: "C1",
          itemized_total_try: "9000.00",
          package_total_try: "2700.00",
        },
      }),
    ).toContain("kalemli faturalandırma (9000.00 ₺)");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "procedure_must_package",
        message_params: {
          procedure_code: "610070",
          method: "tanıya dayalı işlem üzerinden ödeme",
          section: "2.2.2.(1)",
        },
      }),
    ).toContain("paket faturalandırma kullanmalıdır");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "procedure_must_itemized",
        message_params: {
          procedure_code: "600150",
          method: "hizmet başına ödeme",
          section: "2.2.1.B-1.b",
        },
      }),
    ).toContain("kalemli faturalandırma kullanmalıdır");
    expect(
      translateStructuredApiMessage(trT, {
        message_code: "material_copay_rate",
        message_params: { rate_pct: 20 },
      }),
    ).toContain("%20");
    expect(
      translateStructuredApiMessage(trT, { message_code: "ek1a_report_unknown", detail: "x" }),
    ).toBe(
      "EK-1/A tanısı eşleşti; kronik hastalık raporu durumu bilinmiyor, bu yüzden §1.8.5(7) muafiyeti öne sürülmüyor.",
    );
    expect(
      translateStructuredApiMessage(trT, { message_code: "ek1a_report_missing", detail: "x" }),
    ).toBe(
      "EK-1/A tanısı eşleşti; kayıtlı kronik hastalık raporu yok, bu yüzden §1.8.5(7) muafiyeti öne sürülmüyor.",
    );
  });

  it("falls back to prose translation when the code is unknown or absent", () => {
    // Unknown code → falls back to translateApiText(row.detail).
    expect(
      translateStructuredApiMessage(enT, {
        message_code: "not_a_real_code",
        detail: "Some untranslated detail.",
      }),
    ).toBe("Some untranslated detail.");

    // Missing code + missing detail → empty string.
    expect(translateStructuredApiMessage(enT, {})).toBe("");
    expect(translateStructuredApiMessage(enT, null)).toBe("");

    // The fallback path still runs the remaining prose matchers: the
    // exact-string sibling "Billed correctly as package." is NOT part of the
    // removed §2.2 regex cluster and keeps translating.
    setModuleLocale("tr");
    expect(
      translateStructuredApiMessage(trT, {
        detail: "Billed correctly as package.",
      }),
    ).toBe("Paket olarak doğru faturalandırılmış.");
  });
});
