"use client";

import { useMemo, useState } from "react";
import {
  getRuleCatalog,
  type RuleCatalogEntry,
  type RuleCoverageStatus,
} from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import {
  Chip,
  Section,
  Surface,
  TabsRoot,
  TabsList,
  TabsTrigger,
  TabsContent,
  Toolbar,
  Button,
  buttonActiveClass,
  inputClass,
} from "@/components/primitives";
import { cn } from "@/lib/cn";
import { useSutApi } from "../useSutApi";
import { fmtNum } from "../shared";
import { useT } from "@/lib/i18n/useTranslations";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { COVERAGE_KEY, STATUS_FILTERS } from "./rule-database/shared";
import { CoverageSummaryPanel } from "./rule-database/CoverageSummaryPanel";
import { FactCheckRollupBanner } from "./rule-database/FactCheckRollupBanner";
import { RuleList, RuleDetailPanel } from "./rule-database/RuleList";
import { SectionBrowserPanel } from "./rule-database/SectionBrowserPanel";
import { ClauseBrowserPanel, ClauseCard } from "./rule-database/ClauseBrowserPanel";
import { ProseInventoryPanel } from "./rule-database/ProseInventoryPanel";

// Re-export so existing imports (e.g. tests) keep resolving from this module.
export { ClauseCard };

export function RuleDatabaseSection() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<RuleCoverageStatus | "all">("all");
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);

  // URL state: use rdTab/rdClause/rdSection to avoid colliding with the outer
  // app-shell ?tab= param (see constants.ts parseSutHomeTab).
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<string>(
    searchParams.get("rdTab") || "rules",
  );
  const [clauseSearchQ, setClauseSearchQ] = useState<string>(
    searchParams.get("rdSection") || "",
  );
  const initialClauseId = searchParams.get("rdClause");

  const updateUrl = (updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    updateUrl({ rdTab: tab });
  };

  const handleAnchorClick = (anchor: string) => {
    setActiveTab("clauses");
    setClauseSearchQ(anchor);
    updateUrl({ rdTab: "clauses", rdSection: anchor });
  };

  const handleNavigateToRule = (ruleId: string) => {
    setSelectedRuleId(ruleId);
    setActiveTab("rules");
    updateUrl({ rdTab: "rules", rdClause: null, rdSection: null });
  };

  const {
    data: catalog,
    loading,
    error,
  } = useSutApi((opts) => getRuleCatalog(opts), {
    enabled: true,
    errorFallback: t("sections.ruleDatabase.errors.loadFailed"),
  });

  const rules = catalog?.rules ?? null;
  const artifactsAvailable = catalog?.artifacts_available ?? true;

  const zeroClauseRuleIds = useMemo(() => {
    const matches = catalog?.coverage_summary?.registry?.zero_clause_matches ?? [];
    return new Set(matches.map((m) => m.rule_id));
  }, [catalog?.coverage_summary?.registry?.zero_clause_matches]);

  const filteredRules = useMemo(() => {
    if (!rules) return [];
    const needle = query.trim().toLowerCase();
    return rules.filter((rule) => {
      if (statusFilter !== "all" && rule.coverage_status !== statusFilter) return false;
      if (!needle) return true;
      const haystack = [
        rule.rule_id,
        rule.rule_category,
        rule.description,
        ...rule.sources.annexes,
        ...rule.sources.sut_sections,
        ...rule.keywords,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [rules, query, statusFilter]);

  const activeRuleId = selectedRuleId || (filteredRules.length > 0 ? filteredRules[0].rule_id : null);

  if (loading) return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.title")} />;

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  return (
    <Section
      title={t("sections.ruleDatabase.title")}
      description={t("sections.ruleDatabase.subtitle", { total: fmtNum(rules?.length ?? 0) })}
      variant="inset"
      padding="none"
    >
      <Surface variant="base" padding="lg" className="space-y-4">
        {catalog?.coverage_summary && <CoverageSummaryPanel summary={catalog.coverage_summary} />}

        {!artifactsAvailable && (
          <Surface variant="soft" padding="md">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("sections.ruleDatabase.artifactsUnavailable")}
            </p>
          </Surface>
        )}

        {catalog?.fact_check && <FactCheckRollupBanner rollup={catalog.fact_check} />}

        <TabsRoot value={activeTab} onValueChange={handleTabChange}>
          <TabsList density="compact">
            <TabsTrigger value="rules" density="compact">
              {t("sections.ruleDatabase.tabs.rules")}
            </TabsTrigger>
            <TabsTrigger value="sections" density="compact">
              {t("sections.ruleDatabase.tabs.sections")}
            </TabsTrigger>
            <TabsTrigger value="clauses" density="compact">
              {t("sections.ruleDatabase.tabs.clauses")}
            </TabsTrigger>
            <TabsTrigger value="prose" density="compact">
              {t("sections.ruleDatabase.tabs.prose")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="rules" forceMount className="data-[state=inactive]:hidden">
            <div className="space-y-4 pt-4">
              <Toolbar
                leading={
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={t("sections.ruleDatabase.searchPlaceholder")}
                    className={cn(inputClass, "min-w-[220px] max-w-[360px]")}
                  />
                }
              >
                <div className="flex items-center gap-1.5 overflow-x-auto max-w-full no-scrollbar py-0.5">
                  {STATUS_FILTERS.map((status) => (
                    <Button
                      key={status}
                      variant="secondary"
                      size="compact"
                      onClick={() => setStatusFilter(status)}
                      className={cn(statusFilter === status && buttonActiveClass)}
                    >
                      <span className="text-xs font-semibold">
                        {status === "all"
                          ? t("sections.ruleDatabase.filters.all")
                          : t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
                      </span>
                    </Button>
                  ))}
                </div>
              </Toolbar>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-[340px_1fr]">
                <RuleList
                  rules={filteredRules}
                  selectedRuleId={activeRuleId}
                  onSelect={setSelectedRuleId}
                  zeroClauseRuleIds={zeroClauseRuleIds}
                  onClearFilters={() => { setQuery(""); setStatusFilter("all"); }}
                />
                {activeRuleId ? (
                  <RuleDetailPanel
                    key={activeRuleId}
                    ruleId={activeRuleId}
                    artifactsAvailable={artifactsAvailable}
                    onNavigateToRule={handleNavigateToRule}
                  />
                ) : (
                  <Surface variant="soft" padding="lg" className="flex items-center justify-center">
                    <p className="text-sm text-[var(--text-secondary)]">
                      {t("sections.ruleDatabase.detail.selectPrompt")}
                    </p>
                  </Surface>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="sections" forceMount className="data-[state=inactive]:hidden">
            <div className="pt-4">
              <SectionBrowserPanel
                onNavigateToRule={handleNavigateToRule}
                onUrlUpdate={updateUrl}
              />
            </div>
          </TabsContent>

          <TabsContent value="clauses" forceMount className="data-[state=inactive]:hidden">
            <div className="pt-4">
              <ClauseBrowserPanel
                initialQuery={clauseSearchQ}
                initialClauseId={initialClauseId}
                rules={rules}
                onNavigateToRule={handleNavigateToRule}
                onUrlUpdate={updateUrl}
              />
            </div>
          </TabsContent>

          <TabsContent value="prose" forceMount className="data-[state=inactive]:hidden">
            <div className="pt-4">
              <ProseInventoryPanel onAnchorClick={handleAnchorClick} />
            </div>
          </TabsContent>
        </TabsRoot>
      </Surface>
    </Section>
  );
}
