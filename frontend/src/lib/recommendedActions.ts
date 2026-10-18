import type { BillingActionReport, RecommendedActionItem } from "@/lib/domains/sut";
import type { ChipVariant } from "@/components/primitives/Chip";

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
) => string;

export type { RecommendedActionItem };

/** User-facing finding class for recommended-action rows. */
export type FindingType = "compliance" | "opportunity" | "informational";

/**
 * Classify a recommended action for UI badges.
 *
 * The backend classifies rows (`finding_type` on each action row, including
 * the billing_strategy kind special case); rows without it are informational.
 */
export function getFindingType(action: RecommendedActionItem): FindingType {
  const type = action.finding_type;
  if (type === "compliance" || type === "opportunity" || type === "informational") {
    return type;
  }
  return "informational";
}

/** billing_strategy rows are classified by kind (backend parity). */
function billingStrategyFindingType(kind: string): FindingType {
  if (kind === "optional_override") return "opportunity";
  if (
    kind === "compliance_violation" ||
    kind === "mandatory_compliance" ||
    kind === "strategy"
  ) {
    return "compliance";
  }
  return "informational";
}

export function findingTypeChipVariant(type: FindingType): ChipVariant {
  switch (type) {
    case "compliance":
      return "danger";
    case "opportunity":
      return "success";
    default:
      return "neutral";
  }
}

export function findingTypeLabelKey(type: FindingType): string {
  switch (type) {
    case "compliance":
      return "billing.recommendedActions.findingTypes.compliance";
    case "opportunity":
      return "billing.recommendedActions.findingTypes.opportunity";
    default:
      return "billing.recommendedActions.findingTypes.informational";
  }
}

export function getRecommendedActions(
  report: BillingActionReport,
): RecommendedActionItem[] {
  const actions =
    report.recommended_actions?.length
      ? report.recommended_actions
      : buildRecommendedActionsFallback(report);
  return [...actions].sort((a, b) => actionSortValue(b) - actionSortValue(a));
}

function actionSortValue(action: RecommendedActionItem): number {
  const candidates = [
    action.sgk_uplift_try,
    action.compliance_savings_try,
    action.billed_try,
  ].filter((value): value is number => value != null && Number.isFinite(value));
  return candidates.length > 0 ? Math.max(...candidates) : 0;
}

function buildRecommendedActionsFallback(
  report: BillingActionReport,
): RecommendedActionItem[] {
  const actions: RecommendedActionItem[] = [];

  for (const test of report.lab?.flagged_tests ?? []) {
    actions.push({
      action_id: `lab:${test.sut_code ?? test.test_name}`,
      surface: "lab",
      kind: String(test.flag_type ?? "lab_flag"),
      procedure_code: test.sut_code ?? null,
      procedure_name: test.test_name ?? null,
      compliance_savings_try: test.savings_try ?? null,
      detail: test.detail ?? null,
      finding_type: "compliance",
    });
  }

  if (report.copay?.is_exempt) {
    actions.push({
      action_id: "copay:ek1a_exemption_review",
      surface: "copay",
      kind: "exemption_review",
      compliance_savings_try:
        report.copay.patient_copay_waived_total_try ??
        report.copay.total_copay_savings_try ??
        null,
      detail: report.copay.exemption_disease ?? null,
      // Canonical dot form (backend emits "1.8.5.(7)"; legacy "1.8.5(7)" is gone).
      sut_section_id: "1.8.5.(7)",
      finding_type: "opportunity",
    });
  }

  for (const row of report.billing_strategy?.recommendations ?? []) {
    if (row.type === "informational") continue;
    const kind = String(row.type ?? row.recommendation_kind ?? "strategy");
    actions.push({
      action_id: `strategy:${row.claim_id}:${row.procedure_code}:${row.type ?? row.recommendation_kind}`,
      surface: "billing_strategy",
      kind,
      claim_id: row.claim_id ?? null,
      procedure_code: row.procedure_code ?? null,
      procedure_name: row.procedure_name ?? null,
      sgk_uplift_try:
        row.included_in_sgk_total === false
          ? null
          : row.savings_try ?? row.recoverable_uplift_try ?? null,
      detail: row.detail ?? null,
      sut_section_id: row.sut_section_id ?? row.sut_section ?? null,
      finding_type: billingStrategyFindingType(kind),
      message_code:
        (row.message_code as string | undefined) ?? null,
      message_params:
        (row.message_params as Record<string, unknown> | undefined) ?? null,
    });
  }

  const upliftBlocks: Array<[string, { opportunities?: Array<Record<string, unknown>> } | undefined]> =
    [
      ["material_uplift", report.material_uplift],
      ["session_uplift", report.session_uplift],
      ["drg_uplift", report.drg_uplift],
      ["blood_uplift", report.blood_uplift],
    ];

  for (const [surface, block] of upliftBlocks) {
    for (const row of block?.opportunities ?? []) {
      actions.push({
        action_id: `${surface}:${row.claim_id}:${row.procedure_code ?? row.material_code}`,
        surface,
        kind: String(row.type ?? surface),
        claim_id: (row.claim_id as string | undefined) ?? null,
        procedure_code: (row.procedure_code as string | undefined) ?? null,
        procedure_name: (row.procedure_name as string | undefined) ?? null,
        material_code: (row.material_code as string | undefined) ?? null,
        material_name: (row.material_name as string | undefined) ?? null,
        sgk_uplift_try:
          (row.recoverable_uplift_try as number | undefined) ??
          (row.recoverable_gap_try as number | undefined) ??
          null,
        detail: (row.detail as string | undefined) ?? null,
        sut_section_id: (row.sut_section_id as string | undefined) ?? null,
        finding_type: "opportunity",
      });
    }
  }

  return actions;
}

