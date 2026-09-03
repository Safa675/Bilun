import { describe, expect, it } from "vitest";
import { isBackgroundTabPointer, patientViewFromHref, backgroundOpenKind } from "./patientTabOpen";

describe("isBackgroundTabPointer", () => {
  it("treats ctrl, meta, and middle-click as background open", () => {
    expect(isBackgroundTabPointer({ metaKey: false, ctrlKey: false, button: 0 })).toBe(false);
    expect(isBackgroundTabPointer({ metaKey: false, ctrlKey: true, button: 0 })).toBe(true);
    expect(isBackgroundTabPointer({ metaKey: true, ctrlKey: false, button: 0 })).toBe(true);
    expect(isBackgroundTabPointer({ metaKey: false, ctrlKey: false, button: 1 })).toBe(true);
  });
});

describe("patientViewFromHref", () => {
  it("keeps claim and section query on the patient tab", () => {
    expect(
      patientViewFromHref("/patient/P-001?claim=C1&section=billing-copay", "P-001"),
    ).toEqual({
      kind: "patient",
      refId: "P-001",
      query: "claim=C1&section=billing-copay",
    });
  });

  it("omits query when the href is a bare profile", () => {
    expect(patientViewFromHref("/patient/P-001", "P-001")).toEqual({
      kind: "patient",
      refId: "P-001",
    });
  });
});

describe("backgroundOpenKind", () => {
  it("adds when the patient is not already a strip tab, switches when it is", () => {
    expect(
      backgroundOpenKind([], { kind: "patient", refId: "P-001" }),
    ).toBe("add");
    expect(
      backgroundOpenKind([{ id: "patient:P-001" }], { kind: "patient", refId: "P-001" }),
    ).toBe("switch");
  });
});
