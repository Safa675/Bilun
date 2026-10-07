"use client";

import { Chip } from "@/components/primitives";
import {
  formatExemptionCategory,
  getExemptionCategories,
} from "@/lib/copayExemption";
import type { CopayExemptionResult, PatientAlertCopay } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";

export function ExemptionBasisChips({
  copay,
  max = 4,
  className = "",
}: {
  copay: CopayExemptionResult | PatientAlertCopay;
  max?: number;
  className?: string;
}) {
  const t = useT();
  const categories = getExemptionCategories(copay);
  if (categories.length === 0) {
    return <span className="text-[var(--text-muted)]">{"\u2014"}</span>;
  }

  return (
    <span className={`inline-flex flex-wrap gap-1 ${className}`.trim()}>
      {categories.slice(0, max).map((category) => (
        <Chip key={category} variant="outline" className="text-[10px] uppercase tracking-wide">
          {formatExemptionCategory(category, t)}
        </Chip>
      ))}
      {categories.length > max && (
        <Chip variant="outline" className="text-[10px]">
          +{categories.length - max}
        </Chip>
      )}
    </span>
  );
}
