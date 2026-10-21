#!/usr/bin/env node
/**
 * capture-screens.mjs - screenshot baseline and "numbers parity" capture for the
 * app UI overhaul (Phase 0 of the overhaul plan: baseline and guardrails, no UI change).
 *
 * One command writes, from a local production build and the SYNTHETIC cohort:
 *   screens/   viewport + full-page PNGs per route, locale and size (plus one viewport PNG
 *              per Source-drawer state)
 *   numbers/   every money amount / count / percent per rendered state (JSON,
 *              deterministic: no timestamps, no commit, no ports), the honesty
 *              wording, the lone "-" placeholders and the amounts that sit under a label
 *   text/      the normalised text behind each numbers file, for diffs:
 *              <state>.txt = everything on the expanded page, <state>.visible.txt =
 *              what the default view really shows (layout-hidden text left out)
 *   metrics/   layout measurements (page height, first table row, money wraps,
 *              money overlaps and clipping, chat input height)
 *   run-meta.json  commit, tool file hashes, versions, failures (NOT deterministic, never compared)
 * and `--compare A B` checks that no number was added, lost, repeated as a zero
 * amount, detached from its label or stripped of its "not exact" wording between
 * two runs (what it can and cannot prove: header of lib/numbers-parity.mjs).
 *
 * LOCAL RUN (verified 2026-10-07; ports 18001/13000 are this lane's ports):
 *   # once per checkout; Node 22 is closer to CI (Node 20) than the laptop's v26
 *   export PATH=/home/safa/.local/node-v22.16.0-linux-x64/bin:$PATH
 *   export TMPDIR=$HOME/.cache/ui-capture-tmp && mkdir -p "$TMPDIR"   # /tmp is a small tmpfs
 *   PY=/home/safa/Documents/Bilun/.venv/bin/python                     # Python 3.13, as CI
 *   (cd frontend && npm ci --no-audit --no-fund)
 *   PYTHONDONTWRITEBYTECODE=1 $PY scripts/bilun/build_cache.py --activate \
 *       --payload-workers 2 --billing-workers 2       # ~3 min; .cache/bilun.duckdb, git-ignored
 *
 *   # backend (repo root). Public billing mode needs NO credentials and is what
 *   # pilot users see. --timeout-keep-alive 65 is REQUIRED: with uvicorn's default
 *   # (5 s) the Next /api proxy hits "socket hang up" and the UI shows API 500s.
 *   env -i PATH="$PATH" HOME="$HOME" TMPDIR="$TMPDIR" PYTHONDONTWRITEBYTECODE=1 \
 *       BILUN_STARTUP_POLICY=load-only BILUN_PUBLIC_BILLING_ENABLED=1 \
 *       $PY -m uvicorn src.bilun.api:app --host 127.0.0.1 --port 18001 --timeout-keep-alive 65 &
 *
 *   # frontend (frontend/). The /api rewrite target is compiled in at BUILD time
 *   # and also read at run time by the identity check, so set it for both.
 *   export API_PROXY_TARGET=http://127.0.0.1:18001 NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS=--max-old-space-size=4096
 *   npm run build && npx next start -H 127.0.0.1 -p 13000 &     # prints a harmless "standalone" warning
 *
 *   # capture (system Chrome via Playwright channel "chrome"; no browser download)
 *   node scripts/capture-screens.mjs --out <dir>          # <dir> must be new (or pass --overwrite)
 *   node scripts/capture-screens.mjs --compare <baselineDir> <candidateDir>
 *       # --strict-multiplicity: a repeated or merged figure fails; --strict-labels: a renamed label fails unless an
 *       # --allow entry (kind "labelled") names it. Use both for a phase that must not move or rename content.
 *   node scripts/capture-screens.mjs --self-test           # no servers: checks the visibility probes in Chrome
 *
 * Routes: the 8 plan routes, plus (unless --no-extras) the split pane, the ?section=&finding=
 * deep link and every other Compliance and Reference Tools sub-view (lib/capture-routes.mjs).
 * The three patient pages are cohort roles read from data/synthetic/cohort_registry.json (see primaryPatients below);
 * the preflight refuses a backend whose patients or bills differ from that registry.
 * States (extended ones only at the first --sizes entry, 1440x900 by default):
 *   default                          every route
 *   page-2 .. page-N                 Patients tab: every page of the table (?p=N); the route fails when the
 *                                    pages do not show every patient of the cohort
 *   view-revenue, view-audit,
 *   claim-<id>                       patient pages
 *   source-drawer                    patient pages: the page-level Source (SUT clause) drawer, opened with the first
 *                                    "Inspect clause" button (looked for in the default, revenue, audit view)
 *   source-drawer-copay              patient pages: the second drawer instance of the copay section, opened with
 *                                    the first [data-clause-link] button; a patient without such a button has no such
 *                                    state (run-meta.json skippedStates)
 * A capture needs about 15 minutes; --routes <ids> --locales en --sizes 1440x900 is the quick check.
 * Re-recording a baseline: pass --overwrite. The old output is only replaced when the whole
 * new run succeeded (it is written next to it as <out>.incomplete first).
 *
 * KNOWN LIMITS (measured, not fixed here because they live in the app)
 *  - At 390 px the app sizes the chat textarea once, at mount, with a transient width, so
 *    identical runs differ by up to about 60 px in scrollHeight, firstTableRowTop and
 *    firstMoney.top of the patient pages (metrics.chatInputHeight records the cause). At 1440
 *    and 1280 they are identical. deepLink.top is the page's own scroll offset and is not stable.
 *  - The collapsed chat bar planned for Phase 1 should remove that jitter (not verified yet).
 *  - Wave A evidence (human review, advisories) is NOT rendered: the backend serves it only with a signed release
 *    receipt, which a local synthetic run cannot have ("wavea_capability_unavailable", recorded in run-meta.json
 *    limits.waveAEvidence and printed at the end of a run). Every patient page shows one "unavailable" line where
 *    the real page has several screens of cards, so page heights here are SHORTER than the real pages and the
 *    Phase 2 collapse of those blocks cannot be measured or checked with this baseline. Test it with component
 *    fixtures, or on an environment that serves Wave A. Nothing here fakes that data.
 *  - Paged tables: Patients is walked (all pages). Not walked, so only their first page is in the baseline:
 *    Reference Tools Drugs (270 pages of reference data) and Compliance Materials (rows 1-100 of 163). They are
 *    listed in run-meta.json limits.unwalkedPagers and metrics/*.json pagers.
 *  - The Source drawer is captured for the first clause button of each kind on the three patient pages, in the
 *    single pane. Other clauses, the split pane and the drawer's loading and error states are not captured.
 *  - moneyWrapCount cannot fire in Turkish (no space inside "₺66.524,22"); moneyOverlapCount
 *    and moneyClippedCount measure collisions and cut-off amounts in both locales.
 *
 * Stop both servers by listening PID when done: ss -ltnp "sport = :13000" (lsof is unreliable here).
 * Identity: default "public" (anonymous, public billing). "--identity dev" mints a
 * developer session cookie from --env-file (needs BILUN_SESSION_SECRET and
 * BILUN_AUTH_USERNAME; see scripts/generate_developer_auth_env.py). BILUN_AUTH_OPTIONAL
 * is NOT enough for the UI: the Next middleware still redirects to /login.
 */
