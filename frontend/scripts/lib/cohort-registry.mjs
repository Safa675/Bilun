// The synthetic showcase cohort as its registry describes it (data/synthetic/cohort_registry.json, written by
// `python -m scripts.synthetic.cohort.build`). The live-app scripts name patients by ROLE and take amounts from the
// registry's injection records, so none of them pins a patient id, claim id or money value: rebuild the cohort and
// the scripts follow. Roles: `default_landing` and `showcase_S1` .. `showcase_S8`, fixed. A story after the eighth
// (S9, ...) is a scenario: `scenarios.S9 = { patient_id, claim_ids }`, the patient and the claims of its bills.
//
// The path is resolved from this file up to the repository root. COHORT_REGISTRY_PATH overrides it for a one-off
// run against another copy of the registry (for example one built into a scratch directory).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
export const REGISTRY_PATH = process.env.COHORT_REGISTRY_PATH
  ? path.resolve(process.env.COHORT_REGISTRY_PATH)
  : path.join(REPO_ROOT, "data", "synthetic", "cohort_registry.json");

const SCHEMA_VERSION = 1;
const PATIENT_ID = /^SENTETIK-HASTA-\d{4}$/;
const CLAIM_ID = /^F-SENTETIK-HASTA-\d{4}-\d{3}$/;
const STORY = /^S\d+$/;
const SCENARIO_STORY = /^S[1-9]\d*$/;
const ROLE_STORY = /^S[1-8]$/;
const ROLE_NAME = /^(default_landing|showcase_S[1-8])$/;
const AMOUNT = /^\d+\.\d{2}$/;
const FAULT_STRINGS = ["fault_id", "pathway_id", "effect_kind", "engine_rule", "expected_status", "line_type", "sut_section"];
const GROUP = /\B(?=(\d{3})+(?!\d))/g;

/** Validates a parsed registry (shape, id formats, amounts, roles and faults pointing at real encounters) and returns it. */
export function parseRegistry(raw, source = REGISTRY_PATH) {
  const fail = (message) => {
    throw new Error(`Cohort registry ${source}: ${message}`);
  };
  const ownedBy = (entry, label) => {
    if (!entry || typeof entry !== "object") fail(`${label} is not an object`);
    if (!PATIENT_ID.test(entry.patient_id ?? "")) fail(`${label} has a bad patient_id ${JSON.stringify(entry.patient_id)}`);
    if (!CLAIM_ID.test(entry.claim_id ?? "") || !entry.claim_id.startsWith(`F-${entry.patient_id}-`)) {
      fail(`${label} has a claim_id ${JSON.stringify(entry.claim_id)} that does not belong to ${entry.patient_id}`);
    }
  };

  if (!raw || typeof raw !== "object") fail("is not a JSON object");
  if (raw.schema_version !== SCHEMA_VERSION) fail(`has schema_version ${JSON.stringify(raw.schema_version)}, this reader knows ${SCHEMA_VERSION}`);
  if (!Array.isArray(raw.encounters) || !raw.encounters.length) fail("lists no encounters");
  raw.encounters.forEach((encounter, index) => ownedBy(encounter, `encounters[${index}]`));
  const encounterKeys = new Set(raw.encounters.map((e) => `${e.patient_id}|${e.claim_id}`));
  if (encounterKeys.size !== raw.encounters.length) fail("lists the same encounter twice");

  if (!raw.roles || typeof raw.roles !== "object" || !raw.roles.default_landing) fail("has no default_landing role");
  for (const [name, entry] of Object.entries(raw.roles)) {
    if (!ROLE_NAME.test(name)) fail(`role ${name} is not default_landing or showcase_S1..S8; the stories after S8 are scenarios`);
    ownedBy(entry, `role ${name}`);
    if (!encounterKeys.has(`${entry.patient_id}|${entry.claim_id}`)) fail(`role ${name} points at an encounter that does not exist`);
  }

  // A registry written before scenarios existed has none; a fault of a story after the eighth then fails below.
  const scenarios = raw.scenarios ?? {};
  if (!scenarios || typeof scenarios !== "object" || Array.isArray(scenarios)) fail("has scenarios that are not an object");
  for (const [story, entry] of Object.entries(scenarios)) {
    if (!SCENARIO_STORY.test(story) || ROLE_STORY.test(story)) fail(`scenario ${story} is not a story after S8 (S9, S10, ...)`);
    if (!entry || typeof entry !== "object") fail(`scenario ${story} is not an object`);
    if (!PATIENT_ID.test(entry.patient_id ?? "")) fail(`scenario ${story} has a bad patient_id ${JSON.stringify(entry.patient_id)}`);
    const claims = entry.claim_ids;
    if (!Array.isArray(claims) || !claims.length || new Set(claims).size !== claims.length) {
      fail(`scenario ${story} needs a non-empty claim_ids list of distinct claims, not ${JSON.stringify(claims)}`);
    }
    for (const claim of claims) {
      if (!CLAIM_ID.test(claim ?? "") || !claim.startsWith(`F-${entry.patient_id}-`)) {
        fail(`scenario ${story} has a claim_id ${JSON.stringify(claim)} that does not belong to ${entry.patient_id}`);
      }
      if (!encounterKeys.has(`${entry.patient_id}|${claim}`)) fail(`scenario ${story} points at an encounter that does not exist`);
    }
  }

  if (!Array.isArray(raw.faults) || !raw.faults.length) fail("lists no faults");
  const stories = new Set();
  for (const fault of raw.faults) {
    // A fault may have no story (`story: null`): it belongs to no role and no scenario, and is found by its claim only.
    const hasStory = fault?.story !== null && fault?.story !== undefined;
    const label = `fault ${hasStory ? fault.story : fault?.fault_id}`;
    ownedBy(fault, label);
    if (hasStory) {
      if (!STORY.test(fault.story) || stories.has(fault.story)) fail(`${label}: the story is malformed or listed twice`);
      stories.add(fault.story);
    }
    if (typeof fault.amount_try !== "string" || !AMOUNT.test(fault.amount_try)) fail(`${label} has amount_try ${JSON.stringify(fault.amount_try)}, expected a two-decimal string`);
    for (const key of FAULT_STRINGS) if (typeof fault[key] !== "string" || !fault[key]) fail(`${label} has no ${key}`);
    if (!encounterKeys.has(`${fault.patient_id}|${fault.claim_id}`)) fail(`${label} points at an encounter that does not exist`);
    if (!hasStory) continue;
    if (ROLE_STORY.test(fault.story)) {
      const showcase = raw.roles[`showcase_${fault.story}`];
      if (!showcase || showcase.patient_id !== fault.patient_id || showcase.claim_id !== fault.claim_id) {
        fail(`role showcase_${fault.story} is missing or disagrees with the fault of ${fault.story}`);
      }
    } else {
      const named = scenarios[fault.story];
      if (!named || named.patient_id !== fault.patient_id || !named.claim_ids.includes(fault.claim_id)) {
        fail(`scenario ${fault.story} is missing or disagrees with the fault of ${fault.story}`);
      }
    }
  }
  return raw;
}

