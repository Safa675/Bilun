import { chromium } from "playwright";
import crypto from "node:crypto";
import fs from "node:fs";
import { amountPattern, faultForRole, formatTryTr, role } from "./lib/cohort-registry.mjs";

// Patients and amounts come from the cohort registry (data/synthetic/cohort_registry.json), never from this file:
//  - the landing bill and the fault injected into it (its amount, its claim) drive the workspace checks;
//  - the clause drawer needs a row with a clause_ref, and showcase_S7 (copay exemption review, SUT 1.8.5) is the only bill that
//    has one (engine billing reports of the 8 showcase patients, 2026-10-18), so that part runs on its page.
const landing = role("default_landing");
const fault = faultForRole("default_landing");
const clausePatient = role("showcase_S7").patient_id;
if (fault.effect_kind !== "revenue_uplift") {
  throw new Error(`The landing bill's fault (${fault.story}, ${fault.effect_kind}) is not a revenue uplift: the revenue KPI check below needs one. Adapt this script to that story.`);
}
const faultAmount = formatTryTr(fault.amount_try);
const faultAmountPattern = amountPattern(fault.amount_try);

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
  await page.goto(`http://localhost:3000/patient/${landing.patient_id}`, {
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

  // Each trigger ends with its count badge ("Compliance 2"): read it per tab, not as a loose digit anywhere in the tab list.
  const badgeOf = (text) => {
    const match = /(\d+)\s*$/.exec(text.trim());
    return match ? Number(match[1]) : null;
  };
  const [complianceBadge, revenueBadge, auditBadge] = tabTexts.map(badgeOf);
  check(
    "every workspace tab ends with a count badge",
    [complianceBadge, revenueBadge, auditBadge].every(Number.isInteger),
    JSON.stringify(tabTexts),
  );
  // The compliance badge and the "At-risk findings" KPI are the same number (PatientWorkspaceViews.tsx, ComplianceViewSection.tsx).
  const findingsKpi = Number(
    (await page.locator('[data-compliance-metric="findings"] dd').first().innerText()).replace(/\D/g, ""),
  );
  check(
    "compliance badge equals the At-risk findings KPI",
    Number.isInteger(complianceBadge) && complianceBadge === findingsKpi,
    `badge ${complianceBadge}, KPI ${findingsKpi}`,
  );

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

  // Compliance view default: the table row of the injected bill shows its claim and the amount the registry recorded
  // (the strategy row of the landing bill carries the fault's uplift as its amount).
  const kpiAll = await page.locator('[role="tabpanel"]:visible').first().innerText();
  const tableRows = await page.locator('[role="tabpanel"]:visible table tbody tr').allInnerTexts();
  const faultRows = tableRows.filter((text) => faultAmountPattern.test(text) && text.includes(fault.claim_id));
  check(
    `compliance table lists ${fault.claim_id} (${fault.story}) with the injected amount ${faultAmount}`,
    faultRows.length > 0,
    `${tableRows.length} rows; ${kpiAll.replace(/\s+/g, " ").slice(0, 220)}`,
  );

  // Tab-snapback regression: selecting an action sets ?section=, then a
  // manual tab switch must stick (the section-follow effect must not
  // re-apply a stale section parameter over the user's choice).
  const firstActionRow = page.locator('[role="tabpanel"]:visible table tbody tr').first();
  await firstActionRow.click();
  await page.waitForTimeout(300);
  check("action selection sets ?section=", page.url().includes("section="), page.url());

  // Revenue view: click tab, KPI = the registry amount
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
    `revenue KPI shows the injected amount ${faultAmount} (or EN format)`,
    faultAmountPattern.test(revenueKpi),
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
    // One box is checked, so the sub-line reads "1 / <number of boxes on the page>" (AuditViewSection.tsx: checked / items).
    check(
      `ready KPI shows 1 / ${checkboxCount} (checked / total denominator)`,
      new RegExp(`Files ready[\\s\\S]{0,40}\\b1 / ${checkboxCount}\\b`).test(auditText),
      auditText.replace(/\s+/g, " ").slice(0, 140),
    );
    await firstAgain.uncheck().catch(() => {});
  }

  // Clause drawer: clause_refs exist on copay rows (revenue view), per #73's wiring scope. The landing bill has none, so this part
  // runs on the clause-linked bill (see the top of the file). Click a clause-inspect button there.
  await page.goto(`http://localhost:3000/patient/${clausePatient}`, {
    waitUntil: "domcontentloaded",
    timeout: 120000,
  });
  await page.waitForSelector('[role="tab"]', { timeout: 120000 });
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