import { chromium } from "playwright";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { CLAUSE_VIEWS, COMPLIANCE_DEEP_LINK_STORY, complianceFindingId, detectPagers, INSPECT_CLAUSE_LABEL, pageUrl, subtabRoutes } from "./lib/capture-routes.mjs";
import { claimIds, faultFor, patientIds, role } from "./lib/cohort-registry.mjs";
import { compareRuns, describeItem, normaliseLines, SCHEMA, tokenise, verdict } from "./lib/numbers-parity.mjs";
import { installPageProbes } from "./lib/page-probes.mjs";
import { runProbeSelfTest } from "./lib/probe-selftest.mjs";
import { registerSecret, safeMessage } from "./lib/safe-message.mjs";

// ---------------------------------------------------------------- constants

// The page, the second pane of the split view and an open modal (the Source drawer renders outside
// #main-content). A match inside another match is counted once (window.__bilunCapture.scopesOf).
const SCOPE_SELECTOR = '#main-content, [data-workspace-pane="b"], [role="dialog"][aria-modal="true"]';
const HOME_ROUTES = ["patients", "compliance", "revenue", "operations", "reference-tools"];

// The patient pages are cohort ROLES, not ids: lib/cohort-registry.mjs reads data/synthetic/cohort_registry.json, so a rebuilt
// cohort needs no edit here. Why these three (read from the engine's billing reports of the 8 first showcase patients, 2026-10-18; S9 was added after):
//   default_landing   the page the app opens on (today the S1 bill): the landing page and the first pane of the split view.
//   the compliance    the bill of the story COMPLIANCE_DEEP_LINK_STORY (S6, drug indication; its fault has effect_kind
//   story             "compliance_error"). Its compliance row carries a canonical finding_id, which the
//                     ?section=claim-compliance&finding= deep link selects. It is the deep-link patient (the legacy script used
//                     the patient that had a claim-compliance finding) and the second pane of the split view. The story is
//                     named, not searched: "the first compliance_error fault in registry order" was S6 until patient 4's
//                     second visit (S40, a duplicate examination, also compliance_error) came before it in the registry.
//   showcase_S7       the only bill with a clause_ref on an action (copay exemption review, SUT 1.8.5), so the only page that can
//                     show the two Source-drawer states; a state is skipped, and listed in run-meta.json, where no button exists.
// Route ids keep their old shape (patient-<last 4 digits>, patient-<a>+<b>-split, patient-<n>-finding).
const last4 = (patient) => patient.slice(-4);

/** The patient ids of the capture and the deep-link patient, from the registry. The compliance story is named by COMPLIANCE_DEEP_LINK_STORY; its bill is found through the registry. */
function primaryPatients() {
  const fault = faultFor(COMPLIANCE_DEEP_LINK_STORY);
  if (fault.effect_kind !== "compliance_error") throw usage(`The cohort registry's fault for ${COMPLIANCE_DEEP_LINK_STORY} is a ${fault.effect_kind}, not a compliance_error, so the claim-compliance deep link has no patient.`);
  const compliance = role(`showcase_${COMPLIANCE_DEEP_LINK_STORY}`).patient_id;
  return { primary: [...new Set([role("default_landing").patient_id, compliance, role("showcase_S7").patient_id])], compliance };
}

const TIMEZONE = "Europe/Istanbul";
// /api/frontend-config has no backend route at c44aa78c (404 on every page load): known, pre-existing.
const KNOWN_API_NOISE = [{ method: "GET", path: "/api/frontend-config", status: 404 }];
// The chat panel is stubbed with the backend's own "no LLM key" stream so the
// screenshots never depend on a key, on model output or on the 429 rate limit.
const CHAT_STUB = {
  status: 200,
  headers: { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-store" },
  body: ': stream-start\n\ndata: "Chat is temporarily unavailable. Please try later."\n\ndata: "[DONE]"\n\n',
};
const LOADING_TEXT = /(?:loading|refreshing)[^\n]*(?:…|\.\.\.)\s*$|y[üu]kleniyor|yenileniyor/im;

// ---------------------------------------------------------------- cli

const HELP = [
  "Usage: node scripts/capture-screens.mjs [options]   (run commands: see the header of this file)",
  "  --out <dir>  --locales en,tr  --sizes 1440x900,1280x800,390x844  --routes <ids>  --mode all|screens|numbers",
  "  --identity public|dev [--env-file <file>]  --base-url <url>  --retries 2  --probe name=css  --no-extras  --overwrite",
  "  --compare <baselineDir> <candidateDir> [--allow <file>] [--strict-multiplicity] [--strict-labels] [--json <file>]",
  "  --self-test   (checks the visibility probes against a built-in page; needs Chrome, no servers)",
].join("\n");

function usage(message) {
  const error = new Error(message);
  error.exitCode = 2;
  return error;
}

const VALUE_OPTIONS = new Set([
  "base-url", "out", "label", "mode", "locales", "sizes", "routes", "identity", "env-file",
  "channel", "chrome-path", "retries", "dpr", "probe", "compare", "allow", "json",
]);

function parseArgs(argv) {
  const flags = new Set(["no-full-page", "reduced-motion", "no-extras", "strict-multiplicity", "strict-labels", "overwrite", "self-test", "help"]);
  const opts = { probe: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) throw usage(`Unexpected argument: ${arg}`);
    const key = arg.slice(2);
    // A typo such as --route must not silently run the whole matrix.
    if (!flags.has(key) && !VALUE_OPTIONS.has(key)) throw usage(`Unknown option: --${key}\n${HELP}`);
    if (flags.has(key)) opts[key] = true;
    else if (key === "compare") opts.compare = [argv[(i += 1)], argv[(i += 1)]];
    else if (key === "probe") opts.probe.push(argv[(i += 1)]);
    else opts[key] = argv[(i += 1)];
    const missing = key === "compare" ? opts.compare.some((v) => v === undefined) : key === "probe" ? opts.probe.at(-1) === undefined : opts[key] === undefined;
    if (missing) throw usage(`Missing value for --${key}`);
  }
  const cfg = {
    baseUrl: (opts["base-url"] ?? "http://127.0.0.1:13000").replace(/\/$/, ""),
    out: path.resolve(opts.out ?? path.join(".cache", "ui-capture", opts.label ?? "run")),
    mode: opts.mode ?? "all", // all | screens | numbers
    locales: (opts.locales ?? "en,tr").split(","),
    sizes: (opts.sizes ?? "1440x900,1280x800,390x844").split(",").map((s) => s.split("x").map(Number)),
    routes: opts.routes ? opts.routes.split(",") : null,
    identity: opts.identity ?? "public", // public | dev
    envFile: opts["env-file"] ?? null,
    channel: opts.channel ?? "chrome",
    chromePath: opts["chrome-path"] ?? null,
    retries: Number(opts.retries ?? 2),
    dpr: Number(opts.dpr ?? 1),
    fullPage: !opts["no-full-page"],
    reducedMotion: Boolean(opts["reduced-motion"]),
    extras: !opts["no-extras"],
    overwrite: Boolean(opts.overwrite),
    probes: opts.probe.map((p) => ({ name: p.split("=")[0], css: p.slice(p.indexOf("=") + 1) })),
    help: Boolean(opts.help),
    selfTest: Boolean(opts["self-test"]),
    compare: opts.compare ?? null,
    strictMultiplicity: Boolean(opts["strict-multiplicity"]),
    strictLabels: Boolean(opts["strict-labels"]),
    allowFile: opts.allow ?? null,
    jsonReport: opts.json ?? null,
  };
  if (!["all", "screens", "numbers"].includes(cfg.mode)) throw usage("--mode must be all, screens or numbers");
  if (!cfg.locales.every((l) => ["en", "tr"].includes(l))) throw usage("--locales may only contain en and tr");
  if (!cfg.sizes.every(([w, h]) => Number.isInteger(w) && Number.isInteger(h) && w > 0 && h > 0)) throw usage("--sizes must look like 1440x900,390x844");
  if (!Number.isInteger(cfg.retries) || cfg.retries < 0) throw usage("--retries must be a non-negative integer");
  if (!(cfg.dpr > 0)) throw usage("--dpr must be a positive number");
  return cfg;
}