/** Reads and validates a registry file. */
export function loadRegistry(file = REGISTRY_PATH) {
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch (error) {
    throw new Error(`Cannot read the cohort registry ${file} (${error.code ?? error.message}); build it with: python -m scripts.synthetic.cohort.build`);
  }
  return parseRegistry(JSON.parse(text), file);
}

const registry = loadRegistry();

/** { default_landing: { patient_id, claim_id }, showcase_S1: ..., ... } */
export const roles = Object.freeze(
  Object.fromEntries(Object.entries(registry.roles).map(([name, entry]) => [name, Object.freeze({ patient_id: entry.patient_id, claim_id: entry.claim_id })])),
);

/** { S9: { patient_id, claim_ids: [...] }, ... }: the stories after the eighth, each a patient and the claims of its bills. */
export const scenarios = Object.freeze(
  Object.fromEntries(
    Object.entries(registry.scenarios ?? {}).map(([story, entry]) => [story, Object.freeze({ patient_id: entry.patient_id, claim_ids: Object.freeze([...entry.claim_ids]) })]),
  ),
);

/** The injection records, one per fault (stories S1 .. S8 and every scenario story; a fault may have `story: null`), as the generator wrote them. */
export const faults = Object.freeze(registry.faults.map((fault) => Object.freeze({ ...fault })));

/** Every patient and claim of the cohort, sorted. */
export const patientIds = Object.freeze([...new Set(registry.encounters.map((e) => e.patient_id))].sort());
export const claimIds = Object.freeze([...new Set(registry.encounters.map((e) => e.claim_id))].sort());

/** The patient and claim of a role (`default_landing`, `showcase_S1` ..). An unknown role throws and lists the known ones. */
export function role(name) {
  const entry = roles[name];
  if (!entry) throw new Error(`Unknown cohort role ${JSON.stringify(name)}; the registry has: ${Object.keys(roles).join(", ")}`);
  return entry;
}

/** The patient and claims of a story after the eighth ("S9" ..). An unknown story throws and lists the known ones. */
export function scenario(story) {
  const entry = scenarios[story];
  if (!entry) throw new Error(`Unknown cohort scenario ${JSON.stringify(story)}; the registry has: ${Object.keys(scenarios).join(", ")}`);
  return entry;
}

/** The injection record of a story ("S1" .. "S8" and every scenario story): amount_try, line_type, effect_kind, engine_rule, claim_id ... */
export function faultFor(story) {
  const fault = faults.find((item) => item.story === story);
  if (!fault) throw new Error(`The registry has no fault for story ${JSON.stringify(story)}; it has: ${faults.map((f) => f.story).filter(Boolean).join(", ")}`);
  return fault;
}

/** The injection record of the bill a role points at (for `default_landing`: the record of the landing story). */
export function faultForRole(name) {
  const { claim_id: claimId } = role(name);
  const fault = faults.find((item) => item.claim_id === claimId);
  if (!fault) throw new Error(`Role ${JSON.stringify(name)} points at ${claimId}, which carries no injected fault`);
  return fault;
}

function amountParts(amount) {
  const match = /^(\d+)\.(\d{2})$/.exec(String(amount));
  if (!match) throw new Error(`Not a two-decimal amount: ${JSON.stringify(amount)}`);
  return { groups: match[1].replace(GROUP, "|").split("|"), cents: match[2] };
}

/** "4122.06" -> "4.122,06" (Turkish format; string arithmetic only, no float rounding). */
export function formatTryTr(amount) {
  const { groups, cents } = amountParts(amount);
  return `${groups.join(".")},${cents}`;
}

/**
 * A RegExp for an amount as the UI prints it: "4.122,06" (tr) or "4,122.06" (en), with or without the group
 * separator and inside any currency text, but never inside a longer number ("14.122,06", "4.122,065").
 */
export function amountPattern(amount) {
  const { groups, cents } = amountParts(amount);
  return new RegExp(`(?<![\\d.,])${groups.join("[.,]?")}[.,]${cents}(?!\\d)`);
}
