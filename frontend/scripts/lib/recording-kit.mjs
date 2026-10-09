import fs from "node:fs";
import path from "node:path";

export const PATIENTS = ["SENTETIK-HASTA-0003", "SENTETIK-HASTA-0017"];
export const DPR = 2;
export const HELP = "Usage: node scripts/record-workflows.mjs --out <new-directory-outside-git> [--base-url http://127.0.0.1:13000] [--locale tr|en] [--size 1440x900]";

/**
 * Chrome reports "preloaded but not used" for a self-hosted font that a later page found in its
 * memory cache, although the font is loaded and in use (checked with document.fonts). Tolerate only
 * that exact hint for the two same-origin font families; any other warning still fails the run.
 */
export function isKnownFontPreloadHint(text) {
  return /^The resource https?:\/\/127\.0\.0\.1:\d+\/fonts\/(?:inter|fraunces)\/[a-z-]+\.woff2 was preloaded using link preload but not used within a few seconds from the window's load event\./.test(text);
}

export function check(condition, message) {
  if (!condition) throw new Error(message);
}

export function parseRecordingArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (key === "--help") return { help: true };
    check(["--out", "--base-url", "--locale", "--size"].includes(key), "Unknown recording option");
    check(!opts[key] && argv[i + 1] && !argv[i + 1].startsWith("--"), "Missing or duplicate recording option");
    opts[key] = argv[++i];
  }
  check(opts["--out"], "--out is required");
  const url = new URL(opts["--base-url"] ?? "http://127.0.0.1:13000");
  check(url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) && !url.username && !url.password && url.pathname === "/" && !url.search && !url.hash, "Use a credential-free loopback HTTP origin");
  const locale = opts["--locale"] ?? "tr";
  check(["tr", "en"].includes(locale), "--locale must be tr or en (one batch only)");
  const size = /^(\d+)x(\d+)$/.exec(opts["--size"] ?? "1440x900");
  check(size, "--size must look like 1440x900");
  const [width, height] = size.slice(1).map(Number);
  check(width >= 320 && height >= 400 && width <= 1920 && height <= 1200, "Viewport outside recording bounds");
  return { baseUrl: url.origin, out: path.resolve(opts["--out"]), locale, width, height };
}

/** Reject every Git checkout (including linked worktrees), symlinks and overwrites. */
export function prepareRecordingOutput(out) {
  check(!fs.existsSync(out), "Output must be new; recordings are never overwritten");
  let parent = path.dirname(out);
  while (!fs.existsSync(parent)) parent = path.dirname(parent);
  check(fs.realpathSync(parent) === parent, "Output ancestors must not contain symlinks");
  for (let dir = parent; ; dir = path.dirname(dir)) {
    check(!fs.existsSync(path.join(dir, ".git")), "Recordings and frames must stay outside Git worktrees");
    if (dir === path.dirname(dir)) break;
  }
  fs.mkdirSync(out, { recursive: true });
}

export function assertSynthetic(list) {
  check(list.data_source?.mode === "synthetic_demo" && list.data_source?.is_synthetic === true && list.patients?.length > 0 && list.patients.every(id => /^SENTETIK-HASTA-\d{4}$/.test(id)), "Refusing a non-synthetic or unknown cohort");
  check(PATIENTS.every(id => list.patients.includes(id)), "Required authored patients are unavailable");
}

export function assertReport(report, patient, claim = null) {
  check(report.patient_id === patient && report.data_source?.mode === "synthetic_demo" && report.data_source?.is_synthetic === true, "Report patient/provenance mismatch");
  if (claim) check(report.scope === "bill" && report.claim_id === claim, "Report claim scope mismatch");
}

export function rankedActions(report) {
  const value = action => {
    const values = [action.sgk_uplift_try, action.compliance_savings_try, action.billed_try].filter(v => v != null && Number.isFinite(v));
    return values.length ? Math.max(...values) : 0;
  };
  return [...(report.recommended_actions ?? [])].sort((a, b) => value(b) - value(a));
}

export function assertAction(report, id, claimIds) {
  const matches = (report.recommended_actions ?? []).filter(action => action.action_id === id);
  check(matches.length === 1, "Rendered action does not have a unique API owner");
  const action = matches[0];
  check(!action.claim_id || claimIds.includes(action.claim_id), "Action belongs to an unknown claim");
  return action;
}

export function assertClause(clause, key) {
  check(clause.clause_key === key && typeof clause.text_tr === "string" && clause.text_tr.trim().length > 0, "Source drawer clause identity/text mismatch");
}

export function selectRejection(queue, patients, claimsByPatient) {
  check(queue.ingest_available && queue.rows?.length, "Authored rejection queue unavailable");
  check(queue.rows.every(row => patients.includes(row.patient_id)), "Queue contains a non-synthetic patient");
  const row = queue.rows.find(item => item.playbook_matched && item.playbook_key && item.corrective_steps_tr?.length);
  check(row && claimsByPatient[row.patient_id]?.includes(row.claim_id), "No matched authored rejection with a patient-owned claim");
  return row;
}

export function assertPlaybook(report, row) {
  const entries = report.medula_rejection_playbook?.entries ?? [];
  const entry = entries.find(item => item.rejection_event_id === row.rejection_event_id);
  check(entry && entry.patient_id === row.patient_id && entry.claim_id === row.claim_id && entry.playbook_id === row.playbook_key && entry.sonuc_kodu === row.sonuc_kodu && entry.sut_anchor === row.sut_anchor, "Playbook does not own the selected rejection");
  check(JSON.stringify(entry.corrective_steps_tr) === JSON.stringify(row.corrective_steps_tr), "Queue/playbook corrective steps differ");
  return entry;
}

export function pngSize(buffer) {
  check(buffer.subarray(1, 4).toString() === "PNG", "Not a PNG frame");
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}
