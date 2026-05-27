"use client";

import { useCallback } from "react";
import { ArrowUpRight, CircleHelp } from "lucide-react";
import { Eyebrow, Surface } from "@/components/primitives";
import PatientSearch from "@/components/ui/PatientSearch";
import { searchSutPatients } from "@/lib/api/sut";
import { buildSutHomeHref, type SutHomeTab } from "@/lib/constants";
import { useRecents, type RecentEntry } from "@/lib/recents";

interface SutWorkspaceLandingProps {
  onPatientSelect: (patientId: string) => void;
  onOpenBilling: (patientId: string) => void;
  onOpenTab: (tab: SutHomeTab) => void;
  onOpenHowItWorks: () => void;
}

function formatRelative(ts: number, now: number = Date.now()): string {
  const diff = Math.max(0, now - ts);
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

interface RecentRowProps {
  entry: RecentEntry;
  onSelect: (patientId: string) => void;
}

function RecentRow({ entry, onSelect }: RecentRowProps) {
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
            {formatRelative(entry.openedAt)}
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
}

function RecentColumn({ title, entries, emptyHint, onSelect }: RecentColumnProps) {
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
            <RecentRow key={entry.patientId} entry={entry} onSelect={onSelect} />
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
  const recentPatients = useRecents("patient");
  const recentBilling = useRecents("billing");

  const handleAnalytics = useCallback(() => onOpenTab("analytics"), [onOpenTab]);
  const handleOptimizer = useCallback(() => onOpenTab("optimizer"), [onOpenTab]);

  return (
    <div className="space-y-8">
      {/* ── Search ───────────────────────────────────────────────────── */}
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted" as="label" {...{ htmlFor: "sut-landing-search" }}>
          Open a patient workspace
        </Eyebrow>
        <div className="mt-3">
          <PatientSearch
            id="sut-landing-search"
            selectedPatientId={null}
            onSelect={onPatientSelect}
            placeholder="Search a patient ID…"
            searchFn={searchSutPatients}
          />
        </div>
      </Surface>

      {/* ── Recents ──────────────────────────────────────────────────── */}
      <div className="grid gap-4 md:grid-cols-2">
        <RecentColumn
          title="Recent patients"
          entries={recentPatients}
          emptyHint="No recent patients yet. Search above to open one."
          onSelect={onPatientSelect}
        />
        <RecentColumn
          title="Recent billing reports"
          entries={recentBilling}
          emptyHint="No recent billing reports yet. Open a patient, then the billing tab."
          onSelect={onOpenBilling}
        />
      </div>

      {/* ── Tertiary nav ─────────────────────────────────────────────── */}
      <Surface variant="tint" padding="lg">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <Eyebrow tone="muted">Or jump straight into</Eyebrow>
          <a
            href={buildSutHomeHref("analytics")}
            onClick={(event) => {
              event.preventDefault();
              handleAnalytics();
            }}
            className="text-sm font-medium text-[var(--text-primary)] underline-offset-4 hover:underline hover:decoration-[var(--gold)] transition-colors"
          >
            SUT Analytics
          </a>
          <a
            href={buildSutHomeHref("optimizer")}
            onClick={(event) => {
              event.preventDefault();
              handleOptimizer();
            }}
            className="text-sm font-medium text-[var(--text-primary)] underline-offset-4 hover:underline hover:decoration-[var(--gold)] transition-colors"
          >
            SUT Optimizer
          </a>
          <button
            type="button"
            onClick={onOpenHowItWorks}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--gold-hover)] transition-colors"
          >
            <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
            How it works
          </button>
        </div>
      </Surface>
    </div>
  );
}
