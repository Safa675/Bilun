"use client";

import { getProseInventory } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { Chip, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { useSutApi } from "../../useSutApi";

export function ProseInventoryPanel({
  onAnchorClick,
}: {
  onAnchorClick?: (anchor: string) => void;
}) {
  const t = useT();
  const {
    data: result,
    loading,
    error,
  } = useSutApi((opts) => getProseInventory(opts), {
    enabled: true,
    errorFallback: t("sections.ruleDatabase.errors.loadFailed"),
  });

  if (loading) {
    return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.prose.title")} />;
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  if (!result || !result.artifacts_available) {
    return (
      <Surface variant="soft" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.prose.artifactsUnavailable")}
        </p>
      </Surface>
    );
  }

  const engines = result.engines;

  if (engines.length === 0) {
    return (
      <Surface variant="soft" padding="md" className="text-center">
        <p className="text-xs text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.prose.noEngines")}
        </p>
      </Surface>
    );
  }

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead className="bg-[var(--surface-soft)] text-[var(--text-muted)] uppercase tracking-wide">
          <tr>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.ruleSet")}
            </th>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.fileName")}
            </th>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.effectiveDate")}
            </th>
            <th className="px-2 py-1.5 text-right font-medium">
              {t("sections.ruleDatabase.prose.ruleCount")}
            </th>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.anchors")}
            </th>
          </tr>
        </thead>
        <tbody>
          {engines.map((engine) => (
            <tr
              key={engine.rule_set_id}
              className="border-t border-[var(--border-subtle)] hover:bg-[var(--surface-soft)]"
            >
              <td className="px-2 py-1.5 font-semibold text-[var(--text-primary)]">
                {engine.rule_set_id}
              </td>
              <td className="px-2 py-1.5 font-mono text-[var(--text-secondary)]">
                {engine.file_name}
              </td>
              <td className="px-2 py-1.5 text-[var(--text-secondary)]">
                {engine.effective_date ?? "—"}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums text-[var(--text-secondary)]">
                {engine.rule_count ?? "—"}
              </td>
              <td className="px-2 py-1.5">
                <div className="flex flex-wrap gap-1">
                  {engine.sut_anchors.map((anchor) => (
                    <button
                      key={anchor}
                      type="button"
                      onClick={() => onAnchorClick?.(anchor)}
                      className="cursor-pointer transition-opacity hover:opacity-70"
                    >
                      <Chip variant="outline" className="text-[9px]">
                        {anchor}
                      </Chip>
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
