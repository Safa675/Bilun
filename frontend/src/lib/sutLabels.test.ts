import { describe, expect, it } from "vitest";

import {
  getSutRiskTierLabel,
  getSutSeverityLabel,
  SUT_ACTION_LABELS,
  SUT_ALERT_BADGE_LABELS,
  SUT_RISK_BUCKET_LABELS,
} from "./sutLabels";

describe("sutLabels", () => {
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
});
