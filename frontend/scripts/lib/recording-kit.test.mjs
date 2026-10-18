import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { role } from "./cohort-registry.mjs";
import { assertAction, assertClause, isKnownFontPreloadHint, assertPlaybook, assertReport, assertSynthetic, parseRecordingArgs, PATIENTS, prepareRecordingOutput, rankedActions, selectRejection } from "./recording-kit.mjs";

const temporary = [];
afterEach(() => temporary.splice(0).forEach(dir => fs.rmSync(dir, { recursive: true, force: true })));
const source = { mode: "synthetic_demo", is_synthetic: true };

describe("recording CLI safety", () => {
  it("defaults to one Turkish batch and DPR-independent CSS viewport", () => {
    expect(parseRecordingArgs(["--out", "/tmp/ui8-example"])).toMatchObject({ locale: "tr", width: 1440, height: 900, baseUrl: "http://127.0.0.1:13000" });
    expect(parseRecordingArgs(["--out", "/tmp/ui8-example", "--locale", "en", "--size", "390x844"])).toMatchObject({ locale: "en", width: 390, height: 844 });
  });
  it.each(["https://example.com", "http://example.com", "http://127.0.0.1@evil.test", "http://user:secret@localhost", "http://localhost/api", "http://localhost/?token=secret"])("rejects remote/credential/path origins %s", url => {
    expect(() => parseRecordingArgs(["--out", "/tmp/ui8-example", "--base-url", url])).toThrow();
  });
  it.each([["--routes", "patients"], ["--out"], ["--out", "a", "--out", "b"], ["--out", "a", "--locale", "en,tr"], ["--out", "a", "--size", "9000x9000"], ["--out", "a", "--size", "invalid"]])("rejects unsafe/ambiguous options %s", args => {
    expect(() => parseRecordingArgs(args)).toThrow();
  });
  it("rejects linked Git worktrees, symlink ancestors and existing output", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "ui8-cli-")); temporary.push(root);
    fs.writeFileSync(path.join(root, ".git"), "gitdir: /unrelated/shared/store");
    expect(() => prepareRecordingOutput(path.join(root, "public", "videos"))).toThrow(/Git/);
    fs.unlinkSync(path.join(root, ".git"));
    fs.mkdirSync(path.join(root, "real"));
    fs.symlinkSync(path.join(root, "real"), path.join(root, "alias"));
    expect(() => prepareRecordingOutput(path.join(root, "alias", "videos"))).toThrow(/symlink/);
    prepareRecordingOutput(path.join(root, "new", "videos"));
    expect(() => prepareRecordingOutput(path.join(root, "new", "videos"))).toThrow(/new/);
  });
});