const RECOMMENDED_ACTION_SECTION_IDS: Record<string, string> = {
  lab: "billing-lab",
  copay: "billing-copay",
  billing_strategy: "billing-strategy",
  materials: "materials-pre-check",
  payment_methods: "billing-strategy",
  medula_playbook: "medula-playbook",
  claim_checklist: "claim-submission-checklist",
  drug_indication: "drug-indication",
  claim_compliance: "claim-compliance",
  session_uplift: "billing-session-uplift",
  blood_uplift: "billing-blood-uplift",
  material_uplift: "billing-material-uplift",
  procedure_addon_uplift: "billing-procedure-addon-uplift",
  procedure_capture_gap: "billing-procedure-capture-gap",
  drg_package_adequacy: "billing-drg-package-adequacy",
  drg_uplift: "billing-drg-uplift",
  care_setting_review: "billing-care-setting-review",
};

export function recommendedActionSectionId(surface: string | null | undefined): string | null {
  if (!surface) return null;
  return RECOMMENDED_ACTION_SECTION_IDS[surface] ?? null;
}

const SURFACE_LABEL_KEYS: Record<string, string> = {
  lab: "billing.recommendedActions.surfaces.lab",
  copay: "billing.recommendedActions.surfaces.copay",
  billing_strategy: "billing.recommendedActions.surfaces.billingStrategy",
  session_uplift: "billing.recommendedActions.surfaces.sessionUplift",
  drg_uplift: "billing.recommendedActions.surfaces.drgUplift",
  blood_uplift: "billing.recommendedActions.surfaces.bloodUplift",
  material_uplift: "billing.recommendedActions.surfaces.materialUplift",
  care_setting_review: "billing.recommendedActions.surfaces.careSettingReview",
  procedure_addon_uplift: "billing.recommendedActions.surfaces.procedureAddon",
  procedure_capture_gap: "billing.recommendedActions.surfaces.procedureCapture",
  drg_package_adequacy: "billing.recommendedActions.surfaces.drgPackageAdequacy",
  medula_playbook: "billing.recommendedActions.surfaces.medulaPlaybook",
  claim_checklist: "billing.recommendedActions.surfaces.claimChecklist",
  drug_indication: "billing.recommendedActions.surfaces.drugIndication",
  materials: "billing.recommendedActions.surfaces.materials",
  claim_compliance: "billing.recommendedActions.surfaces.claimCompliance",
  yatak_puani: "billing.recommendedActions.surfaces.yatakPuani",
  anestezi_puani: "billing.recommendedActions.surfaces.anesteziPuani",
  refakatci: "billing.recommendedActions.surfaces.refakatci",
  icu_puani: "billing.recommendedActions.surfaces.icuPuani",
  yenidogan_yatak: "billing.recommendedActions.surfaces.yenidoganYatak",
  audit_exposure: "billing.recommendedActions.surfaces.auditExposure",
};

