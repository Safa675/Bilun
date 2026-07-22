/**
 * Crawl Turkish UI and flag likely-English visible strings.
 * Run from repo root:
 *   NODE_PATH=frontend/node_modules node scripts/i18n/audit-tr-ui-english.mjs
 * or:
 *   cd frontend && npm i -D playwright && node ../scripts/i18n/audit-tr-ui-english.mjs
 */
import { createRequire } from "module";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  ({ chromium } = require(path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../frontend/node_modules/playwright",
  )));
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.BILUN_BASE_URL || "http://localhost:3000";
const USER = process.env.BILUN_AUTH_USERNAME || "bilun_admin";
const PASS = process.env.BILUN_AUTH_PASSWORD || "gD2YhidC5CeF_PqN_NcSkVNP";
const OUT =
  process.env.BILUN_TR_AUDIT_OUT || path.join(__dirname, "tr-ui-english-findings.json");

const EN_HINT =
  /\b(the|and|or|for|with|from|this|that|are|is|was|were|been|being|have|has|had|only|also|into|over|under|review|package|billing|claim|claims|patient|patients|exempt|exemption|mandatory|violation|compliant|recommended|actions|amount|billed|uplift|savings|priority|high|medium|low|surface|section|note|detail|unavailable|loading|error|sign out|how it works|developer|billing officer|all bills|financial|overview|summary|revenue|opportunities|materials|pre-check|copay|strategy|status|recommendation|rule type|method kind|corrective|informational|compliance risk|revenue opportunity|bed-day|standard bed|billable|gross|surgery|inclusive|discharge|bundled|separately|catalog|verify|interval|history|required|before|submission|waiver|grounds|eligible|applicable|procedures|exposure|mean rate|chapters|analyzed|risk state|potential|opportunity|recoverable|priority tier|normative|across|labs|drugs|policy|controls|exactness|aware|total billed|expected payable|clinical|snapshot|diagnosis|driven|findings|select|below|scoped|optimization|combined|reflects|waivable|facility|surcharge|portion|transparency|included|prescription|attributed|until|flags exist|reference rate|lines show|payable|participation|fee|skip to main content|role|workspace|officer|implemented|encoded|deferred|algorithmic|registry|manifest|deontic|export subset)\b/i;

/** Exact strings that look Title-Case English but are Turkish product chrome. */
const TR_ALLOWLIST = new Set([
  "Bilun Analizi",
  "Yatak Puani",
  "Anestezi Puani",
  "Eylemli Hastalar",
  "Kohorttaki Hastalar",
  "Riskli Hastalar",
  "Strateji Tasarrufu",
  "Laboratuvar Tasarrufu",
  "Malzeme Arama",
  "Paket Kalemler",
  "Muaf Fatura",
  "Toplam Fatura",
  "Toplam Hasta",
  "Not",
  "SGK",
  "SUT",
  "DRG",
  "MEDULA",
]);

function looksEnglish(text) {
  const t = text.replace(/\s+/g, " ").trim();
  if (!t || t.length < 3) return false;
  if (TR_ALLOWLIST.has(t)) return false;
  if (/^[A-Z0-9][A-Z0-9._/-]{1,}$/.test(t)) return false;
  if (/^§/.test(t) || /^F-SENTETIK/.test(t) || /^SENTETIK/.test(t)) return false;
  if (/^₺/.test(t) || /^\d([.,]\d+)*$/.test(t)) return false;
  if (/^(SGK|SUT|DRG|MEDULA|TRY|ICD-10|EK-\d)/i.test(t) && t.length < 24) return false;
  // Code paths / file paths are technical allowlist
  if (/^Uygulandığı yer:/.test(t) || /src\/bilun\//.test(t)) return false;
  const hasTurkish = /[ĞğÜüŞşİıÖöÇç]/.test(t);
  if (hasTurkish && !EN_HINT.test(t)) return false;
  if (EN_HINT.test(t)) return true;
  if (
    !hasTurkish &&
    /\b(Unknown|Review|Package|Compliant|Violation|Status|Claim|Amount|High|Low|Medium|Sign|How|Role|Developer|Patients|Compliance|Revenue|Operations|Reference|Tools|Rule|Database|Skip|Workspace|Officer|Informational|Gazette Repricing)\b/.test(
      t,
    )
  ) {
    return true;
  }
  // Title-Case alone is not enough — too many Turkish chrome false positives
  // (e.g. "Bilun Analizi", "Yatak Puani"). Require an English cue word.
  return false;
}

async function collectVisibleTexts(page) {
  return page.evaluate(() => {
    const out = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent) continue;
      const tag = parent.tagName;
      if (["SCRIPT", "STYLE", "NOSCRIPT"].includes(tag)) continue;
      const style = window.getComputedStyle(parent);
      if (style.visibility === "hidden" || style.display === "none" || style.opacity === "0") {
        continue;
      }
      const text = (node.textContent || "").replace(/\s+/g, " ").trim();
      if (!text) continue;
      out.push({ text, tag, path: location.pathname + location.search });
    }
    document.querySelectorAll("[aria-label],[title],[placeholder]").forEach((el) => {
      for (const attr of ["aria-label", "title", "placeholder"]) {
        const v = el.getAttribute(attr);
        if (v && v.trim()) {
          out.push({
            text: v.trim(),
            tag: `${el.tagName}@${attr}`,
            path: location.pathname + location.search,
          });
        }
      }
    });
    return out;
  });
}

