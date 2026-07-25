"use client";

import { useState } from "react";
import {
  getProseInventory,
  listProseRuleSources,
  type GateBSourceCite,
  type ProseRuleSources,
} from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { Button, Chip, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtDate } from "@/lib/i18n/formatters";
import { useSutApi } from "../../useSutApi";

function SourceCite({
  cite,
  onCoordinateClick,
}: {
  cite: GateBSourceCite;
  onCoordinateClick?: (anchor: string) => void;
}) {
  const label = cite.clause_coordinate || cite.ref;
  return (
    <button
      type="button"
      onClick={() => onCoordinateClick?.(label)}
      className="block max-w-full text-left"
    >
      <Chip variant="outline" className="text-[9px]">
        {label}
      </Chip>
      {cite.text_snippet ? (
        <p className="mt-0.5 line-clamp-2 text-[10px] text-[var(--text-muted)]">
          {cite.text_snippet}
        </p>
      ) : null}
    </button>
  );
}

function EngineRules({
  ruleSetId,
  onCoordinateClick,
}: {
  ruleSetId: string;
  onCoordinateClick?: (anchor: string) => void;
}) {
  const t = useT();
  const [rules, setRules] = useState<ProseRuleSources[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (rules !== null || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listProseRuleSources(ruleSetId, { page: 1, per_page: 25 });
      setRules(res.rules);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("sections.ruleDatabase.errors.loadFailed"),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-2 space-y-2 border-t border-[var(--border-subtle)] pt-2">
      {rules === null && !loading && !error && (
        <Button variant="secondary" size="compact" onClick={() => void load()}>
          {t("sections.ruleDatabase.prose.loadSources")}
        </Button>
      )}
      {loading && (
        <p className="text-[11px] text-[var(--text-muted)]">
          {t("sections.ruleDatabase.prose.loadingSources")}
        </p>
      )}
      {error && <p className="text-[11px] text-[var(--danger)]">{error}</p>}
      {rules && rules.length === 0 && (
        <p className="text-[11px] text-[var(--text-muted)]">
          {t("sections.ruleDatabase.prose.noRules")}
        </p>
      )}
      {rules &&
        rules.map((rule) => (
          <div key={rule.rule_id} className="rounded bg-[var(--surface-soft)] px-2 py-1.5">
            <div className="font-mono text-[10px] font-semibold text-[var(--text-primary)]">
              {rule.rule_id}
              {rule.sut_section ? (
                <span className="ml-2 font-normal text-[var(--text-muted)]">
                  {rule.sut_section}
                </span>
              ) : null}
            </div>
            <div className="mt-1 space-y-1">
              {(rule.gate_b_sources || []).map((cite) => (
                <SourceCite
                  key={`${rule.rule_id}:${cite.ref}`}
                  cite={cite}
                  onCoordinateClick={onCoordinateClick}
                />
              ))}
              {(rule.gate_b_sources || []).length === 0 && (
                <p className="text-[10px] text-[var(--text-muted)]">
                  {t("sections.ruleDatabase.prose.noSources")}
                </p>
              )}
            </div>
          </div>
        ))}
    </div>
  );
}

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
  const [expanded, setExpanded] = useState<string | null>(null);

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
          {engines.map((engine) => {
            const isOpen = expanded === engine.rule_set_id;
            return (
              <tr
                key={engine.rule_set_id}
                className="border-t border-[var(--border-subtle)] hover:bg-[var(--surface-soft)]"
              >
                <td className="px-2 py-1.5 align-top font-semibold text-[var(--text-primary)]" colSpan={isOpen ? 5 : 1}>
                  <button
                    type="button"
                    className="text-left hover:underline"
                    onClick={() =>
                      setExpanded((prev) =>
                        prev === engine.rule_set_id ? null : engine.rule_set_id,
                      )
                    }
                  >
                    {engine.rule_set_id}
                  </button>
                  {isOpen ? (
                    <EngineRules
                      ruleSetId={engine.rule_set_id}
                      onCoordinateClick={onAnchorClick}
                    />
                  ) : null}
                </td>
                {!isOpen && (
                  <>
                    <td className="px-2 py-1.5 font-mono text-[var(--text-secondary)]">
                      {engine.file_name}
                    </td>
                    <td className="px-2 py-1.5 text-[var(--text-secondary)]">
                      {engine.effective_date ? fmtDate(engine.effective_date) : "—"}
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
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