describe("actual API ownership gates (unit fixtures only)", () => {
  it("rejects real or unknown provenance and an injected non-synthetic patient", () => {
    assertSynthetic({ patients: PATIENTS, data_source: source });
    for (const data_source of [{}, { mode: "real_claims", is_synthetic: false }, { mode: "synthetic_demo", is_synthetic: false }]) {
      expect(() => assertSynthetic({ patients: PATIENTS, data_source })).toThrow();
    }
    expect(() => assertSynthetic({ patients: [...PATIENTS, "PRIVATE-IDENTIFIER"], data_source: source })).toThrow();
  });
  it("takes the recorded patients from cohort roles and refuses a cohort list that lacks one", () => {
    expect(PATIENTS).toEqual([role("default_landing").patient_id, role("showcase_S5").patient_id]);
    expect(new Set(PATIENTS).size).toBe(PATIENTS.length);
    for (const missing of PATIENTS) {
      const patients = PATIENTS.filter(id => id !== missing);
      expect(() => assertSynthetic({ patients, data_source: source })).toThrow(/Required authored patients are unavailable/);
    }
  });
  it("rejects swapped patient/claim ownership", () => {
    const report = { patient_id: PATIENTS[0], data_source: source, scope: "bill", claim_id: "unit-claim-a" };
    assertReport(report, PATIENTS[0], "unit-claim-a");
    expect(() => assertReport(report, PATIENTS[1])).toThrow();
    expect(() => assertReport(report, PATIENTS[0], "unit-claim-b")).toThrow();
  });
  it("ranks without changing null amounts or negative values and rejects foreign actions", () => {
    const report = { recommended_actions: [{ action_id: "negative", billed_try: -1 }, { action_id: "unknown", billed_try: null }, { action_id: "known", claim_id: "unit-claim-a", sgk_uplift_try: 10 }] };
    expect(rankedActions(report).map(a => a.action_id)).toEqual(["known", "unknown", "negative"]);
    expect(report.recommended_actions[1].billed_try).toBeNull();
    expect(() => assertAction(report, "known", ["unit-claim-b"])).toThrow();
    expect(() => assertAction(report, "invented", [])).toThrow();
    expect(() => assertAction({ recommended_actions: [report.recommended_actions[0], report.recommended_actions[0]] }, "negative", [])).toThrow();
  });
  it("rejects a swapped or missing clause instead of filling it", () => {
    assertClause({ clause_key: "unit-key-a", text_tr: "Unit test text" }, "unit-key-a");
    expect(() => assertClause({ clause_key: "unit-key-b", text_tr: "Unit test text" }, "unit-key-a")).toThrow();
    expect(() => assertClause({ clause_key: "unit-key-a", text_tr: null }, "unit-key-a")).toThrow();
  });
  it("requires a real queue match, owned claim and identical playbook steps", () => {
    const row = { patient_id: PATIENTS[0], claim_id: "unit-claim-a", rejection_event_id: "unit-event", playbook_matched: true, playbook_key: "unit-playbook", playbook_id: "unit-playbook", sonuc_kodu: "unit-code", sut_anchor: "unit-anchor", corrective_steps_tr: ["Unit step"] };
    expect(selectRejection({ ingest_available: true, rows: [row] }, PATIENTS, { [PATIENTS[0]]: ["unit-claim-a"] })).toBe(row);
    expect(() => selectRejection({ ingest_available: true, rows: [row] }, PATIENTS, { [PATIENTS[0]]: ["unit-claim-b"] })).toThrow();
    expect(() => selectRejection({ ingest_available: false, rows: [] }, PATIENTS, {})).toThrow();
    expect(() => assertPlaybook({ medula_rejection_playbook: { entries: [{ ...row, claim_id: "unit-claim-b" }] } }, row)).toThrow();
    expect(() => assertPlaybook({ medula_rejection_playbook: { entries: [{ ...row, corrective_steps_tr: ["Different step"] }] } }, row)).toThrow();
    assertPlaybook({ medula_rejection_playbook: { entries: [row] } }, row);
  });
});

describe("known browser hints", () => {
  const hint = file => `The resource http://127.0.0.1:13008/fonts/${file} was preloaded using link preload but not used within a few seconds from the window's load event. Please make sure it has an appropriate \`as\` value and it is preloaded intentionally.`;
  it("tolerates only the exact font preload hint for the two self-hosted families", () => {
    expect(isKnownFontPreloadHint(hint("inter/normal-latin.woff2"))).toBe(true);
    expect(isKnownFontPreloadHint(hint("fraunces/italic-latin-ext.woff2"))).toBe(true);
  });
  it("still rejects every other warning, other hosts and other paths", () => {
    expect(isKnownFontPreloadHint(hint("other/normal-latin.woff2"))).toBe(false);
    expect(isKnownFontPreloadHint(hint("inter/../../secret.woff2"))).toBe(false);
    expect(isKnownFontPreloadHint(hint("inter/normal-latin.woff2").replace("127.0.0.1", "example.com"))).toBe(false);
    expect(isKnownFontPreloadHint("The resource http://127.0.0.1:13008/api/x was preloaded using link preload but not used")).toBe(false);
    expect(isKnownFontPreloadHint("Failed to load resource: the server responded with a status of 404 (Not Found)")).toBe(false);
  });
});
