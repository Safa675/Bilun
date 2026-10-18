import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { amountPattern, claimIds, faultFor, faultForRole, faults, formatTryTr, loadRegistry, parseRegistry, patientIds, REGISTRY_PATH, role, roles } from "./cohort-registry.mjs";

// These tests read the REAL registry (data/synthetic/cohort_registry.json, or COHORT_REGISTRY_PATH): nothing is copied here.
const real = JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf8"));
const temporary = [];
afterEach(() => temporary.splice(0).forEach((dir) => fs.rmSync(dir, { recursive: true, force: true })));
const scratch = () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cohort-registry-"));
  temporary.push(dir);
  return dir;
};

describe("the real registry", () => {
  it("has the default landing and one showcase role per injected story", () => {
    expect(faults.length).toBeGreaterThan(0);
    expect(Object.keys(roles).sort()).toEqual(["default_landing", ...faults.map((fault) => `showcase_${fault.story}`)].sort());
  });

  it("counts the cohort the way the registry's own tables do", () => {
    expect(claimIds).toHaveLength(real.counts["claim_headers.parquet"]);
    expect(patientIds).toHaveLength(real.clean_counts["anadata_clean.parquet"]);
    // both lists are sorted and hold every id once
    expect([...patientIds]).toEqual([...new Set(patientIds)].sort());
    expect([...claimIds]).toEqual([...new Set(claimIds)].sort());
    for (const { patient_id: patient, claim_id: claim } of Object.values(roles)) {
      expect(patientIds).toContain(patient);
      expect(claimIds).toContain(claim);
    }
  });

  it("gives every story a fault record that belongs to its showcase role", () => {
    for (const fault of faults) {
      expect(faultFor(fault.story)).toBe(fault);
      expect(role(`showcase_${fault.story}`)).toMatchObject({ patient_id: fault.patient_id, claim_id: fault.claim_id });
      expect(faultForRole(`showcase_${fault.story}`)).toBe(fault);
    }
  });

  it("lands on a bill that carries an injected fault", () => {
    expect(faults).toContain(faultForRole("default_landing"));
  });

  it("names an unknown role or story instead of returning undefined", () => {
    expect(() => role("showcase_S99")).toThrow(/showcase_S99[\s\S]*default_landing/);
    expect(() => faultFor("S99")).toThrow(/S99/);
    expect(() => faultForRole("nobody")).toThrow(/nobody/);
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
  ])("%s", (_name, change, message) => {
    const broken = structuredClone(real);
    change(broken);
    expect(() => parseRegistry(broken, "unit-registry.json")).toThrow(message);
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
