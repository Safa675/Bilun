import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { amountPattern, claimIds, faultFor, faultForRole, faults, formatTryTr, loadRegistry, parseRegistry, patientIds, REGISTRY_PATH, role, roles, scenario, scenarios } from "./cohort-registry.mjs";

// These tests read the REAL registry (data/synthetic/cohort_registry.json, or COHORT_REGISTRY_PATH): nothing is copied here.
const real = JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf8"));
const temporary = [];
afterEach(() => temporary.splice(0).forEach((dir) => fs.rmSync(dir, { recursive: true, force: true })));
const scratch = () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cohort-registry-"));
  temporary.push(dir);
  return dir;
};

// The roles are fixed: the default landing and the first eight stories. Every later story is a scenario.
const ROLE_STORIES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"];
const scenarioStories = [...new Set(real.encounters.map((encounter) => encounter.story))].filter((story) => !ROLE_STORIES.includes(story));
// a bill without a fault (a clean bill, S39) is a scenario too: a story and a claim, no injection record
const cleanStories = real.encounters.filter((encounter) => encounter.is_clean).map((encounter) => encounter.story);
const faultedScenarioStories = scenarioStories.filter((story) => !cleanStories.includes(story));

describe("the real registry", () => {
  it("has the default landing and one showcase role per injected story of the first eight", () => {
    expect(faults.length).toBeGreaterThan(0);
    expect(Object.keys(roles).sort()).toEqual(["default_landing", ...ROLE_STORIES.map((story) => `showcase_${story}`)].sort());
    expect(faults.map((fault) => fault.story)).toEqual(expect.arrayContaining(ROLE_STORIES));
  });

  it("names every story after the eighth as a scenario and never as a role", () => {
    expect(scenarioStories.length).toBeGreaterThan(0);
    expect(Object.keys(scenarios).sort()).toEqual([...scenarioStories].sort());
    expect(scenarios).toEqual(real.scenarios);
    for (const story of scenarioStories) {
      expect(Object.keys(roles)).not.toContain(`showcase_${story}`);
      const { patient_id: patient, claim_ids: claims } = scenario(story);
      expect(patientIds).toContain(patient);
      expect(claims.length).toBeGreaterThan(0);
      for (const claim of claims) {
        expect(claimIds).toContain(claim);
        expect(claim.startsWith(`F-${patient}-`)).toBe(true);
      }
      if (cleanStories.includes(story)) {
        expect(faults.map((fault) => fault.story)).not.toContain(story);
        expect(() => faultFor(story)).toThrow(/no fault for story/);
        continue;
      }
      expect(claims).toContain(faultFor(story).claim_id);
      expect(faultFor(story).patient_id).toBe(patient);
    }
  });

  it("has a fault for every story but the clean bills, and a clean bill has one claim and no record", () => {
    expect(cleanStories.length).toBeGreaterThan(0);
    const stories = [...ROLE_STORIES, ...scenarioStories].sort();
    expect(stories.filter((story) => !cleanStories.includes(story))).toEqual(faults.map((fault) => fault.story).sort());
    for (const story of cleanStories) {
      expect(scenario(story).claim_ids).toHaveLength(1);
      expect(real.faults.filter((fault) => fault.claim_id === scenario(story).claim_ids[0])).toEqual([]);
    }
  });

  it("lists a patient's bills under that patient: every bill of a patient with several is a registry encounter", () => {
    const perPatient = {};
    for (const encounter of real.encounters) (perPatient[encounter.patient_id] ??= []).push(encounter);
    expect(Object.keys(perPatient).sort()).toEqual([...patientIds]);
    for (const [patient, encounters] of Object.entries(perPatient)) {
      const bills = encounters.map((encounter) => encounter.claim_id).sort();
      expect(bills).toEqual(claimIds.filter((claim) => claim.startsWith(`F-${patient}-`)));
    }
    // a story belongs to one bill, so a patient with two bills names them under two stories
    const stories = real.encounters.map((encounter) => encounter.story);
    expect(new Set(stories).size).toBe(stories.length);
    for (const { patient_id: patient, claim_ids: claims } of Object.values(scenarios)) {
      for (const claim of claims) expect(perPatient[patient].map((encounter) => encounter.claim_id)).toContain(claim);
    }
  });

  it("gives every patient of the cohort a role or a scenario", () => {
    const named = new Set([...Object.values(roles), ...Object.values(scenarios)].map((entry) => entry.patient_id));
    expect([...named].sort()).toEqual([...patientIds]);
  });

  it("counts the cohort the way the registry's own tables do", () => {
    // A patient may have several bills: a bill is a claim header and an anadata row, a patient is a copay profile.
    expect(claimIds).toHaveLength(real.counts["claim_headers.parquet"]);
    expect(claimIds).toHaveLength(real.clean_counts["anadata_clean.parquet"]);
    expect(patientIds).toHaveLength(real.counts["patient_copay_profiles.parquet"]);
    // both lists are sorted and hold every id once
    expect([...patientIds]).toEqual([...new Set(patientIds)].sort());
    expect([...claimIds]).toEqual([...new Set(claimIds)].sort());
    for (const { patient_id: patient, claim_id: claim } of Object.values(roles)) {
      expect(patientIds).toContain(patient);
      expect(claimIds).toContain(claim);
    }
  });

  it("gives every story of the first eight a fault record that belongs to its showcase role", () => {
    for (const story of ROLE_STORIES) {
      const fault = faultFor(story);
      expect(role(`showcase_${story}`)).toMatchObject({ patient_id: fault.patient_id, claim_id: fault.claim_id });
      expect(faultForRole(`showcase_${story}`)).toBe(fault);
    }
    for (const fault of faults) expect(faultFor(fault.story)).toBe(fault);
  });

  it("lands on a bill that carries an injected fault", () => {
    expect(faults).toContain(faultForRole("default_landing"));
  });

  it("names an unknown role, story or scenario instead of returning undefined", () => {
    expect(() => role("showcase_S99")).toThrow(/showcase_S99[\s\S]*default_landing/);
    expect(() => role(`showcase_${scenarioStories[0]}`)).toThrow(/default_landing/);
    expect(() => faultFor("S99")).toThrow(/S99/);
    expect(() => faultForRole("nobody")).toThrow(/nobody/);
    expect(() => scenario("S99")).toThrow(new RegExp(`S99[\\s\\S]*${scenarioStories[0]}`));
    expect(() => scenario("S3")).toThrow(/S3/);
  });

  it("holds every amount as a two-decimal string the UI formatter can be compared with", () => {
    for (const fault of faults) {
      expect(fault.amount_try).toMatch(/^\d+\.\d{2}$/);
      expect(amountPattern(fault.amount_try).test(formatTryTr(fault.amount_try))).toBe(true);
    }
  });
});

