#!/usr/bin/env node
/**
 * capture-screens.mjs - screenshot baseline and "numbers parity" capture for the
 * app UI overhaul (Phase 0 of the overhaul plan: baseline and guardrails, no UI change).
 *
 * One command writes, from a local production build and the SYNTHETIC cohort:
 *   screens/   viewport + full-page PNGs per route, locale and size
 *   numbers/   every money amount / count / percent per rendered state (JSON,
 *              deterministic: no timestamps, no commit, no ports)
 *   text/      the normalised visible text behind each numbers file (for diffs)
 *   metrics/   layout measurements (page height, first table row, money wraps)
 *   run-meta.json  commit, versions, failures (NOT deterministic, never compared)
 * and `--compare A B` proves that no number changed between two runs.
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
import { compareRuns, normaliseLines, SCHEMA, tokenise } from "./lib/numbers-parity.mjs";

// ---------------------------------------------------------------- constants

const SCOPE_SELECTOR = '#main-content, [data-workspace-pane="b"]';
const PRIMARY_PATIENTS = ["SENTETIK-HASTA-0003", "SENTETIK-HASTA-0017", "SENTETIK-HASTA-0029"];
const HOME_ROUTES = ["patients", "compliance", "revenue", "operations", "reference-tools"];
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
  "  --compare <baselineDir> <candidateDir> [--allow <file>] [--strict-multiplicity] [--json <file>]",
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
  const flags = new Set(["no-full-page", "reduced-motion", "no-extras", "strict-multiplicity", "overwrite", "help"]);
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
    compare: opts.compare ?? null,
    strictMultiplicity: Boolean(opts["strict-multiplicity"]),
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
  return `${payload.toString("base64url")}.${signature.toString("base64url")}`;
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
      const nodes = [...document.querySelectorAll(selector)];
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
      for (const scope of document.querySelectorAll(selector)) {
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

const readScopes = (page) =>
  page.evaluate((selector) => [...document.querySelectorAll(selector)].map((s) => s.innerText).join("\n"), SCOPE_SELECTOR);

/** Layout metrics of the default view (taken before anything is expanded). */
function measure(page, probes) {
  return page.evaluate(
    ({ selector, probes: probeList }) => {
      const scope = document.querySelector(selector);
      const scrollY = window.scrollY;
      const round = (n) => Math.round(n);
      const en = /-?\d[\d,]*(?:\.\d+)? TRY/g;
      const tr = /₺-?\d[\d.]*(?:,\d+)?/g;
      const wraps = [];
      let first = null;
      let moneyCount = 0;
      const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = node.nodeValue.replace(/\s/g, " ");
        for (const re of [en, tr]) {
          re.lastIndex = 0;
          for (let m = re.exec(text); m; m = re.exec(text)) {
            const range = document.createRange();
            range.setStart(node, m.index);
            range.setEnd(node, m.index + m[0].length);
            const rects = [...range.getClientRects()].filter((r) => r.width > 0);
            if (!rects.length) continue;
            moneyCount += 1;
            const lines = new Set(rects.map((r) => round(r.top))).size;
            const top = round(Math.min(...rects.map((r) => r.top)) + scrollY);
            const bottom = round(Math.max(...rects.map((r) => r.bottom)) + scrollY);
            if (!first || top < first.top) first = { text: m[0], top, bottom };
            if (lines > 1) wraps.push({ text: m[0], lines });
          }
        }
      }
      const row = scope.querySelector("tbody tr");
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
      const de = document.documentElement;
      return {
        scrollHeight: de.scrollHeight,
        horizontalScroll: de.scrollWidth > de.clientWidth,
        firstTableRowTop: row ? round(row.getBoundingClientRect().top + scrollY) : null,
        firstMoney: first,
        moneyCount,
        moneyWrapCount: wraps.length,
        moneyWraps: wraps,
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
    for (const id of PRIMARY_PATIENTS) if (!ids.includes(id)) throw usage(`Patient ${id} is not in the cohort.`);
    // Dynamic inputs: bills per patient and one claim-compliance finding for the deep-link route.
    const claims = {};
    for (const id of PRIMARY_PATIENTS) {
      const body = await fetchJson(context, cfg, `/api/patients/${id}/claims`);
      claims[id] = (body.claims ?? []).map((c) => c.claim_id).sort();
    }
    const report = await fetchJson(context, cfg, "/api/billing-report/SENTETIK-HASTA-0029");
    const findings = (report.claim_compliance?.findings ?? []).map((f) => f.finding_id).sort();
    if (cfg.extras && !findings.length) {
      throw usage("SENTETIK-HASTA-0029 has no claim-compliance finding, so the deep-link route cannot be captured. Use --no-extras to skip it on purpose.");
    }
    return { cohortSize: ids.length, claims, findingId: findings[0] ?? null };
  } finally {
    await context.close();
  }
}

function buildRoutes(cfg, facts) {
  const routes = HOME_ROUTES.map((id) => ({ id, kind: "home", url: `/?tab=${id}` }));
  for (const patient of PRIMARY_PATIENTS) {
    routes.push({ id: `patient-${patient.slice(-4)}`, kind: "patient", url: `/patient/${patient}`, patient });
  }
  if (cfg.extras) {
    // Beyond the eight plan routes: split pane (every patient-page change is tested in both) and the
    // ?section=&finding= deep link that Phase 2 must keep working.
    routes.push({
      id: "patient-0003+0017-split",
      kind: "split",
      url: "/patient/SENTETIK-HASTA-0003",
      split: { a: "SENTETIK-HASTA-0003", b: "SENTETIK-HASTA-0017" },
    });
    if (facts.findingId) {
      routes.push({
        id: "patient-0029-finding",
        kind: "deeplink",
        url: `/patient/SENTETIK-HASTA-0029?section=claim-compliance&finding=${encodeURIComponent(facts.findingId)}`,
        findingId: facts.findingId,
      });
    }
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
  }
  return states;
}

async function openState(page, watch, cfg, route, spec) {
  await page.goto(`${cfg.baseUrl}${spec.url}`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  const scopes = route.kind === "split" ? 2 : 1;
  await settle(page, watch, { scopes });
  if (spec.view) {
    // Radix gives each trigger the id "<base>-trigger-<value>" (components/primitives/Tabs.tsx).
    await page.locator(`#main-content [role="tab"][id$="-trigger-${spec.view}"]`).first().click();
    await settle(page, watch, { scopes });
  }
}

async function captureRoute(browser, cfg, route, locale, size, primary, facts, token) {
  const context = await newContext(browser, cfg, { locale, size, split: route.split, token });
  const page = await context.newPage();
  const watch = watchPage(page);
  const result = { states: [], metrics: null, screens: {} };
  try {
    for (const spec of planStates(route, facts, primary)) {
      await openState(page, watch, cfg, route, spec);
      const visibleText = await readScopes(page);
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
      }
      await expandAll(page);
      await settle(page, watch, { scopes: route.kind === "split" ? 2 : 1 });
      const expandedText = await readScopes(page);
      result.states.push({
        state: spec.state,
        visibleLines: normaliseLines(visibleText),
        expandedLines: normaliseLines(expandedText),
      });
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
      writeFile(path.join(cfg.out, "numbers", `${base}.json`), `${JSON.stringify(doc, null, 2)}\n`);
      writeFile(path.join(cfg.out, "text", `${base}.txt`), `${s.expandedLines.join("\n")}\n`);
    }
  }
  if (result.screens.viewport) writeFile(path.join(cfg.out, "screens", locale, tag, `${route.id}.png`), result.screens.viewport);
  if (result.screens.full) writeFile(path.join(cfg.out, "screens", locale, tag, `${route.id}.full.png`), result.screens.full);
  if (result.metrics) {
    writeFile(path.join(cfg.out, "metrics", locale, tag, `${route.id}.json`), `${JSON.stringify(result.metrics, null, 2)}\n`);
  }
}

const GENERATED = ["numbers", "text", "metrics", "screens", "run-meta.json"];

/** A capture must never mix with files of an earlier run: stale numbers would pass a compare as if they were new. */
function prepareOutDir(cfg) {
  const existing = GENERATED.filter((name) => fs.existsSync(path.join(cfg.out, name)));
  if (existing.length && !cfg.overwrite) {
    throw usage(`${cfg.out} already holds capture output (${existing.join(", ")}). Use a new --out, or pass --overwrite to replace it.`);
  }
  for (const name of existing) fs.rmSync(path.join(cfg.out, name), { recursive: true, force: true });
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

function runCompare(cfg) {
  const [a, b] = cfg.compare.map((d) => path.resolve(d));
  const baseline = walkJson(path.join(a, "numbers"));
  if (!Object.keys(baseline).length) throw usage(`No numbers files under ${a}/numbers`);
  const allow = cfg.allowFile ? JSON.parse(fs.readFileSync(cfg.allowFile, "utf8")) : {};
  const report = compareRuns(baseline, walkJson(path.join(b, "numbers")), { strictMultiplicity: cfg.strictMultiplicity, allow });
  const line = (item) => `  ${item.key}  ${item.problem}  ${item.kind ?? ""} ${item.value ?? ""}`.trimEnd();
  console.log(`states compared: ${Object.keys(baseline).length}`);
  console.log(`failures: ${report.failures.length}, warnings: ${report.warnings.length}, unused allow entries: ${report.unusedAllow.length}`);
  for (const item of report.failures.slice(0, 60)) console.log(line(item));
  if (report.failures.length > 60) console.log(`  ... ${report.failures.length - 60} more`);
  for (const item of report.warnings.slice(0, 15)) console.log(`  (warning) ${line(item).trim()}`);
  for (const item of report.unusedAllow) console.log(`  (unused allow, remove it) ${item.list} ${item.key} ${item.kind} ${item.value}${item.reason ? ` - ${item.reason}` : ""}`);
  if (cfg.jsonReport) writeFile(path.resolve(cfg.jsonReport), `${JSON.stringify(report, null, 2)}\n`);
  console.log(report.ok ? "PARITY OK: no number changed" : "PARITY FAILED");
  return report.ok ? 0 : 1;
}

// ---------------------------------------------------------------- main

async function main() {
  const cfg = parseArgs(process.argv.slice(2));
  if (cfg.help) {
    console.log(HELP);
    return 0;
  }
  if (cfg.compare) return runCompare(cfg);
  if (!["public", "dev"].includes(cfg.identity)) throw usage("--identity must be public or dev");
  if (cfg.identity === "dev" && !cfg.envFile) throw usage("--identity dev needs --env-file");
  const token = cfg.identity === "dev" ? mintSessionToken(cfg.envFile) : null;
  prepareOutDir(cfg);

  const startedAt = new Date().toISOString();
  const browser = await chromium.launch({
    headless: true,
    ...(cfg.chromePath ? { executablePath: cfg.chromePath } : { channel: cfg.channel }),
  });
  const meta = { schema: SCHEMA, startedAt, git: gitMeta(), node: process.version, chrome: browser.version(), identity: cfg.identity, baseUrl: cfg.baseUrl, config: { mode: cfg.mode, locales: cfg.locales, sizes: cfg.sizes.map((s) => s.join("x")), routes: cfg.routes, extras: cfg.extras, dpr: cfg.dpr, reducedMotion: cfg.reducedMotion }, failedRoutes: [], warnings: [], written: 0 };
  let exitCode = 0;
  try {
    const facts = await preflight(browser, cfg, token);
    const routes = buildRoutes(cfg, facts);
    if (!routes.length) throw usage("No routes selected.");
    meta.cohortSize = facts.cohortSize;
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
              meta.warnings.push(...result.warnings.map((w) => `${label}: ${w}`));
              done = true;
              console.log(`ok   ${label} (${result.states.length} state${result.states.length === 1 ? "" : "s"})`);
            } catch (error) {
              console.log(`fail ${label} attempt ${attempt + 1}: ${error.message}`);
              if (attempt === cfg.retries) meta.failedRoutes.push({ route: label, reason: error.message });
              else await sleep(2000);
            }
          }
        }
      }
    }
    if (meta.failedRoutes.length) exitCode = 1;
  } catch (error) {
    meta.error = error.message;
    throw error;
  } finally {
    await browser.close();
    meta.finishedAt = new Date().toISOString();
    meta.durationSeconds = Math.round((Date.now() - Date.parse(startedAt)) / 1000);
    writeFile(path.join(cfg.out, "run-meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
  }
  console.log(exitCode === 0 ? `done: ${meta.written} states in ${meta.durationSeconds} s -> ${cfg.out}` : `FAILED routes: ${meta.failedRoutes.length} (see run-meta.json)`);
  return exitCode;
}

main().then(
  (code) => process.exit(code),
  (error) => {
    console.error(error.message);
    process.exit(error.exitCode ?? 1);
  },
);
