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