async function forceTurkish(page) {
  await page.evaluate(() => {
    localStorage.setItem("bilun:locale", "tr");
    document.cookie = "bilun:locale=tr; path=/";
  });
  const trBtn = page.getByRole("button", { name: /Türkçe|Turkish|🇹🇷/i });
  if (await trBtn.count()) {
    const pressed = await trBtn.first().getAttribute("aria-pressed");
    if (pressed !== "true") {
      await trBtn.first().click();
      await page.waitForTimeout(1200);
    }
  }
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await forceTurkish(page);
  await page.reload({ waitUntil: "networkidle" });
  await forceTurkish(page);
  await page.fill("#username", USER);
  await page.fill("#password", PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20000 });
  await forceTurkish(page);
}

async function visitAndScan(page, urlPath, findings, label) {
  await page.goto(`${BASE}${urlPath}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await forceTurkish(page);
  await page.waitForTimeout(2200);
  await page.waitForLoadState("networkidle").catch(() => {});
  const texts = await collectVisibleTexts(page);
  const seen = new Set();
  for (const item of texts) {
    if (!looksEnglish(item.text)) continue;
    const key = `${item.path}||${item.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    findings.push({ page: label, path: item.path, tag: item.tag, text: item.text });
  }
  const shot = path.join(path.dirname(OUT), `tr-audit-${label.replace(/\W+/g, "_")}.png`);
  await page.screenshot({ path: shot, fullPage: true });
  return shot;
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  locale: "tr-TR",
  viewport: { width: 1440, height: 1200 },
});
await context.addCookies([{ name: "bilun:locale", value: "tr", url: BASE }]);
const page = await context.newPage();
const findings = [];
const shots = [];

try {
  await login(page);
  shots.push(await visitAndScan(page, "/?tab=patients", findings, "home-patients"));
  shots.push(
    await visitAndScan(page, "/patient/SENTETIK-HASTA-0001", findings, "patient-0001"),
  );
  for (const [href, label] of [
    ["/?tab=compliance", "compliance"],
    ["/?tab=revenue", "revenue"],
    ["/?tab=reference-tools", "reference-tools"],
    ["/?tab=rule-database", "rule-database"],
  ]) {
    try {
      shots.push(await visitAndScan(page, href, findings, label));
    } catch (e) {
      findings.push({ page: label, path: href, tag: "ERROR", text: String(e) });
    }
  }
} finally {
  await browser.close();
}

const byText = {};
for (const f of findings) {
  byText[f.text] = byText[f.text] || { text: f.text, pages: new Set(), count: 0 };
  byText[f.text].pages.add(f.page);
  byText[f.text].count += 1;
}
const summary = Object.values(byText)
  .map((x) => ({ text: x.text, count: x.count, pages: [...x.pages].sort() }))
  .sort((a, b) => b.count - a.count || a.text.localeCompare(b.text));

const report = {
  base: BASE,
  generatedAt: new Date().toISOString(),
  findingCount: findings.length,
  uniqueEnglishStrings: summary.length,
  summary,
  findings,
  screenshots: shots,
};
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(
  JSON.stringify(
    { findingCount: findings.length, unique: summary.length, out: OUT },
    null,
    2,
  ),
);
console.log("--- TOP 80 ---");
for (const row of summary.slice(0, 80)) {
  console.log(`[${row.count}] (${row.pages.join(",")}) ${row.text.slice(0, 200)}`);
}
