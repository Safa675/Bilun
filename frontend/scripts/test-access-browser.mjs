/** Production frontend contract test. Uses only local synthetic identities/data.
 * Build first with API_PROXY_TARGET=http://127.0.0.1:18281 npm run build.
 * Run: node scripts/test-access-browser.mjs
 * Backend authorization is covered separately by the real Python API tests.
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { cpSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";

const apiPort = Number(process.env.ACCESS_TEST_API_PORT ?? 18281);
const frontendPort = Number(process.env.ACCESS_TEST_FRONTEND_PORT ?? 18280);
const origin = `http://127.0.0.1:${frontendPort}`;
const sessions = new Map();
const state = { publicEnabled: true, failLogout: false, loginLifetime: 120 };
const requests = [];
const guest = () => ({ authenticated: false, username: null, role: "billing_officer", capabilities: state.publicEnabled ? ["billing"] : [], public_billing_enabled: state.publicEnabled, expires_at: null });
const rule = { rule_id: "PRIVATE_ENGINE_MARKER", rule_category: "test", rule_category_tr: "test", coverage_status: "implemented", description: "Developer-only test detail", description_tr: "Developer-only test detail", sources: { annexes: [], sut_sections: [] }, keywords: [], domain_modules: ["private_detector.py"], matched_clause_count: 0, has_clause_mapping: false };

const api = createServer(async (req, res) => {
  const path = new URL(req.url, origin).pathname;
  const token = /(?:^|; )bilun:session=([^;]*)/.exec(req.headers.cookie ?? "")?.[1];
  const session = sessions.get(token);
  const identity = session && session.expires_at > Date.now() / 1000 ? { ...session, public_billing_enabled: state.publicEnabled } : guest();
  requests.push({ path, authenticated: identity.authenticated, role: identity.role });
  const json = (value, status = 200, headers = {}) => { res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "private, no-store", ...headers }); res.end(JSON.stringify(value)); };
  if (path === "/api/auth/me") return json(identity);
  if (path === "/api/auth/login") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw);
    if (body.password !== "fixture-password" || !["fixture-developer", "fixture-officer"].includes(body.username)) return json({ ok: false }, 401);
    const developer = body.username === "fixture-developer";
    const token = randomUUID();
    sessions.set(token, { authenticated: true, username: body.username, role: developer ? "dev" : "billing_officer", capabilities: developer ? ["billing", "developer", "repository"] : ["billing"], expires_at: Math.floor(Date.now() / 1000) + state.loginLifetime });
    return json({ ok: true }, 200, { "Set-Cookie": `bilun:session=${token}; Path=/; HttpOnly; SameSite=Lax` });
  }
  if (path === "/api/auth/logout") {
    if (state.failLogout) return json({ ok: false }, 503);
    sessions.delete(token);
    return json({ ok: true }, 200, { "Set-Cookie": "bilun:session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax" });
  }
  if (!identity.capabilities.includes("billing")) return json({ detail: "Authentication required" }, 401);
  if (path.startsWith("/api/rules") && !identity.capabilities.includes("developer")) return json({ detail: "Developer access required" }, 403);
  if (path === "/api/frontend-config") return json({ regulatory: { ek1a_exemption_count: 0, ek2g_procedure_count: 0, ek2c1_procedure_count: 0 }, sut_data_source: { mode: "synthetic_demo", label: "Synthetic demo", notice: "Synthetic test data", is_synthetic: true } });
  if (path === "/api/patients") return json({ patients: [], patient_meta: [], total: 0 });
  if (path === "/api/medula-rejections/ingest-status") return json({ ingest_available: false });
  if (path === "/api/rules") return json({ rules: [rule], artifacts_available: true });
  if (path === "/api/rules/PRIVATE_ENGINE_MARKER") return json({ rule, clauses: [], clause_total: 0, total_pages: 1 });
  if (path === "/api/rules/sections") return json({ sections: [], total: 0, total_pages: 1, artifacts_available: true });
  if (path === "/api/rules/clauses") return json({ clauses: [], total: 0, total_pages: 1, artifacts_available: true });
  if (path === "/api/rules/prose-inventory") return json({ engines: [], total: 0 });
  if (path === "/api/rules/deferrals") return json({ deferrals: [], total: 0, total_pages: 1 });
  if (path === "/api/chat") { res.writeHead(200, { "Content-Type": "text/event-stream" }); res.end('data: "Synthetic billing explanation"\n\ndata: "[DONE]"\n\n'); return; }
  return json({ detail: "No synthetic fixture for this read" }, 404);
});

await new Promise((resolve, reject) => { api.once("error", reject); api.listen(apiPort, "127.0.0.1", resolve); });
let logs = "";
cpSync(".next/static", ".next/standalone/frontend/.next/static", { recursive: true });
cpSync("public", ".next/standalone/frontend/public", { recursive: true });
const next = spawn(process.execPath, [".next/standalone/frontend/server.js"], {
  cwd: process.cwd(), env: { ...process.env, NODE_ENV: "production", NODE_OPTIONS: "--max-old-space-size=4096", HOSTNAME: "127.0.0.1", PORT: String(frontendPort), API_PROXY_TARGET: `http://127.0.0.1:${apiPort}` }, stdio: ["ignore", "pipe", "pipe"],
});
next.stdout.on("data", (data) => { logs += data; });
next.stderr.on("data", (data) => { logs += data; });
let browser;
try {
  let ready = false;
  for (let i = 0; i < 200; i++) {
    try { if ((await fetch(`${origin}/login`)).ok) { ready = true; break; } } catch { /* Starting. */ }
    await delay(100);
  }
  assert(ready, "Production frontend did not start");
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const visible = (locator) => locator.waitFor({ state: "visible", timeout: 12_000 });
  const noDeveloper = async (target = page) => {
    await visible(target.getByRole("link", { name: "Developer sign in", exact: true }));
    assert.equal(await target.locator('select#role-switcher').count(), 0);
    assert.equal(await target.locator('aside a[href*="tab=rule-database"]').count(), 0);
    assert.equal(await target.getByText("PRIVATE_ENGINE_MARKER", { exact: true }).count(), 0);
  };
  const login = async (username = "fixture-developer", password = "fixture-password") => {
    await page.goto(`${origin}/login`);
    await page.getByLabel("Username", { exact: true }).fill(username);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
  };

  await context.addCookies([{ name: "bilun:role", value: "dev", url: origin }]);
  await page.goto(`${origin}/`);
  await noDeveloper();
  await page.evaluate(() => {
    localStorage.setItem("bilun_user_role", "dev");
    sessionStorage.setItem("bilun:workspace-tabs", JSON.stringify({ tabs: [{ id: "section:rule-database", kind: "section", refId: "rule-database", query: "tab=rule-database&admin=1", lastActivatedAt: 1 }], activeTabId: "section:rule-database", paneBTabId: null }));
  });
  await page.reload();
  await noDeveloper();
  assert.equal(await page.evaluate(() => localStorage.getItem("bilun_user_role")), null);
  assert.equal(await page.locator('[data-workspace-tab="section:rule-database"]').count(), 0);
  for (const path of ["/?tab=rule-database", "/?admin=1", "/design-system"]) {
    await page.goto(`${origin}${path}`);
    assert.equal(new URL(page.url()).pathname, "/login");
  }
  assert(!requests.some((request) => request.path === "/api/rules" && !request.authenticated), "Anonymous UI fetched developer catalogue");
  console.log("PASS public entry, forged role preferences, saved tabs and direct developer URLs");

  await login("fixture-developer", "wrong-password");
  await visible(page.getByText("Invalid username or password.", { exact: true }));
  await login("fixture-officer");
  await visible(page.getByText("This account does not have developer access.", { exact: true }));
  await login();
  await page.waitForURL(`${origin}/`);
  await visible(page.locator('aside a[href*="tab=rule-database"]'));
  await page.goto(`${origin}/?tab=rule-database&rdTab=rules`);
  await visible(page.getByText("PRIVATE_ENGINE_MARKER", { exact: true }).first());
  const other = await context.newPage();
  await other.goto(`${origin}/?tab=rule-database&rdTab=rules`);
  await visible(other.getByText("PRIVATE_ENGINE_MARKER", { exact: true }).first());
  state.failLogout = true;
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await visible(page.getByRole("alert").filter({ hasText: "Could not confirm sign-out" }));
  await visible(page.getByText("PRIVATE_ENGINE_MARKER", { exact: true }).first());
  state.failLogout = false;
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await noDeveloper();
  await noDeveloper(other);
  await page.goBack();
  assert.equal(await page.getByText("PRIVATE_ENGINE_MARKER", { exact: true }).count(), 0);
  console.log("PASS invalid/nondeveloper login, developer entry, failed/successful logout, second tab and browser back");

  state.loginLifetime = 3;
  await login();
  await page.waitForURL(`${origin}/`);
  await visible(page.locator('aside a[href*="tab=rule-database"]'));
  await noDeveloper();
  console.log("PASS session expiry returns to public billing");

  state.publicEnabled = false;
  await page.goto(`${origin}/`);
  assert.equal(new URL(page.url()).pathname, "/login");
  assert.equal(await page.getByRole("link", { name: "Return to billing", exact: true }).count(), 0);
  const apiDenied = await page.request.get(`${origin}/api/rules`);
  assert.equal(apiDenied.status(), 401);
  assert.match(apiDenied.headers()["content-type"], /json/);
  assert.deepEqual(errors, [], `Browser errors: ${errors.join("; ")}`);
  console.log("PASS rollout disabled, API JSON denials and no browser exceptions");
} catch (error) {
  console.error(logs.slice(-6000));
  throw error;
} finally {
  await browser?.close();
  next.kill("SIGTERM");
  await new Promise((resolve) => { if (next.exitCode !== null) resolve(); else next.once("exit", resolve); });
  await new Promise((resolve) => api.close(resolve));
}
