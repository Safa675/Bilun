"use client";

import type { SutMaterialBundlingCoverageScope } from "@/lib/api/sut";
import { Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

const DEFAULT_SCOPE: SutMaterialBundlingCoverageScope = {
  prose_rule_id: "material_bundling_prose",
  prose_section_prefixes: ["3.1", "3.2"],
  prose_engine_status: "implemented",
  prose_coverage_tier: "partial",
  prose_rules_implemented: 22,
  medula_overlap_classification: "additive",
  prose_effective_date: "2026-01-17",
  implemented_annexes: ["EK-3B-1", "EK-3B-2"],
  ek3b1_row_count: 54,
  ek3b2_row_count: 13,
  p2_plan_path: "plans/billing/material-bundling-prose-p2-plan.md",
};

type Props = {
  scope?: SutMaterialBundlingCoverageScope | null;
  compact?: boolean;
};

export function MaterialBundlingScopeNotice({ scope, compact }: Props) {
  const t = useT();
  const s = scope ?? DEFAULT_SCOPE;
  const ruleCount = s.prose_rules_implemented ?? 0;

  if (s.prose_engine_status === "out_of_scope") {
    return (
      <Surface variant="soft" padding={compact ? "sm" : "md"}>
        <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "#B45309" }}>
          {t("sections.materialBundlingScope.title")}
        </p>
        <p className="text-xs leading-relaxed" style={{ color: "#71717A" }}>
          {t("sections.materialBundlingScope.body", {
            ek3b1: s.ek3b1_row_count,
            ek3b2: s.ek3b2_row_count,
          })}
        </p>
        {!compact && (
          <p className="text-xs mt-2 italic" style={{ color: "#A1A1AA" }}>
            {t("sections.materialBundlingScope.p2Plan", { path: s.p2_plan_path })}
          </p>
        )}
      </Surface>
    );
  }

  if (s.prose_engine_status === "implemented") {
    return (
      <Surface variant="soft" padding={compact ? "sm" : "md"}>
        <p className="text-xs leading-relaxed" style={{ color: "#52525B" }}>
          {t("sections.materialBundlingScope.bodyImplemented", {
            ek3b1: s.ek3b1_row_count,
            ek3b2: s.ek3b2_row_count,
            proseRules: ruleCount,
            effectiveDate: s.prose_effective_date || "—",
          })}
        </p>
        {s.medula_savings_note && (
          <p className="text-xs mt-2 leading-relaxed italic" style={{ color: "#A1A1AA" }}>
            {t("sections.materialBundlingScope.medulaNote")}
          </p>
        )}
        {typeof s.kdv_pricing_clauses === "number" && s.kdv_pricing_clauses > 0 && (
          <p className="text-xs mt-2 leading-relaxed" style={{ color: "#71717A" }}>
            {t("sections.materialBundlingScope.kdvPricingClauses", {
              count: s.kdv_pricing_clauses,
            })}
          </p>
        )}
      </Surface>
    );
  }

  return (
    <Surface variant="soft" padding={compact ? "sm" : "md"}>
      <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "#B45309" }}>
        {t("sections.materialBundlingScope.title")}
      </p>
      <p className="text-xs leading-relaxed" style={{ color: "#71717A" }}>
        {t("sections.materialBundlingScope.bodyPartial", {
          ek3b1: s.ek3b1_row_count,
          ek3b2: s.ek3b2_row_count,
          proseRules: ruleCount,
        })}
      </p>
      {!compact && (
        <p className="text-xs mt-2 italic" style={{ color: "#A1A1AA" }}>
          {t("sections.materialBundlingScope.p2Plan", { path: s.p2_plan_path })}
        </p>
      )}
    </Surface>
  );
}
