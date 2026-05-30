"use client";

import { useCallback } from "react";
import { ArrowUpRight, CircleHelp } from "lucide-react";
import { Eyebrow, Surface } from "@/components/primitives";
import PatientSearch from "@/components/ui/PatientSearch";
import { searchSutPatients } from "@/lib/api/sut";
import { buildSutHomeHref, type SutHomeTab } from "@/lib/constants";
import { useRecents, type RecentEntry } from "@/lib/recents";
import { useT } from "@/lib/i18n/useTranslations";

interface SutWorkspaceLandingProps {
  onPatientSelect: (patientId: string) => void;
  onOpenBilling: (patientId: string) => void;
  onOpenTab: (tab: SutHomeTab) => void;
  onOpenHowItWorks: () => void;
}

function formatRelative(
  ts: number,
  t: ReturnType<typeof useT>,
  now: number = Date.now(),
): string {
  const diff = Math.max(0, now - ts);
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return t("home.workspaceLanding.relativeTime.justNow");
  if (minutes < 60) return t("home.workspaceLanding.relativeTime.minutesAgo", { count: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("home.workspaceLanding.relativeTime.hoursAgo", { count: hours });
  const days = Math.floor(hours / 24);
  if (days < 30) return t("home.workspaceLanding.relativeTime.daysAgo", { count: days });
  const months = Math.floor(days / 30);
  if (months < 12) return t("home.workspaceLanding.relativeTime.monthsAgo", { count: months });
  return t("home.workspaceLanding.relativeTime.yearsAgo", { count: Math.floor(months / 12) });
}

interface RecentRowProps {
  entry: RecentEntry;
  onSelect: (patientId: string) => void;
  t: ReturnType<typeof useT>;
}

function RecentRow({ entry, onSelect, t }: RecentRowProps) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(entry.patientId)}
        className="group flex w-full items-center justify-between gap-3 rounded-[var(--r-md)] border border-transparent px-3 py-2 text-left transition-colors duration-150 hover:border-[var(--border-subtle)] hover:bg-[var(--surface-tint)] focus-visible:outline-2 focus-visible:outline-[var(--gold)]"
      >
        <span className="flex items-baseline gap-3 min-w-0">
          <span className="font-mono text-sm font-medium text-[var(--text-primary)] truncate">
            {entry.patientId}
          </span>
          <span className="text-xs text-[var(--text-muted)] tabular-nums">
            {formatRelative(entry.openedAt, t)}
          </span>
        </span>
        <ArrowUpRight
          className="h-3.5 w-3.5 flex-shrink-0 text-[var(--text-muted)] transition-colors group-hover:text-[var(--gold-hover)]"
          aria-hidden="true"
        />
      </button>
    </li>
  );
}

interface RecentColumnProps {
  title: string;
  entries: RecentEntry[];
  emptyHint: string;
  onSelect: (patientId: string) => void;
  t: ReturnType<typeof useT>;
}

function RecentColumn({ title, entries, emptyHint, onSelect, t }: RecentColumnProps) {
  return (
    <Surface as="section" variant="base" padding="lg" aria-label={title}>
      <Eyebrow as="h2" tone="muted">
        {title}
      </Eyebrow>
      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--text-muted)]">{emptyHint}</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-1">
          {entries.map((entry) => (
            <RecentRow key={entry.patientId} entry={entry} onSelect={onSelect} t={t} />
          ))}
        </ul>
      )}
    </Surface>
  );
}

export default function SutWorkspaceLanding({
  onPatientSelect,
  onOpenBilling,
  onOpenTab,
  onOpenHowItWorks,
}: SutWorkspaceLandingProps) {
  const t = useT();
  const recentPatients = useRecents("patient");
  const recentBilling = useRecents("billing");

  const handlePatients = useCallback(() => onOpenTab("patients"), [onOpenTab]);
  const handleCompliance = useCallback(() => onOpenTab("compliance"), [onOpenTab]);
  const handleRevenue = useCallback(() => onOpenTab("revenue"), [onOpenTab]);

  return (
    <div className="space-y-8">
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted" as="label" {...{ htmlFor: "sut-landing-search" }}>
          {t("home.workspaceLanding.openPatientWorkspace")}
        </Eyebrow>
        <div className="mt-3">
          <PatientSearch
            id="sut-landing-search"
            selectedPatientId={null}
            onSelect={onPatientSelect}
            placeholder={t("home.workspaceLanding.searchPlaceholder")}
            searchFn={searchSutPatients}
          />
        </div>
      </Surface>

      <div className="grid gap-4 md:grid-cols-2">
        <RecentColumn
          title={t("home.workspaceLanding.recentPatients")}
          entries={recentPatients}
          emptyHint={t("home.workspaceLanding.recentPatientsEmpty")}
          onSelect={onPatientSelect}
          t={t}
        />
        <RecentColumn
          title={t("home.workspaceLanding.recentBilling")}
          entries={recentBilling}
          emptyHint={t("home.workspaceLanding.recentBillingEmpty")}
          onSelect={onOpenBilling}
          t={t}
        />
      </div>

      <Surface variant="tint" padding="lg">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <Eyebrow tone="muted">{t("home.workspaceLanding.jumpInto")}</Eyebrow>
          <a
            href={buildSutHomeHref("patients")}
            onClick={(event) => {
              event.preventDefault();
              handlePatients();
            }}
            className="text-sm font-medium text-[var(--text-primary)] underline-offset-4 hover:underline hover:decoration-[var(--gold)] transition-colors"
          >
            {t("home.workspaceLanding.tabPatients")}
          </a>
          <a
            href={buildSutHomeHref("compliance")}
            onClick={(event) => {
              event.preventDefault();
              handleCompliance();
            }}
            className="text-sm font-medium text-[var(--text-primary)] underline-offset-4 hover:underline hover:decoration-[var(--gold)] transition-colors"
          >
            {t("home.workspaceLanding.tabCompliance")}
          </a>
          <a
            href={buildSutHomeHref("revenue")}
            onClick={(event) => {
              event.preventDefault();
              handleRevenue();
            }}
            className="text-sm font-medium text-[var(--text-primary)] underline-offset-4 hover:underline hover:decoration-[var(--gold)] transition-colors"
          >
            {t("home.workspaceLanding.tabRevenue")}
          </a>
          <button
            type="button"
            onClick={onOpenHowItWorks}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--gold-hover)] transition-colors"
          >
            <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
            {t("home.workspaceLanding.howItWorks")}
          </button>
        </div>
      </Surface>
    </div>
  );
}