const KIND_LABEL_KEYS: Record<string, string> = {
  compliance_violation: "billing.recommendedActions.kinds.complianceViolation",
  optional_override: "billing.recommendedActions.kinds.optionalOverride",
  mandatory_compliance: "billing.recommendedActions.kinds.mandatoryCompliance",
  exemption_review: "billing.recommendedActions.kinds.exemptionReview",
  hemogram_unbundling: "billing.recommendedActions.kinds.hemogramUnbundling",
  missing_billable_material: "billing.recommendedActions.kinds.missingMaterial",
  material_pre_auth: "billing.recommendedActions.kinds.materialPreAuth",
  material_miat: "billing.recommendedActions.kinds.materialMiat",
  material_miat_interval: "billing.recommendedActions.kinds.materialMiatInterval",
  material_bundling: "billing.recommendedActions.kinds.materialBundling",
  material_prose_bundling: "billing.recommendedActions.kinds.materialProseBundling",
  material_specialty_prose: "billing.recommendedActions.kinds.materialSpecialtyProse",
  yatak_puani: "billing.recommendedActions.kinds.yatakPuani",
  yatak_puani_standard_bed: "billing.recommendedActions.kinds.yatakPuaniStandardBed",
  anestezi_puani_group: "billing.recommendedActions.kinds.anesteziPuaniGroup",
  refakatci_companion_bed: "billing.recommendedActions.kinds.refakatciCompanionBed",
  icu_puani_yogun_bakim: "billing.recommendedActions.kinds.icuPuaniYogunBakim",
  yenidogan_yatak: "billing.recommendedActions.kinds.yenidoganYatak",
  session_point_violation: "billing.recommendedActions.kinds.sessionPointViolation",
  blood_component_partial_bill: "billing.recommendedActions.kinds.bloodComponentPartialBill",
  bundled_line_flag: "billing.recommendedActions.kinds.bundledLineFlag",
  yatak_newborn_overlap_double_billing: "billing.recommendedActions.kinds.yatakNewbornOverlapDoubleBilling",
};

/** Prefer i18n map; otherwise humanize snake_case so new backend kinds aren't "Unknown". */
function labelOrHumanize(
  t: TranslateFn,
  key: string | undefined,
  raw: string,
  unknownKey: string,
): string {
  if (key) {
    return t(key);
  }
  const humanized = raw
    .trim()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
  return humanized || t(unknownKey);
}

export function recommendedActionSurfaceLabel(
  t: TranslateFn,
  surface: string,
): string {
  return labelOrHumanize(
    t,
    SURFACE_LABEL_KEYS[surface],
    surface,
    "common.unknownSurface",
  );
}

export function recommendedActionKindLabel(t: TranslateFn, kind: string): string {
  return labelOrHumanize(
    t,
    KIND_LABEL_KEYS[kind],
    kind,
    "common.unknownKind",
  );
}

const MATERIAL_BILLED_KINDS = new Set([
  "material_pre_auth",
  "material_miat",
  "material_miat_interval",
  "material_bundling",
  "material_prose_bundling",
  "material_specialty_prose",
]);

function isMaterialAnchoredAction(action: RecommendedActionItem): boolean {
  return action.surface === "materials" || action.surface === "material_uplift";
}

export function recommendedActionPrimaryCode(action: RecommendedActionItem): string | null {
  if (isMaterialAnchoredAction(action)) {
    return action.material_code ?? action.procedure_code ?? action.drug_code ?? null;
  }
  return action.procedure_code ?? action.material_code ?? action.drug_code ?? null;
}