describe("registry validation refuses a registry that no longer describes the cohort", () => {
  it("accepts the committed registry", () => {
    expect(parseRegistry(structuredClone(real))).toMatchObject({ schema_version: 1 });
  });

  it("refuses something that is not an object", () => {
    expect(() => parseRegistry(null, "unit-registry.json")).toThrow(/unit-registry\.json[\s\S]*not a JSON object/);
  });

  it.each([
    ["another schema version", (r) => { r.schema_version = 2; }, /schema_version/],
    ["no encounters", (r) => { r.encounters = []; }, /no encounters/],
    ["the same encounter twice", (r) => { r.encounters.push({ ...r.encounters[0] }); }, /twice/],
    ["no default landing", (r) => { delete r.roles.default_landing; }, /default_landing/],
    ["a role at a bill that does not exist", (r) => { r.roles.default_landing = { patient_id: "SENTETIK-HASTA-9999", claim_id: "F-SENTETIK-HASTA-9999-001" }; }, /does not exist/],
    ["a role whose claim belongs to another patient", (r) => { r.roles.default_landing.claim_id = r.roles.showcase_S2.claim_id; }, /does not belong/],
    ["an amount with one decimal", (r) => { r.faults[0].amount_try = "4122.6"; }, /amount_try/],
    ["an amount that is a number", (r) => { r.faults[0].amount_try = 4122.06; }, /amount_try/],
    ["a story listed twice", (r) => { r.faults[1].story = r.faults[0].story; }, /listed twice/],
    ["a story that is not S<number>", (r) => { r.faults[0].story = "first"; }, /malformed/],
    ["a fault without its engine rule", (r) => { delete r.faults[0].engine_rule; }, /no engine_rule/],
    ["a showcase role that disagrees with its fault", (r) => { r.roles.showcase_S1 = { ...r.roles.showcase_S2 }; }, /disagrees/],
    ["a role for a story after the eighth", (r) => { r.roles.showcase_S9 = { ...r.roles.showcase_S1 }; }, /scenario/],
    ["a role with another name", (r) => { r.roles.second_landing = { ...r.roles.default_landing }; }, /not default_landing or showcase_S1/],
    ["scenarios that are not an object", (r) => { r.scenarios = ["S9"]; }, /scenarios/],
    ["a scenario named like a story of the first eight", (r) => { r.scenarios.S3 = structuredClone(r.scenarios.S9); }, /after S8/],
    ["a scenario that is not S<number>", (r) => { r.scenarios.ninth = structuredClone(r.scenarios.S9); }, /after S8/],
    ["a scenario named S0", (r) => { r.scenarios.S0 = structuredClone(r.scenarios.S9); }, /after S8/],
    ["a scenario named S01", (r) => { r.scenarios.S01 = structuredClone(r.scenarios.S9); }, /after S8/],
    ["a scenario at a bill that does not exist", (r) => { r.scenarios.S9 = { patient_id: "SENTETIK-HASTA-9999", claim_ids: ["F-SENTETIK-HASTA-9999-001"] }; }, /does not exist/],
    ["a scenario whose claim belongs to another patient", (r) => { r.scenarios.S9.claim_ids = [r.roles.showcase_S2.claim_id]; }, /does not belong/],
    ["a scenario without claims", (r) => { r.scenarios.S9.claim_ids = []; }, /claim_ids/],
    ["a scenario with a claim twice", (r) => { r.scenarios.S9.claim_ids = [r.scenarios.S9.claim_ids[0], r.scenarios.S9.claim_ids[0]]; }, /claim_ids/],
    ["a scenario with the role shape", (r) => { r.scenarios.S9 = { patient_id: r.scenarios.S9.patient_id, claim_id: r.scenarios.S9.claim_ids[0] }; }, /claim_ids/],
    ["a fault of a scenario story off its scenario", (r) => { delete r.scenarios.S9; }, /scenario S9 is missing or disagrees/],
    ["a fault of a scenario story on another claim", (r) => { r.faults.find((fault) => fault.story === "S9").claim_id = r.roles.showcase_S2.claim_id; r.faults.find((fault) => fault.story === "S9").patient_id = r.roles.showcase_S2.patient_id; }, /scenario S9 is missing or disagrees/],
  ])("%s", (_name, change, message) => {
    const broken = structuredClone(real);
    change(broken);
    expect(() => parseRegistry(broken, "unit-registry.json")).toThrow(message);
  });
});

