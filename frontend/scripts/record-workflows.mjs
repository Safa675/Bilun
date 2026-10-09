#!/usr/bin/env node
// Local authored-synthetic recordings. Existing Phase0 probes/selectors/redaction;
// no mocks, overlays, text edits, auth secrets, parity claims or release attestation.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { INSPECT_CLAUSE_LABEL } from "./lib/capture-routes.mjs";
import { installPageProbes } from "./lib/page-probes.mjs";
import { safeMessage } from "./lib/safe-message.mjs";
import { assertAction, assertClause, isKnownFontPreloadHint, assertPlaybook, assertReport, assertSynthetic, check, DPR, HELP, parseRecordingArgs, PATIENTS, pngSize, prepareRecordingOutput, rankedActions, selectRejection } from "./lib/recording-kit.mjs";

const SCOPE = '#main-content, [role="dialog"][aria-modal="true"]';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const normalized = text => text.replace(/\s+/g, " ").trim();

function watchPage(page) {
  const pending = new Set();
  const errors = [];
  let known404 = 0;
  let knownFontHints = 0;
  let chat = 0;
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) pending.add(request);
    if (new URL(request.url()).pathname === "/api/chat") chat++;
  });
  page.on("requestfinished", request => pending.delete(request));
  page.on("requestfailed", request => {
    pending.delete(request);
    if (!/ERR_ABORTED/.test(request.failure()?.errorText ?? "")) errors.push("Browser request failed");
  });
  page.on("response", response => {
    pending.delete(response.request());
    if (response.status() < 400) return;
    if (new URL(response.url()).pathname === "/api/frontend-config" && response.status() === 404) known404++;
    else errors.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`);
  });
  page.on("pageerror", error => errors.push(safeMessage(error)));
  page.on("console", message => {
    if (!["error", "warning"].includes(message.type())) return;
    if (message.type() === "warning" && isKnownFontPreloadHint(message.text())) { knownFontHints++; return; }
    if (new URL(message.location().url || page.url()).pathname === "/api/frontend-config" && /404/.test(message.text())) return;
    errors.push(`console ${message.type()}: ${safeMessage(message.text())}`);
  });
  return { pending, errors, get known404() { return known404; }, get knownFontHints() { return knownFontHints; }, get chat() { return chat; } };
}

async function settle(page, watch) {
  const start = Date.now();
  let previous = "";
  let stable = start;
  while (Date.now() - start < 60_000) {
    check(!watch.errors.length && watch.chat === 0, "Browser/console/API error or unexpected chat request");
    const snapshot = await page.evaluate(selector => {
      const scopes = window.__bilunCapture.scopesOf(selector);
      return { count: scopes.length, busy: scopes.some(s => s.querySelector('.skeleton, [aria-busy="true"]')), text: scopes.map(s => s.innerText).join("\n") };
    }, SCOPE);
    if (snapshot.text !== previous || watch.pending.size) { stable = Date.now(); previous = snapshot.text; }
    if (snapshot.count && !snapshot.busy && !/(?:loading|refreshing)[^\n]*(?:…|\.\.\.)|yükleniyor|yenileniyor/i.test(snapshot.text) && Date.now() - stable >= 1200) {
      await page.evaluate(() => document.fonts.ready);
      return;
    }
    await delay(200);
  }
  throw new Error("UI did not settle; refusing to present a loading state as a result");
}

async function get(context, cfg, apiPath) {
  const response = await context.request.get(cfg.baseUrl + apiPath, { maxRedirects: 0 });
  check(response.ok(), `API preflight HTTP ${response.status()}`);
  return response.json();
}

async function preflight(browser, cfg) {
  const context = await browser.newContext();
  try {
    const me = await get(context, cfg, "/api/auth/me");
    check(!me.authenticated && me.public_billing_enabled && me.capabilities?.includes("billing"), "Use anonymous local public billing mode");
    const list = await get(context, cfg, "/api/patients");
    assertSynthetic(list);
    const reports = {}, claims = {};
    for (const patient of PATIENTS) {
      reports[patient] = await get(context, cfg, `/api/billing-report/${patient}`);
      assertReport(reports[patient], patient);
      claims[patient] = (await get(context, cfg, `/api/patients/${patient}/claims`)).claims.map(item => item.claim_id);
    }
    const queue = await get(context, cfg, "/api/medula-rejections/queue?page=1&page_size=50");
    for (const patient of new Set((queue.rows ?? []).map(row => row.patient_id))) {
      check(list.patients.includes(patient), "Queue contains an unknown patient");
      claims[patient] ??= (await get(context, cfg, `/api/patients/${patient}/claims`)).claims.map(item => item.claim_id);
    }
    const rejection = selectRejection(queue, list.patients, claims);
    const wave = await get(context, cfg, `/api/wavea-evidence/${PATIENTS[0]}?kind=reviews&offset=0&limit=1`);
    return { reports, claims, rejection, wave: wave.available ? "available" : wave.unavailable_reason ?? "unavailable" };
  } finally { await context.close(); }
}

async function record(browser, cfg, facts, name, workflow) {
  const context = await browser.newContext({
    viewport: { width: cfg.width, height: cfg.height }, deviceScaleFactor: DPR,
    locale: cfg.locale === "tr" ? "tr-TR" : "en-US", timezoneId: "Europe/Istanbul",
    reducedMotion: "no-preference", colorScheme: "light", serviceWorkers: "block",
  });
  await context.addCookies([{ name: "bilun:locale", value: cfg.locale, url: cfg.baseUrl }]);
  await context.addInitScript(installPageProbes);
  // Fail on accidental chat and prevent any live LLM request from reaching the API.
  await context.route("**/api/chat", route => route.abort());
  const page = await context.newPage();
  // Native Chrome screencasting ignores DPR and pads a CSS-sized picture.
  // Encode unmodified device-scale frames, preserving their real elapsed time.
  const raw = path.join(cfg.out, `.${name}-frames`);
  fs.mkdirSync(raw);
  const start = Date.now();
  const frames = [];
  let capturing = true;
  let captureError;
  const capture = (async () => {
    while (capturing) {
      const at = (Date.now() - start) / 1000;
      try {
        const buffer = await page.screenshot({ scale: "device" });
        const size = pngSize(buffer);
        check(size.width === cfg.width * DPR && size.height === cfg.height * DPR, "Recorded device frame has wrong density");
        const file = `${String(frames.length).padStart(6, "0")}.png`;
        fs.writeFileSync(path.join(raw, file), buffer);
        frames.push({ file, at });
      } catch (error) { captureError = error; break; }
      await delay(Math.max(0, 1000 / 16 - (Date.now() - start - at * 1000)));
    }
  })();
  const watch = watchPage(page);
  const steps = [];
  const checkpoint = async label => {
    await settle(page, watch);
    if (captureError) throw captureError;
    check(await page.evaluate(() => devicePixelRatio) === DPR, "Browser DPR is not 2");
    const size = pngSize(await page.screenshot());
    check(size.width === cfg.width * DPR && size.height === cfg.height * DPR, "Rendered frame is not at DPR 2");
    await delay(1600);
    steps.push({ label, at: (Date.now() - start) / 1000 - 0.7 });
  };
  let result;
  try {
    result = await workflow({ page, context, watch, checkpoint });
    check(!watch.errors.length && watch.chat === 0, "Recording has browser errors or a chat request");
  } finally {
    capturing = false;
    await capture;
    await context.close();
  }
  if (captureError) throw captureError;
  check(frames.length > 1, "Recording has no device-scale frames");
  const filename = path.join(cfg.out, `${name}.webm`);
  const manifest = path.join(raw, "frames.txt");
  fs.writeFileSync(manifest, frames.map((frame, index) => `file '${frame.file}'\nduration ${frames[index + 1] ? frames[index + 1].at - frame.at : 0.1}\n`).join("") + `file '${frames.at(-1).file}'\n`);
  execFileSync("ffmpeg", ["-v", "error", "-f", "concat", "-safe", "1", "-i", manifest, "-fps_mode", "vfr", "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-crf", "24", "-b:v", "0", "-threads", "2", "-pix_fmt", "yuv420p", filename]);
  fs.rmSync(raw, { recursive: true });
  const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height:format=duration", "-of", "json", filename], { encoding: "utf8" }));
  check(probe.streams[0]?.width === cfg.width * DPR && probe.streams[0]?.height === cfg.height * DPR, "Encoded video dimensions do not match DPR 2");
  for (const step of steps) {
    const frame = path.join(cfg.out, `${name}-${step.label}.png`);
    execFileSync("ffmpeg", ["-v", "error", "-ss", String(Math.min(step.at, Number(probe.format.duration) - 0.1)), "-i", filename, "-frames:v", "1", "-threads", "1", frame]);
    const size = pngSize(fs.readFileSync(frame));
    check(size.width === cfg.width * DPR && size.height === cfg.height * DPR, "Extracted video frame dimensions differ");
  }
  return { name, ...result, file: filename, dimensions: `${probe.streams[0].width}x${probe.streams[0].height}`, seconds: probe.format.duration, capturedFrames: frames.length, known404: watch.known404, knownFontPreloadHints: watch.knownFontHints, chatRequests: watch.chat, browserErrors: watch.errors.length, steps };
}

async function openSource(page, context, cfg, watch, control, key) {
  const response = page.waitForResponse(r => new URL(r.url()).pathname === `/api/rules/clauses/${encodeURIComponent(key)}`);
  await control.click();
  const actualResponse = await response;
  check(actualResponse.ok(), "Drawer source request failed");
  const clause = await actualResponse.json();
  assertClause(clause, key);
  // data-clause-key sits on the real dialog itself.
  const drawer = page.locator(`[role="dialog"][data-clause-key=${JSON.stringify(key)}]`);
  await drawer.waitFor({ state: "visible" });
  await settle(page, watch);
  check(normalized(await drawer.innerText()).includes(normalized(clause.text_tr)), "Drawer text differs from its source API");
  check(await drawer.locator(".sut-source-slide").evaluate(e => getComputedStyle(e).animationName) === "sutSourceSlide", "Normal Source motion is missing");
  return clause.clause_coordinate;
}

async function main() {
  const cfg = parseRecordingArgs(process.argv.slice(2));
  if (cfg.help) { console.log(HELP); return; }
  // Required tools are checked before browser creation or any recordings.
  for (const command of ["ffprobe", "ffmpeg"]) execFileSync(command, ["-version"], { stdio: "ignore" });
  prepareRecordingOutput(cfg.out);
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const results = [];
  try {
    const facts = await preflight(browser, cfg);
    results.push(await record(browser, cfg, facts, "01-patients-source", async ({ page, context, watch, checkpoint }) => {
      await page.goto(`${cfg.baseUrl}/?tab=patients`);
      const link = page.getByRole("link", { name: PATIENTS[0], exact: true }).first();
      await link.waitFor(); await checkpoint("patients"); await link.click();
      const row = page.locator("[data-next-actions] li").first(); await row.waitFor();
      const report = facts.reports[PATIENTS[0]];
      const action = assertAction(report, await row.getAttribute("data-action-id"), facts.claims[PATIENTS[0]]);
      check(action.action_id === rankedActions(report)[0]?.action_id, "Rendered first action is not the API's top action");
      const key = action.clause_ref?.clause_key;
      check(key && await row.getAttribute("data-clause-key") === key, "Top action has no real source link");
      await checkpoint("top-action");
      const coordinate = await openSource(page, context, cfg, watch, row.getByRole("button", { name: new RegExp(`^${INSPECT_CLAUSE_LABEL[cfg.locale]}`) }), key);
      await checkpoint("source");
      return { status: "complete", patient: report.patient_id, action: action.action_id, clause: key, coordinate };
    }));
    results.push(await record(browser, cfg, facts, "02-materials-precheck", async ({ page, context, watch, checkpoint }) => {
      await page.goto(`${cfg.baseUrl}/patient/${PATIENTS[1]}`);
      const report = facts.reports[PATIENTS[1]];
      const action = rankedActions(report).find(item => item.surface === "materials" && item.kind === "material_pre_auth");
      check(action, "Actual authored materials pre-check is unavailable");
      assertAction(report, action.action_id, facts.claims[PATIENTS[1]]);
      const row = page.locator(`[data-next-actions] li[data-action-id=${JSON.stringify(action.action_id)}]`);
      await row.waitFor(); await checkpoint("patient");
      await row.getByRole("button").first().click();
      const section = page.locator("#materials-pre-check"); await section.waitFor({ state: "visible" });
      const material = report.materials.pre_auth_required.find(item => item.claim_id === action.claim_id && item.sut_code === action.material_code);
      check(material && normalized(await section.innerText()).includes(material.sut_code), "Materials pre-check does not own the selected action");
      await checkpoint("precheck");
      const key = action.clause_ref?.clause_key;
      if (!key) {
        check(await row.getByRole("button").last().isDisabled(), "An unowned material Source link is enabled");
        return { status: "partial", patient: report.patient_id, action: action.action_id, claim: action.claim_id, material: material.sut_code, limitation: "Actual pre-check recorded; API clause_ref is null and its Source control is disabled. No linked clause can be recorded." };
      }
      await row.scrollIntoViewIfNeeded();
      await openSource(page, context, cfg, watch, row.getByRole("button", { name: new RegExp(`^${INSPECT_CLAUSE_LABEL[cfg.locale]}`) }), key);
      await checkpoint("source");
      return { status: "complete", patient: report.patient_id, action: action.action_id, claim: action.claim_id, material: material.sut_code, clause: key };
    }));
    results.push(await record(browser, cfg, facts, "03-rejection-playbook", async ({ page, watch, checkpoint }) => {
      const row = facts.rejection;
      await page.goto(`${cfg.baseUrl}/?tab=operations`);
      const link = page.getByRole("link", { name: row.claim_id, exact: true }); await link.waitFor();
      const queueRow = link.locator("xpath=ancestor::tr");
      check(normalized(await queueRow.innerText()).includes(row.sonuc_kodu), "Queue row code mismatch");
      await link.scrollIntoViewIfNeeded(); await checkpoint("queue");
      await queueRow.getByRole("cell", { name: row.sonuc_kodu, exact: true }).click();
      const expanded = queueRow.locator("xpath=following-sibling::tr[1]");
      check(normalized(await expanded.innerText()).includes(normalized(row.corrective_steps_tr[0])), "Queue corrective steps mismatch");
      await checkpoint("corrective-steps");
      const response = page.waitForResponse(r => new URL(r.url()).pathname === `/api/billing-report/${row.patient_id}/bills/${row.claim_id}`);
      await link.click();
      const actualResponse = await response; check(actualResponse.ok(), "Scoped playbook request failed");
      const report = await actualResponse.json(); assertReport(report, row.patient_id, row.claim_id);
      const entry = assertPlaybook(report, row);
      const section = page.locator("#medula-playbook"); await section.waitFor({ state: "visible" });
      await section.scrollIntoViewIfNeeded(); await settle(page, watch);
      const rendered = normalized(await section.innerText());
      check(rendered.includes(row.claim_id) && rendered.includes(row.sonuc_kodu) && rendered.includes(normalized(entry.sut_anchor)), "Rendered playbook ownership mismatch");
      const steps = cfg.locale === "en" ? entry.corrective_steps_en ?? entry.corrective_steps_tr : entry.corrective_steps_tr ?? entry.corrective_steps_en;
      check(steps.every(step => rendered.includes(normalized(step))), "Rendered playbook steps differ from API");
      await checkpoint("playbook");
      // Walk the real horizontally scrolling table so its result column is
      // readable too; visibility is not proven by innerText alone.
      await section.getByRole("cell").last().scrollIntoViewIfNeeded();
      await checkpoint("playbook-steps");
      return { status: "complete", patient: row.patient_id, claim: row.claim_id, rejection: row.rejection_event_id, playbook: entry.playbook_id, code: row.sonuc_kodu, reportedEntryCount: report.medula_rejection_playbook.entry_count, actualEntries: report.medula_rejection_playbook.entries.length };
    }));
    const log = { git: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(), locale: cfg.locale, viewport: `${cfg.width}x${cfg.height}`, dpr: DPR, waveA: facts.wave, results };
    // One compact outside-Git diagnostic; no API payload dumps or signed evidence.
    fs.writeFileSync(path.join(cfg.out, "run.txt"), JSON.stringify(log, null, 2) + "\n");
    console.log(JSON.stringify(log, null, 2));
    if (results.some(result => result.status !== "complete")) process.exitCode = 3;
  } finally { await browser.close(); }
}

main().catch(error => { console.error(safeMessage(error)); process.exitCode = 1; });
