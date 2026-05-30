import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentDark: "#047857",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

import {
  buildSutHomeHref,
  buildSutBillingHref,
  buildSutPatientHref,
  parseSutHomeTab,
  SUT_HOME_TABS,
} from "./constants";
import {
  buildCohortPatientIdSet,
  cohortFilterIsActive,
  matchesCohortFilter,
  parseCohortFilter,
} from "./cohortFilter";

describe("sut constants", () => {
  it("parses home tab query parameters safely", () => {
    expect(parseSutHomeTab("patients")).toBe("patients");
    expect(parseSutHomeTab("compliance")).toBe("compliance");
    expect(parseSutHomeTab("revenue")).toBe("revenue");
    expect(parseSutHomeTab("reference-tools")).toBe("reference-tools");
    expect(parseSutHomeTab("analytics")).toBe("patients");
    expect(parseSutHomeTab("optimizer")).toBe("compliance");
    expect(parseSutHomeTab("unknown")).toBe("patients");
    expect(parseSutHomeTab(null)).toBe("patients");
  });

  it("builds split SUT navigation routes", () => {
    expect(buildSutHomeHref("patients")).toBe("/?tab=patients");
    expect(buildSutHomeHref("compliance")).toBe("/?tab=compliance");
    expect(buildSutHomeHref("revenue")).toBe("/?tab=revenue");
    expect(buildSutHomeHref("reference-tools")).toBe("/?tab=reference-tools");
    expect(buildSutPatientHref("A 123/45")).toBe("/patient/A%20123%2F45");
    expect(buildSutBillingHref("A 123/45")).toBe("/patient/A%20123%2F45");
  });

  it("preserves cohort filter params when switching tabs", () => {
    const source = new URLSearchParams("cohortQ=SENTETIK&cohortSex=K&admin=1");
    expect(buildSutHomeHref("compliance", source)).toBe(
      "/?tab=compliance&cohortQ=SENTETIK&cohortSex=K&admin=1",
    );
  });

  it("defines the expected split SUT tabs", () => {
    expect(SUT_HOME_TABS.map((tab) => tab.id)).toEqual([
      "patients",
      "compliance",
      "revenue",
      "reference-tools",
    ]);
  });
});

describe("cohortFilter", () => {
  it("matches patient meta against active filters", () => {
    const filter = parseCohortFilter(
      new URLSearchParams("cohortSex=K&cohortAgeMin=40&cohortAgeMax=60"),
    );
    expect(cohortFilterIsActive(filter)).toBe(true);
    expect(
      matchesCohortFilter(
        {
          patient_id: "P1",
          age: 51,
          sex: "K",
          weight_kg: null,
          doctor_code: "DR-1",
          comorbidity_conditions: [],
        },
        filter,
      ),
    ).toBe(true);
    expect(
      matchesCohortFilter(
        {
          patient_id: "P2",
          age: 22,
          sex: "E",
          weight_kg: null,
          doctor_code: null,
          comorbidity_conditions: [],
        },
        filter,
      ),
    ).toBe(false);
  });

  it("builds cohort patient id sets", () => {
    const meta = [
      {
        patient_id: "P1",
        age: 51,
        sex: "K",
        weight_kg: null,
        doctor_code: null,
        comorbidity_conditions: [],
      },
      {
        patient_id: "P2",
        age: 22,
        sex: "E",
        weight_kg: null,
        doctor_code: null,
        comorbidity_conditions: [],
      },
    ];
    const filter = parseCohortFilter(new URLSearchParams("cohortSex=K"));
    expect([...buildCohortPatientIdSet(meta, filter)]).toEqual(["P1"]);
  });
});
