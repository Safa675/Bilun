"use client";

import type { SutSpecialtyProseCoverageScope } from "@/lib/api/sut";
import { Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

type Props = {
  scope?: SutSpecialtyProseCoverageScope | null;
  compact?: boolean;
};

export function SpecialtyProseScopeNotice({ scope, compact }: Props) {
  const t = useT();
  if (!scope || scope.prose_engine_status !== "implemented") {
    return null;
  }

  const ruleCount = scope.prose_rules_implemented ?? 0;

  return (
    <Surface variant="soft" padding={compact ? "sm" : "md"}>
      <p className="text-xs leading-relaxed" style={{ color: "#52525B" }}>
        {t("sections.specialtyProseScope.bodyImplemented", {
          proseRules: ruleCount,
          effectiveDate: scope.prose_effective_date || "—",
        })}
      </p>
      {scope.medula_savings_note && (
        <p className="text-xs mt-2 leading-relaxed italic" style={{ color: "#A1A1AA" }}>
          {t("sections.specialtyProseScope.medulaNote")}
        </p>
      )}
    </Surface>
  );
}