describe("a fault without a story", () => {
  it("is accepted: it belongs to no role and no scenario, and is found by its claim", () => {
    const loose = structuredClone(real);
    const record = loose.faults.find((fault) => fault.story === faultedScenarioStories[0]);
    record.story = null;
    expect(parseRegistry(loose, "unit-registry.json").faults).toContain(record);
    const names = loose.faults.filter((fault) => fault.story).map((fault) => fault.story);
    expect(names).not.toContain(faultedScenarioStories[0]);
  });

  it("still has to be a whole record on a bill that exists", () => {
    const missingAmount = structuredClone(real);
    missingAmount.faults[0].story = null;
    delete missingAmount.faults[0].amount_try;
    expect(() => parseRegistry(missingAmount, "unit-registry.json")).toThrow(/amount_try/);
    const strayBill = structuredClone(real);
    strayBill.faults[0].story = null;
    strayBill.faults[0].claim_id = "F-SENTETIK-HASTA-9999-001";
    strayBill.faults[0].patient_id = "SENTETIK-HASTA-9999";
    expect(() => parseRegistry(strayBill, "unit-registry.json")).toThrow(/does not exist/);
  });

  it("does not hide a story that is malformed: an empty string is not null", () => {
    const empty = structuredClone(real);
    empty.faults[0].story = "";
    expect(() => parseRegistry(empty, "unit-registry.json")).toThrow(/malformed/);
  });
});

describe("loading a registry file", () => {
  it("reads the same registry from any path", () => {
    const file = path.join(scratch(), "copy.json");
    fs.writeFileSync(file, JSON.stringify(real));
    expect(loadRegistry(file)).toEqual(real);
  });

  it("says which file is missing and how to build it", () => {
    const file = path.join(scratch(), "absent.json");
    expect(() => loadRegistry(file)).toThrow(file);
    expect(() => loadRegistry(file)).toThrow(/scripts\.synthetic\.cohort\.build/);
  });

  it("names the file that failed validation", () => {
    const file = path.join(scratch(), "broken.json");
    fs.writeFileSync(file, JSON.stringify({ ...real, schema_version: 99 }));
    expect(() => loadRegistry(file)).toThrow(file);
  });
});

describe("amounts as the UI prints them", () => {
  it.each([
    ["4122.06", "4.122,06"],
    ["667.08", "667,08"],
    ["0.00", "0,00"],
    ["6465.27", "6.465,27"],
    ["1234567.80", "1.234.567,80"],
  ])("formats %s as %s", (amount, turkish) => {
    expect(formatTryTr(amount)).toBe(turkish);
  });

  it.each(["4122.6", "4122", "abc", "", "-4122.06"])("refuses %j", (amount) => {
    expect(() => formatTryTr(amount)).toThrow(/two-decimal/);
    expect(() => amountPattern(amount)).toThrow(/two-decimal/);
  });

  it("finds the amount in Turkish and English formatting, inside currency text", () => {
    const pattern = amountPattern("4122.06");
    for (const text of ["4.122,06", "4,122.06", "₺4.122,06", "4,122.06 TRY", "4.122,06 ₺", "Recoverable SGK uplift\n4.122,06 TRY", "4122,06", "Toplam: 4.122,06."]) {
      expect(pattern.test(text), text).toBe(true);
    }
  });

  it("does not find it inside another number or when the page shows nothing", () => {
    const pattern = amountPattern("4122.06");
    for (const text of ["14.122,06", "34,122.06", "4.122,065", "4.123,06", "122,06", "4.122,6", "—", "", "Recoverable SGK uplift"]) {
      expect(pattern.test(text), text).toBe(false);
    }
    expect(amountPattern("0.00").test("₺10,00")).toBe(false);
    expect(amountPattern("0.00").test("₺0,00")).toBe(true);
  });
});
