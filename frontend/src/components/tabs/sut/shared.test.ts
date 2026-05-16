import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

vi.mock("@/lib/constants", () => ({
  ACCENT: "#059669",
}));

let shared: typeof import("./shared");

beforeAll(async () => {
  shared = await import("./shared");
});

describe("SUT shared formatting", () => {
  it("formats TRY values with the en-US locale strategy", () => {
    expect(shared.fmtTRY(1836)).toBe("1,836 TRY");
    expect(shared.fmtTRY2(1836)).toBe("1,836.00 TRY");
    expect(shared.fmtTRYOrUnavailable(null)).toBe("Unavailable");
    expect(shared.fmtTRY2OrUnavailable(undefined)).toBe("Unavailable");
    expect(shared.fmtNumOrUnavailable(null)).toBe("Unavailable");
  });

  it("formats label enums in title case", () => {
    expect(shared.fmtLabel("top_action_type")).toBe("Top Action Type");
    expect(shared.fmtPriorityLabel("very_high")).toBe("Very High");
    expect(shared.fmtRiskLabel("medium")).toBe("Medium risk");
  });

  it("formats percentages consistently", () => {
    expect(shared.fmtPct(12.34)).toBe("12.3%");
    expect(shared.fmtPct(12.34, 0)).toBe("12%");
  });
});

describe("SUT patient outcome view state", () => {
  it("returns the correct state for retryable and ready flows", () => {
    expect(
      shared.getSutOutcomeViewState({
        selectedPatientId: null,
        loading: false,
        error: null,
        hasData: false,
      }),
    ).toBe("idle");

    expect(
      shared.getSutOutcomeViewState({
        selectedPatientId: "P1",
        loading: true,
        error: null,
        hasData: false,
      }),
    ).toBe("loading");

    expect(
      shared.getSutOutcomeViewState({
        selectedPatientId: "P1",
        loading: false,
        error: "boom",
        hasData: false,
      }),
    ).toBe("error");

    expect(
      shared.getSutOutcomeViewState({
        selectedPatientId: "P1",
        loading: false,
        error: null,
        hasData: false,
      }),
    ).toBe("empty");

    expect(
      shared.getSutOutcomeViewState({
        selectedPatientId: "P1",
        loading: false,
        error: null,
        hasData: true,
      }),
    ).toBe("ready");
  });
});