// ---------------------------------------------------------------- identity

function envValue(text, key) {
  // dotenv semantics: trim and strip surrounding quotes (tasks/lessons.md, 2026-08-16).
  return text.match(new RegExp(`^${key}=(.*)$`, "m"))?.[1]?.trim().replace(/^["']|["']$/g, "");
}

/** Mirrors src/bilun/api/auth.py issue_session_token: base64url("<purpose>:<user>.<exp>") . base64url(HMAC-SHA256). */
function mintSessionToken(envFile) {
  const text = fs.readFileSync(envFile, "utf8");
  const secret = envValue(text, "BILUN_SESSION_SECRET");
  const user = envValue(text, "BILUN_AUTH_USERNAME");
  const purpose = envValue(text, "BILUN_SESSION_TOKEN_PURPOSE") ?? "bilun-developer-v1";
  if (!secret || !user) throw usage("--env-file must define BILUN_SESSION_SECRET and BILUN_AUTH_USERNAME");
  const payload = Buffer.from(`${purpose}:${user}.${Math.floor(Date.now() / 1000) + 8 * 3600}`, "utf8");
  const signature = crypto.createHmac("sha256", secret).update(payload).digest();
  const token = `${payload.toString("base64url")}.${signature.toString("base64url")}`;
  registerSecret(token);
  registerSecret(secret);
  return token;
}

// ---------------------------------------------------------------- browser helpers

async function newContext(browser, cfg, { locale, size, split, token }) {
  const [width, height] = size;
  const context = await browser.newContext({
    viewport: { width, height },
    locale: locale === "tr" ? "tr-TR" : "en-US",
    timezoneId: TIMEZONE,
    colorScheme: "light",
    deviceScaleFactor: cfg.dpr,
    reducedMotion: cfg.reducedMotion ? "reduce" : "no-preference",
    serviceWorkers: "block",
  });
  const cookies = [{ name: "bilun:locale", value: locale, url: cfg.baseUrl }];
  if (token) cookies.push({ name: "bilun:session", value: token, url: cfg.baseUrl });
  await context.addCookies(cookies);
  await context.addInitScript(installPageProbes);
  await context.route("**/api/chat", (route) => route.fulfill(CHAT_STUB));
  if (split) {
    // Pane B is store-only (lib/workspaceTabs.ts WORKSPACE_STORAGE_KEY), so seed the session.
    const tab = (refId, at) => ({ id: `patient:${refId}`, kind: "patient", refId, lastActivatedAt: at });
    const session = {
      tabs: [tab(split.a, 2), tab(split.b, 1)],
      activeTabId: `patient:${split.a}`,
      paneBTabId: `patient:${split.b}`,
    };
    await context.addInitScript(
      ({ key, value }) => {
        try {
          if (!sessionStorage.getItem(key)) sessionStorage.setItem(key, value);
        } catch {
          /* storage unavailable */
        }
      },
      { key: "bilun:workspace-tabs", value: JSON.stringify(session) },
    );
  }
  return context;
}

/** Tracks in-flight /api requests and every failure that would make a capture untrustworthy. */
function watchPage(page) {
  const open = new Set();
  const failures = [];
  const warnings = [];
  const apiPath = (request) => {
    const url = new URL(request.url());
    return url.pathname.startsWith("/api/") ? url.pathname : null;
  };
  page.on("request", (request) => {
    if (apiPath(request)) open.add(request);
  });
  page.on("response", (response) => {
    const request = response.request();
    open.delete(request);
    const p = apiPath(request);
    if (!p || response.status() < 400) return;
    const known = KNOWN_API_NOISE.some((n) => n.method === request.method() && n.path === p && n.status === response.status());
    if (!known) failures.push(`${request.method()} ${p} -> ${response.status()}`);
  });
  page.on("requestfinished", (request) => open.delete(request));
  page.on("requestfailed", (request) => {
    open.delete(request);
    const p = apiPath(request);
    const reason = request.failure()?.errorText ?? "";
    // ERR_ABORTED is the app cancelling its own fetch (AbortController), not a failure.
    if (p && !/ERR_ABORTED/.test(reason)) failures.push(`${request.method()} ${p} FAILED ${reason}`);
  });
  page.on("pageerror", (error) => warnings.push(`pageerror: ${String(error.message).slice(0, 160)}`));
  return { inflight: () => open.size, failures, warnings };
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * "Ready" = scopes present, no skeleton / aria-busy / "Loading…" text, no /api request in
 * flight for 1 s, and the scope text unchanged for 1.2 s. Fails (throws) after timeoutMs:
 * a half-loaded page must never become a baseline. (Playwright "networkidle" is unusable:
 * the app polls /api/auth/me every 30 s and /api/frontend-config never completes.)
 */
async function settle(page, watch, { scopes = 1, timeoutMs = 90_000 } = {}) {
  const start = Date.now();
  let lastText = null;
  let stableSince = Date.now();
  let quietSince = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (watch.failures.length) throw new Error(`API failures: ${[...new Set(watch.failures)].join("; ")}`);
    const snap = await page.evaluate((selector) => {
      const nodes = window.__bilunCapture.scopesOf(selector);
      return {
        count: nodes.length,
        pending: nodes.reduce((n, s) => n + s.querySelectorAll('.skeleton, [aria-busy="true"]').length, 0),
        text: nodes.map((s) => s.innerText).join("\n"),
      };
    }, SCOPE_SELECTOR);
    if (watch.inflight() > 0) quietSince = Date.now();
    if (snap.text !== lastText) {
      lastText = snap.text;
      stableSince = Date.now();
    }
    if (
      snap.count >= scopes &&
      snap.pending === 0 &&
      !LOADING_TEXT.test(snap.text) &&
      Date.now() - quietSince >= 1000 &&
      Date.now() - stableSince >= 1200
    ) {
      await page.evaluate(() => document.fonts.ready);
      return;
    }
    await sleep(250);
  }
  throw new Error(`settle timeout after ${timeoutMs} ms (in flight: ${watch.inflight()})`);
}

/** Open every <details> and every plain disclosure button so collapsed numbers become measurable. */
async function expandAll(page) {
  for (let round = 0; round < 4; round += 1) {
    const changed = await page.evaluate((selector) => {
      let n = 0;
      for (const scope of window.__bilunCapture.scopesOf(selector)) {
        for (const d of scope.querySelectorAll("details:not([open])")) {
          d.open = true;
          n += 1;
        }
        const buttons = scope.querySelectorAll(
          'button[aria-expanded="false"][aria-controls]:not([aria-haspopup]):not([role="combobox"]):not([role="tab"])',
        );
        for (const b of buttons) {
          if (!b.closest("form")) {
            b.click();
            n += 1;
          }
        }
      }
      return n;
    }, SCOPE_SELECTOR);
    if (!changed) return;
    await sleep(400);
  }
}

/** Everything innerText gives: the expanded page, including text CSS merely collapsed. */
const readScopes = (page) =>
  page.evaluate((selector) => window.__bilunCapture.scopesOf(selector).map((s) => s.innerText).join("\n"), SCOPE_SELECTOR);

/** What the default view really shows: innerText minus anything the layout hides (lib/page-probes.mjs). */
const readVisible = (page) => page.evaluate((selector) => window.__bilunCapture.visibleText(selector), SCOPE_SELECTOR);

/** Layout metrics of the default view (taken before anything is expanded). */
function measure(page, probes) {
  return page.evaluate(
    ({ selector, probes: probeList }) => {
      const scopes = window.__bilunCapture.scopesOf(selector);
      const scrollY = window.scrollY;
      const round = (n) => Math.round(n);
      const isHidden = window.__bilunCapture.hiddenCheck();
      const en = /-?\d[\d,]*(?:\.\d+)? TRY/g;
      const tr = /₺-?\d[\d.]*(?:,\d+)?/g;
      const trPostfix = /(?<![\w.,])-?\d+(?:\.\d+)? ?₺/g; // backend prose: "9000.00 ₺"
      // 1. every rendered text node of the scopes (layout-hidden ones left out) with its line boxes,
      //    cut to what the clipping ancestors (overflow hidden / ellipsis / scroll boxes) really show
      const clipBox = new Map();
      const clippingBox = (el) => {
        if (!clipBox.has(el)) {
          const cs = getComputedStyle(el);
          clipBox.set(el, cs.overflowX !== "visible" || cs.overflowY !== "visible" ? el.getBoundingClientRect() : null);
        }
        return clipBox.get(el);
      };
      const shown = (rect, from) => {
        let box = { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
        for (let el = from; el && el !== document.body; el = el.parentElement) {
          const c = clippingBox(el);
          if (!c) continue;
          box = { left: Math.max(box.left, c.left), right: Math.min(box.right, c.right), top: Math.max(box.top, c.top), bottom: Math.min(box.bottom, c.bottom) };
          if (box.right <= box.left || box.bottom <= box.top) return null;
        }
        return { ...box, width: box.right - box.left, height: box.bottom - box.top };
      };
      const texts = [];
      for (const scope of scopes) {
        const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          if (!node.nodeValue.trim() || !node.parentElement || isHidden(node.parentElement)) continue;
          const range = document.createRange();
          range.selectNodeContents(node);
          const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
          if (rects.length) texts.push({ node, rects, shown: rects.map((r) => shown(r, node.parentElement)).filter(Boolean) });
        }
      }
      // 2. money amounts
      const wraps = [];
      const money = [];
      let first = null;
      for (const entry of texts) {
        const text = entry.node.nodeValue.replace(/\s/g, " ");
        for (const re of [en, tr, trPostfix]) {
          re.lastIndex = 0;
          for (let m = re.exec(text); m; m = re.exec(text)) {
            const range = document.createRange();
            range.setStart(entry.node, m.index);
            range.setEnd(entry.node, m.index + m[0].length);
            const rects = [...range.getClientRects()].filter((r) => r.width > 0);
            if (!rects.length) continue;
            money.push({ text: m[0], node: entry.node, rects, shown: rects.map((r) => shown(r, entry.node.parentElement)).filter(Boolean) });
            const lines = new Set(rects.map((r) => round(r.top))).size;
            const top = round(Math.min(...rects.map((r) => r.top)) + scrollY);
            const bottom = round(Math.max(...rects.map((r) => r.bottom)) + scrollY);
            if (!first || top < first.top) first = { text: m[0], top, bottom };
            if (lines > 1) wraps.push({ text: m[0], lines });
          }
        }
      }
      // 3. collisions: an amount printed over other text (or another amount), and an amount cut off by a clipping ancestor
      // Two text boxes collide when they share the same line band (at least half of the smaller box's
      // height, so a label right above a value does not count) and cross horizontally by at least
      // 10% of the narrower box (and more than 2 px).
      const collide = (a, b) => {
        const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        return ox > 2 && oy >= 0.5 * Math.min(a.height, b.height) && ox >= 0.1 * Math.min(a.width, b.width);
      };
      const overlaps = [];
      const clipped = [];
      for (const m of money) {
        const hit = texts.find(
          (other) => other.node !== m.node && other.shown.some((o) => m.shown.some((r) => collide(r, o))),
        );
        if (hit) overlaps.push({ text: m.text, top: round(Math.min(...m.rects.map((r) => r.top)) + scrollY), with: hit.node.nodeValue.trim().slice(0, 60) });
        const left = Math.min(...m.rects.map((r) => r.left));
        const right = Math.max(...m.rects.map((r) => r.right));
        let cut = right > document.documentElement.clientWidth + 1 || left < -1 ? "page" : null;
        for (let el = m.node.parentElement; el && el !== document.body && !cut; el = el.parentElement) {
          const box = clippingBox(el);
          if (box && (right > box.right + 1 || left < box.left - 1)) cut = `${el.tagName.toLowerCase()}${el.className && typeof el.className === "string" ? `.${el.className.split(" ")[0]}` : ""}`;
        }
        if (cut) clipped.push({ text: m.text, top: round(Math.min(...m.rects.map((r) => r.top)) + scrollY), by: cut });
      }
      // 4. named probes and page numbers
      const row = scopes[0]?.querySelector("tbody tr");
      const boxes = {};
      for (const { name, css } of probeList) {
        const el = document.querySelector(css);
        if (!el) {
          boxes[name] = null;
          continue;
        }
        const r = el.getBoundingClientRect();
        boxes[name] = { top: round(r.top + scrollY), bottom: round(r.bottom + scrollY), left: round(r.left), width: round(r.width) };
      }
      const chat = scopes[0]?.querySelector("textarea");
      const de = document.documentElement;
      return {
        scrollHeight: de.scrollHeight,
        horizontalScroll: de.scrollWidth > de.clientWidth,
        firstTableRowTop: row ? round(row.getBoundingClientRect().top + scrollY) : null,
        firstMoney: first,
        moneyCount: money.length,
        moneyWrapCount: wraps.length,
        moneyWraps: wraps,
        moneyOverlapCount: overlaps.length,
        moneyOverlaps: overlaps.slice(0, 10),
        moneyClippedCount: clipped.length,
        moneyClipped: clipped.slice(0, 10),
        chatInputHeight: chat ? round(chat.getBoundingClientRect().height) : null,
        probes: boxes,
      };
    },
    { selector: SCOPE_SELECTOR, probes },
  );
}

// ---------------------------------------------------------------- routes and states

async function fetchJson(context, cfg, apiPath) {
  const response = await context.request.get(`${cfg.baseUrl}${apiPath}`);
  if (!response.ok()) throw new Error(`GET ${apiPath} -> ${response.status()}`);
  return response.json();
}

async function preflight(browser, cfg, token) {
  const context = await newContext(browser, cfg, { locale: "en", size: [1440, 900], token });
  try {
    const me = await fetchJson(context, cfg, "/api/auth/me");
    if (cfg.identity === "public" && !(me.public_billing_enabled && !me.authenticated && me.capabilities?.includes("billing"))) {
      throw usage("Backend is not in public billing mode. Start it with BILUN_PUBLIC_BILLING_ENABLED=1.");
    }
    if (cfg.identity === "dev" && !(me.authenticated && me.role === "dev")) {
      throw usage("The session cookie was not accepted: --env-file does not match the running backend.");
    }
    const list = await fetchJson(context, cfg, "/api/patients");
    const ids = list.patients ?? [];
    if (list.data_source?.is_synthetic !== true || !ids.every((id) => id.startsWith("SENTETIK-HASTA-"))) {
      throw usage("Refusing to capture: the cohort is not the synthetic demo cohort.");
    }
    // The backend must serve the cohort the registry describes: a cache built from older data would pass every id test below.
    const unknown = ids.filter((id) => !patientIds.includes(id));
    const missing = patientIds.filter((id) => !ids.includes(id));
    if (unknown.length || missing.length) {
      throw usage(`The backend serves a cohort that differs from the registry (${missing.length} registry patients missing, ${unknown.length} others). Rebuild the cache (scripts/bilun/build_cache.py --activate) and restart the backend.`);
    }
    const { primary, compliance: compliancePatient } = primaryPatients();
    // Dynamic inputs: bills per patient (they must be the registry's bills) and one compliance finding for the deep-link route.
    const claims = {};
    for (const id of primary) {
      const body = await fetchJson(context, cfg, `/api/patients/${id}/claims`);
      claims[id] = (body.claims ?? []).map((c) => c.claim_id).sort();
      const expected = claimIds.filter((claim) => claim.startsWith(`F-${id}-`));
      if (JSON.stringify(claims[id]) !== JSON.stringify(expected)) {
        throw usage(`The bills of ${id} are [${claims[id].join(", ")}] but the registry says [${expected.join(", ")}]: the backend is not serving this cohort.`);
      }
    }
    const report = await fetchJson(context, cfg, `/api/billing-report/${compliancePatient}`);
    const findingId = complianceFindingId(report);
    if (cfg.extras && !findingId) {
      throw usage(`${compliancePatient} has no compliance finding with an id, so the deep-link route cannot be captured. Use --no-extras to skip it on purpose.`);
    }
    // Wave A evidence (human review, advisories) is served only with a signed release receipt, which a local
    // synthetic run cannot have. Record what the backend says so the limit is data, not memory.
    let waveA = { available: null, reason: "probe failed" };
    try {
      const wave = await fetchJson(context, cfg, `/api/wavea-evidence/${primary[0]}?kind=reviews&offset=0&limit=1`);
      waveA = { available: wave.available === true, reason: wave.unavailable_reason ?? null };
    } catch (error) {
      waveA.reason = safeMessage(error);
    }
    return { cohortSize: ids.length, primary, compliancePatient, claims, findingId, waveA };
  } finally {
    await context.close();
  }
}

function buildRoutes(cfg, facts) {
  // The Patients table shows 10 patients per page (PAGE_SIZE in PatientInvoiceTable.tsx) and keeps its page in ?p=: the tool walks
  // every page. A cohort that fits one page has a single page and no pager with more to see; the 11 showcase patients
  // (14 bills: a patient list row is a patient, not a bill) take two.
  const routes = HOME_ROUTES.map((id) => ({ id, kind: "home", url: `/?tab=${id}`, ...(id === "patients" ? { pageWalk: true } : {}) }));
  for (const patient of facts.primary) {
    routes.push({ id: `patient-${last4(patient)}`, kind: "patient", url: `/patient/${patient}`, patient });
  }
  if (cfg.extras) {
    // Beyond the eight plan routes: split pane (every patient-page change is tested in both), the
    // ?section=&finding= deep link that Phase 2 must keep working, and the sub-views below.
    const [a, b] = facts.primary;
    routes.push({ id: `patient-${last4(a)}+${last4(b)}-split`, kind: "split", url: `/patient/${a}`, split: { a, b } });
    if (facts.findingId) {
      routes.push({
        id: `patient-${last4(facts.compliancePatient)}-finding`,
        kind: "deeplink",
        url: `/patient/${facts.compliancePatient}?section=claim-compliance&finding=${encodeURIComponent(facts.findingId)}`,
        findingId: facts.findingId,
      });
    }
    // The other Compliance and Reference Tools sub-views: Phases 3 and 4 rewrite their tables and tiles.
    routes.push(...subtabRoutes());
  }
  if (!cfg.routes) return routes;
  const unknown = cfg.routes.filter((id) => !routes.some((r) => r.id === id));
  if (unknown.length) throw usage(`Unknown route id(s): ${unknown.join(", ")}. Known: ${routes.map((r) => r.id).join(", ")}`);
  return routes.filter((r) => cfg.routes.includes(r.id));
}

/** [{ state, url, afterOpen }] for one route. Extended states only at the primary size. */
function planStates(route, facts, primary) {
  const states = [{ state: "default", url: route.url }];
  if (route.kind === "patient" && primary) {
    for (const view of ["revenue", "audit"]) {
      states.push({ state: `view-${view}`, url: route.url, view });
    }
    for (const claimId of facts.claims[route.patient] ?? []) {
      states.push({ state: `claim-${claimId}`, url: `${route.url}?claim=${encodeURIComponent(claimId)}` });
    }
    // The Source (SUT clause) drawer: the page-level drawer ("Inspect clause") and the second drawer instance of the
    // copay section. First button of each kind; a patient without such a button has no such state (run-meta lists it).
    states.push({ state: "source-drawer", url: route.url, clause: "inspect", screenshot: true });
    states.push({ state: "source-drawer-copay", url: route.url, clause: "copay", screenshot: true });
  }
  return states;
}

/** Click the tab of a patient view (Radix gives each trigger the id "<base>-trigger-<value>", components/primitives/Tabs.tsx). */
async function switchView(page, watch, scopes, view) {
  await page.locator(`#main-content [role="tab"][id$="-trigger-${view}"]`).first().click();
  await settle(page, watch, { scopes });
}

/**
 * Opens the first clause button of one kind. Looks in the default view, then the revenue view, then the audit
 * view (a later phase may move the button). Returns false when no view has such a button.
 */
async function openClause(page, watch, locale, kind, scopes) {
  const selector =
    kind === "inspect"
      ? `#main-content button[aria-label^="${INSPECT_CLAUSE_LABEL[locale]}"]`
      : "#main-content [data-clause-link]";
  for (const view of CLAUSE_VIEWS) {
    if (view !== "default") await switchView(page, watch, scopes, view);
    const button = page.locator(selector).first();
    if (await button.count()) {
      await button.click();
      await page.locator('[role="dialog"][aria-modal="true"]').first().waitFor({ state: "visible", timeout: 15_000 });
      await settle(page, watch, { scopes });
      return true;
    }
  }
  return false;
}

/** Returns false when the state cannot exist on this page (no clause button). */
async function openState(page, watch, cfg, route, spec, locale) {
  await page.goto(`${cfg.baseUrl}${spec.url}`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  const scopes = route.kind === "split" ? 2 : 1;
  await settle(page, watch, { scopes });
  if (spec.view) await switchView(page, watch, scopes, spec.view);
  if (spec.clause) return openClause(page, watch, locale, spec.clause, scopes);
  return true;
}

/** The patient ids in the first column of the table(s) on the page (locale independent). */
const readPatientRows = (page) =>
  page.evaluate(
    (selector) =>
      window.__bilunCapture
        .scopesOf(selector)
        .flatMap((scope) => [...scope.querySelectorAll("tbody tr")].map((tr) => tr.querySelector("td, th")?.innerText.trim() ?? ""))
        .filter((text) => /^SENTETIK-HASTA-\d{4}$/.test(text)),
    SCOPE_SELECTOR,
  );

async function captureRoute(browser, cfg, route, locale, size, primary, facts, token) {
  const context = await newContext(browser, cfg, { locale, size, split: route.split, token });
  const page = await context.newPage();
  const watch = watchPage(page);
  const scopes = route.kind === "split" ? 2 : 1;
  const result = { states: [], skipped: [], metrics: null, screens: {}, layoutHiddenElements: 0 };
  const patientRows = new Set();
  try {
    const queue = planStates(route, facts, primary);
    for (let index = 0; index < queue.length; index += 1) {
      const spec = queue[index];
      if (!(await openState(page, watch, cfg, route, spec, locale))) {
        result.skipped.push({ state: spec.state, reason: "no clause button of this kind on the patient page" });
        continue;
      }
      if (spec.page) {
        // A page that did not open (the app clamps ?p= to the last page) would be recorded twice under a wrong name.
        const shown = detectPagers(await readScopes(page)).find((pager) => pager.kind === "page");
        if (shown?.current !== spec.page) throw new Error(`state ${spec.state}: the pager shows page ${shown?.current ?? "none"}`);
      }
      if (spec.state === "default") {
        // Measure first: screenshots can move the scroll position (deep link).
        result.metrics = await measure(page, cfg.probes);
        if (route.kind === "deeplink") {
          result.metrics.deepLink = await page.evaluate((id) => {
            const row = [...document.querySelectorAll("[data-finding-id]")].find((e) => e.dataset.findingId === id);
            if (!row) return { found: false };
            const r = row.getBoundingClientRect();
            return { found: true, inViewport: r.top >= 0 && r.bottom <= window.innerHeight, top: Math.round(r.top) };
          }, route.findingId);
        }
        if (cfg.mode !== "numbers") {
          if (route.kind !== "deeplink") await page.evaluate(() => window.scrollTo(0, 0));
          result.screens.viewport = await page.screenshot({ animations: "disabled", caret: "hide" });
          if (cfg.fullPage) result.screens.full = await page.screenshot({ animations: "disabled", caret: "hide", fullPage: true });
        }
      } else if (spec.screenshot && cfg.mode !== "numbers") {
        result.screens[spec.state] = await page.screenshot({ animations: "disabled", caret: "hide" });
      }
      // After measure() and the screenshots: reading the visible text briefly hides collapsed boxes
      // (lib/page-probes.mjs), which a component with a ResizeObserver could react to.
      const visible = await readVisible(page);
      result.layoutHiddenElements += visible.hiddenElements;
      await expandAll(page);
      await settle(page, watch, { scopes });
      const expandedText = await readScopes(page);
      result.states.push({
        state: spec.state,
        visibleLines: normaliseLines(visible.text),
        expandedLines: normaliseLines(expandedText),
      });
      if (route.pageWalk) for (const id of await readPatientRows(page)) patientRows.add(id);
      if (spec.state === "default") {
        // Every pager on the page goes into the metrics, walked or not (run-meta lists the ones nobody walked).
        result.metrics.pagers = detectPagers(expandedText);
        const pager = result.metrics.pagers.find((candidate) => candidate.kind === "page");
        if (route.pageWalk && primary) {
          // detectPagers lists only pagers with more to see, so a cohort that fits one page (the 9 showcase patients) has none:
          // the default state is then the whole table. A pager the tool failed to read is still caught below, because the walk
          // must have seen every patient of the cohort.
          const pages = pager ? pager.total : 1;
          for (let number = 2; number <= pages; number += 1) queue.push({ state: `page-${number}`, url: pageUrl(route.url, number), page: number });
          result.metrics.pagesWalked = pages;
        }
      }
    }
    if (route.pageWalk && primary) {
      // The walk is only worth something if it reached every patient of the cohort.
      if (patientRows.size !== facts.cohortSize) throw new Error(`the page walk saw ${patientRows.size} of ${facts.cohortSize} patients`);
      result.metrics.patientRowsSeen = patientRows.size;
    }
  } finally {
    await context.close();
  }
  result.failures = watch.failures;
  result.warnings = watch.warnings;
  return result;
}

// ---------------------------------------------------------------- output

function writeFile(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
}

function writeResult(cfg, route, locale, size, result) {
  const tag = `${size[0]}x${size[1]}`;
  for (const s of result.states) {
    const base = path.join(locale, tag, route.id, s.state);
    if (cfg.mode !== "screens") {
      const doc = {
        schema: SCHEMA,
        identity: cfg.identity,
        locale,
        route: route.id,
        state: s.state,
        visible: tokenise(s.visibleLines),
        expanded: tokenise(s.expandedLines),
      };
      writeFile(path.join(cfg.writeDir, "numbers", `${base}.json`), `${JSON.stringify(doc, null, 2)}\n`);
      writeFile(path.join(cfg.writeDir, "text", `${base}.txt`), `${s.expandedLines.join("\n")}\n`);
      writeFile(path.join(cfg.writeDir, "text", `${base}.visible.txt`), `${s.visibleLines.join("\n")}\n`);
    }
  }
  for (const [name, png] of Object.entries(result.screens)) {
    const file = name === "viewport" ? `${route.id}.png` : name === "full" ? `${route.id}.full.png` : `${route.id}.${name}.png`;
    writeFile(path.join(cfg.writeDir, "screens", locale, tag, file), png);
  }
  if (result.metrics) {
    writeFile(path.join(cfg.writeDir, "metrics", locale, tag, `${route.id}.json`), `${JSON.stringify(result.metrics, null, 2)}\n`);
  }
}

const GENERATED = ["numbers", "text", "metrics", "screens", "run-meta.json"];

/**
 * A capture must never mix with files of an earlier run (stale numbers would pass a compare as
 * if they were new), and a failed run must never destroy a recorded baseline. So: a fresh --out
 * is written in place; with --overwrite over an existing capture the new run is staged in
 * <out>.incomplete and replaces the old output only when the whole run succeeded.
 */
function prepareOutDir(cfg) {
  const existing = GENERATED.filter((name) => fs.existsSync(path.join(cfg.out, name)));
  if (existing.length && !cfg.overwrite) {
    throw usage(`${cfg.out} already holds capture output (${existing.join(", ")}). Use a new --out, or pass --overwrite to replace it.`);
  }
  cfg.staged = existing.length > 0;
  cfg.writeDir = cfg.staged ? `${cfg.out}.incomplete` : cfg.out;
  if (cfg.staged) fs.rmSync(cfg.writeDir, { recursive: true, force: true });
}

/** Replace the old output by the staged one (all generated names go, so nothing of the old run survives). */
function publishStaged(cfg) {
  for (const name of GENERATED) fs.rmSync(path.join(cfg.out, name), { recursive: true, force: true });
  for (const name of GENERATED) {
    const from = path.join(cfg.writeDir, name);
    if (fs.existsSync(from)) fs.renameSync(from, path.join(cfg.out, name));
  }
  fs.rmSync(cfg.writeDir, { recursive: true, force: true });
}

function gitMeta() {
  const git = (...args) => {
    try {
      return execFileSync("git", args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    } catch {
      return null;
    }
  };
  return { sha: git("rev-parse", "HEAD"), branch: git("branch", "--show-current"), dirty: Boolean(git("status", "--porcelain")) };
}

// ---------------------------------------------------------------- compare

function walkJson(dir) {
  const found = {};
  const visit = (current) => {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) visit(full);
      else if (entry.name.endsWith(".json")) found[path.relative(dir, full).replace(/\.json$/, "").split(path.sep).join("/")] = JSON.parse(fs.readFileSync(full, "utf8"));
    }
  };
  visit(dir);
  return found;
}

const REPORT_LIMIT = 60;

function runCompare(cfg) {
  const [a, b] = cfg.compare.map((d) => path.resolve(d));
  const baseline = walkJson(path.join(a, "numbers"));
  if (!Object.keys(baseline).length) throw usage(`No numbers files under ${a}/numbers`);
  const allow = cfg.allowFile ? JSON.parse(fs.readFileSync(cfg.allowFile, "utf8")) : {};
  const report = compareRuns(baseline, walkJson(path.join(b, "numbers")), { strictMultiplicity: cfg.strictMultiplicity, strictLabels: cfg.strictLabels, allow });
  console.log(`states compared: ${Object.keys(baseline).length}`);
  console.log(`failures: ${report.failures.length}, warnings: ${report.warnings.length}, unused allow entries: ${report.unusedAllow.length}`);
  for (const item of report.failures.slice(0, REPORT_LIMIT)) console.log(`  ${describeItem(item)}`);
  if (report.failures.length > REPORT_LIMIT) console.log(`  ... ${report.failures.length - REPORT_LIMIT} more (use --json for all)`);
  for (const item of report.warnings.slice(0, REPORT_LIMIT)) console.log(`  (warning) ${describeItem(item)}`);
  if (report.warnings.length > REPORT_LIMIT) console.log(`  (warning) ... ${report.warnings.length - REPORT_LIMIT} more (use --json for all)`);
  for (const item of report.unusedAllow) console.log(`  (unused allow, remove it) ${item.list} ${item.key} ${item.kind} ${item.value}${item.reason ? ` - ${item.reason}` : ""}`);
  if (cfg.jsonReport) writeFile(path.resolve(cfg.jsonReport), `${JSON.stringify(report, null, 2)}\n`);
  if (report.failures.some((f) => f.problem === "schema_differs")) {
    console.log(`The two captures were recorded with different tool versions (schema ${SCHEMA} is current). Re-record the baseline with this tool: --out <baselineDir> --overwrite.`);
    return 2;
  }
  const result = verdict(report);
  console.log(result.line);
  return result.exitCode;
}

// ---------------------------------------------------------------- self-test

/** Checks the visibility probes against a built-in page in the real browser (lib/probe-selftest.mjs). Needs Chrome only. */
async function selfTest(cfg) {
  const { problems, premises } = await runProbeSelfTest(cfg.chromePath ? { executablePath: cfg.chromePath } : { channel: cfg.channel });
  const all = [...problems, ...premises.map((note) => `premise changed: ${note}`)];
  console.log(all.length ? `self-test FAILED:\n  ${all.join("\n  ")}` : "self-test OK: layout-collapsed text (also with padding, border, scale or clip-path) is left out of the default view and the page is restored");
  return all.length ? 1 : 0;
}

// ---------------------------------------------------------------- main

const toolHashes = () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const files = ["capture-screens.mjs", "lib/numbers-parity.mjs", "lib/page-probes.mjs", "lib/probe-selftest.mjs", "lib/capture-routes.mjs", "lib/cohort-registry.mjs", "lib/safe-message.mjs"];
  return Object.fromEntries(files.map((f) => [f, crypto.createHash("sha256").update(fs.readFileSync(path.join(here, f))).digest("hex")]));
};

async function main() {
  const cfg = parseArgs(process.argv.slice(2));
  if (cfg.help) {
    console.log(HELP);
    return 0;
  }
  if (cfg.compare) return runCompare(cfg);
  if (cfg.selfTest) return selfTest(cfg);
  if (!["public", "dev"].includes(cfg.identity)) throw usage("--identity must be public or dev");
  if (cfg.identity === "dev" && !cfg.envFile) throw usage("--identity dev needs --env-file");
  const token = cfg.identity === "dev" ? mintSessionToken(cfg.envFile) : null;
  prepareOutDir(cfg);

  const startedAt = new Date().toISOString();
  const browser = await chromium.launch({
    headless: true,
    ...(cfg.chromePath ? { executablePath: cfg.chromePath } : { channel: cfg.channel }),
  });
  const meta = { schema: SCHEMA, startedAt, git: gitMeta(), tool: toolHashes(), node: process.version, chrome: browser.version(), identity: cfg.identity, baseUrl: cfg.baseUrl, config: { mode: cfg.mode, locales: cfg.locales, sizes: cfg.sizes.map((s) => s.join("x")), routes: cfg.routes, extras: cfg.extras, dpr: cfg.dpr, reducedMotion: cfg.reducedMotion }, failedRoutes: [], warnings: [], layoutNotes: [], skippedStates: [], pagedTables: {}, limits: {}, layoutHiddenElements: 0, written: 0 };
  let exitCode = 0;
  let complete = false;
  let facts = null;
  try {
    facts = await preflight(browser, cfg, token);
    const routes = buildRoutes(cfg, facts);
    if (!routes.length) throw usage("No routes selected.");
    meta.cohortSize = facts.cohortSize;
    meta.patients = { primary: facts.primary, compliance: facts.compliancePatient };
    for (const locale of cfg.locales) {
      for (const [index, size] of cfg.sizes.entries()) {
        for (const route of routes) {
          const label = `${locale} ${size.join("x")} ${route.id}`;
          let done = false;
          for (let attempt = 0; attempt <= cfg.retries && !done; attempt += 1) {
            try {
              const result = await captureRoute(browser, cfg, route, locale, size, index === 0, facts, token);
              if (result.failures.length) throw new Error(`API failures: ${[...new Set(result.failures)].join("; ")}`);
              writeResult(cfg, route, locale, size, result);
              meta.written += result.states.length;
              meta.layoutHiddenElements += result.layoutHiddenElements;
              for (const item of result.skipped) {
                meta.skippedStates.push({ route: label, ...item });
                console.log(`skip ${label} ${item.state}: ${item.reason}`);
              }
              if (result.metrics?.pagers?.length) meta.pagedTables[route.id] = { pagers: result.metrics.pagers, walked: Boolean(route.pageWalk) };
              meta.warnings.push(...result.warnings.map((w) => `${label}: ${w}`));
              const m = result.metrics;
              const note = m && (m.moneyOverlapCount || m.moneyClippedCount) ? `${m.moneyOverlapCount} money overlap(s), ${m.moneyClippedCount} clipped` : "";
              if (note) meta.layoutNotes.push(`${label}: ${note}`);
              done = true;
              console.log(`ok   ${label} (${result.states.length} state${result.states.length === 1 ? "" : "s"})${note ? `  [layout: ${note}]` : ""}`);
            } catch (error) {
              const reason = safeMessage(error);
              console.log(`fail ${label} attempt ${attempt + 1}: ${reason}`);
              if (attempt === cfg.retries) meta.failedRoutes.push({ route: label, reason });
              else await sleep(2000);
            }
          }
        }
      }
    }
    if (meta.failedRoutes.length) exitCode = 1;
    complete = exitCode === 0;
    // What this baseline cannot show (run-meta.json limits; the header lists them too).
    meta.limits.waveAEvidence = facts.waveA;
    meta.limits.unwalkedPagers = Object.fromEntries(Object.entries(meta.pagedTables).filter(([, table]) => !table.walked));
  } catch (error) {
    meta.error = safeMessage(error);
    throw error;
  } finally {
    await browser.close();
    meta.finishedAt = new Date().toISOString();
    meta.durationSeconds = Math.round((Date.now() - Date.parse(startedAt)) / 1000);
    writeFile(path.join(cfg.writeDir, "run-meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
    if (cfg.staged && complete) publishStaged(cfg);
    else if (cfg.staged) console.error(`The previous capture in ${cfg.out} is untouched; the incomplete new run is in ${cfg.writeDir}.`);
  }
  console.log(exitCode === 0 ? `done: ${meta.written} states in ${meta.durationSeconds} s -> ${cfg.out}` : `FAILED routes: ${meta.failedRoutes.length} (see run-meta.json)`);
  const unwalked = Object.entries(meta.limits.unwalkedPagers ?? {});
  if (unwalked.length) {
    const describe = (pager) => (pager.kind === "page" ? `page 1 of ${pager.total}` : `rows ${pager.from}-${pager.to} of ${pager.total}`);
    console.log(`paged tables NOT walked (only their first page is recorded): ${unwalked.map(([id, table]) => `${id} (${table.pagers.map(describe).join(", ")})`).join("; ")}`);
  }
  if (meta.limits.waveAEvidence && meta.limits.waveAEvidence.available !== true) {
    console.log(`Wave A evidence is NOT rendered by this backend (${meta.limits.waveAEvidence.reason}): human-review and advisory blocks, and the page heights with them, are missing from this capture.`);
  }
  if (meta.skippedStates.length) console.log(`states skipped (no such button on the page): ${meta.skippedStates.length} (see run-meta.json skippedStates)`);
  if (meta.layoutNotes.length) console.log(`layout notes: ${meta.layoutNotes.length} route(s) have overlapping or cut-off amounts (see run-meta.json layoutNotes and the metrics files)`);
  return exitCode;
}

main().then(
  (code) => process.exit(code),
  (error) => {
    console.error(safeMessage(error));
    process.exit(error.exitCode ?? 1);
  },
);