/**
 * Map a recommended action to the invoice-line codes it references, partitioned
 * by OriginalBillView section so the caller can highlight matching lines.
 *
 * - `lab` → labs (procedure_code)
 * - `materials` / `material_uplift` → materials (material_code; procedure_code is
 *   the package parent and is also surfaced against the procedures section)
 * - `drug_indication` → drugs (drug_code)
 * - everything else (copay, billing_strategy, *_uplift, yatak_puani, anestezi_puani,
 *   refakatci, icu_puani, yenidogan_yatak, audit_exposure, care_setting_review,
 *   procedure_addon_uplift, procedure_capture_gap, drg_package_adequacy,
 *   medula_playbook, claim_checklist)
 *   → procedures
 *
 * Surfaces whose action row carries no code (e.g. medula_playbook, copay) yield
 * empty arrays — a graceful no-op, not a highlight.
 */
export function recommendedActionLineCodes(
  action: RecommendedActionItem,
): { procedures: string[]; labs: string[]; materials: string[]; drugs: string[] } {
  const result = { procedures: [] as string[], labs: [] as string[], materials: [] as string[], drugs: [] as string[] };
  const surface = action.surface;
  const procCode = action.procedure_code ?? null;
  const matCode = action.material_code ?? null;
  const drugCode = action.drug_code ?? null;

  if (surface === "lab") {
    if (procCode) result.labs.push(procCode);
  } else if (surface === "materials" || surface === "material_uplift") {
    if (matCode) result.materials.push(matCode);
    if (procCode) result.procedures.push(procCode);
  } else if (surface === "drug_indication") {
    if (drugCode) result.drugs.push(drugCode);
    else if (procCode) result.procedures.push(procCode);
  } else {
    if (procCode) result.procedures.push(procCode);
  }
  return result;
}

export function recommendedActionTitle(
  t: TranslateFn,
  action: RecommendedActionItem,
): string {
  const kindLabel = recommendedActionKindLabel(t, action.kind);
  const code = recommendedActionPrimaryCode(action);

  if (isMaterialAnchoredAction(action) && code && action.material_name) {
    return t("billing.recommendedActions.titleMaterialWithName", {
      kind: kindLabel,
      code,
      name: action.material_name,
    });
  }

  if (isMaterialAnchoredAction(action) && code) {
    return t("billing.recommendedActions.titleWithCode", {
      kind: kindLabel,
      code,
    });
  }

  if (code && action.procedure_name) {
    return t("billing.recommendedActions.titleWithName", {
      kind: kindLabel,
      code,
      name: action.procedure_name,
    });
  }

  if (code) {
    return t("billing.recommendedActions.titleWithCode", {
      kind: kindLabel,
      code,
    });
  }

  return kindLabel;
}

export function recommendedActionAmountParts(
  t: TranslateFn,
  action: RecommendedActionItem,
): { label: string; value: number | null } | null {
  if (
    action.surface === "materials" &&
    action.billed_try != null &&
    action.billed_try > 0 &&
    MATERIAL_BILLED_KINDS.has(action.kind)
  ) {
    return {
      label: t("billing.recommendedActions.amountBilledAtRisk"),
      value: action.billed_try,
    };
  }
  if (action.sgk_uplift_try != null && action.sgk_uplift_try > 0) {
    return {
      label: t("billing.recommendedActions.amountSgkUplift"),
      value: action.sgk_uplift_try,
    };
  }
  if (action.compliance_savings_try != null && action.compliance_savings_try > 0) {
    return {
      label: t("billing.recommendedActions.amountCompliance"),
      value: action.compliance_savings_try,
    };
  }
  if (action.audit_risk_try != null && action.audit_risk_try > 0) {
    return {
      label: t("billing.recommendedActions.amountAuditRisk"),
      value: action.audit_risk_try,
    };
  }
  if (action.surface === "copay" && action.kind === "exemption_review") {
    return {
      label: t("billing.recommendedActions.amountExemptionReview"),
      value: null,
    };
  }
  if (action.kind === "compliance_violation") {
    return {
      label: t("billing.recommendedActions.amountComplianceOnly"),
      value: null,
    };
  }
  return null;
}
