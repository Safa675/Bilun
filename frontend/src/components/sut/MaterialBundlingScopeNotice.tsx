"use client";

import type { SutMaterialBundlingCoverageScope } from "@/lib/api/sut";
import { Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

type Props = {
  scope?: SutMaterialBundlingCoverageScope | null;
  compact?: boolean;
};

export function MaterialBundlingScopeNotice({ scope, compact }: Props) {
  const t = useT();
  const s = scope;
  if (!s || typeof s.prose_rules_implemented !== "number") {
    return <Surface variant="soft" padding={compact ? "sm" : "md"}>
      <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{t("sections.materialBundlingScope.publicNotice")}</p>
      {s?.implemented_annexes?.length ? <p className="mt-1 text-xs">{s.implemented_annexes.join(" · ")}</p> : null}
      {s?.medula_savings_note && <p className="mt-2 text-xs leading-relaxed italic text-[var(--text-secondary)]">{t("sections.materialBundlingScope.medulaNote")}</p>}
    </Surface>;
  }
  const ruleCount = s.prose_rules_implemented;

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
    </Surface>
  );
}
