// Sub-views of the two home tabs that have a sub-view strip. The ids mirror
// COMPLIANCE_SUB_IDS and BILLING_SUB_IDS in src/lib/workspaceSubtabs.ts; a vitest
// check (capture-routes.test.mjs) fails when the two lists drift apart.
// The first id of each list is the default sub-view that the plain tab URL shows.

/** ?tab=compliance&compTab=<id> (SUTComplianceDashboard.tsx) */
export const COMPLIANCE_SUBTABS = ["exemptions", "surcharge", "copay_rates", "materials", "drug_indication", "lab", "payment_methods", "claim_compliance"];

/** ?tab=reference-tools&toolSub=<id> (ToolsSection.tsx) */
export const TOOL_SUBTABS = ["validator", "search", "bundled", "price_history", "visits", "drugs", "specialty", "lab_prices"];

/** Extra home routes: every sub-view except the default one, which the plain tab route already captures. */
export function subtabRoutes() {
  return [
    ...COMPLIANCE_SUBTABS.slice(1).map((sub) => ({ id: `compliance-${sub}`, kind: "home", url: `/?tab=compliance&compTab=${sub}` })),
    ...TOOL_SUBTABS.slice(1).map((sub) => ({ id: `reference-tools-${sub}`, kind: "home", url: `/?tab=reference-tools&toolSub=${sub}` })),
  ];
}

/**
 * aria-label prefix of the "Inspect clause" button per locale: messages billing.recommendedActions.inspectClause
 * ("Inspect clause: {coordinate}"). Rendered by RecommendedActionsPanel and UnifiedComplianceFindingsTable;
 * both open the page-level SutClauseDrawer. capture-routes.test.mjs ties it to the messages.
 */
export const INSPECT_CLAUSE_LABEL = { en: "Inspect clause:", tr: "Fıkrayı incele:" };

/** The patient-page views a clause button can sit in (tab ids of the view switch), in the order the tool looks. */
export const CLAUSE_VIEWS = ["default", "revenue", "audit"];

/**
 * Pagers the tool recognises in rendered text. "Page 1 of 5" / "Sayfa 1 / 5" (Patients, messages home
 * pagination.pageOf), "Page 1 / 270" (Reference Tools Drugs) and the range form "1–100 / 163" (Compliance Materials;
 * a single page shows "1 / 1" on Operations, which is not a pager with more to see).
 * Returns [{ kind: "page", current, total } | { kind: "range", from, to, total }] for pagers that have more to see.
 */
export function detectPagers(text) {
  const pagers = [];
  for (const m of String(text).matchAll(/\b(?:Page|Sayfa)\s+(\d+)\s*(?:of|\/)\s*(\d+)\b/g)) {
    if (Number(m[2]) > 1) pagers.push({ kind: "page", current: Number(m[1]), total: Number(m[2]) });
  }
  for (const m of String(text).matchAll(/^(\d+)[–-](\d+) \/ (\d+)$/gm)) {
    if (Number(m[2]) < Number(m[3])) pagers.push({ kind: "range", from: Number(m[1]), to: Number(m[2]), total: Number(m[3]) });
  }
  return pagers;
}

/** The URL of table page `page` of a home route (the Patients tab keeps its page in ?p=, PatientInvoiceTable.tsx). */
export function pageUrl(url, page) {
  return `${url}${url.includes("?") ? "&" : "?"}p=${page}`;
}

/**
 * The id the ?finding= deep link can select on a patient page: a canonical claim-compliance finding, else the finding_id of a
 * compliance-classified recommended action. UnifiedComplianceFindingsTable marks the row whose canonicalFindingId (the finding_id
 * of its action, or of its claim-compliance finding) equals the param, and puts the id on the row as data-finding-id.
 * Null when the report has neither.
 */
export function complianceFindingId(report) {
  const ids = (rows) => (rows ?? []).map((row) => row?.finding_id).filter((id) => typeof id === "string" && id.length > 0).sort();
  const canonical = ids(report?.claim_compliance?.findings);
  const fromActions = ids((report?.recommended_actions ?? []).filter((action) => action?.finding_type === "compliance"));
  return canonical[0] ?? fromActions[0] ?? null;
}
