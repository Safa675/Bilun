import type { LucideIcon } from "lucide-react";
import {
  AlertOctagon,
  BookOpen,
  Boxes,
  BriefcaseMedical,
  CalendarCheck,
  CircleDollarSign,
  ClipboardList,
  Clock,
  Cpu,
  Database,
  FileCheck2,
  FlaskConical,
  FolderTree,
  PackageSearch,
  Pill,
  Scissors,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  User,
  Users,
} from "lucide-react";
import type { SutHomeTab } from "@/lib/constants";
import type { WorkspaceTab } from "./workspaceTabs";

export function tabMessageKey(tabId: SutHomeTab): string {
  if (tabId === "reference-tools") return "referenceTools";
  if (tabId === "rule-database") return "ruleDatabase";
  return tabId;
}

export type BillingToolSubSection =
  | "validator"
  | "search"
  | "bundled"
  | "price_history"
  | "visits"
  | "drugs"
  | "specialty"
  | "lab_prices";

export const BILLING_SUB_IDS: readonly BillingToolSubSection[] = [
  "validator",
  "search",
  "bundled",
  "price_history",
  "visits",
  "drugs",
  "specialty",
  "lab_prices",
] as const;

export const BILLING_SUB_KEY = {
  validator: "validator",
  search: "search",
  bundled: "bundled",
  price_history: "priceHistory",
  visits: "visits",
  drugs: "drugs",
  specialty: "specialty",
  lab_prices: "labPrices",
} as const satisfies Record<BillingToolSubSection, string>;

export const BILLING_SUB_ICONS: Record<BillingToolSubSection, LucideIcon> = {
  validator: FileCheck2,
  search: PackageSearch,
  bundled: Boxes,
  price_history: TrendingUp,
  visits: CalendarCheck,
  drugs: Pill,
  specialty: BriefcaseMedical,
  lab_prices: FlaskConical,
};

export type ComplianceSubSection =
  | "exemptions"
  | "surcharge"
  | "materials"
  | "payment_methods"
  | "surgical_sessions"
  | "diagnostics_lab"
  | "pre_flight_docs"
  | "medula_rejections";

export const COMPLIANCE_SUB_IDS: readonly ComplianceSubSection[] = [
  "exemptions",
  "surcharge",
  "materials",
  "payment_methods",
  "surgical_sessions",
  "diagnostics_lab",
  "pre_flight_docs",
  "medula_rejections",
] as const;

export const COMPLIANCE_SUB_KEY = {
  exemptions: "exemptions",
  surcharge: "surcharge",
  materials: "materials",
  payment_methods: "paymentMethods",
  surgical_sessions: "surgicalSessions",
  diagnostics_lab: "diagnosticsLab",
  pre_flight_docs: "preFlightDocs",
  medula_rejections: "medulaRejections",
} as const satisfies Record<ComplianceSubSection, string>;

export const COMPLIANCE_SUB_ICONS: Record<ComplianceSubSection, LucideIcon> = {
  exemptions: ShieldCheck,
  surcharge: ShieldAlert,
  materials: PackageSearch,
  payment_methods: Boxes,
  surgical_sessions: Scissors,
  diagnostics_lab: FlaskConical,
  pre_flight_docs: FileCheck2,
  medula_rejections: AlertOctagon,
};

export type RuleDatabaseSubSection =
  | "rules"
  | "sections"
  | "clauses"
  | "prose"
  | "deferrals";

export const RULE_DATABASE_SUB_IDS: readonly RuleDatabaseSubSection[] = [
  "rules",
  "sections",
  "clauses",
  "prose",
  "deferrals",
] as const;

export const RULE_DATABASE_SUB_ICONS: Record<RuleDatabaseSubSection, LucideIcon> = {
  rules: BookOpen,
  sections: FolderTree,
  clauses: ScrollText,
  prose: Cpu,
  deferrals: Clock,
};

export const MAIN_SECTION_ICONS: Record<SutHomeTab, LucideIcon> = {
  patients: Users,
  compliance: ShieldCheck,
  revenue: CircleDollarSign,
  operations: ClipboardList,
  "reference-tools": BookOpen,
  "rule-database": Database,
};

export interface ResolvedTabInfo {
  /** The specific display label for the tab (subtab label if active, else parent section/patient ID). */
  label: string;
  /** Full descriptive title for tooltips, e.g. "Referans Araçları · Branşa Göre". */
  fullTitle: string;
  /** The icon associated with this specific view/subtab. */
  Icon: LucideIcon;
  /** The identified subtab key, or null if root / patient. */
  subtab: string | null;
}

export function resolveTabInfo(
  tab: WorkspaceTab,
  t: (key: string) => string,
): ResolvedTabInfo {
  if (tab.kind === "patient") {
    return {
      label: tab.refId,
      fullTitle: tab.refId,
      Icon: User,
      subtab: null,
    };
  }

  const parentKey = tabMessageKey(tab.refId as SutHomeTab);
  const parentLabel = t(`constants.homeTabs.${parentKey}.label`);
  const parentIcon = MAIN_SECTION_ICONS[tab.refId as SutHomeTab] ?? Database;

  const params = new URLSearchParams(tab.query ?? "");

  if (tab.refId === "reference-tools") {
    const rawSub = params.get("toolSub");
    const sub: BillingToolSubSection =
      rawSub && (BILLING_SUB_IDS as readonly string[]).includes(rawSub)
        ? (rawSub as BillingToolSubSection)
        : "validator";
    const subLabel = t(`sections.tools.subs.${BILLING_SUB_KEY[sub]}`);
    const Icon = BILLING_SUB_ICONS[sub];

    return {
      label: subLabel,
      fullTitle: `${parentLabel} · ${subLabel}`,
      Icon,
      subtab: sub,
    };
  }

  if (tab.refId === "compliance") {
    const rawSub = params.get("compTab") || params.get("subtab");
    const sub: ComplianceSubSection =
      rawSub && (COMPLIANCE_SUB_IDS as readonly string[]).includes(rawSub)
        ? (rawSub as ComplianceSubSection)
        : "exemptions";
    const subLabel = t(`optimizer.tabs.${COMPLIANCE_SUB_KEY[sub]}`);
    const Icon = COMPLIANCE_SUB_ICONS[sub];

    return {
      label: subLabel,
      fullTitle: `${parentLabel} · ${subLabel}`,
      Icon,
      subtab: sub,
    };
  }

  if (tab.refId === "rule-database") {
    const rawSub = params.get("rdTab");
    const sub: RuleDatabaseSubSection =
      rawSub && (RULE_DATABASE_SUB_IDS as readonly string[]).includes(rawSub)
        ? (rawSub as RuleDatabaseSubSection)
        : "rules";
    const subLabel = t(`sections.ruleDatabase.tabs.${sub}`);
    const Icon = RULE_DATABASE_SUB_ICONS[sub];

    return {
      label: subLabel,
      fullTitle: `${parentLabel} · ${subLabel}`,
      Icon,
      subtab: sub,
    };
  }

  return {
    label: parentLabel,
    fullTitle: parentLabel,
    Icon: parentIcon,
    subtab: null,
  };
}
