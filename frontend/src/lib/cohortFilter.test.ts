import { describe, expect, it } from "vitest";
import {
  formatAgeRangeDisplay,
  matchesCohortFilter,
  parseAgeRangeInput,
  parseCohortFilter,
} from "./cohortFilter";
import type { PatientMeta } from "@/lib/domains/patient";

describe("parseAgeRangeInput", () => {
  it("parses min-max ranges with spaces and dashes", () => {
    expect(parseAgeRangeInput("20 - 30")).toEqual({ ageMin: 20, ageMax: 30 });
    expect(parseAgeRangeInput("20-30")).toEqual({ ageMin: 20, ageMax: 30 });
  });

  it("parses a single age as exact match bounds", () => {
    expect(parseAgeRangeInput("40")).toEqual({ ageMin: 40, ageMax: 40 });
  });

  it("clears bounds for empty or invalid input", () => {
    expect(parseAgeRangeInput("")).toEqual({ ageMin: null, ageMax: null });
    expect(parseAgeRangeInput("abc")).toEqual({ ageMin: null, ageMax: null });
  });
});

describe("formatAgeRangeDisplay", () => {
  it("formats stored bounds for the combined age input", () => {
    expect(formatAgeRangeDisplay({ ageMin: 20, ageMax: 30 })).toBe("20 - 30");
    expect(formatAgeRangeDisplay({ ageMin: 40, ageMax: 40 })).toBe("40");
    expect(formatAgeRangeDisplay({ ageMin: null, ageMax: null })).toBe("");
  });
});

describe("parseCohortFilter age params", () => {
  it("still reads legacy cohortAgeMin and cohortAgeMax URL params", () => {
    const params = new URLSearchParams("cohortAgeMin=25&cohortAgeMax=35");
    expect(parseCohortFilter(params)).toEqual(
      expect.objectContaining({ ageMin: 25, ageMax: 35 }),
    );
  });
});

describe("matchesCohortFilter patient selection", () => {
  const meta: PatientMeta = {
    patient_id: "SENTETIK-HASTA-0001",
    age: 42,
    sex: "E",
    weight_kg: null,
    doctor_code: "DR-01",
    comorbidity_conditions: [],
  };

  it("matches the selected patient by exact ID", () => {
    expect(
      matchesCohortFilter(meta, {
        q: "SENTETIK-HASTA-0001",
        sex: "",
        ageMin: null,
        ageMax: null,
        doctor: "",
      }),
    ).toBe(true);
  });

  it("does not match partial patient ID prefixes", () => {
    expect(
      matchesCohortFilter(meta, {
        q: "SENTETIK-HASTA",
        sex: "",
        ageMin: null,
        ageMax: null,
        doctor: "",
      }),
    ).toBe(false);
  });
});
