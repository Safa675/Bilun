import { beforeEach, describe, expect, it } from "vitest";
import { setModuleLocale } from "@/lib/i18n/localeModule";

import {
  getSutDomainLabel,
  getSutRiskTierLabel,
  getSutSeverityLabel,
  SUT_ACTION_LABELS,
  SUT_ALERT_BADGE_LABELS,
  SUT_RISK_BUCKET_LABELS,
} from "./sutLabels";

describe("sutLabels", () => {
  beforeEach(() => {
    setModuleLocale("en");
  });

  it("returns centralized alert and action labels", () => {
    expect(SUT_ALERT_BADGE_LABELS.exempt).toBe("Exempt");
    expect(SUT_ALERT_BADGE_LABELS.notExempt).toBe("Not exempt");
    expect(SUT_ACTION_LABELS.noActionNeeded).toBe("No action needed");
  });

  it("returns centralized risk labels", () => {
    expect(SUT_RISK_BUCKET_LABELS.atRisk).toBe("At risk");
    expect(SUT_RISK_BUCKET_LABELS.noRisk).toBe("No risk");
    expect(getSutRiskTierLabel("high")).toBe("High risk");
    expect(getSutRiskTierLabel("medium")).toBe("Medium risk");
  });

  it("normalizes severity labels", () => {
    expect(getSutSeverityLabel("warning")).toBe("Warning");
    expect(getSutSeverityLabel("info")).toBe("Info");
    expect(getSutSeverityLabel("custom_state")).toBe("Custom State");
  });

  it("maps rule and action type labels in Turkish", () => {
    setModuleLocale("tr");
    expect(getSutDomainLabel("surcharge")).toBe("İlave ücret");
  });

  // The cohort table's "Top action" column renders top_action_type through getSutDomainLabel; a value
  // without a label would be title-cased ("Anestezi Puani") instead of named.
  it.each([
    ["anestezi_puani", "Anesthesia score", "Anestezi puanı"],
    ["refakatci", "Companion allowance", "Refakatçi ücreti"],
    ["icu_puani", "Intensive care score", "Yoğun bakım puanı"],
    ["yenidogan_yatak", "Newborn bed-day score", "Yenidoğan yatak günü puanı"],
  ])("labels the cohort top action %s in English and Turkish", (value, english, turkish) => {
    expect(getSutDomainLabel(value)).toBe(english);
    setModuleLocale("tr");
    expect(getSutDomainLabel(value)).toBe(turkish);
  });
});
