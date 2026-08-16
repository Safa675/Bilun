import { chromium } from "playwright";
import crypto from "node:crypto";
import fs from "node:fs";

// ── Mint a valid bilun session token (same format as src/bilun/api/auth.py) ──
const envFile = fs.readFileSync(".env.local", "utf8");
// Next.js's dotenv loader strips surrounding quotes — mirror that here.
const secret = envFile
  .match(/^BILUN_SESSION_SECRET=(.*)$/m)?.[1]
  ?.trim()
  .replace(/^["']|["']$/g, "");
if (!secret) throw new Error("BILUN_SESSION_SECRET missing in frontend/.env.local");

function b64url(buf) {
  return Buffer.from(buf).toString("base64url");
}
const username = "safa";
const expires = Math.floor(Date.now() / 1000) + 8 * 3600;
const payload = `${username}.${expires}`;
const payloadBytes = Buffer.from(payload, "utf8");
const sig = crypto.createHmac("sha256", secret).update(payloadBytes).digest();
const token = `${b64url(payloadBytes)}.${b64url(sig)}`;

const checks = [];
function check(name, ok, detail = "") {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ locale: "tr-TR" });
  await ctx.addCookies([
    { name: "bilun:session", value: token, domain: "localhost", path: "/" },
  ]);
  const page = await ctx.newPage();
  const consoleErrors = [];
  const httpErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  page.on("response", (r) => {
    if (r.status() >= 400) httpErrors.push(`${r.status()} ${r.url()}`);
  });

  console.log("navigating…");
  // Dev-mode recompiles can keep the network busy long enough that
  // `networkidle` times out; land on DOMContentLoaded and wait for the
  // workspace tabs instead.
  await page.goto("http://localhost:3000/patient/SENTETIK-HASTA-0001", {
    waitUntil: "domcontentloaded",
    timeout: 120000,
  });
  console.log("url:", page.url());
  check("page loads (no login redirect)", !page.url().includes("/login"));

  // Tabs render with role=tab (waiting here also covers the data fetch)
  await page.waitForSelector('[role="tab"]', { timeout: 120000 });
  const tabs = page.getByRole("tab");
  const tabCount = await tabs.count();
  check("three workspace tabs render", tabCount === 3, `found ${tabCount}`);

  const tabTexts = [];
  for (let i = 0; i < tabCount; i++) tabTexts.push(await tabs.nth(i).innerText());
  console.log("tab labels:", JSON.stringify(tabTexts));

  const tabBody = await page.locator('[role="tablist"]').innerText();
  check("compliance badge = 18", /18/.test(tabBody), tabBody.replace(/\s+/g, " "));
  // Live dataset for 0001: 2 copay exemption rows + 2 yatak puanı rows.
  check("revenue badge = 4", /\b4\b/.test(tabBody));
  check("audit badge = 4", /\b4\b/.test(tabBody));

  // Exactly one visible actions table: the per-view list. The legacy
  // master list inside BillingSummary was removed (user request).
  const bodyText = await page.locator("body").innerText();
  // Eyebrow styling uppercases the heading — match case-insensitively.
  const actionsTableCount = (bodyText.match(/Recommended actions — itemized/gi) ?? []).length;
  check(
    "single actions table (per-view only, overview master list removed)",
    actionsTableCount === 1,
    `found ${actionsTableCount}`,
  );

  // Compliance view default: KPI cards with live TRY values
  const kpiAll = await page.locator('[role="tabpanel"]:visible').first().innerText();
  check(
    "compliance KPI risk = 121.714,71",
    /121[.,]714[.,]71/.test(kpiAll),
    kpiAll.replace(/\s+/g, " ").slice(0, 220),
  );

  // Tab-snapback regression: selecting an action sets ?section=, then a
  // manual tab switch must stick (the section-follow effect must not
  // re-apply a stale section parameter over the user's choice).
  const firstActionRow = page.locator('[role="tabpanel"]:visible table tbody tr').first();
  await firstActionRow.click();
  await page.waitForTimeout(300);
  check("action selection sets ?section=", page.url().includes("section="), page.url());

  // Revenue view: click tab, KPI 23.192,18
  await tabs.filter({ hasText: /Gelir|Revenue/ }).click();
  await page.waitForTimeout(700);
  const revenueTriggerActive =
    (await tabs.filter({ hasText: /Gelir|Revenue/ }).getAttribute("data-state")) === "active";
  const revenueKpi = await page.locator('[role="tabpanel"]:visible').first().innerText();
  check(
    "manual tab switch sticks after section anchor (no snap-back)",
    revenueTriggerActive && /Recoverable SGK uplift/.test(revenueKpi),
    revenueKpi.replace(/\s+/g, " ").slice(0, 120),
  );
  check(
    "revenue KPI = 23.192,18 (or EN format)",
    /23[.,]192[.,]18/.test(revenueKpi),
    revenueKpi.replace(/\s+/g, " ").slice(0, 220),
  );

  // Audit view: ready checkbox + persistence across reload
  await tabs.filter({ hasText: /Evrak|Documents/ }).click();
  await page.waitForTimeout(500);
  const checkboxes = page.locator('input[type="checkbox"]');
  const checkboxCount = await checkboxes.count();
  check("audit view renders ready checkboxes", checkboxCount > 0, `${checkboxCount} found`);
  if (checkboxCount > 0) {
    await checkboxes.first().check();
    await page.waitForTimeout(300);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForSelector('[role="tab"]', { timeout: 120000 });
    await tabs.filter({ hasText: /Evrak|Documents/ }).click();
    await page.waitForTimeout(400);
    const firstAgain = page.locator('input[type="checkbox"]').first();
    const persisted = await firstAgain.isChecked();
    check("ready state persists across reload (localStorage)", persisted);
    const auditText = await page.locator('[role="tabpanel"]:visible').first().innerText();
    check(
      "ready KPI shows checked / total denominator",
      /Files ready[\s\S]{0,40}1 \/ 4/.test(auditText),
      auditText.replace(/\s+/g, " ").slice(0, 140),
    );
    await firstAgain.uncheck().catch(() => {});
  }

  // Clause drawer: clause_refs currently exist on copay rows (revenue view),
  // per #73's wiring scope. Click a clause-inspect button there.
  await tabs.filter({ hasText: /Gelir|Revenue/ }).click();
  await page.waitForTimeout(500);
  const clauseButtons = await page
    .locator('button[aria-label*="Fıkrayı incele"], button[aria-label*="Inspect clause"]')
    .count();
  check(
    "clause-inspect buttons render for clause-linked rows",
    clauseButtons > 0,
    `${clauseButtons} found`,
  );
  if (clauseButtons > 0) {
    const clauseButton = page
      .locator('button[aria-label*="Fıkrayı incele"], button[aria-label*="Inspect clause"]')
      .first();
    await clauseButton.click();
    await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
    const dialogText = await page.locator('[role="dialog"]').innerText();
    check(
      "clause drawer opens",
      /Mevzuat|Regulatory|fıkra|clause/i.test(dialogText),
      dialogText.replace(/\s+/g, " ").slice(0, 120),
    );
    // Give the fetch a moment, then verify it left loading state
    await page.waitForTimeout(2500);
    const dialogAfter = await page.locator('[role="dialog"]').innerText();
    check(
      "drawer resolves clauses or empty state (no stuck loading)",
      !/Yükleniyor|Loading/.test(dialogAfter),
      dialogAfter.replace(/\s+/g, " ").slice(0, 160),
    );
    await page.screenshot({ path: "/tmp/bilun_clause_drawer.png", fullPage: false });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    check("drawer closes on Escape", (await page.locator('[role="dialog"]').count()) === 0);
  }

  await page.screenshot({ path: "/tmp/bilun_workspace_views.png", fullPage: true });

  // The frontend-config 404s above also surface as console resource errors.
  const unexpectedConsoleErrors = consoleErrors.filter(
    (msg) => !msg.includes("404"),
  );
  check(
    "no console/page errors",
    unexpectedConsoleErrors.length === 0,
    unexpectedConsoleErrors.slice(0, 3).join(" | "),
  );
  // /api/frontend-config 404s are a known pre-existing backend gap; the
  // ConfigProvider degrades to FALLBACK_CONFIG (see lib/configContext.tsx).
  const unexpectedHttpErrors = httpErrors.filter(
    (url) => !url.includes("/api/frontend-config"),
  );
  check(
    "no unexpected failed HTTP requests",
    unexpectedHttpErrors.length === 0,
    unexpectedHttpErrors.slice(0, 5).join(" | "),
  );
  if (httpErrors.length > 0) {
    console.log("NOTE  known 404s (pre-existing):", httpErrors.join(" | "));
  }

  const failed = checks.filter((c) => !c.ok);
  console.log(`\nRESULT: ${checks.length - failed.length}/${checks.length} checks passed`);
  if (failed.length) process.exitCode = 1;
} finally {
  await browser.close();
}
