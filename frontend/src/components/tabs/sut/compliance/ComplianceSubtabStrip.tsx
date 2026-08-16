"use client";

import type { LucideIcon } from "lucide-react";
import {
  COMPLIANCE_SUB_ICONS,
  COMPLIANCE_SUB_IDS,
  COMPLIANCE_SUB_KEY,
  type ComplianceSubSection,
} from "@/lib/workspaceSubtabs";
import { useT } from "@/lib/i18n/useTranslations";
import { Button, buttonActiveClass } from "@/components/primitives";
import { cn } from "@/lib/cn";

export interface ComplianceSubtabStripProps {
  activeSubtab: ComplianceSubSection;
  onSelectSubtab: (subtab: ComplianceSubSection) => void;
  badgeCounts?: Partial<Record<ComplianceSubSection, number>>;
}

export function ComplianceSubtabStrip({
  activeSubtab,
  onSelectSubtab,
  badgeCounts = {},
}: ComplianceSubtabStripProps) {
  const t = useT();

  return (
    <div
      role="tablist"
      aria-label={t("optimizer.tabs.categoriesAria")}
      className="flex flex-wrap gap-2"
    >
      {COMPLIANCE_SUB_IDS.map((subId) => {
        const isActive = activeSubtab === subId;
        const Icon: LucideIcon = COMPLIANCE_SUB_ICONS[subId];
        const labelKey = COMPLIANCE_SUB_KEY[subId];
        const label = t(`optimizer.tabs.${labelKey}`);
        const count = badgeCounts[subId];

        return (
          <Button
            key={subId}
            role="tab"
            aria-selected={isActive}
            variant="secondary"
            size="compact"
            onClick={() => onSelectSubtab(subId)}
            className={cn("gap-1.5", isActive && buttonActiveClass)}
          >
            <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="text-xs font-semibold">{label}</span>
            {count != null && count > 0 && (
              <span
                className={cn(
                  "ml-1 rounded-full px-1.5 py-0.2 text-[10px] font-bold tabular-nums",
                  isActive
                    ? "bg-[var(--gold)] text-[var(--gold-contrast,#1a1a1a)]"
                    : "bg-[var(--surface-tint)] text-[var(--text-secondary)]",
                )}
              >
                {count}
              </span>
            )}
          </Button>
        );
      })}
    </div>
  );
}
